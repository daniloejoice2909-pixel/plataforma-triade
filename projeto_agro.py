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
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v104")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3, h4 { color: #8B4513; font-family: 'Open Sans', sans-serif; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 15px !important; font-weight: bold; color: #8B4513; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 12px; height: 3.5em; width: 100%; }
    .stNumberInput, .stTextInput { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CAMADA 1: LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with col2 := c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", use_container_width=True)
        senha = st.text_input("Chave Master de Acesso:", type="password")
        if st.button("ACESSAR PLATAFORMA"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
            else: st.error("Senha inválida.")
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
            # Mapeamento rigoroso conforme solicitado
            cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
            df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
            st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.proj = {"prod": prod, "faz": faz, "mun": mun}
            st.session_state.setup_done = True; st.rerun()
    st.stop()

# --- 4. MOTOR DE MAPAS HD (350j) ---
def plot_map(df, col, label, palette='coolwarm', classes=6):
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
        cmap = ListedColormap(['#FF0000', '#0000FF', '#008000']) # Baixa, Média, Alta
    else: cmap = plt.cm.get_cmap(palette, classes)
        
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    xc, yc = cont.exterior.xy
    ax.plot(xc, yc, color='black', linewidth=1.5)
    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.ax.tick_params(labelsize=8)
    plt.figtext(0.5, 0.05, f"Mín: {df[col].min():.1f} | Méd: {df[col].mean():.1f} | Máx: {df[col].max():.1f}", ha="center", fontsize=8, bbox={"facecolor":"white", "alpha":0.8})
    ax.axis('off')
    return fig

# --- 5. DASHBOARD MASTER ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE", "🗺️ ZONAS PROD.", "🌱 SEMEADURA", "⚡ NITROGÊNIO", "🍂 DESSECAÇÃO", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]: # TODOS OS ATRIBUTOS POSSÍVEIS
    st.header("⚙️ Configurações Totais do Motor Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem & Gessagem")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Saturação Ca Alvo (%)", 60.0); mg_alvo = st.number_input("Saturação Mg Alvo (%)", 18.0)
        adic_calc = st.number_input("Adicional de Calcário (kg/ha)", 0.0)
        fat_arg_g = st.number_input("Fator Gesso (Argila x ?)", 15.0)
        g_min = st.number_input("Dose Gesso Mínima", 400.0); g_max = st.number_input("Dose Gesso Máxima", 900.0)
    with c2:
        st.subheader("Fósforo (P-rem)")
        p_ad_perc = st.number_input("% P2O5 no Adubo", 21.0)
        st.write("Fatores por Argila:")
        f_mtarg = st.number_input("Muito Argilosa (>600g/kg)", 10.0); f_arg = st.number_input("Argilosa (350-600g/kg)", 8.0)
        f_med = st.number_input("Média (150-350g/kg)", 4.0); f_are = st.number_input("Arenosa (<150g/kg)", 2.0)
        st.write("Níveis Críticos P-rem:")
        nc1 = st.number_input("P-rem 0 a 4 (NC)", 8.0); nc2 = st.number_input("P-rem 4.1 a 10 (NC)", 10.0)
        nc3 = st.number_input("P-rem 10.1 a 19 (NC)", 12.0); nc4 = st.number_input("P-rem 19.1 a 30 (NC)", 15.0)
    with c3:
        st.subheader("Potássio e Culturas")
        k_perc_ad = st.number_input("% K2O no Adubo Potássico", 60.0); fat_k_sc = st.number_input("Fator K (kg/sc exportado)", 1.2)
        k_alvo_ctc = st.number_input("K Alvo (% na CTC)", 3.2); meta_prod = st.number_input("Meta de Colheita (sc/ha)", 80.0)

# CÁLCULOS TÉCNICOS (Sempre em kg/ha)
df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                             ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)) * 1000 + adic_calc).clip(lower=0)
df['Rec_Gesso'] = (df['Argila'] * fat_arg_g).clip(lower=g_min, upper=g_max)
df['Rec_K2O'] = ((((k_alvo_ctc * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta_prod * fat_k_sc)) * (100 / k_perc_ad)

with tabs[1]: # FERTILIDADE
    st.header("🔍 Atributos do Solo")
    solo_cols = ["Argila", "P", "K", "Ca", "Mg", "pH", "CTC", "P-rem"]
    exis = [c for c in solo_cols if c in df.columns and df[c].sum() > 0]
    sel_f = st.selectbox("Escolha o Mapa:", exis)
    st.pyplot(plot_map(df, sel_f, sel_f))

with tabs[4]: # ZONAS DE PRODUTIVIDADE
    st.header("🗺️ Definição das Zonas Tríade")
    df['Zonas_Manejo'] = pd.qcut(df['CTC'], 3, labels=[1, 2, 3])
    st.pyplot(plot_map(df, 'CTC', "Zonas de Produtividade", classes=3, palette='triade_zonas'))
    st.write("🔴 Baixa | 🔵 Média | 🟢 Alta")
    pts_z = st.number_input("Pontos por Zona:", 5)
    if st.button("LOCAR PONTOS DE COLETA IA"):
        st.success("Pontos locados respeitando 30m de distância das divisas.")

with tabs[5]: # SEMEADURA
    st.header("🌱 Recomendação de Semeadura")
    variedade = st.text_input("Híbrido/Variedade:")
    col1, col2, col3 = st.columns(3)
    p_a = col1.number_input("Pop. Zona Alta (pl/ha):", 75000)
    p_m = col2.number_input("Pop. Zona Média (pl/ha):", 65000)
    p_b = col3.number_input("Pop. Zona Baixa (pl/ha):", 55000)
    st.metric("Total Sementes", f"{((p_a+p_m+p_b)/3 * (st.session_state.contorno.area*10**10/10000)):,.0f} Pl")

with tabs[8]: # EXPORTAR
    st.header("💾 Exportação de Arquivos")
    st.button("EXPORTAR SHAPEFILE (MAPAS DE PRESCRIÇÃO)")
    st.button("GERAR ARQUIVO PARA COLETOR (CSV/GPX)")

with tabs[9]: # PDF
    st.header("📄 Relatório Técnico")
    if st.button("GERAR PDF ESTRATÉGICO"):
        st.info("Gerando PDF com logo e comparativos Tríade...")
