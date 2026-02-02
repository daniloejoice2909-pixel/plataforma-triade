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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM (OPEN SANS + RIGOR VISUAL) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 13px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #ffffff; padding: 15px; border-radius: 8px; 
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; 
        text-align: center; margin-bottom: 10px;
    }
    .kpi-value { font-size: 22px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { 
        font-size: 12px; color: #333; background: #e8f4f8; padding: 12px; 
        border-radius: 6px; border-left: 5px solid #27ae60; margin-top: 8px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO ---
if 'db' not in st.session_state: st.session_state['db'] = {}

# --- CAMADA 1: INTERFACE (SIDEBAR) - AUDITORIA DE CONTROLE TOTAL ---
def configurar_sidebar():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### 📍 Hierarquia: Produtor > Fazenda > Talhão")
    
    produtor = st.sidebar.text_input("Produtor", "Gilson Berneck")
    fazenda = st.sidebar.text_input("Fazenda", "Unidade MT")
    talhao = st.sidebar.text_input("Talhão", "T1")

    st.sidebar.divider()
    
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod_alvo = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0, max_value=500.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT %", 80.0, step=1.0, min_value=0.0, max_value=120.0)
        c_cao = st.number_input("CaO %", 36.0, step=0.1, min_value=0.0)
        c_mgo = st.number_input("MgO %", 9.0, step=0.1, min_value=0.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0, step=1.0, min_value=0.0)
        c_t_mg = st.number_input("Alvo Mg %", 18.0, step=1.0, min_value=0.0)
        c_res = st.number_input("Reserva (kg/ha)", 0.0, step=10.0)
        c_preco = st.number_input("Preço R$/Ton Calc", 190.0, step=1.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc0_4 = st.number_input("NC 0-4", 8.0, step=0.1); nc4_10 = st.number_input("NC 4-10", 10.0, step=0.1)
        nc10_19 = st.number_input("NC 10-19", 12.0, step=0.1); nc19_30 = st.number_input("NC 19-30", 15.0, step=0.1)
        nc30_45 = st.number_input("NC 30-45", 18.0, step=0.1); nc45_60 = st.number_input("NC 45-60", 22.0, step=0.1)
        st.write("**Fatores Argila**")
        f_m_arg = st.number_input("M. Argiloso", 10.0, step=0.1); f_arg = st.number_input("Argiloso", 8.0, step=0.1)
        f_med = st.number_input("Médio", 4.0, step=0.1); f_are = st.number_input("Arenoso", 2.0, step=0.1)
        p_teor = st.number_input("Teor Adubo P %", 21.0, step=0.1); p_exp_f = st.number_input("Exp (kg/sc) P", 0.8, step=0.01)
        p_preco = st.number_input("Preço R$/Ton P", 2000.0, step=10.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K % CTC", 3.2, step=0.1)
        k_exp_f = st.number_input("Exp (kg/sc) K", 1.2, step=0.01)
        k_teor = st.number_input("Teor Adubo K %", 60.0, step=0.1)
        k_preco = st.number_input("Preço R$/Ton K", 2800.0, step=10.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", 15.0, step=0.1)
        g_min = st.number_input("Mín (kg/ha)", 400.0, step=10.0); g_max = st.number_input("Máx (kg/ha)", 900.0, step=10.0)
        g_preco = st.number_input("Preço R$/Ton Gesso", 400.0, step=1.0)

    return {
        "global": {"prod": prod_alvo},
        "calcario": {"cao": c_cao, "mgo": c_mgo, "prnt": c_prnt, "t_ca": c_t_ca, "t_mg": c_t_mg, "res": c_res, "preco": c_preco},
        "fosforo": {"nc": [nc0_4, nc4_10, nc10_19, nc19_30, nc30_45, nc45_60], "f_arg": [f_m_arg, f_arg, f_med, f_are], "teor": p_teor, "exp": p_exp_f, "preco": p_preco},
        "potassio": {"target": k_target, "exp": k_exp_f, "teor": k_teor, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco},
        "meta": {"produtor": produtor, "fazenda": fazenda, "talhao": talhao}
    }

# --- CAMADA 2: MOTOR LÓGICO V43 ---
def motor_v43(df, p):
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'})
    
    # Gesso: Argila % x Fator (15)
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])

    # Calagem: Maior dose Ca (560) ou Mg (400) + Reserva
    df['nc_ca'] = ((p['calcario']['t_ca'] - df['ca_p']) * df['ctc'] / 100).clip(lower=0)
    df['nc_mg'] = ((p['calcario']['t_mg'] - df['mg_p']) * df['ctc'] / 100).clip(lower=0)
    df['dose_ca'] = (df['nc_ca'] * 5600000) / (p['calcario']['cao'] * p['calcario']['prnt'] + 0.1)
    df['dose_mg'] = (df['nc_mg'] * 4000000) / (p['calcario']['mgo'] * p['calcario']['prnt'] + 0.1)
    df['rec_calcario'] = (np.maximum(df['dose_ca'], df['dose_mg']) + p['calcario']['res']).round(2)

    # Fósforo: NC P-rem com Crédito de Solo + Exportação
    def calc_p(row):
        nc_idx
