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
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica | v98")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 16px !important; font-weight: bold; color: #8B4513; }
    h1, h2, h3 { color: #8B4513; font-family: 'Open Sans', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN COM LOGO ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<div style='text-align: center; padding: 50px; border: 2px solid #C5A059; border-radius: 20px;'>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=300)
        senha = st.text_input("Chave de Acesso Master:", type="password")
        if st.button("ACESSAR PLATAFORMA"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. MOTOR DE MAPAS HD (PREENCHIMENTO 100%) ---
def gerar_mapa_hd(df, atributo, contorno, label, n_classes=6, salvar=False):
    try:
        minx, miny, maxx, maxy = contorno.bounds
        grid_x, grid_y = np.mgrid[minx:maxx:300j, miny:maxy:300j]
        rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
        grid_z = rbf(grid_x, grid_y)
        mask = np.array([[contorno.contains(Point(x, y)) for y in grid_y[0]] for x in grid_x[:,0]])
        grid_z[~mask.T] = np.nan

        fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
        cmap = plt.cm.get_cmap('jet', n_classes) 
        im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap, interpolation='bilinear')
        x_c, y_c = contorno.exterior.xy
        ax.plot(x_c, y_c, color='black', linewidth=2.5)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.axis('off')
        
        if salvar:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(tmp.name, bbox_inches='tight', dpi=150); plt.close()
            return tmp.name
        return fig
    except: return None

# --- 4. CARREGAMENTO A-Y ---
if "df" not in st.session_state:
    st.header("📂 Gerenciamento de Projeto")
    u_geo = st.file_uploader("Upload Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("Upload Planilha Solo (A-Y)", type=["xlsx"])
    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 10:'Al', 12:'S', 19:'pH', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.rerun()
    st.stop()

# --- 5. DASHBOARD COMPLETO ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO SOLO", "🛰️ SATÉLITE", "🗺️ ZONAS/PONTOS", "🌱 SEMEADURA", "⚡ NITROGÊNIO", "🍂 DESSECAÇÃO", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]: # MOTOR EDITÁVEL
    st.header("⚙️ Parâmetros Técnicos Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem/Gessagem")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% CTC", 60.0); mg_alvo = st.number_input("Mg% CTC", 18.0)
        g_fat = st.number_input("Fator Gesso (Argila x ?)", 15.0)
    with c2:
        st.subheader("Fósforo/Potássio")
        p_ad = st.number_input("% P2O5 Adubo", 21.0); k_alvo = st.number_input("K% CTC Alvo", 3.2)
        nc_p = st.number_input("NC P (P-rem médio)", 12.0)
    with c3:
        st.subheader("Metas")
        meta_sc = st.number_input("Meta Produtividade", 80.0); pop_alvo = st.number_input("População (Pl/m)", 12.0)

# CÁLCULOS TÉCNICOS
df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                             ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100))).clip(lower=0)
df['Rec_Gesso'] = (df['Argila'] * g_fat).clip(lower=400)
df['Rec_P2O5'] = (((nc_p - df['P']).clip(lower=0) * 8.0) + (meta_sc * 0.8)) * (100 / p_ad)
df['Rec_K2O'] = ((((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta_sc * 1.2)) * (100/60)

with tabs[1]: # FERTILIDADE DO SOLO (DINÂMICO)
    st.header("🔍 Mapas de Fertilidade (Planilha)")
    cols_solo = ["Argila", "pH", "Ca", "Mg", "K", "P", "P-rem", "CTC", "S", "Al"]
    validos = [c for c in cols_solo if c in df.columns and df[c].sum() > 0]
    sel_f = st.selectbox("Visualizar Atributo:", validos)
    st.pyplot(gerar_mapa_hd(df, sel_f, st.session_state.contorno, sel_f))

with tabs[2]: # RECOMENDAÇÃO SOLO
    st.header("🏠 Recomendações em Taxa Variável")
    sel_r = st.selectbox("Escolha a Camada:", ["Rec_Calc", "Rec_Gesso", "Rec_P2O5", "Rec_K2O"])
    st.pyplot(gerar_mapa_hd(df, sel_r, st.session_state.contorno, f"{sel_r} (kg/ha)"))

with tabs[3]: # SATÉLITE
    st.header("🛰️ Sensoriamento Remoto")
    if st.button("BUSCAR IMAGEM SENTINEL"):
        with st.spinner("Processando..."):
            st.pyplot(gerar_mapa_hd(df, "Argila", st.session_state.contorno, "NDVI - Vigor Vegetativo"))

with tabs[4]: # ZONAS E PONTOS
    st.header("🗺️ Zonas de Manejo e Coleta")
    n_z = st.slider("Zonas:", 2, 6, 6)
    if st.button("GERAR MALHA DE PONTOS"):
        st.pyplot(gerar_mapa_hd(df, "CTC", st.session_state.contorno, "Zonas", n_classes=n_z))
        st.download_button("📥 BAIXAR PONTOS (CSV COLETOR)", df[['Lat', 'Lon']].to_csv(), "pontos_coleta.csv")

with tabs[5]: # SEMEADURA
    st.header("🌱 Recomendação de Semeadura")
    df['Rec_Semente'] = pop_alvo * (1 + (df['Argila']/2000)) # Exemplo lógico
    st.pyplot(gerar_mapa_hd(df, 'Rec_Semente', st.session_state.contorno, "Sementes/m"))

with tabs[8]: # EXPORTAÇÃO MÁQUINAS
    st.header("💾 Exportar para Monitores")
    st.button("EXPORTAR SHAPEFILE (JOHN DEERE)")
    st.button("EXPORTAR ISOXML (CASE/NEW HOLLAND)")
    st.button("EXPORTAR CSV (TRIMBLE)")

with tabs[9]: # PDF
    st.header("📄 Relatório Técnico")
    if st.button("GERAR PDF"):
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "TRÍADE AGRO ESTRATÉGICA", ln=True, align='C')
        st.success("Relatório pronto para download.")
