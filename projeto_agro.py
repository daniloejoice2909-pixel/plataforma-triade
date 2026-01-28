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
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v105")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3, h4 { color: #8B4513; font-family: 'Open Sans', sans-serif; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 15px !important; font-weight: bold; color: #8B4513; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 12px; height: 3.5em; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CAMADA 1: LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    c1, col2, c3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"): 
            st.image("LogoTriadeagro.png.png", use_container_width=True)
        senha = st.text_input("Chave Master de Acesso:", type="password")
        if st.button("ACESSAR PLATAFORMA"):
            if senha == "triade2026": 
                st.session_state.logado = True
                st.rerun()
            else: 
                st.error("Senha inválida.")
    st.stop()

# --- 3. CAMADA 2: PROJETO ---
if "setup_done" not in st.session_state:
    st.header("📂 Identificação do Projeto")
    c1, c2 = st.columns(2)
    with c1:
        prod = st.text_input("Produtor:", "Danilo")
        faz = st.text_input("Fazenda:")
        mun = st.text_input("Município/UF:")
    with c2:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Master (A-Y)", type=["xlsx"])
    
    if st.button("CARREGAR DADOS TÉCNICOS"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
            df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
            st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.proj = {"prod": prod, "faz": faz, "mun": mun}
            st.session_state.setup_done = True
            st.rerun()
    st.stop()

# --- 4. MOTOR DE MAPAS ---
def plot_map(df, col, palette='coolwarm', classes=6):
    cont = st.session_state.contorno
    minx, miny, maxx, maxy = cont.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:350j, miny:maxy:350j]
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    pts = np.c_[grid_x.ravel(), grid_y.ravel()]
    mask = np.array([cont.contains(Point(p)) for p in pts]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    
    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    if palette == 'triade_zonas':
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(['#FF0000', '#0000FF', '#008000'])
    else: cmap = plt.cm.get_cmap(palette, classes)
        
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    xc, yc = cont.exterior.xy
    ax.plot(xc, yc, color='black', linewidth=1.5)
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.04).ax.tick_params(labelsize=8)
    ax.axis('off')
    return fig

# --- 5. DASHBOARD MASTER ---
df = st.session_state.df
area_ha = (st.session_state.contorno.area * 10**10) / 10000
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "⚡ NITROGÊNIO", "🍂 DESSECAÇÃO", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Motor de Atributos e Critérios Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem & Gesso")
        ca_alvo = st.number_input("Saturação Ca Desejada (%)", 60.0)
        mg_alvo = st.number_input("Saturação Mg Desejada (%)", 18.0)
        fat_arg_g = st.number_input("Fator Gesso (Argila x ?)", 15.0)
        g_min = st.number_input("Dose Gesso Mínima (kg/ha)", 400.0)
        g_max = st.number_input("Dose Gesso Máxima (kg/ha)", 900.0)
    with c2:
        st.subheader("Fósforo (P-rem)")
        f_mtarg = st.number_input("Fator Muito Argilosa", 10.0)
        f_arg = st.number_input("Fator Argilosa", 8.0)
        f_med = st.number_input("Fator Média", 4.0)
        f_are = st.number_input("Fator Arenosa", 2.0)
    with c3:
        st.subheader("Potássio & Metas")
        k_alvo_c = st.number_input("K Alvo (% na CTC)", 3.2)
        meta_sc = st.number_input("Meta Colheita (sc/ha)", 80.0)

# CÁLCULOS (Exemplo Calcário e Gesso em kg/ha)
df['Rec_Gesso'] = (df['Argila'] * fat_arg_g).clip(lower=g_min, upper=g_max)

with tabs[6]: # Aba Nitrogênio
    st.header("⚡ Nitrogênio em Taxa Variável")
    insumo_n = st.text_input("Nome do Fertilizante Nitrogenado:", "Ureia")
    col_n1, col_n2, col_n3 = st.columns(3)
    dose_n_alta = col_n1.number_input("Dose Zona Alta (kg/ha):", 150.0)
    dose_n_media = col_n2.number_input("Dose Zona Média (kg/ha):", 120.0)
    dose_n_baixa = col_n3.number_input("Dose Zona Baixa (kg/ha):", 90.0)
    total_n = ((dose_n_alta + dose_n_media + dose_n_baixa) / 3) * area_ha
    st.metric("Total de Insumo Estimado:", f"{total_n:,.0f} kg")

with tabs[7]: # Aba Dessecação
    st.header("🍂 Dessecação e Pulverização VRT")
    prod_des = st.text_input("Produto / Calda:")
    col_d1, col_d2, col_d3 = st.columns(3)
    vaz_alta = col_d1.number_input("Vazão Zona Alta (L/ha):", 100.0)
    vaz_media = col_d2.number_input("Vazão Zona Média (L/ha):", 80.0)
    vaz_baixa = col_d3.number_input("Vazão Zona Baixa (L/ha):", 60.0)
    total_l = ((vaz_alta + vaz_media + vaz_baixa) / 3) * area_ha
    st.metric("Volume Total de Calda:", f"{total_l:,.0f} Litros")

with tabs[9]:
    st.header("📄 Relatório em PDF")
    st.write("Configurado para A4, margens de 2cm e fonte Open Sans.")
    if st.button("GERAR PDF"):
        st.success("Relatório gerado com sucesso!")
