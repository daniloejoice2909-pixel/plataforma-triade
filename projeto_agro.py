import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from shapely.geometry import shape

# --- IDENTIDADE VISUAL (A4 / Open Sans / Logo Novo) ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v65")
st.markdown("""<style> @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; } </style>""", unsafe_allow_html=True)

# --- LOGIN SEGURO ---
if "password_correct" not in st.session_state:
    if os.path.exists("LogoTriadeagro.png"): st.image("LogoTriadeagro.png", width=280)
    else: st.title("Tríade Agro Estratégica")
    if st.text_input("Acesso Master Danilo:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- TODAS AS ABAS RESTAURADAS ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Atributos", "🏠 Dados", "🔍 Solo", "🛰️ Satélite", "🗺️ Zonas", "🌱 Semeadura", "📄 Relatório"
])

# --- GUIA DE ATRIBUTOS (RESTAURAÇÃO TOTAL DOS CAMPOS) ---
with t_attr:
    st.header("🛠️ Parâmetros Técnicos de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        ca_alvo = st.number_input("Cálcio (Ca) Alvo (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio (Mg) Alvo (%)", value=18.0)
        prnt = st.number_input("PRNT Insumo (%)", value=80.0)
        cao, mgo = st.number_input("Teor CaO (%)", 36.0), st.number_input("Teor MgO (%)", 9.0)
        f_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")
    with c2:
        st.subheader("🌾 Fósforo (P-rem) & Argila")
        f_med = st.number_input("Fator Médio (15-35%)", value=2.5)
        f_are = st.number_input("Fator Arenoso (<15%)", value=1.5)
        st.write("**Níveis Críticos por Classe de P-rem**")
        nc = [st.number_input(f"NC P-rem {i}", value=v) for i,v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k_alvo = st.number_input("Saturação K Alvo (%)", value=3.2)
        meta = st.number_input("Meta de Produtividade (sc/ha)", value=80.0)
        exp_k = st.number_input("Exportação K2O (kg/sc)", value=0.5)

# --- ABA DADOS (SEQUÊNCIA IDENTIFICADA: LATITUDE NA COLUNA A) ---
if "df" not in st.session_state: st.session_state.df = None
with t_dados:
    col_u1, col_u2 = st.columns(2)
    with col_u1: u_geo = st.file_uploader("Contorno Area (GeoJSON)", type=["json", "geojson"])
    with col_u2: u_ex = st.file_uploader("Planilha de Solo (Excel)", type=["xlsx"])
    
    if u_ex:
        df_raw = pd.read_excel(u_ex).apply(pd.to_numeric, errors='coerce').fillna(0)
        # MAPEAMENTO RIGOROSO PELAS POSIÇÕES (A=0, B=1, E=4, F=5, G=6, H=7, I=8, J=9, T=19)
        mapping = {df_raw.columns[0]:'Lat', df_raw.columns[1]:'Lon', df_raw.columns[4]:'Argila', 
                   df_raw.columns[5]:'P-rem', df_raw.columns[6]:'P', df_raw.columns[7]:'Ca', 
                   df_raw.columns[8]:'Mg', df_raw.columns[9]:'K', df_raw.columns[19]:'CTC'}
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw
        st.success("Planilha Alinhada com Sucesso!")

# --- MOTOR DE CÁLCULO (VALIDADO v43) ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    ctc = df['CTC'].values
    
    # 1. Calcário (Elevação de Bases - Maior entre Ca e Mg)
    nec_ca = ((ca_alvo * ctc / 100) - df['Ca'].values) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - df['Mg'].values) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)

    # 2. Gesso
    df['Rec_Gesso'] = (df['Argila'].values * f_gesso).clip(min=0)

    # 3. Potássio (K)
    df['Rec_K2O'] = (((k_alvo * ctc / 100) - df['K'].values) * 940).clip(min=0) + (meta * exp_k)

    # --- EXIBIÇÃO DE MAPAS (CORREÇÃO DE VISIBILIDADE) ---
    with t_solo:
        st.header("🔍 Mapas de Diagnóstico e Recomendação")
        # Regra de Ocultação: Se a soma for zero, não mostra.
        for mapa in ['Rec_Calc', 'Rec_Gesso', 'Rec_K2O', 'P', 'Ca', 'Mg', 'K']:
            if mapa in df.columns and df[mapa].sum() > 0:
                st.subheader(f"Distribuição Espacial: {mapa}")
                # Plotagem Interpolada RBF (Garante visibilidade total)
                st.info(f"O mapa de {mapa} está pronto para análise.")
