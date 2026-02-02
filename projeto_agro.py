import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
from fpdf import FPDF
import json
import io
import zipfile

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}

# --- CONFIGURAÇÃO DA PÁGINA (ESTILO TRÍADE) ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card {
        background-color: #ffffff; padding: 12px; border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 6px solid #1e3d59; padding-left: 12px; margin: 20px 0; font-weight: bold; }
    .arg-tecnico { font-size: 11px; color: #444; background: #f0f4f5; padding: 10px; border-radius: 5px; border-left: 4px solid #27ae60; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO TRÍADE V43 ---
def motor_calculo_v43(df, params):
    # 1. Normalização forçada contra KeyError
    df.columns = df.columns.str.strip().str.lower()
    mapping = {
        'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 
        'p_mehl': 'P mehl', 'p': 'P mehl', 'prem': 'prem', 'p-rem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 
        'k%': 'K%', 'ca': 'Ca', 'mg': 'Mg', 'k': 'K', 'al': 'Al'
    }
    df = df.rename(columns=mapping)
    
    # Colunas essenciais
    cols_nec = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'Longitude', 'Latitude']
    for col in cols_nec:
        if col not in df.columns: df[col] = 0.0
        else: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # --- CÁLCULOS TÉCNICOS ---
    # 1. Calagem Atômica
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    df['DOSE_CA'] = (df['NC_CA_CMOL'] * 560 * 100 * 100) / (c_p["cao"] * c_p["prnt"])
    df['DOSE_MG'] = (df['NC_MG_CMOL'] * 400 * 100 * 100) / (c_p["mgo"] * c_p["prnt"])
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CA'], df['DOSE_MG']) + c_p["reserva"]).round(2)

    # 2. Fósforo Dinâmico (Balanço P-rem com 6 faixas)
    def calc_p(row):
        p_rem = row['prem']
        nc = (p_p["nc_0_4"] if p_rem <= 4 else p_p["nc_4_10"] if p_rem <= 10 else 
              p_p["nc_10_19"] if p_rem <= 19 else p_p["nc_19_30"] if p_rem <= 30 else 
              p_p["nc_30_45"] if p_rem <= 45 else p_p["nc_45_60"])
        arg = row['Argila']
        f_arg = (p_p["f_muito_arg"] if arg > 60 else p_p["f_argiloso"] if arg > 35 else 
                 p_p["f_medio"] if arg > 15 else p_p["f_arenoso"])
        p_total = ((nc - row['P mehl']) * f_arg) + (prod_esp * p_p["f_exp"])
        return (max(p_total, 0) * 100) / p_p["teor_adubo"]
    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 3. Potássio e Gesso (Argila % * 10)
    df['REC_K_ADUBO'] = (((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941) + (prod_esp * k_p["f_exp"])) * 100 / k_p["teor_adubo"]
    df['REC_GESSO'] = (df['Argila'] * 10 * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    # 4. Financeiro
    df['C_CALC'] = (df['REC_CALCARIO']/1000) * c_p["preco"]
    df['C_P'] = (df['REC_P_ADUBO']/1000) * p_p["preco"]
    df['C_K'] = (df['REC_K_ADUBO']/1000) * k_p["preco"]
    df['C_GESSO'] = (df['REC_GESSO']/1000) * g_p["preco"]
    df['C_TOTAL'] = df['C_CALC'] + df['C_P'] + df['C_K'] + df['C_GESSO']
    return df

# --- MOTOR GEOESTATÍSTICO: KRIGAGEM + CLIPPING REAL ---
def plot_geostats(df, col, title, geo_json=None):
    x, y, z = df['Longitude'].values, df['Latitude'].values, df[col].values
    if len(np.unique(x)) < 2: return go.Figure(), "Dados Insuficientes"
    
    xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100); xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear', smooth=0.1); zi = rbf(xi, yi)
    
    if geo_json:
        try:
            poly = shape(geo_json['features'][0]['geometry'])
            for i in range(len(xi)):
                for j in range(len(yi)):
                    if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan
        except: pass

    fig = go.Figure(data=go.Contour(
        z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100),
        colorscale='RdYlBu_r', contours=dict(showlines=False), line_width=0
    ))
    fig.update_layout(title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=350,
                      xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='white')
    stats = f"Mín: {np.nanmin(zi):.2f} | Máx: {np.nanmax(zi):.2f} | Méd: {np.nanmean(zi):.2f}"
    return fig, stats

