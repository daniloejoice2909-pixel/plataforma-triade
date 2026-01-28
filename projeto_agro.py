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

# --- 1. CONFIGURAÇÃO VISUAL ---
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
        if os.path.exists(logo): st.image(logo, width=250)
        st.markdown("<h2 style='text-align: center;'>Acesso Master</h2>", unsafe_allow_html=True)
        senha = st.text_input("Senha:", type="password")
        if st.button("Entrar"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. FUNÇÃO MAPA (AZUL -> VERMELHO) ---
def gerar_mapa_triade(df, atributo, contorno, label, salvar=False):
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:200j, miny:maxy:200j]
    rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    
    for i in range(len(grid_x)):
        for j in range(len(grid_y)):
            if not contorno.contains(Point(grid_x[i,j], grid_y[i,j])):
                grid_z[i,j] = np.nan

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap='coolwarm')
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title(f"Mapa: {label}", fontsize=14, fontweight='bold')
    ax.axis('off')
    
    if salvar:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
        plt.close()
        return tmp.name
    return fig

# --- 4. CARREGAMENTO ---
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

# --- 5. INTERFACE ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # ATRIBUTOS
    st.header("⚙️ Parâmetros Técnicos")
    c1, c2, c3 = st.columns(3)
    with c1:
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% Desejado (CTC)", 60.0); mg_alvo = st.number_input("Mg% Desejado (CTC)", 18.0)
    with c2:
        p2o5_ad = st.number_input("% P2O5 do Adubo", 21.0)
        st.write("Níveis Críticos (P-rem): 0-4: 8 | 4-10: 10 | 10-19: 12...")
    with c3:
        k_alvo = st.number_input("K% Desejado (CTC)", 3.2); meta_prod = st.number_input("Meta (sc/ha)", 80.0)

with tabs[2]: # RECOMENDAÇÕES
    st.header("🏠 Recomendações")
    adic_calc = st.number_input("Adicional de Calcário (t/ha)", 0.0)
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)) + adic_calc).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=400, upper=900)
    df['Rec_K2O'] = (((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta_prod * 1.2)
    st.pyplot(gerar_mapa_triade(df, "Rec_Calc", st.session_state.contorno, "Calcário (t/ha)"))

with tabs[8]: # RELATÓRIO PDF
    st.header("📄 Gerar Relatório PDF Final")
    if st.button("Exportar PDF Premium"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "Relatório Tríade Agro Estratégica", ln=True, align='C')
        pdf.set_font("Arial", '', 12)
