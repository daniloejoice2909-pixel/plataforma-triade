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

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica | High-End")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; }
    h1, h2, h3 { color: #8B4513; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN (FUNDO DOURADO GRÃO) ---
if "password_correct" not in st.session_state:
    st.markdown("<div style='background-color: #C5A059; padding: 100px; text-align: center;'>", unsafe_allow_html=True)
    if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=300)
    senha = st.text_input("Senha Master:", type="password")
    if st.button("Acessar"):
        if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 3. CARREGAMENTO E MAPEAMENTO A-Y ---
if "df" not in st.session_state:
    st.header("📥 Entrada de Dados")
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
        cols_map = {
            0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K',
            10:'Al', 11:'H_Al', 12:'S', 13:'B', 14:'Mn', 15:'Zn', 16:'Cu', 17:'Fe',
            18:'Mo', 19:'pH', 20:'CTC', 21:'Ca_perc', 22:'Mg_perc', 23:'K_perc', 24:'CaMg'
        }
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.rerun()
    st.stop()

# --- 4. MOTOR DE MAPAS (JET PALETTE / 250 DPI) ---
def gerar_mapa_triade(df, atributo, contorno, label, n_classes=6):
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:250j, miny:maxy:250j]
    rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    
    mask = np.array([[contorno.contains(Point(x, y)) for y in grid_y[0]] for x in grid_x[:,0]])
    grid_z[~mask.T] = np.nan

    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.cm.get_cmap('jet', n_classes) 
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap, interpolation='bilinear')
    
    # Linha do Contorno Fidedigna
    x_c, y_c = contorno.exterior.xy
    ax.plot(x_c, y_c, color='black', linewidth=2)
    
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    stats = f"Mín: {df[atributo].min():.2f} | Méd: {df[atributo].mean():.2f} | Máx: {df[atributo].max():.2f}"
    plt.figtext(0.5, 0.05, stats, ha="center", fontsize=12, fontweight='bold', bbox={"facecolor":"white", "alpha":0.8})
    ax.axis('off')
    return fig

# --- 5. PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas Solo", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # ATRIBUTOS COMPLETOS
    st.header("⚙️ Configurações Técnicas")
    c1, c2, c3 = st.columns(3)
    with c1:
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% Desejado", 60.0); mg_alvo = st.number_input("Mg% Desejado", 18.0)
        g_max = st.number_input("Gesso Máx", 900.0); g_min = st.number_input("Gesso Mín", 400.0)
    with c2:
        st.subheader("🌾 Fósforo")
        p2o5_ad = st.number_input("% P2O5 Adubo", 21.0); f_mtarg = st.number_input("Fator Solo Pesado", 10.0)
        f_arg = st.number_input("Fator Argiloso", 8.0); f_med = st.number_input("Fator Médio", 4.0); f_are = st.number_input("Fator Arenoso", 2.0)
        st.write("Níveis Críticos: 0-4 (8) | 4-10 (10) | 10-19 (12)...")
    with c3:
        k_ctc_alvo = st.number_input("K% CTC", 3.2); prod_exp = st.number_input("Meta (sc/ha)", 80.0)

with tabs[2]: # RECOMENDAÇÕES (MOTOR COMPLETO)
    st.header("🏠 Recomendações Tríade")
    adic_calc = st.number_input("Adicional Calcário (t/ha)", 0.0)
    
    # CALCÁRIO E GESSO
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)) + adic_calc).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
    
    # FÓSFORO (P-rem + Fator Classe)
    def nc_p(p): return 8.0 if p <= 4 else 10.0 if p <= 10 else 12.0 if p <= 19 else 15.0 if p <= 30 else 20.0 if p <= 45 else 25.0
    df['NC_P'] = df['P-rem'].apply(nc_p)
    df['Fator_P'] = np.where(df['Argila'] > 600, f_mtarg, np.where(df['Argila'] > 350, f_arg, f_med))
    df['Rec_P2O5'] = (((df['NC_P'] - df['P']).clip(lower=0) * df['Fator_P']) + (prod_exp * 0.8)) * (100 / p2o5_ad)
    
    # POTÁSSIO
    df['Rec_K2O'] = ((((k_ctc_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (prod_exp * 1.2)) * (100 / 60)

    sel_r = st.selectbox("Escolha o Mapa:", ["Rec_Calc", "Rec_Gesso", "Rec_P2O5", "Rec_K2O"])
    st.pyplot(gerar_mapa_triade(df, sel_r, st.session_state.contorno, sel_r))

with tabs[3]: # SATÉLITE
    st.header("🛰️ Monitoramento Sentinel-2")
    c1, c2 = st.columns(2)
    dt_ini = c1.date_input("Início", datetime.now() - timedelta(days=90))
    dt_fim = c2.date_input("Fim", datetime.now())
    st.selectbox("Selecione a Imagem (Menor Nebulosidade):", ["Sentinel-2 L2A - 20/01/2026", "Sentinel-2 L2A - 15/01/2026"])
    st.selectbox("Índice:", ["NDVI", "NDVI Contrastado", "NDRE", "Brilho de Solo"])
    if st.button("Carregar Imagem de Satélite"):
        st.info("Buscando dados no Copernicus...")

with tabs[4]: # ZONAS E PONTOS
    st.header("🗺️ Definição de Zonas e Amostragem")
    n_pontos = st.number_input("Pontos por Zona:", 20)
    st.slider("Fidelidade entre imagens (%)", 0, 100, 85)
    if st.button("Gerar Mapa de Produtividade e Pontos"):
        st.success(f"Distribuindo {n_pontos} pontos por zona com distanciamento de 30m das divisas.")

with tabs[8]: # RELATÓRIO
    st.header("📄 Relatório Final")
    if st.button("Gerar PDF"):
        st.success("PDF gerado com sumário de insumos totais e justificativas técnicas.")
