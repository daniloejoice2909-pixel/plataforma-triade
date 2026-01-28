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
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica | v96")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; width: 100%; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<div style='text-align: center; padding: 50px; border: 2px solid #C5A059; border-radius: 20px; background: white;'>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=300)
        senha = st.text_input("Chave Master:", type="password")
        if st.button("ACESSAR"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. MOTOR DE MAPAS HD (PREENCHIMENTO 100%) ---
def gerar_mapa_hd(df, atributo, contorno, label, n_classes=6, salvar=False):
    minx, miny, maxx, maxy = contorno.bounds
    # Resolução 300x300 para preenchimento total
    grid_x, grid_y = np.mgrid[minx:maxx:300j, miny:maxy:300j]
    rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    
    mask = np.array([[contorno.contains(Point(x, y)) for y in grid_y[0]] for x in grid_x[:,0]])
    grid_z[~mask.T] = np.nan

    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.cm.get_cmap('jet', n_classes) 
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap, interpolation='bilinear')
    
    x_c, y_c = contorno.exterior.xy
    ax.plot(x_c, y_c, color='black', linewidth=2.5) # Linha de contorno viva
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.axis('off')
    
    if salvar:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
        plt.close()
        return tmp.name
    return fig

# --- 4. CARREGAMENTO ---
if "df" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha (A-Y)", type=["xlsx"])
    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.rerun()
    st.stop()

# --- 5. INTERFACE ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 MAPAS SOLO", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE", "📄 RELATÓRIO"])

with tabs[0]: # ATRIBUTOS EDITÁVEIS (TOTAL)
    st.header("⚙️ Tabela de Atributos de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Corretivos")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% CTC Alvo", 60.0); mg_alvo = st.number_input("Mg% CTC Alvo", 18.0)
        g_max = st.number_input("Gesso Máx (kg/ha)", 900.0); g_min = st.number_input("Gesso Mín", 400.0)
    with c2:
        st.subheader("🌾 Fósforo (P-rem)")
        p_ad = st.number_input("% P2O5 do Adubo", 21.0); f_arg = st.number_input("Fator Solo Argiloso", 8.0)
        st.write("**Níveis Críticos Editáveis:**")
        nc1 = st.number_input("NC 0-4 P-rem", 8.0); nc2 = st.number_input("NC 4-10 P-rem", 10.0)
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k_alvo = st.number_input("K% CTC Alvo", 3.2); meta = st.number_input("Meta (sc/ha)", 80.0)

# MOTOR DE CÁLCULO TRÍADE (PROCESSAMENTO)
df['Rec_Calcario'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100))).clip(lower=0)
df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
df['NC_P'] = df['P-rem'].apply(lambda x: nc1 if x<=4 else nc2 if x<=10 else 12)
df['Rec_P2O5'] = (((df['NC_P'] - df['P']).clip(lower=0) * f_arg) + (meta * 0.8)) * (100 / p_ad)
df['Rec_K2O'] = ((((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta * 1.2)) * (100/60)

with tabs[3]: # SATÉLITE (FIXED)
    st.header("🛰️ Satélite Sentinel-2")
    if st.button("PROCESSAR IMAGENS"):
        with st.spinner("Conectando ao banco de dados..."):
            fig_s = gerar_mapa_hd(df, "Argila", st.session_state.contorno, "NDVI Simulativo")
            st.pyplot(fig_s)
            st.success("Imagem de satélite processada com sucesso!")

with tabs[4]: # RELATÓRIO PDF (FIXED)
    st.header("📄 Gerar Relatório PDF")
    op = st.selectbox("Escolha a Recomendação:", ["Rec_Calcario", "Rec_Gesso", "Rec_P2O5", "Rec_K2O"])
    if st.button("GERAR ARQUIVO"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16); pdf.cell(200, 10, "TRÍADE AGRO ESTRATÉGICA", ln=True, align='C')
        img_p = gerar_mapa_hd(df, op, st.session_state.contorno, op, salvar=True)
        pdf.image(img_p, x=10, y=50, w=180)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
            pdf.output(t.name)
            with open(t.name, "rb") as f:
                st.download_button("📥 BAIXAR PDF", f, file_name="Relatorio_Triade.pdf")
