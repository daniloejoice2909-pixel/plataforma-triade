import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import plotly.express as px
from shapely.geometry import shape

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""<style> .stApp { background-color: #FFFFFF; } html, body { font-family: 'Open Sans', sans-serif; font-size: 16px; } </style>""", unsafe_allow_html=True)

# --- 2. LOGIN ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        logo = "LogoTriadeagro.png.png"
        if os.path.exists(logo): st.image(logo, width=200)
        senha = st.text_input("Senha Master:", type="password")
        if st.button("Acessar"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. CARREGAMENTO ---
if "df" not in st.session_state:
    st.header("📥 Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Dados Solo (A-Y)", type=["xlsx"])
    with c2:
        st.session_state.prod = st.text_input("Produtor:")
        st.session_state.faz = st.text_input("Fazenda:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items()}, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.success("✅ Projeto Carregado!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. FUNÇÃO DE CLASSIFICAÇÃO (6 CAMADAS) ---
def categorizar_6_classes(serie):
    if serie.nunique() <= 1: return serie
    # Divide em 6 faixas iguais (Quantis) para facilitar a leitura do monitor
    return pd.qcut(serie, q=6, labels=False, duplicates='drop')

# --- 5. PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas Solo", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # Atributos
    st.header("⚙️ Parâmetros")
    c1, c2, c3 = st.columns(3)
    with c1:
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo, mg_alvo = st.number_input("Ca% Desejado", 60.0); mg_alvo_val = st.number_input("Mg% Desejado", 18.0)
    with c2:
        p2o5_ad = st.number_input("% P2O5 do Adubo", 21.0); fat_p_sc = st.number_input("Fator P (kg/sc)", 0.8)
    with c3:
        k_alvo = st.number_input("K% Desejado", 3.2); meta_prod = st.number_input("Meta sc/ha", 80.0)

with tabs[2]: # Recomendações (Com 6 camadas)
    st.header("🏠 Recomendações (Processado para Monitores)")
    
    # Motor de Cálculo Tríade
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo_val * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100))).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=400, upper=900)
    df['Rec_K2O'] = (((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta_prod * 1.2)

    mapa_sel = st.selectbox("Escolha o Mapa para Visualizar em 6 Camadas:", ["Rec_Calc", "Rec_Gesso", "Rec_K2O"])
    
    # Criando as 6 camadas
    df['Classe'] = categorizar_6_classes(df[mapa_sel])
    
    # Mapa Visual
    fig = px.scatter_mapbox(df, lat="Lat", lon="Lon", color="Classe", 
                            title=f"Prescrição {mapa_sel} - Agrupada em 6 Zonas",
                            color_continuous_scale="RdYlGn_r", zoom=14, mapbox_style="carto-positron")
    st.plotly_chart(fig, use_container_width=True)
    
    st.info("💡 Este formato agrupa as doses em 6 faixas, permitindo que o controlador do trator aplique sem travamentos.")
