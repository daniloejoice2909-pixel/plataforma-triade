import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from shapely.geometry import shape

# --- 1. CONFIGURAÇÃO VISUAL (FONTE E FUNDO) ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 15px; } /* Letras maiores */
    h1, h2, h3 { color: #8B4513; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN (PÁGINA 1) ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        logo = "LogoTriadeagro.png.png"
        if os.path.exists(logo): st.image(logo, width=200)
        st.markdown("<h2 style='text-align: center;'>Acesso Master</h2>", unsafe_allow_html=True)
        senha = st.text_input("Senha de Acesso:", type="password")
        if st.button("Entrar"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. CARREGAMENTO (PÁGINA 2) ---
if "df" not in st.session_state:
    st.header("📥 Configuração do Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Dados de Solo (A-Y)", type=["xlsx"])
    with c2:
        st.session_state.produtor = st.text_input("Nome do Produtor:")
        st.session_state.fazenda = st.text_input("Fazenda:")
        st.session_state.municipio = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items()}, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Tudo pronto!"); st.button("Iniciar")
    st.stop()

# --- 4. PLATAFORMA (PÁGINA 3) ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações", "🛰️ Satélite", 
                "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório Final"])

# --- ABA ATRIBUTOS (FÓSFORO EDITÁVEL) ---
with tabs[0]:
    st.header("⚙️ Parâmetros de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        cao = st.number_input("Teor CaO %", 36.0); mgo = st.number_input("Teor MgO %", 9.0)
        prnt = st.number_input("PRNT %", 80.0); ca_alvo = st.number_input("Ca desejado (% CTC)", 60.0)
        mg_alvo = st.number_input("Mg desejado (% CTC)", 18.0)
        g_max = st.number_input("Gesso Máx (kg/ha)", 900); g_min = st.number_input("Gesso Mín (kg/ha)", 400)
    with c2:
        st.subheader("🌾 Fósforo (P-rem)")
        # AGORA EDITÁVEL CONFORME PEDIDO
        p2o5_ad = st.number_input("% de P2O5 do Adubo", value=21.0) 
        fat_p_sc = st.number_input("Fator P (kg/sc)", 0.8)
        st.write("**Níveis Críticos por P-rem:**")
        nc1 = st.
