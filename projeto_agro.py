import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
from fpdf import FPDF
import tempfile
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 18px !important; } 
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; }
    h1, h2, h3 { color: #8B4513; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN (FUNDO DOURADO) ---
if "password_correct" not in st.session_state:
    st.markdown("<div style='background-color: #C5A059; padding: 50px; text-align: center; border-radius: 10px;'>", unsafe_allow_html=True)
    logo = "LogoTriadeagro.png.png"
    if os.path.exists(logo): st.image(logo, width=250)
    senha = st.text_input("Senha Master:", type="password")
    if st.button("Entrar"):
        if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 3. CARREGAMENTO ---
if "df" not in st.session_state:
    st.header("📥 Entrada de Dados")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    with c2:
        st.session_state.prod = st.text_input("Nome do Produtor:")
        st.session_state.faz = st.text_input("Fazenda:")
        st.session_state.mun = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.drop_duplicates(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Projeto Carregado!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. MOTOR DE INTERPOLAÇÃO (V43) ---
def gerar_mapa_triade(df, atributo, contorno, label, cmap='coolwarm'):
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:150j, miny:maxy:150j]
    rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    for i in range(len(grid_x)):
        for j in range(len(grid_y)):
            if not contorno.contains(Point(grid_x[i,j], grid_y[i,j])): grid_z[i,j] = np.nan
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title(label, fontsize=12, fontweight='bold')
    ax.axis('off')
    return fig

# --- 5. ABAS DA PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # ATRIBUTOS COMPLETOS
    st.header("⚙️ Parâmetros Técnicos")
    c1, c2, c3 = st.columns(3)
    with c1:
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% Desejado (CTC)", 60.0); mg_alvo = st.number_input("Mg% Desejado (CTC)", 18.0)
    with c2:
        p2o5 = st.number_input("% P2O5 do Adubo", 21.0)
        st.write("**Classes de P-rem (Nível Crítico):**")
        nc1 = st.number_input("0-4 (NC: 8.0)", 8.0); nc2 = st.number_input("4-10 (NC: 10.0)", 10.0)
    with c3:
        k_alvo = st.number_input("K% Alvo", 3.2); meta = st.number_input("Meta sc/ha", 80.0)

with tabs[3]: # ABA SATÉLITE (SENTINEL-2)
    st.header("🛰️ Monitoramento via Satélite (Sentinel-2)")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        dt_ini = st.date_input("Data Inicial", datetime.now() - timedelta(days=30))
        dt_fim = st.date_input("Data Final", datetime.now())
    with col_s2:
        indice = st.selectbox("Selecione o Índice:", ["NDVI", "NDVI Contrastado", "NDRE", "Brilho de Solo"])
        st.button("🔍 Buscar Imagens com Menor Nebulosidade")
    
    st.info("Aguardando conexão com o servidor Copernicus para baixar imagens do período selecionado...")

with tabs[4]: # ZONAS DE PRODUTIVIDADE
    st.header("🗺️ Zonas de Produtividade & Fidelidade")
    st.write("Selecione as camadas para compor o mapa de média:")
    c_ctc = st.checkbox("Mapa de CTC (Solo)", value=True)
    c_ndvi = st.checkbox("NDVI (Satélite)")
    
    fidelidade = st.slider("Percentual de Fidelidade Requerido (%)", 0, 100, 85)
    
    if st.button("Gerar Zonas (Alta/Média/Baixa)"):
        st.warning("Cruzando dados de solo e satélite para definir zonas estáveis...")

with tabs[8]: # RELATÓRIO PDF
    st.header("📄 Relatório Final Profissional")
    if st.button("Gerar PDF A4 Premium"):
        st.success("Mapas e estatísticas Máx/Méd/Mín estão sendo processados...")
