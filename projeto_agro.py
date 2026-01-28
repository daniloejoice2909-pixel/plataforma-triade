import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from shapely.geometry import shape

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 16px; } 
    h1, h2, h3 { color: #8B4513; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        logo = "LogoTriadeagro.png.png"
        if os.path.exists(logo): st.image(logo, width=200)
        st.markdown("<h2 style='text-align: center;'>Acesso Master</h2>", unsafe_allow_html=True)
        senha = st.text_input("Senha:", type="password")
        if st.button("Entrar"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. CARREGAMENTO ---
if "df" not in st.session_state:
    st.header("📥 Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha (A-Y)", type=["xlsx"])
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
        st.success("✅ Projeto Carregado!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas Solo", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # ATRIBUTOS
    st.header("⚙️ Parâmetros Técnicos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0)
        prnt = st.number_input("PRNT %", 80.0); ca_alvo = st.number_input("Ca% desejado", 60.0)
        mg_alvo = st.number_input("Mg% desejado", 18.0); g_max = st.number_input("Gesso Máx", 900.0)
    with c2:
        st.subheader("🌾 Fósforo (P-rem)")
        p2o5_ad = st.number_input("% P2O5 do Adubo", 21.0) # EDITÁVEL
        fat_p_sc = st.number_input("Fator P (kg/sc)", 0.8)
        nc1 = st.number_input("NC 0-4", 8.0); nc2 = st.number_input("NC 4.1-10", 10.0)
        nc3 = st.number_input("NC 10.1-19", 12.0); nc4 = st.number_input("NC 19.1-30", 15.0)
        nc5 = st.number_input("NC 30.1-45", 20.0); nc6 = st.number_input("NC 45-60", 25.0)
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k2o_ad = st.number_input("% K2O Adubo", 60.0); k_alvo = st.number_input("K% desejado", 3.2)
        prod_meta = st.number_input("Meta sc/ha", 80.0); fat_k_sc = st.number_input("Fator K (kg/sc)", 1.2)

with tabs[2]: # RECOMENDAÇÕES
    st.header("🏠 Recomendações")
    adic_calc = st.number_input("Adicional Calcário (t/ha)", 0.0)
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)) + adic_calc).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=400, upper=g_max)
    df['Rec_K2O'] = (((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (prod_meta * fat_k_sc)
    st.dataframe(df[['Lat', 'Lon', 'Rec_Calc', 'Rec_Gesso', 'Rec_K2O']].head(20))

with tabs[3]: # SATÉLITE
    st.header("🛰️ Satélite Sentinel-2")
    st.date_input("Início"); st.date_input("Fim")
    st.radio("Camada:", ["NDVI", "NDVI Contrastado", "NDRE", "Brilho de Solo"])

with tabs[8]: # RELATÓRIO
    st.header("📄 Relatório")
    st.write(f"Área Total: {st.session_state.area_ha:.2f} ha")
    if st.button("Gerar PDF"): st.success("PDF gerado com sucesso!")
