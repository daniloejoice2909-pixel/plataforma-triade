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

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 18px !important; } 
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; }
    h1, h2, h3 { color: #8B4513; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN ---
if "password_correct" not in st.session_state:
    st.markdown("<div style='background-color: #C5A059; padding: 100px; text-align: center; border-radius: 10px;'>", unsafe_allow_html=True)
    if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=300)
    senha = st.text_input("Acesso Master:", type="password")
    if st.button("Entrar"):
        if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 3. CARREGAMENTO A-Y ---
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
        cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Projeto Carregado!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. MOTOR DE MAPAS (AZUL -> VERMELHO COM CAMADAS DEFINIDAS) ---
def gerar_mapa_triade(df, atributo, contorno, label, n_classes=6, salvar=False):
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:200j, miny:maxy:200j]
    rbf = Rbf(df.Lon + np.random.normal(0,1e-10,len(df)), 
              df.Lat + np.random.normal(0,1e-10,len(df)), 
              df[atributo], function='linear')
    grid_z = rbf(grid_x, grid_y)
    
    for i in range(len(grid_x)):
        for j in range(len(grid_y)):
            if not contorno.contains(Point(grid_x[i,j], grid_y[i,j])): grid_z[i,j] = np.nan

    fig, ax = plt.subplots(figsize=(10, 8))
    # Paleta JET (Azul-Verde-Amarelo-Vermelho) com níveis definidos
    cmap = plt.cm.get_cmap('jet', n_classes) 
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    
    # Desenhar a linha do contorno
    x, y = contorno.exterior.xy
    ax.plot(x, y, color='black', linewidth=2)
    
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    txt = f"Mín: {df[atributo].min():.1f} | Méd: {df[atributo].mean():.1f} | Máx: {df[atributo].max():.1f}"
    plt.figtext(0.5, 0.05, txt, horizontalalignment='center', fontsize=12, fontweight='bold')
    ax.axis('off')
    
    if salvar:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
        plt.close()
        return tmp.name
    return fig

# --- 5. PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # ATRIBUTOS COMPLETOS
    st.header("⚙️ Configurações da Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Corretivos")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% CTC Alvo", 60.0); mg_alvo = st.number_input("Mg% CTC Alvo", 18.0)
        g_max = st.number_input("Gesso Máx (kg/ha)", 900.0); g_min = st.number_input("Gesso Mín", 400.0)
    with c2:
        st.subheader("🌾 Fósforo")
        p2o5_ad = st.number_input("% P2O5 Adubo", 21.0); f_arg = st.number_input("Fator Solo Argiloso", 8.0)
        st.write("Níveis Críticos: 0-4 (8) | 4-10 (10) | 10-19 (12)...")
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k_ctc_alvo = st.number_input("K% CTC Alvo", 3.2); prod_exp = st.number_input("Meta sc/ha", 80.0)

with tabs[2]: # RECOMENDAÇÕES
    st.header("🏠 Motor de Fórmulas Tríade")
    adic_calc = st.number_input("Adicional Calcário (t/ha)", 0.0)
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)) + adic_calc).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
    
    sel_rec = st.selectbox("Selecione o Mapa:", ["Rec_Calc", "Rec_Gesso"])
    st.pyplot(gerar_mapa_triade(df, sel_rec, st.session_state.contorno, sel_rec))

with tabs[8]: # RELATÓRIO PDF INTEGRADO
    st.header("📄 Relatório Final A4")
    if st.button("Gerar Relatório Completo"):
        pdf = FPDF(); pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "Relatório Técnico - Tríade Agro Estratégica", ln=True, align='C')
        
        path_map = gerar_mapa_triade(df, "Rec_Calc", st.session_state.contorno, "Recomendação Calcário", salvar=True)
        pdf.image(path_map, x=10, y=40, w=180)
        
        # Sumário de Insumos
        pdf.set_y(190); pdf.set_font("Arial", 'B', 12)
        total_calc = (df['Rec_Calc'].mean() * st.session_state.area_ha)
        pdf.cell(200, 10, f"SUMÁRIO: Total Calcário: {total_calc:.2f} Toneladas", ln=True)
        
        pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(pdf_file.name)
        with open(pdf_file.name, "rb") as f:
            st.download_button("Clique aqui para Baixar o PDF", f, "Relatorio_Final_Triade.pdf")
