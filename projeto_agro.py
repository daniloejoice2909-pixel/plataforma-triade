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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM TRÍADE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card {
        background-color: #ffffff; padding: 12px; border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); text-align: center;
        border-top: 4px solid #1e3d59; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 6px solid #1e3d59; padding-left: 12px; margin: 15px 0; font-weight: bold; }
    .arg-tecnico { font-size: 11px; color: #444; background: #f0f4f5; padding: 10px; border-radius: 5px; border-left: 4px solid #27ae60; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO TRÍADE V43 (REGRAS DE OURO) ---
def motor_calculo_v43(df, params):
    df.columns = df.columns.str.strip().str.lower()
    mapping = {
        'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 
        'p_mehl': 'P mehl', 'prem': 'prem', 'p-rem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 
        'k%': 'K%', 'ca': 'Ca', 'mg': 'Mg', 'k': 'K', 'al': 'Al', 'mo': 'MO',
        'longitude': 'Longitude', 'latitude': 'Latitude'
    }
    df = df.rename(columns=mapping)
    
    cols_nec = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'Ca', 'Mg', 'K', 'Al', 'Longitude', 'Latitude']
    for col in cols_nec:
        if col not in df.columns: df[col] = 0.0
        else: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # 1. Calagem Atômica
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    df['DOSE_CA'] = (df['NC_CA_CMOL'] * 560 * 100 * 100) / (c_p["cao"] * c_p["prnt"])
    df['DOSE_MG'] = (df['NC_MG_CMOL'] * 400 * 100 * 100) / (c_p["mgo"] * c_p["prnt"])
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CA'], df['DOSE_MG']) + c_p["reserva"]).round(2)
    df['RATIO_CA_MG'] = (df['Ca%'] + (df['NC_CA_CMOL']/df['CTC']*100)) / (df['Mg%'] + (df['NC_MG_CMOL']/df['CTC']*100 + 0.001))

    # 2. Fósforo (NC P-rem)
    def calc_p(row):
        nc = p_p["nc_0_4"] if row['prem'] <= 4 else p_p["nc_4_10"] if row['prem'] <= 10 else p_p["nc_10_19"] if row['prem'] <= 19 else p_p["nc_19_30"] if row['prem'] <= 30 else p_p["nc_30_45"] if row['prem'] <= 45 else p_p["nc_45_60"]
        f_arg = p_p["f_muito_arg"] if row['Argila'] > 60 else p_p["f_argiloso"] if row['Argila'] > 35 else p_p["f_medio"] if row['Argila'] > 15 else p_p["f_arenoso"]
        p_corr = (nc - row['P mehl']) * f_arg
        p_exp = prod_esp * p_p["f_exp"]
        return (max(p_corr + p_exp, 0) * 100) / p_p["teor_adubo"]
    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 3. Potássio e Gesso (Argila % * 10)
    df['REC_K_ADUBO'] = (((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941) + (prod_esp * k_p["f_exp"])) * 100 / k_p["teor_adubo"]
    df['REC_GESSO'] = (df['Argila'] * 10 * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    # Financeiro
    df['C_CALC'] = (df['REC_CALCARIO']/1000) * c_p["preco"]
    df['C_P'] = (df['REC_P_ADUBO']/1000) * p_p["preco"]
    df['C_K'] = (df['REC_K_ADUBO']/1000) * k_p["preco"]
    df['C_GESSO'] = (df['REC_GESSO']/1000) * g_p["preco"]
    df['C_TOTAL'] = df['C_CALC'] + df['C_P'] + df['C_K'] + df['C_GESSO']
    return df

# --- MOTOR DE KRIGAGEM COM CLIPPING REAL ---
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

    fig = go.Figure(data=go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100),
                                    colorscale='RdYlBu_r', contours=dict(showlines=False), line_width=0))
    fig.update_layout(title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=350,
                      xaxis=dict(showticklabels=False, showgrid=False), yaxis=dict(showticklabels=False, showgrid=False), plot_bgcolor='white')
    stats = f"Mín: {np.nanmin(zi):.2f} | Máx: {np.nanmax(zi):.2f} | Méd: {np.nanmean(zi):.2f}"
    return fig, stats

# --- INTERFACE DE NAVEGAÇÃO E ATRIBUTOS ---
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
    with st.sidebar.expander("🌍 Atributos Tríade (Bidirecional)", expanded=True):
        prod = st.number_input("Produtividade Alvo", 80.0, step=1.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0, step=1.0); c_t_mg = st.number_input("Alvo Mg %", 18.0, step=1.0)
        c_res = st.number_input("Reserva kg/ha", 0.0, step=100.0); c_preco = st.number_input("Preço Calcário R$/T", 280.0, step=10.0)
        p_teor = st.number_input("Teor Adubo P %", 21.0, step=1.0); p_preco = st.number_input("Preço P R$/T", 3200.0, step=50.0)
        k_preco = st.number_input("Preço K R$/T", 2900.0, step=50.0); g_fator = st.number_input("Fator Gesso", 15.0, step=1.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": 80.0, "cao": 36.0, "mgo": 9.0, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {"nc_0_4": 8.0, "nc_4_10": 10.0, "nc_10_19": 12.0, "nc_19_30": 15.0, "nc_30_45": 18.0, "nc_45_60": 22.0, "f_muito_arg": 10.0, "f_argiloso": 8.0, "f_medio": 4.0, "f_arenoso": 2.0, "teor_adubo": p_teor, "f_exp": 0.8, "preco": p_preco},
        "potassio": {"target_k": 3.2, "teor_adubo": 60.0, "f_exp": 1.2, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": 400.0, "max": 900.0, "preco": 190.0},
        "path": (sel_p, sel_f, sel_t)
    }
    return params

# --- PÁGINA DE OPERAÇÕES ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Talhão: {t} | {f} | {p}</h2>", unsafe_allow_html=True)
    tabs = st.tabs(["📁 Dados", "📊 Fertilidade", "🗺️ VRT", "📄 Relatório", "📥 Exportar"])
    
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            up_csv = st.file_uploader("CSV Solo", type=['csv'], key=f"c_{t}")
            up_geo = st.file_uploader("Contorno (GeoJSON)", type=['geojson','json'], key=f"g_{t}")
            if st.button("🚀 Processar Dados"):
                if up_csv: st.session_state['db'][p][f][t]["df"] = pd.read_csv(up_csv, sep=None, engine='python', encoding='utf-8-sig')
                if up_geo: st.session_state['db'][p][f][t]["contorno"] = json.load(up_geo)
                st.success("Dados vinculados!")
        with c2:
            if st.session_state['db'].get(p,{}).get(f,{}).get(t,{}).get("df") is not None:
                st.dataframe(st.session_state['db'][p][f][t]["df"].head())

    if st.session_state['db'].get(p,{}).get(f,{}).get(t,{}).get("df") is not None:
        df_res = motor_calculo_v43(st.session_state['db'][p][f][t]["df"], params)
        contorno = st.session_state['db'][p][f][t]["contorno"]

        with tabs[1]:
            attrs = ["pH", "Argila", "Ca%", "Mg%", "K%", "V%", "P mehl", "prem"]
            for i in range(0, len(attrs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(attrs):
                        fig, stats = plot_geostats(df_res, attrs[i+j], attrs[i+j], contorno)
                        cols[j].plotly_chart(fig, use_container_width=True); cols[j].info(stats)

        with tabs[2]:
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><small>Calcário</small><div class='kpi-value'>R$ {df_res['C_CALC'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><small>Fósforo</small><div class='kpi-value'>R$ {df_res['C_P'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><small>Potássio</small><div class='kpi-value'>R$ {df_res['C_K'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><small>INVESTIMENTO TOTAL</small><div class='kpi-value' style='color:#27ae60'>R$ {df_res['C_TOTAL'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            
            recs = [("REC_CALCARIO", "Calcário"), ("REC_P_ADUBO", "Fosfatado"), ("REC_K_ADUBO", "Potássico"), ("REC_GESSO", "Gesso")]
            args_tec = {"Calcário": "Equilíbrio atômico individual de Ca e Mg.", "Fosfatado": "NC via P-rem com crédito de solo.", "Potássio": "Saturação ideal + exportação.", "Gesso": "Melhoria baseada em Argila %."}
            for i in range(0, len(recs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(recs):
                        fig, stats = plot_geostats(df_res, recs[i+j][0], f"VRT {recs[i+j][1]} (kg/ha)", contorno)
                        cols[j].plotly_chart(fig, use_container_width=True); cols[j].success(stats)
                        cols[j].markdown(f"<div class='arg-tecnico'><b>Vantagem Tríade:</b> {args_tec[recs[i+j][1]]}</div>", unsafe_allow_html=True)

        with tabs[3]:
            st.button("📝 Gerar Relatório PDF A4")

        with tabs[4]:
            st.selectbox("Monitor", ["John Deere", "Case", "Trimble"])
            st.button("📦 Exportar Shapefiles (ZIP)")

# --- EXECUÇÃO ---
params = configurar_interface()
p, f, t = params["path"]
if not p or not f or not t: st.info("Selecione o talhão na barra lateral.")
else: pag_produtores(params)
