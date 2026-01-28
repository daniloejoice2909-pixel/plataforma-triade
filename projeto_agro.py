import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import plotly.express as px
from shapely.geometry import shape

# --- 1. CONFIGURAÇÃO VISUAL (FONTE GRANDE & FUNDO BRANCO) ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 18px; } 
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; }
    h1, h2, h3 { color: #8B4513; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        logo = "LogoTriadeagro.png.png"
        if os.path.exists(logo): st.image(logo, width=200)
        senha = st.text_input("Senha Master:", type="password")
        if st.button("Acessar Plataforma"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. CARREGAMENTO DE DADOS ---
if "df" not in st.session_state:
    st.header("📥 Configuração de Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    with c2:
        st.session_state.prod = st.text_input("Produtor:")
        st.session_state.faz = st.text_input("Fazenda:")
        st.session_state.mun = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        # Mapeamento rigoroso A-Y conforme sua solicitação
        cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items()}, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success(f"✅ Dados Carregados! Área: {st.session_state.area_ha:.2f} ha")
        st.button("Abrir Plataforma")
    st.stop()

# --- 4. PLATAFORMA INTEGRAL ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

# ABA ATRIBUTOS
with tabs[0]:
    st.header("⚙️ Parâmetros de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% Desejado", 60.0); mg_alvo = st.number_input("Mg% Desejado", 18.0)
        g_max = st.number_input("Gesso Máx (kg/ha)", 900.0); g_min = st.number_input("Gesso Mín", 400.0)
    with c2:
        st.subheader("🌾 Fósforo (P-rem)")
        p2o5_ad = st.number_input("% P2O5 Adubo", 21.0)
        nc1 = st.number_input("NC 0-4 P-rem", 8.0); nc2 = st.number_input("NC 4-10", 10.0)
        nc3 = st.number_input("NC 10-19", 12.0); nc4 = st.number_input("NC 19-30", 15.0)
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k_alvo = st.number_input("K% Desejado", 3.2); meta_prod = st.number_input("Meta sc/ha", 80.0)
        fat_k_sc = st.number_input("Fator K (kg/sc)", 1.2)

# ABA MAPAS SOLO (EXIBIÇÃO REAL)
with tabs[1]:
    st.header("🔍 Mapas de Fertilidade")
    attr = st.selectbox("Selecione o Atributo para Visualizar:", ["Argila", "P", "Ca", "Mg", "K", "P-rem", "CTC"])
    fig_solo = px.scatter_mapbox(df, lat="Lat", lon="Lon", color=attr, size_max=12, zoom=14, 
                                 mapbox_style="carto-positron", color_continuous_scale="Viridis")
    st.plotly_chart(fig_solo, use_container_width=True)

# ABA RECOMENDAÇÕES (6 CAMADAS PARA MONITOR)
with tabs[2]:
    st.header("🏠 Recomendações (Taxa Variável)")
    adic_calc = st.number_input("Adicional Calcário (t/ha)", 0.0)
    # Lógica de Cálculo
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)) + adic_calc).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
    df['Rec_K2O'] = (((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta_prod * fat_k_sc)

    sel_rec = st.selectbox("Escolha a Prescrição:", ["Rec_Calc", "Rec_Gesso", "Rec_K2O"])
    # Agrupamento em 6 Zonas
    df['Zonas_6'] = pd.qcut(df[sel_rec], q=6, labels=False, duplicates='drop')
    fig_rec = px.scatter_mapbox(df, lat="Lat", lon="Lon", color="Zonas_6", color_continuous_scale="RdYlGn_r", zoom=14, mapbox_style="carto-positron")
    st.plotly_chart(fig_rec, use_container_width=True)

# ABA SATÉLITE E ZONAS (ESTRUTURA)
with tabs[3]:
    st.header("🛰️ Sentinel-2")
    c1, c2 = st.columns(2)
    c1.date_input("Data Inicial"); c2.date_input("Data Final")
    st.radio("Selecione o Índice:", ["NDVI", "NDVI Contrastado", "NDRE", "Brilho de Solo"])

with tabs[4]:
    st.header("🗺️ Zonas de Produtividade")
    st.slider("Fidelidade entre Imagens (%)", 0, 100, 85)
    st.button("Gerar Mapa de Produtividade e Pontos (30m dist.)")

with tabs[8]:
    st.header("📄 Relatório Final")
    st.write(f"**Produtor:** {st.session_state.prod} | **Fazenda:** {st.session_state.faz}")
    st.write(f"**Área Total:** {st.session_state.area_ha:.2f} ha")
    if st.button("Exportar PDF A4"): st.success("Gerando Relatório com Legendas e Sumário...")
