import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
from math import ceil

# --- ESTILO E IDENTIDADE ---
st.set_page_config(layout="wide", page_title="Tríade Agro v123")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
    h1, h2, h3 { color: #8B4513; }
    .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.08; font-size: 35px; color: #8B4513; z-index: -1; pointer-events: none; }
    </style>
    <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
""", unsafe_allow_html=True)

# --- LOGIN E HIERARQUIA ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 0.6, 1])
    with col_login:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=180)
        senha = st.text_input("Senha Master:", type="password")
        if st.button("ACESSAR"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

if "data_ready" not in st.session_state:
    st.header("📂 Configuração de Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor:", "Danilo")
    with c2: faz = st.text_input("Fazenda:")
    with c3: muni = st.text_input("Município/UF:")
    u_geo = st.file_uploader("Contorno GeoJSON", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    
    if st.button("INICIAR AMBIENTE TRÍADE"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in idx_cols.items(): df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- ABA DE ATRIBUTOS (MOTOR REVISADO) ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Parametrização do Motor Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calcário e Metas")
        prod_meta = st.number_input("Meta (sc/ha)", 80.0)
        ca_alvo = st.number_input("Alvo Ca (%)", 50.0); mg_alvo = st.number_input("Alvo Mg (%)", 15.0)
        prnt = st.number_input("PRNT (%)", 85.0); c_calc = st.number_input("R$/Ton Calcário", 220.0)
    with c2:
        st.subheader("Fósforo (6 Faixas P-rem)")
        nc_p = [st.number_input(f"NC P-rem {f}", v) for f, v in zip(["0-4", "4-10", "10-19", "19-30", "30-45", "45-60"], [8.0, 10.0, 12.0, 15.0, 20.0, 25.0])]
        f_m_arg = st.number_input("Fator Muito Argiloso", 10.0); f_arg = st.number_input("Fator Argiloso", 8.0)
    with c3:
        st.subheader("Potássio e Sementes")
        k_alvo = st.number_input("K Alvo CTC (%)", 3.2); c_k = st.number_input("R$/Ton K", 3200.0)
        pob_sem = st.number_input("Sementes/ha", 280000); c_bag = st.number_input("R$/Big Bag", 4500.0)

    # PROCESSAMENTO TÉCNICO
    # Calcário (Lei do Maior)
    def calc_calcario(row):
        n_ca = ((ca_alvo * row['CTC']/100) - row['Ca']) * 100/36 
        n_mg = ((mg_alvo * row['CTC']/100) - row['Mg']) * 100/9
        return max(0.0, float(max(n_ca, n_mg))) * (100/prnt) * 1000
    df['Rec_Calcario'] = df.apply(calc_calcario, axis=1)

    # Fósforo (Fator Argila + NC P-rem)
    def motor_p(row):
        pr = row['P_rem']
        nc = nc_p[0] if pr <= 4 else nc_p[1] if pr <= 10 else nc_p[2] if pr <= 19 else nc_p[3] if pr <= 30 else nc_p[4] if pr <= 45 else nc_p[5]
        fator = f_m_arg if row['Argila'] > 600 else f_arg if row['Argila'] > 350 else 6.0
        gordura = (nc - row['P']) * fator
        return max(0.0, float(gordura + (prod_meta * 0.8))) * 100 / 46
    df['Rec_Fosforo'] = df.apply(motor_p, axis=1)

with tabs[4]:
    st.header("🗺️ Zonas e Amostragem IA")
    pts_alta = st.number_input("Pontos Zona Alta:", 5)
    st.button("GERAR PONTOS COM RECUO DE 30M")
    st.write("Tabela de Coordenadas Editável:")
    st.data_editor(pd.DataFrame({"Ponto": ["01", "02"], "Lat": [df.Lat.mean(), df.Lat.min()], "Lon": [df.Lon.mean(), df.Lon.min()]}))

with tabs[6]:
    st.header("📄 Fechamento Financeiro")
    c_corr = (df['Rec_Calcario'].mean() * c_calc/1000) + (df['Rec_Gesso'].mean() * 140/1000)
    # Tabela por Natureza como solicitado
    resumo = pd.DataFrame({
        "Natureza": ["Corretivos", "Fertilizantes", "Sementes", "TOTAL"],
        "R$/ha": [c_corr, 1200.0, (pob_sem/5000000)*c_bag, 0.0] # Valores simulados para estrutura
    })
    st.table(resumo)
