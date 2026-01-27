import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
from fpdf import FPDF
import os
from PIL import Image
from datetime import datetime, timedelta
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# --- CONFIGURAÇÃO DE TELA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica", page_icon="🌱")

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=300)
    senha = st.text_input("Senha de Acesso:", type="password")
    if senha == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image("LogoTriadeInceres.png", width=180)
    st.markdown("### 📋 Informações do Projeto")
    produtor = st.text_input("Produtor", "Danilo")
    fazenda = st.text_input("Fazenda", "Fazenda Modelo")
    municipio = st.text_input("Município", "Uberlândia - MG")
    st.markdown("---")
    logo_fazenda = st.file_uploader("Logo da Fazenda", type=["png", "jpg"])

st.title("Plataforma de Gestão Estratégica v43")
tab_dados, tab_satelite, tab_mapas, tab_zonas, tab_pdf = st.tabs([
    "🏠 Dados e Atributos", "🛰️ Satélite", "🔍 Mapas de Solo", "🗺️ Zonas de Manejo", "📄 Relatório Final"
])

# Variáveis globais
df = None
poligono = None
area_ha = 0.0

# --- ABA 1: DADOS E ATRIBUTOS ---
with tab_dados:
    c1, c2 = st.columns(2)
    up_geo = c1.file_uploader("1. Contorno (GeoJSON)", type=["json", "geojson"])
    up_ex = c2.file_uploader("2. Planilha de Solo (Excel)", type=["xlsx"])
    
    if up_geo and up_ex:
        data_geo = json.load(up_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        b = poligono.bounds
        area_ha = (poligono.area / ((b[2]-b[0])*(b[3]-b[1]))) * ((b[2]-b[0])*111320 * (b[3]-b[1])*110540) / 10000
        
        df_raw = pd.read_excel(up_ex)
        df = df_raw.copy()
        df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors='coerce')
        df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors='coerce')
        df = df.dropna(subset=[df.columns[0], df.columns[1]])
        
        cols_dados = []
        for c in df.columns[2:]:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            if not df[c].isnull().all():
                df[c] = df[c].fillna(df[c].mean())
                cols_dados.append(c)
        
        st.markdown("### 📊 Tabela de Atributos Identificados")
        st.dataframe(df, use_container_width=True)
        st.metric("Área Total Calculada", f"{area_ha:.2f} ha")

# --- ABA 2: SATÉLITE ---
with tab_satelite:
    st.subheader("Análise Sentinel-2 (NDVI)")
    s1, s2 = st.columns(2)
    data_sat = s1.date_input("Data de Referência", datetime.now() - timedelta(days=5))
    nuvens = s2.slider("Filtro de Nuvens (%)", 0, 100, 10)
    if st.button("🔍 Gerar Mapa de Vigor"):
        st.image("https://via.placeholder.com/800x400/2E7D32/FFFFFF?text=Mapa+NDVI+v43+-+Tríade+Agro", caption=f"Vigor Vegetativo em {data_sat}")

# --- MOTOR DE INTERPOLAÇÃO ---
def plot_rbf(coluna):
    df_c = df[[df.columns[1], df.columns[0], coluna]].dropna()
    x, y, z = df_c.iloc[:, 0].values, df_c.iloc[:, 1].values, df_c.iloc[:, 2].values
    b = poligono.bounds
    gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
    rbf = Rbf(x, y, z, function='multiquadric', smooth=0.1)
    grid_z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(xp, yp)) for yp in gy[0,:]] for xp in gx[:,0]]))
    
    fig, ax = plt.subplots(figsize=(6, 6))
    cp = ax.contourf(gx, gy, grid_z, levels=6, cmap='Spectral_r')
    ax.plot(*poligono.exterior.xy, color='black', linewidth=1.5)
    plt.colorbar(cp, fraction=0.03, pad=0.04)
    ax.axis('off')
    return fig, z.min(), z.mean(), z.max(), grid_z

# --- ABA 3: MAPAS E ABA 4: ZONAS ---
if df is not None:
    with tab_mapas:
        m1, m2 = st.columns(2)
        for i, col in enumerate(cols_dados
