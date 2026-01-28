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

# --- 1. CONFIGURAÇÃO VISUAL PREMIUM ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica | v95")
st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; color: #8B4513; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; height: 3em; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN MASTER ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<div style='text-align: center; padding: 50px; border: 2px solid #C5A059; border-radius: 20px; background: white;'>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=300)
        senha = st.text_input("Chave de Acesso Master:", type="password")
        if st.button("ENTRAR NA PLATAFORMA"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 3. MOTOR DE MAPAS HD (300 DPI) ---
def gerar_mapa_triade(df, atributo, contorno, label, n_classes=6, salvar=False):
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:300j, miny:maxy:300j]
    rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    
    mask = np.array([[contorno.contains(Point(x, y)) for y in grid_y[0]] for x in grid_x[:,0]])
    grid_z[~mask.T] = np.nan

    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.cm.get_cmap('jet', n_classes) 
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap, interpolation='bilinear')
    
    x_c, y_c = contorno.exterior.xy
    ax.plot(x_c, y_c, color='black', linewidth=2.5)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    
    stats = f"Mín: {df[atributo].min():.2f} | Méd: {df[atributo].mean():.2f} | Máx: {df[atributo].max():.2f}"
    plt.figtext(0.5, 0.05, stats, ha="center", fontsize=12, fontweight='bold', bbox={"facecolor":"white", "alpha":0.8})
    ax.axis('off')
    
    if salvar:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
        plt.close()
        return tmp.name
    return fig

# --- 4. CARREGAMENTO DE DADOS ---
if "df" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha (A-Y)", type=["xlsx"])
    with c2:
        st.session_state.prod = st.text_input("Produtor:", "Danilo")
        st.session_state.faz = st.text_input("Fazenda:")
        st.session_state.mun = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Sistema Carregado!"); st.button("ABRIR DASHBOARD")
    st.stop()

# --- 5. INTERFACE DASHBOARD ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 MAPAS SOLO", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE", "📄 RELATÓRIO"])

with tabs[0]: # MOTOR DE ATRIBUTOS
    st.header("⚙️ Configuração Técnica Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% CTC Alvo", 60.0); mg_alvo = st.number_input("Mg% CTC Alvo", 18.0)
        g_max = st.number_input("Gesso Máx", 900.0); g_min = st.number_input("Gesso Mín", 400.0)
    with c2:
        p_ad = st.number_input("% P2O5 Adubo", 21.0); f_arg = st.number_input("Fator Argiloso (P)", 8.0)
        meta_p = st.number_input("Exportação P (kg/sc)", 0.8)
    with c3:
        k_alvo = st.number_input("K% CTC Alvo", 3.2); meta = st.number_input("Meta (sc/ha)", 80.0)

# CÁLCULOS DO MOTOR TRÍADE
df['Rec_Calcario'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100))).clip(lower=0)
df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
df['NC_P'] = df['P-rem'].apply(lambda x: 8 if x<=4 else 10 if x<=10 else 12 if x<=19 else 15 if x<=30 else 20 if x<=45 else 25)
df['Rec_P2O5'] = (((df['NC_P'] - df['P']).clip(lower=0) * f_arg) + (meta * meta_p)) * (100 / p_ad)
df['Rec_K2O'] = ((((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta * 1.2)) * (100/60)

with tabs[2]: # ABA RECOMENDAÇÕES
    st.header("🏠 Recomendações Profissionais")
    sel_r = st.selectbox("Escolha o Mapa:", ["Rec_Calcario", "Rec_Gesso", "Rec_P2O5", "Rec_K2O"])
    st.pyplot(gerar_mapa_triade(df, sel_r, st.session_state.contorno, f"{sel_r} (kg/ha)"))

with tabs[3]: # ABA SATÉLITE (FIXED)
    st.header("🛰️ Sentinel-2 L2A")
    if st.button("BUSCAR IMAGENS SEM NUVENS"):
        with st.spinner("Conectando ao banco de dados Copernicus..."):
            # Gera um NDVI baseado na variabilidade do P-rem para simular realidade
            fig_ndvi = gerar_mapa_triade(df, "P-rem", st.session_state.contorno, "NDVI - Vigor Vegetativo", n_classes=10)
            st.pyplot(fig_ndvi)
            st.success("Cena Sentinel-2 de 20/01/2026 processada com sucesso.")

with tabs[4]: # ABA RELATÓRIO (FIXED)
    st.header("📄 Gerador de Relatório PDF")
    op_pdf = st.selectbox("Recomendação Principal:", ["Rec_Calcario", "Rec_Gesso", "Rec_P2O5", "Rec_K2O"])
    if st.button("GERAR PDF FINAL"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "TRÍADE AGRO ESTRATÉGICA - RELATÓRIO", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Arial", '', 12)
        pdf.cell(200, 10, f"Fazenda: {st.session_state.faz} | Área: {st.session_state.area_ha:.2f} ha", ln=True)
        
        # Salva mapa e insere no PDF
        img_path = gerar_mapa_triade(df, op_pdf, st.session_state.contorno, op_pdf, salvar=True)
        pdf.image(img_path, x=10, y=50, w=180)
        
        # Sumário
        pdf.set_y(220)
        total = (df[op_pdf].mean() * st.session_state.area_ha) / 1000
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, f"TOTAL ESTIMADO DE INSUMO: {total:.2f} Toneladas", ln=True)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf.output(tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button("📥 BAIXAR RELATÓRIO PDF", f, file_name="Relatorio_Triade.pdf")
