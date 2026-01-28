import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point

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

# --- 3. CARREGAMENTO ---
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
        cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items()}, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Projeto Carregado!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. FUNÇÃO DE MAPA PROFISSIONAL (INTERPOLAÇÃO RBF) ---
def gerar_mapa_profissional(df, atributo, contorno, label, classes=6):
    points = np.array(list(zip(df.Lon, df.Lat)))
    values = df[atributo].values
    
    # Criar grade sobre o contorno
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:150j, miny:maxy:150j]
    
    # Interpolação RBF (Radial Basis Function) - Padrão v43
    rbf = Rbf(df.Lon, df.Lat, values, function='thin_plate')
    grid_z = rbf(grid_x, grid_y)
    
    # Máscara para manter apenas dentro do contorno
    for i in range(len(grid_x)):
        for j in range(len(grid_y)):
            if not contorno.contains(Point(grid_x[i,j], grid_y[i,j])):
                grid_z[i,j] = np.nan

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap='RdYlGn_r')
    plt.colorbar(im, ax=ax, label=label, fraction=0.046, pad=0.04)
    ax.set_title(f"Mapa de {label} - 6 Zonas de Manejo", fontsize=14)
    ax.axis('off')
    return fig

# --- 5. PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # ATRIBUTOS
    st.header("⚙️ Parâmetros Técnicos")
    c1, c2, c3 = st.columns(3)
    with c1:
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% Desejado", 60.0); mg_alvo = st.number_input("Mg% Desejado", 18.0)
    with c2:
        p2o5_ad = st.number_input("% P2O5 Adubo", 21.0)
        st.write("**Nível Crítico P-rem:**")
        nc_p = st.number_input("NC Médio", 12.0)
    with c3:
        k_alvo = st.number_input("K% Alvo", 3.2); meta_prod = st.number_input("Meta (sc/ha)", 80.0)

with tabs[1]: # MAPAS DE FERTILIDADE
    st.header("🔍 Mapas de Fertilidade Interpolados")
    attr = st.selectbox("Atributo:", ["Argila", "P", "Ca", "Mg", "K", "CTC"])
    fig = gerar_mapa_profissional(df, attr, st.session_state.contorno, attr)
    st.pyplot(fig)

with tabs[2]: # RECOMENDAÇÕES
    st.header("🏠 Recomendações (6 Camadas)")
    # Motor Tríade
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100))).clip(lower=0)
    
    sel_rec = st.selectbox("Prescrição:", ["Rec_Calc"])
    fig_rec = gerar_mapa_profissional(df, sel_rec, st.session_state.contorno, f"{sel_rec} (kg/ha)")
    st.pyplot(fig_rec)

with tabs[8]: # RELATÓRIO
    st.header("📄 Relatório Final A4")
    st.write(f"**Produtor:** {st.session_state.prod} | **Área:** {st.session_state.area_ha:.2f} ha")
    st.table(df[['Rec_Calc']].describe().T) # Exibe Máx, Mín, Méd