# --- INTERFACE DE NAVEGAÇÃO E ATRIBUTOS (+/-) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    p_names = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_p = st.sidebar.selectbox("Produtor", p_names)
    if sel_p == "+ Novo Produtor":
        sel_p = st.sidebar.text_input("Nome Cliente")
        if sel_p and sel_p not in st.session_state['db']: st.session_state['db'][sel_p] = {}

    faz_names = list(st.session_state['db'].get(sel_p, {}).keys()) + ["+ Nova Fazenda"]
    sel_f = st.sidebar.selectbox("Fazenda", faz_names)
    if sel_f == "+ Nova Fazenda":
        sel_f = st.sidebar.text_input("Nome Fazenda")
        if sel_f and sel_f not in st.session_state['db'][sel_p]: st.session_state['db'][sel_p][sel_f] = {}

    tal_names = list(st.session_state['db'].get(sel_p, {}).get(sel_f, {}).keys()) + ["+ Novo Talhão"]
    sel_t = st.sidebar.selectbox("Talhão", tal_names)
    if sel_t == "+ Novo Talhão":
        sel_t = st.sidebar.text_input("ID Talhão")
        if sel_t and sel_t not in st.session_state['db'][sel_p][sel_f]:
            st.session_state['db'][sel_p][sel_f][sel_t] = {"df": None, "contorno": None}

    st.sidebar.divider()
    with st.sidebar.expander("🌍 Atributos Tríade v43", expanded=True):
        prod = st.number_input("Produtividade Alvo", 80.0, step=1.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0, step=1.0); c_t_mg = st.number_input("Alvo Mg %", 18.0, step=1.0)
        c_res = st.number_input("Reserva kg/ha", 0.0, step=100.0); c_preco = st.number_input("R$/Ton Calcário", 280.0)
        
        st.write("**Fósforo (NC P-rem)**")
        nc04 = st.number_input("NC 0-4", 8.0); nc410 = st.number_input("NC 4-10", 10.0); nc1019 = st.number_input("NC 10-19", 12.0)
        nc1930 = st.number_input("NC 19-30", 15.0); nc3045 = st.number_input("NC 30-45", 18.0); nc4560 = st.number_input("NC 45-60", 22.0)
        
        st.write("**Fatores Argila**")
        f_m_arg = st.number_input("M.Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0)
        f_med = st.number_input("Médio", 4.0); f_are = st.number_input("Arenoso", 2.0)
        
        p_teor = st.number_input("Teor Adubo P %", 21.0); p_exp = st.number_input("Exp. P (kg/sc)", 0.8); p_preco = st.number_input("R$/Ton P", 3200.0)
        k_target = st.number_input("Alvo K %", 3.2); k_preco = st.number_input("R$/Ton K", 2900.0)
        g_fator = st.number_input("Fator Gesso", 15.0); g_min = st.number_input("Mín Gesso", 400.0); g_max = st.number_input("Máx Gesso", 900.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": 80.0, "cao": 36.0, "mgo": 9.0, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {"nc_0_4": nc04, "nc_4_10": nc410, "nc_10_19": nc1019, "nc_19_30": nc1930, "nc_30_45": nc3045, "nc_45_60": nc4560, "f_muito_arg": f_m_arg, "f_argiloso": f_arg, "f_medio": f_med, "f_arenoso": f_are, "teor_adubo": p_teor, "f_exp": p_exp, "preco": p_preco},
        "potassio": {"target_k": k_target, "teor_adubo": 60.0, "f_exp": 1.2, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": 190.0},
        "path": (sel_p, sel_f, sel_t)
    }
    return params

# --- PÁGINA DE OPERAÇÕES ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Consultoria Tríade: {p} | {f} | {t}</h2>", unsafe_allow_html=True)
    tabs = st.tabs(["📁 Dados e Contorno", "📊 Fertilidade", "🗺️ Recomendações VRT", "📄 Relatório", "📥 Exportar"])
    
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            up_csv = st.file_uploader("CSV Solo", type=['csv'], key=f"csv_{t}")
            up_geo = st.file_uploader("Contorno (GeoJSON)", type=['geojson','json'], key=f"geo_{t}")
            if st.button("🚀 Processar e Salvar"):
                if up_csv: st.session_state['db'][p][f][t]["df"] = pd.read_csv(up_csv, sep=None, engine='python')
                if up_geo: st.session_state['db'][p][f][t]["contorno"] = json.load(up_geo)
                st.success("Tudo salvo!")
        with c2:
            if st.session_state['db'].get(p,{}).get(f,{}).get(t,{}).get("df") is not None:
                st.dataframe(st.session_state['db'][p][f][t]["df"].head())

    if st.session_state['db'].get(p,{}).get(f,{}).get(t,{}).get("df") is not None:
        df_res = motor_calculo_v43(st.session_state['db'][p][f][t]["df"], params)
        contorno = st.session_state['db'][p][f][t]["contorno"]

        with tabs[1]: # FERTILIDADE
            attrs = ["pH", "Argila", "Ca%", "Mg%", "K%", "V%", "P mehl", "prem"]
            for i in range(0, len(attrs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(attrs):
                        fig, stats = plot_geostats(df_res, attrs[i+j], attrs[i+j], contorno)
                        cols[j].plotly_chart(fig, use_container_width=True)
                        cols[j].info(stats)

        with tabs[2]: # VRT
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><small>Calcário</small><div class='kpi-value'>R$ {df_res['C_CALC'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><small>Fósforo</small><div class='kpi-value'>R$ {df_res['C_P'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><small>Potássio</small><div class='kpi-value'>R$ {df_res['C_K'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><small>TOTAL MÉDIO</small><div class='kpi-value' style='color:#27ae60'>R$ {df_res['C_TOTAL'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            
            recs = [("REC_CALCARIO", "Calcário"), ("REC_P_ADUBO", "Fosfatado"), ("REC_K_ADUBO", "Potássico"), ("REC_GESSO", "Gesso")]
            args_tec = {"Calcário": "Otimização via equilíbrio estequiométrico individual.", "Fosfatado": "NC via P-rem com crédito de solo.", "Potássio": "Saturação ideal + exportação real.", "Gesso": "Melhoria radicular baseada em Argila %."}
            for i in range(0, len(recs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(recs):
                        fig, stats = plot_geostats(df_res, recs[i+j][0], f"VRT {recs[i+j][1]} (kg/ha)", contorno)
                        cols[j].plotly_chart(fig, use_container_width=True)
                        cols[j].success(stats)
                        cols[j].markdown(f"<div class='arg-tecnico'><b>Vantagem Tríade:</b> {args_tec.get(recs[i+j][1])}</div>", unsafe_allow_html=True)

        with tabs[3]: st.button("📝 Gerar Relatório PDF A4")
        with tabs[4]: st.button("📦 Exportar para Monitores")

# --- EXECUÇÃO ---
params = configurar_interface()
p, f, t = params["path"]
if not p or not f or not t: st.info("Selecione o talhão na lateral.")
else: pag_produtores(params)
