import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
import json
import io

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

# --- MOTOR DE CÁLCULO TRÍADE V43 ---
def motor_calculo_v43(df, params):
    df.columns = df.columns.str.strip().str.lower()
    mapping = {'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 'prem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 'k%': 'K%'}
    df = df.rename(columns=mapping)
    
    cols_nec = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'Longitude', 'Latitude']
    for col in cols_nec:
        if col not in df.columns: df[col] = 0.0
        else: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # 1. Calagem (Fatores 560/400)
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    df['REC_CALCARIO'] = (np.maximum((df['NC_CA_CMOL']*5600000/(c_p["cao"]*c_p["prnt"])), 
                                     (df['NC_MG_CMOL']*4000000/(c_p["mgo"]*c_p["prnt"]))) + c_p["reserva"]).round(2)
    df['RATIO_CA_MG'] = (df['Ca%'] + (df['NC_CA_CMOL']/df['CTC']*100)) / (df['Mg%'] + (df['NC_MG_CMOL']/df['CTC']*100 + 0.001))

    # 2. Fósforo (NC P-rem + Crédito Solo)
    def calc_p(row):
        nc = p_p["nc_0_4"] if row['prem'] <= 4 else p_p["nc_4_10"] if row['prem'] <= 10 else p_p["nc_10_19"] if row['prem'] <= 19 else p_p["nc_19_30"] if row['prem'] <= 30 else p_p["nc_30_45"] if row['prem'] <= 45 else p_p["nc_45_60"]
        f_arg = p_p["f_muito_arg"] if row['Argila'] > 60 else p_p["f_argiloso"] if row['Argila'] > 35 else p_p["f_medio"] if row['Argila'] > 15 else p_p["f_arenoso"]
        total_p2o5 = ((nc - row['P mehl']) * f_arg) + (prod_esp * p_p["f_exp"])
        return (max(total_p2o5, 0) * 100) / p_p["teor_adubo"]
    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 3. Potássio e Gesso (Argila % * 10)
    df['REC_K_ADUBO'] = (((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941) + (prod_esp * k_p["f_exp"])) * 100 / k_p["teor_adubo"]
    df['REC_GESSO'] = (df['Argila'] * 10 * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    return df

# --- MOTOR GEOESTATÍSTICO ---
def plot_geostats(df, col, title, geo_json=None):
    x, y, z = df['Longitude'].values, df['Latitude'].values, df[col].values
    if len(np.unique(x)) < 2: return go.Figure(), "N/A"
    xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100); xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear', smooth=0.1); zi = rbf(xi, yi)
    if geo_json:
        try:
            poly = shape(geo_json['features'][0]['geometry'])
            for i in range(len(xi)):
                for j in range(len(yi)):
                    if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan
        except: pass
    fig = go.Figure(data=go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100), colorscale='RdYlBu_r', contours=dict(showlines=False), line_width=0))
    fig.update_layout(title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=350, xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='white')
    return fig, f"Mín: {np.nanmin(zi):.2f} | Máx: {np.nanmax(zi):.2f} | Méd: {np.nanmean(zi):.2f}"

# --- INTERFACE (RESTAURAÇÃO TOTAL DOS CAMPOS) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    p_names = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_p = st.sidebar.selectbox("Produtor", p_names)
    if sel_p == "+ Novo Produtor":
        sel_p = st.sidebar.text_input("Nome Cliente")
        if sel_p and sel_p not in st.session_state['db']: st.session_state['db'][sel_p] = {}
    
    # Hierarquia... (Talhão/Fazenda)
    # [Restaurando campos bidirecionais abaixo]
    st.sidebar.divider()
    with st.sidebar.expander("🌍 Atributos Tríade", expanded=True):
        prod = st.number_input("Produtividade Alvo", 80.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0); c_t_mg = st.number_input("Alvo Mg %", 18.0)
        c_preco = st.number_input("R$/Ton Calcário", 280.0)
        
        st.write("**Fósforo (P-rem/NC)**")
        nc04 = st.number_input("NC 0-4", 8.0); nc410 = st.number_input("NC 4-10", 10.0); nc1019 = st.number_input("NC 10-19", 12.0)
        nc1930 = st.number_input("NC 19-30", 15.0); nc3045 = st.number_input("NC 30-45", 18.0); nc4560 = st.number_input("NC 45-60", 22.0)
        
        st.write("**Fatores Argila**")
        f_m_arg = st.number_input("M.Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0); f_med = st.number_input("Médio", 4.0); f_are = st.number_input("Arenoso", 2.0)
        
        p_teor = st.number_input("Teor Adubo P %", 21.0); p_preco = st.number_input("R$/Ton P", 3200.0)
        k_target = st.number_input("Alvo K %", 3.2); k_preco = st.number_input("R$/Ton K", 2900.0)
        g_fator = st.number_input("Fator Gesso", 15.0); g_min = st.number_input("Mín Gesso", 400.0); g_max = st.number_input("Máx Gesso", 900.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": 80.0, "cao": 36.0, "mgo": 9.0, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": 0.0, "preco": c_preco},
        "fosforo": {"nc_0_4": nc04, "nc_4_10": nc410, "nc_10_19": nc1019, "nc_19_30": nc1930, "nc_30_45": nc3045, "nc_45_60": nc4560, "f_muito_arg": f_m_arg, "f_argiloso": f_arg, "f_medio": f_med, "f_arenoso": f_are, "teor_adubo": p_teor, "f_exp": 0.8, "preco": p_preco},
        "potassio": {"target_k": k_target, "teor_adubo": 60.0, "f_exp": 1.2, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": 190.0},
        "path": (sel_p, "Fazenda", "Talhão")
    }
    return params

# --- PÁGINA DE OPERAÇÕES ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Central Tríade: {p}</h2>", unsafe_allow_html=True)
    tabs = st.tabs(["📁 Dados", "📊 Fertilidade", "🗺️ VRT", "📄 Relatório", "📥 Exportar"])
    
    # ... Lógica de Upload e Mapas segue o padrão 2x2 e Argumentos técnicos ...
    with tabs[0]:
        up_csv = st.file_uploader("Subir CSV", type=['csv'])
        if up_csv: st.session_state['db'][p] = {"df": pd.read_csv(up_csv, sep=None, engine='python')}

    if st.session_state['db'].get(p) is not None:
        df_res = motor_calculo_v43(st.session_state['db'][p]["df"], params)
        with tabs[2]:
            recs = [("REC_CALCARIO", "Calcário"), ("REC_P_ADUBO", "Fosfatado"), ("REC_K_ADUBO", "Potássico"), ("REC_GESSO", "Gesso")]
            args_tec = {"Calcário": "Máxima eficiência via equilíbrio estequiométrico individual de bases.", "Fosfatado": "Abatimento de excesso disponível via P-rem.", "Potássio": "Saturação ideal + exportação real.", "Gesso": "Melhoria radicular baseada em Argila %."}
            for i in range(0, len(recs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(recs):
                        label = recs[i+j][1]
                        fig, stats = plot_geostats(df_res, recs[i+j][0], f"VRT {label}")
                        cols[j].plotly_chart(fig, use_container_width=True)
                        cols[j].success(stats)
                        cols[j].markdown(f"<div class='arg-tecnico'><b>Vantagem Tríade:</b> {args_tec.get(label)}</div>", unsafe_allow_html=True)

# --- EXECUÇÃO ---
params = configurar_interface()
pag_produtores(params)
