import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json, os, io, requests, tempfile, zipfile
from fpdf import FPDF
from datetime import datetime

# --- 1. CONFIGURAÇÕES DE INTERFACE E ESTILO TRÍADE ---
st.set_page_config(layout="wide", page_title="Tríade Agro v142", page_icon="🌱")

def aplicar_estilo():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
        .stApp { font-family: 'Open Sans', sans-serif; font-size: 12pt; }
        h1, h2, h3 { color: #8B4513; font-weight: bold; }
        .stMetric { background-color: #fdf5e6; padding: 15px; border-radius: 10px; border-left: 5px solid #8B4513; }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo()

# --- 2. LOGIN E LOGOTIPO ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col, _ = st.columns([1, 0.8, 1])
    with col:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", use_container_width=True)
        st.subheader("Acesso Restrito")
        senha = st.text_input("Senha Mestra:", type="password")
        if st.button("DESBLOQUEAR PLATAFORMA"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
            else: st.error("Acesso Negado.")
    st.stop()

# --- 3. CARREGAMENTO DE DADOS ---
if "data_ready" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor:", "Danilo")
    with c2: faz = st.text_input("Fazenda:")
    with c3: muni = st.text_input("Município/UF:")
    
    col_u1, col_u2 = st.columns(2)
    with col_u1: u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    with col_u2: u_sol = st.file_uploader("Planilha Solo (Colunas A-Y)", type=["xlsx"])
    
    if st.button("CARREGAR AMBIENTE"):
        if u_geo and u_sol:
            df_raw = pd.read_excel(u_sol)
            idx = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for k, v in idx.items(): df[v] = pd.to_numeric(df_raw.iloc[:, k], errors='coerce')
            st.session_state.df_base = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- 4. MOTOR DE CÁLCULO TRÍADE V142 (INTEGRADO) ---
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🌱 SEMEADURA", "🧪 N & DEFENSIVOS", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Ajustes de Metodologia")
    col1, col2, col3 = st.columns(3)
    with col1:
        meta_base = st.number_input("Meta Base (sc/ha)", 80.0)
        ca_alvo = st.number_input("Alvo Ca (%)", 50.0)
        mg_alvo = st.number_input("Alvo Mg (%)", 15.0)
        prnt = st.number_input("PRNT do Calcário (%)", 85.0)
    with col2:
        nc_p = [st.number_input(f"NC P-rem F{i+1}", v) for i,v in enumerate([8,10,12,15,20,25])]
        f_ma = st.number_input("Fator Argila > 600", 10.0)
        f_a = st.number_input("Fator Argila 350-600", 8.0)
    with col3:
        k_alvo = st.number_input("Alvo K (%)", 3.2)
        pob_alvo = st.number_input("População (Sem/ha)", 280000)

def motor_calculo():
    d = st.session_state.df_base.copy()
    # Integração Satélite (Simulada se não houver API ativa)
    fator_sat = st.session_state.get('ndvi_map', 1.0)
    meta_viva = meta_base * fator_sat
    
    # Gesso e Calcário (kg/ha)
    d['Gesso_kg_ha'] = (d['Argila'] * 15).clip(400, 900)
    n_ca = (((ca_alvo * d['CTC']/100) - d['Ca']) * 100/36).clip(0)
    n_mg = (((mg_alvo * d['CTC']/100) - d['Mg']) * 100/9).clip(0)
    d['Calcario_kg_ha'] = np.maximum(n_ca, n_mg) * (100/prnt) * 1000
    
    # Fósforo e Potássio (kg/ha) - Baseado na Meta Viva do Satélite
    def calc_p(r, mv):
        pr = r['P_rem']
        nc = nc_p[0] if pr <= 4 else nc_p[1] if pr <= 10 else nc_p[2] if pr <= 19 else nc_p[3] if pr <= 30 else nc_p[4] if pr <= 45 else nc_p[5]
        fator = f_ma if r['Argila'] > 600 else f_a
        return max(0.0, (nc - r['P']) * fator + (
