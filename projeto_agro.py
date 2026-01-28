import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
from math import ceil

# --- CONFIGURAÇÕES DE ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro v124")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
    .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.08; font-size: 30px; color: #8B4513; z-index: -1; pointer-events: none; }
    </style>
    <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
""", unsafe_allow_html=True)

# --- FLUXO DE ACESSO ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col, _ = st.columns([1, 0.6, 1])
    with col:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=200)
        senha = st.text_input("Acesso Restrito:", type="password")
        if st.button("ENTRAR"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

# --- GESTÃO DE DADOS ---
if "data_ready" not in st.session_state:
    st.header("📂 Gestão de Projetos")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor:", "Danilo")
    with c2: faz = st.text_input("Fazenda:")
    with c3: muni = st.text_input("Município/UF:")
    u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("Dados de Solo (Excel)", type=["xlsx"])
    
    if st.button("PROCESSAR DADOS TRÍADE"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            # Mapeamento fixo das colunas conforme sua planilha
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in idx_cols.items(): df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- MOTOR DE CÁLCULO CENTRALIZADO (EVITA KEYERROR) ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Configurações do Motor")
    c1, c2, c3 = st.columns(3)
    with c1:
        prod_meta = st.number_input("Produtividade Alvo (sc/ha)", 80.0)
        ca_alvo = st.number_input("Alvo Ca na CTC (%)", 50.0)
        mg_alvo = st.number_input("Alvo Mg na CTC (%)", 15.0)
        prnt = st.number_input("PRNT Calcário (%)", 85.0)
    with c2:
        st.subheader("Fatores P (Fator Argila)")
        f_ma = st.number_input("Muito Argiloso (>600)", 10.0); f_a = st.number_input("Argiloso (350-600)", 8.0)
        st.subheader("NC P-rem")
        nc_p_list = [st.number_input(f"NC Faixa {i}", v) for i, v in enumerate([8, 10, 12, 15, 20, 25])]
    with c3:
        st.subheader("Custos Insumos")
        c_p = st.number_input("R$/Ton P2O5", 3800.0); c_k = st.number_input("R$/Ton K2O", 3200.0)
        c_calc = st.number_input("R$/Ton Calcário", 220.0); c_gesso = st.number_input("R$/Ton Gesso", 140.0)
        pob_alvo = st.number_input("Sementes/ha", 280000); c_bag = st.number_input("R$/Big Bag", 4500.0)

    # PROCESSAMENTO DE TODAS AS VARIÁVEIS DE UMA VEZ
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(400, 900)
    
    def calc_triade(row):
        # Calcário (Maior Dose Ca vs Mg)
        n_ca = max(0.0, ((ca_alvo * row['CTC']/100) - row['Ca']) * 100/36)
        n_mg = max(0.0, ((mg_alvo * row['CTC']/100) - row['Mg']) * 100/9)
        rec_calc = max(n_ca, n_mg) * (100/prnt) * 1000
        
        # Fósforo (Fator Argila + NC P-rem)
        pr = row['P_rem']
        nc = nc_p_list[0] if pr <= 4 else nc_p_list[1] if pr <= 10 else nc_p_list[2] if pr <= 19 else nc_p_list[3] if pr <= 30 else nc_p_list[4] if pr <= 45 else nc_p_list[5]
        fator = f_ma if row['Argila'] > 600 else f_a if row['Argila'] > 350 else 6.0
        rec_p = max(0.0, (nc - row['P']) * fator + (prod_meta * 0.8)) * 100 / 46
        
        # Potássio
        rec_k = (max(0.0, ((3.2 * row['CTC']/100) - row['K']) * 940) + (prod_meta * 1.2)) * 100 / 60
        
        return pd.Series([rec_calc, rec_p, rec_k])

    df[['Rec_Calcario', 'Rec_Fosforo', 'Rec_Potassio']] = df.apply(calc_triade, axis=1)

# --- A PARTIR DAQUI, TODAS AS COLUNAS EXISTEM E NÃO GERARÃO KEYERROR ---
with tabs[6]:
    st.header("📊 Resumo Financeiro por Natureza")
    c_corretivos = (df['Rec_Calcario'].mean() * c_calc/1000) + (df['Rec_Gesso'].mean() * c_gesso/1000)
    c_fertilizantes = (df['Rec_Fosforo'].mean() * c_p/1000) + (df['Rec_Potassio'].mean() * c_k/1000)
    c_sementes = (pob_alvo / 5000000) * c_bag
    
    financeiro = pd.DataFrame({
        "Natureza": ["Corretivos", "Fertilizantes", "Sementes", "TOTAL"],
        "R$/ha": [c_corretivos, c_fertilizantes, c_sementes, c_corretivos+c_fertilizantes+c_sementes]
    })
    st.table(financeiro.style.format({"R$/ha": "R$ {:.2f}"}))
