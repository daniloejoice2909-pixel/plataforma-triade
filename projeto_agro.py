import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
import json
import io
import zipfile
from fpdf import FPDF

# --- INICIALIZAÇÃO E SEGURANÇA ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}

st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- ESTILIZAÇÃO PREMIUM TRÍADE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 13px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #fff; padding: 15px; border-radius: 8px; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; 
        text-align: center; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { 
        font-size: 11px; color: #333; background: #eef5f8; padding: 12px; 
        border-radius: 5px; border-left: 5px solid #27ae60; margin-top: 5px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: INTERFACE SIDEBAR (AUDITADA) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### 📍 Hierarquia de Dados")
    p_nome = st.sidebar.text_input("Produtor", value="Gilson Berneck")
    f_nome = st.sidebar.text_input("Fazenda", value="Brasnorte")
    t_nome = st.sidebar.text_input("Talhão", value="T1")

    st.sidebar.divider()
    
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0, min_value=0.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1)
        c_mgo = st.number_input("MgO %", value=9.0, step=0.1)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0)
        c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)
        c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_preco = st.number_input("R$/Ton Calc", value=190.0, step=1.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc = [st.number_input(f"NC {f}", value=v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        st.write("**Fatores Argila**")
        f_arg = [st.number_input(f, value=v, step=0.1) for f, v in zip(["M. Argiloso", "Argiloso", "Médio", "Arenoso"], [10.0, 8.0, 4.0, 2.0])]
        p_teor = st.number_input("Teor Adubo P %", value=21.0)
        p_exp = st.number_input("Exp (kg/sc) P", value=0.8, step=0.01)
        p_preco = st.number_input("R$/Ton P", value=2000.0, step=10.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K % CTC", value=3.2, step=0.1)
        k_exp = st.number_input("Exp (kg/sc) K", value=1.2, step=0.01)
        k_teor = st.number_input("Teor Adubo K %", value=60.0)
        k_preco = st.number_input("R$/Ton K", value=2800.0, step=10.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_min = st.number_input("Mín (kg/ha)", value=400.0, step=10.0)
        g_max = st.number_input("Máx (kg/ha)", value=900.0, step=10.0)
        g_preco = st.number_input("R$/Ton Gesso", value=400.0, step=1.0)

    return locals()

# --- CAMADA 2: MOTOR AGRONÔMICO (AUDITADO) ---
@st.cache_data
def processar_motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'})
    
    # Gesso: Argila % x Fator (15)
    df['rec_gesso'] = (df['argila'] * p['g_fator']).clip(p['g_min'], p['g_max'])

    # Calagem: Maior dose Ca (560) ou Mg (400) + Reserva
    df['nc_ca'] = ((p['c_t_ca'] - df.get('ca_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['nc_mg'] = ((p['c_t_mg'] - df.get('mg_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['dose_ca'] = (df['nc_ca'] * 5600000) / (p['c_cao'] * p['c_prnt'] + 0.1)
    df['dose_mg'] = (df['nc_mg'] * 4000000) / (p['c_mgo'] * p['c_prnt'] + 0.1)
    df['rec_calcario'] = (np.maximum(df['dose_ca'], df['dose_mg']) + p['c_res']).round(2)

    # Fósforo: NC P-rem com Crédito de Solo + Exportação
    def calc_p(row):
        nc_idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
        nc = p['nc'][nc_idx]
        f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
        f_arg = p['f_arg'][f_idx]
        p_nec = (nc - row['p_mehl']) * f_arg
        p_exp = p['prod'] * p['p_exp']
        return (max(p_nec, 0) + p_exp) * 100 / p['p_teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)

    # Potássio: Elevação 3.2% + Exportação Mandatória (1.2 kg/sc)
    df['k_eleva'] = ((p['k_target'] - df.get('k_p', 0)).clip(lower=0) * df.get('ctc', 0) / 100 * 391)
    df['k_export'] = p['prod'] * p['k_exp']
    df['rec_potassio'] = (df['k_eleva'] + df['k_export']) * 100 / p['k_teor']

    return df

# --- CAMADA 3: GEOPROCESSAMENTO (AUDITADO) ---
def plot_v43(df, col, title, poly=None):
    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100)
    xi, yi = np.meshgrid(xi, yi); rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    fig = go.Figure()
    fig.add_trace(go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100), 
                             colorscale='RdBu_r', contours=dict(showlines=False), line_width=0,
                             colorbar=dict(title=dict(text="Unid.", font=dict(size=10)), thickness=15, x=1.02)))
    
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scatter(x=cx, y=cy, mode='lines', line=dict(color='black', width=2.5), showlegend=False))

    fig.update_layout(title=f"<b>{title}</b>", height=500, margin=dict(l=10,r=100,b=10,t=50), 
                      xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='white')
    return fig
