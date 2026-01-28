import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os

# --- 1. CONFIGURAÇÃO INICIAL E IDENTIDADE ---
st.set_page_config(layout="wide", page_title="Tríade Agro v125", initial_sidebar_state="collapsed")

def carregar_estilo():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
        .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
        .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.08; font-size: 30px; color: #8B4513; z-index: -1; pointer-events: none; }
        div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; width: 100%; }
        </style>
        <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
    """, unsafe_allow_html=True)

carregar_estilo()

# --- 2. LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col, _ = st.columns([1, 0.6, 1])
    with col:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=200)
        senha = st.text_input("Acesso Restrito:", type="password")
        if st.button("DESBLOQUEAR SISTEMA"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

# --- 3. GESTÃO DE PASTAS E ARQUIVOS ---
if "data_ready" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor:", "Danilo")
    with c2: faz = st.text_input("Fazenda:")
    with c3: muni = st.text_input("Município/UF:")
    
    col_u1, col_u2 = st.columns(2)
    with col_u1: u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    with col_u2: u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    
    if st.button("CARREGAR DADOS"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in idx_cols.items(): df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df_base = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- 4. PARÂMETROS E MOTOR DE CÁLCULO DINÂMICO ---
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Configuração do Motor Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calcário e Metas")
        meta_sc = st.number_input("Meta Produtividade (sc/ha)", 80.0)
        ca_alvo = st.number_input("Alvo Cálcio na CTC (%)", 50.0)
        mg_alvo = st.number_input("Alvo Magnésio na CTC (%)", 15.0)
        prnt = st.number_input("PRNT Calcário (%)", 85.0)
        c_calc = st.number_input("Preço Calcário (R$/Ton)", 220
