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

# --- CONFIGURAÇÃO E ESTADO ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

if 'fert_maps' not in st.session_state: st.session_state['fert_maps'] = False
if 'vrt_maps' not in st.session_state: st.session_state['vrt_maps'] = False

# --- CSS PREMIUM ---
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
        font-size: 11px; color: #333; background: #eef5f8; padding: 10px; 
        border-radius: 5px; border-left: 5px solid #27ae60; margin-top: 5px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: INTERFACE SIDEBAR (AUDITORIA V43) ---
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
        c_cao = st.number_input("CaO %", value=36.0, step=0.1, min_value=0.0)
        c_mgo = st.number_input("MgO %", value=9.0, step=0.1, min_value=0.0)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0, min_value=0.0)
        c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0, min_value=0.0)
        c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0, min_value=0.0)
        c_preco = st.number_input("Preço R$/Ton Calc", value=190.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc = [st.number_input(f"NC {f}", value=v, step=0.1, min_value=0.0) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        st.write("**Fatores Argila**")
        f_arg = [st.number_input(f, value=v, step=0.1, min_value=0.0) for f, v in zip(["M. Argiloso", "Argiloso", "Médio", "Arenoso"], [10.0, 8.0, 4.0, 2.0])]
        p_teor = st.number_input("Teor Adubo P %", value=21.0, step=0.1)
        p_exp = st.number_input("Exp (kg/sc) P", value=0.8, step=0.01)
        p_preco = st.number_input("Preço R$/Ton P", value=2000.0, step=10.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K % CTC", value=3.2, step=0.1, min_value=0.0)
        k_exp = st.number_input("Exp (kg/sc) K", value=1.2, step=0.01)
        k_teor = st.number_input("Teor Adubo K %", value=60.0, step=0.1)
        k_preco = st.number_input("Preço R$/Ton K", value=2800.0, step=10.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", value=15.0, step=0.1, min_value=0.0)
        g_min = st.number_input("Mín kg/ha", value=400.0, step=10.0); g_max = st.number_input("Máx kg/ha", value=900.0, step=10.0)
        g_preco = st.number_input("Preço R$/Ton Gesso", value=400.0, step=1.0)

    return locals()

# --- CAMADA 2: MOTOR LÓGICO V43 ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    mapping = {'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'}
    df = df.rename(columns=mapping)
    
    # Gesso: Argila % x Fator 15
    df['rec_gesso'] = (df['argila'] * p['g_fator']).clip(p['g_min'], p['g_max'])

    # Calagem: Maior dose Ca/Mg + Reserva
    df['nc_ca'] = ((p['c_t_ca'] - df.get('ca_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['nc_mg'] = ((p['c_t_mg'] - df.get('mg_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['dose_ca'] = (df['nc_ca'] * 5600000) / (p['c_cao'] * p['c_prnt'] + 0.1)
    df['dose_mg'] = (df['nc_mg'] * 4000000) / (p['c_mgo'] * p['c_prnt'] + 0.1)
    df['rec_calcario'] = (np.maximum(df['dose_ca'], df['dose_mg']) + p['c_res']).round(2)

    # Potássio: Alvo + Exportação Mandatória
    df['k_eleva'] = ((p['k_target'] - df.get('k_p', 0)).clip(lower=0) * df.get('ctc', 0) / 100 * 391)
    df['k_export'] = p['prod'] * p['k_exp']
    df['rec_potassio'] = (df['k_eleva'] + df['k_export']) * 100 / p['k_teor']

    #
