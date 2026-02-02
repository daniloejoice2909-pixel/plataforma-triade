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

# --- CSS PREMIUM ---
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
    .section-header { color: #1e3d59; border-left: 6px solid #1e3d59; padding-left: 12px; margin: 15px 0; font-weight: bold; }
    .arg-tecnico { font-size: 11px; color: #444; background: #f0f4f5; padding: 10px; border-radius: 5px; border-left: 4px solid #27ae60; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO TRÍADE V43 (INTEGRIDADE TOTAL) ---
def motor_calculo_v43(df, params):
    df.columns = df.columns.str.strip().str.lower()
    mapping = {
        'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 
        'p_mehl': 'P mehl', 'prem': 'prem', 'p-rem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 
        'k%': 'K%', 'ca': 'Ca', 'mg': 'Mg', 'k': 'K', 'al': 'Al', 'mo': 'MO'
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

    # 2. Fósforo (6 Faixas + Crédito Solo)
    def calc_p(row):
        pr = row['prem']
        nc = (p_p["nc_0_4"] if pr <= 4 else p_p["nc_4_10"] if pr <= 10 else p_p["nc_10_19"] if pr <= 19 else 
              p_p["nc_19_30"] if pr <= 30 else p_p["nc_30_45"] if pr <= 45 else p_p["nc_45_60"])
        f_arg = (p_p["f_muito_arg"] if row['Argila'] > 60 else p_p["f_argiloso"] if row['Argila'] > 35 else 
                 p_p["f_medio"] if row['Argila'] > 15 else p_p["f_arenoso"])
        p_total = ((nc - row['P mehl']) * f_arg) + (prod_esp * p_p["f_exp"])
        return (max(p_total, 0) * 100) / p_p["teor_adubo"]
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

# --- MOTOR GEOESTATÍSTICO: KRIGAGEM + CLIPPING ---
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
    fig = go.Figure(data=go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100),
                                    colorscale='RdYlBu_r', contours=dict(showlines=False), line_width=0))
    fig.update_layout(title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=350, xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='white')
    stats = f"Mín: {np.nanmin(zi):.2f} | Máx: {np.nanmax(zi):.2f} | Méd: {np.nanmean(zi):.2f}"
    return fig, stats

# --- INTERFACE DE NAVEGAÇÃO E ATRIBUTOS (PASTAS RESTAURADAS) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.header("📍 Hierarquia de Dados")
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
    st.sidebar.header("⚙️ Atributos Técnicos (+/-)")
    with st.sidebar.expander("🌍 Global & Produtividade"):
        prod = st.number_input("Produtividade (sc/ha)", 80.0, step=1.0)
    with st.sidebar.expander("🪨 Calagem Atômica"):
        c_cao = st.number_input("CaO %", 36.0); c_mgo = st.number_input("MgO %", 9.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0); c_t_mg = st.number_input("Alvo Mg %", 18.0)
        c_res = st.number_input("Reserva kg", 0.0); c_preco = st.number_input("R$/Ton Calc", 280.0)
    with st.sidebar.expander("🧪 Fósforo (6 Classes P-rem)"):
        nc04 = st.number_input("NC 0-4", 8.0); nc410 = st.number_input("NC 4-10", 10.0); nc1019 = st.number_input("NC 10-19", 12.0)
        nc1930 = st.number_input("NC 19-30", 15.0); nc3045 = st.number_input("NC 30-45", 18.0); nc4560 = st.number_input("NC 45-60", 22.0)
        st.write("Fatores de Argila")
        f_m_arg = st.number_input("M. Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0); f_med = st.number_input("Médio", 4.0); f_are = st.number_input("Arenoso", 2.0)
        p_teor = st.number_input("Teor Adubo P %", 21.0); p_exp = st.number_input("Exp. P", 0.8); p_preco = st.number_input("R$/Ton P", 3200.0)
    with st.sidebar.expander("🍌 Potássio & Gesso"):
        k_target = st.number_input("Alvo K %", 3.2); k_preco =
