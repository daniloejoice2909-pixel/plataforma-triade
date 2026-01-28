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
from datetime import datetime

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v102")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3 { color: #8B4513; font-family: 'Open Sans', sans-serif; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 16px !important; font-weight: bold; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 10px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. TELA DE LOGIN (CAMADA 1) ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Acesso Restrito</h2>", unsafe_allow_html=True)
        senha = st.text_input("Chave de Acesso Master:", type="password")
        if st.button("ENTRAR NA PLATAFORMA"):
            if senha == "triade2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

# --- 3. TELA DE PROJETO (CAMADA 2 - SÓ APARECE APÓS LOGIN) ---
if "auth_projeto" not in st.session_state:
    st.header("📂 Configuração do Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.prod = st.text_input("Nome do Produtor:", "Danilo")
        st.session_state.faz = st.text_input("Nome da Fazenda:")
        st.session_state.mun = st.text_input("Município:")
    with c2:
        u_geo = st.file_uploader("Upload Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Upload Planilha Solo (A-Y)", type=["xlsx"])
    
    if st.button("CONFIGURAR DASHBOARD"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            # Mapeamento rigoroso A-Y conforme pedido
            cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
            df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
            st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.auth_projeto = True
            st.rerun()
        else:
            st.warning("Por favor, suba os arquivos de Contorno e a Planilha.")
    st.stop()

# --- 4. MOTOR DE MAPAS (RESOLUÇÃO 350j) ---
def gerar_mapa_triade(df, atributo, label, n_classes=6, palette='coolwarm'):
    contorno = st.session_state.contorno
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:350j, miny:maxy:350j]
    rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    points = np.c_[grid_x.ravel(), grid_y.ravel()]
    mask = np.array([contorno.contains(Point(p)) for p in points]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    
    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    if palette == 'triade_zonas':
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(['#FF0000', '#0000FF', '#008000']) # Vermelho (B), Azul (M), Verde (A)
    else:
        cmap = plt.cm.get_cmap(palette, n_classes)
        
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap, interpolation='bilinear')
    x_c, y_c = contorno.exterior.xy
    ax.plot(x_c, y_c, color='black', linewidth=1.5)
    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.ax.tick_params(labelsize=8)
    stats = f"Min: {df[atributo].min():.1f} | Med: {df[atributo].mean():.1f} | Max: {df[atributo].max():.1f}"
    plt.figtext(0.5, 0.05, stats, ha="center", fontsize=8, bbox={"facecolor":"white", "alpha":0.8})
    ax.axis('off')
    return fig

# --- 5. DASHBOARD FINAL
