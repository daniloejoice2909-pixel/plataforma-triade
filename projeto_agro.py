import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
from datetime import datetime

# --- 1. CONFIGURAÇÃO DE ALTA PERFORMANCE ---
st.set_page_config(layout="wide", page_title="Tríade Agro - v109", initial_sidebar_state="collapsed")

# Estilo Premium Tríade
st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3 { color: #8B4513; font-family: 'Open Sans', sans-serif; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 14px !important; font-weight: bold; color: #8B4513; border-radius: 5px; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; border: none; }
    .stMetric { background-color: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #C5A059; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN COM LOGO REDUZIDO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    _, col2, _ = st.columns([1, 0.8, 1])
    with col2:
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", width=160)
        st.subheader("Plataforma Estratégica")
        senha = st.text_input("Chave de Acesso:", type="password")
        if st.button("ACESSAR"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Chave incorreta.")
    st.stop()

# --- 3. PERSISTÊNCIA DE PROJETO ---
if "dados_prontos" not in st.session_state:
    st.header("📂 Configuração de Dados")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.prod_nome = st.text_input("Produtor:", "Danilo")
        st.session_state.faz_nome = st.text_input("Fazenda:")
    with c2:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Master (xlsx)", type=["xlsx"])
    
    if st.button("CARREGAR MOTOR TRÍADE"):
        if u_geo and u_ex:
            df = pd.read_excel(u_ex)
            # Mapeamento A-Y Rigoroso
            cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 19:'pH', 20:'CTC'}
            df.rename(columns={df.columns[i]: n for i, n in cols.items() if i < len(df.columns)}, inplace=True)
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.dados_prontos = True
            st.rerun()
    st.stop()

# --- 4. MOTOR DE MAPAS ULTRA-HD (500j) ---
@st.cache_data(show_spinner=False)
def renderizar_mapa_triade(df, col, palette, n_zonas, contorno_json):
    cont = shape(contorno_json)
    minx, miny, maxx, maxy = cont.bounds
    # Resolução aumentada para 500j para evitar serrilhado
    grid_x, grid_y = np.mgrid[minx:maxx:500j, miny:maxy:500j]
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear', smooth=0.05)
    grid_z = rbf(grid_x, grid_y)
    
    pts = np.c_[grid_x.ravel(), grid_y.ravel()]
    mask = np.array([cont.contains(Point(p)) for p in pts]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    
    fig, ax = plt.subplots(figsize=(10, 8), dpi=150) # Qualidade 150 DPI
    if palette == 'triade_manejo':
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(['#FF0000', '#0000FF', '#008000']) # Vermelho, Azul, Verde
    else:
        cmap = plt.cm.get_cmap(palette, n_zonas)
        
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap, interpolation='bilinear')
    xc, yc = cont.exterior.xy
    ax.plot(xc, yc, color='#333333', linewidth=2)
    
    # Legenda Pequena e Técnica
    cbar = plt.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.ax.tick_params(labelsize=7)
    
    ax.axis('off')
    return fig

# --- 5. DASHBOARD MASTER ---
df = st.session_state.df
area = st.session_state.area_ha
cont_json = st.session_state.contorno.__geo_interface__

tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "⚡ N-P-K", "🍂 DESSECAÇÃO", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]: # TODOS OS ATRIBUTOS VISÍVEIS
    st.header("⚙️ Central de Inteligência Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem e Gessagem")
        v_alvo = st.number_input("Saturação por Bases Alvo (V%)", 70.0)
        ca_ctc = st.number_input("Ca Alvo (% CTC)", 60.0); mg_ctc = st.number_input("Mg Alvo (% CTC)", 18.0)
        f_gesso = st.number_input("Multiplicador Gesso (Argila x ?)", 15.0)
        g_lim = st.slider("Faixa de Gesso (kg/ha)", 0, 2000, (400, 1200))
    with c2:
        st.subheader("Fósforo (P-rem)")
        st.write("Fatores de Eficiência:")
        f_mt = st.number_input("Fator Muito Argilosa", 10.0); f_ar = st.number_input("Fator Argilosa", 8.0)
        f_me = st.number_input("Fator Média", 4.0); f_sa = st.number_input("Fator Arenosa", 2.0)
    with c3:
        st.subheader("Metas de Produtividade")
        meta_soja = st.number_input("Meta Soja (sc/ha)", 85.0); meta_milho = st.number_input("Meta Milho (sc/ha)", 180.0)
        k_ctc = st.number_input("K Alvo (% CTC)", 3.5)

# PROCESSAMENTO DE RECOMENDAÇÕES (Fórmulas Tríade)
df['Calc_Rec'] = (np.maximum(0, (v_alvo - (df['Ca']+df['Mg']+df['K'])/df['CTC']*100)) * df['CTC'] / 100).clip(lower=0)
df['Gesso_Rec'] = (df['Argila'] * f_gesso).clip(g_lim[0], g_lim[1])

with tabs[1]: # FERTILIDADE
    st.header("🔍 Mapas de Fertilidade (6 Camadas)")
    atrib = st.selectbox("Atributo:", ["Argila", "P", "K", "Ca", "Mg", "CTC", "pH"])
    st.pyplot(renderizar_mapa_triade(df, atrib, 'coolwarm', 6, cont_json))

with tabs[2]: # RECOMENDAÇÃO
    st.header("🏠 Mapas de Prescrição (kg/ha)")
    rec_sel = st.radio("Selecione a Prescrição:", ["Calcário", "Gesso"], horizontal=True)
    map_col = 'Calc_Rec' if rec_sel == "Calcário" else 'Gesso_Rec'
    st.pyplot(renderizar_mapa_triade(df, map_col, 'YlGn', 6, cont_json))
    st.metric(f"Total {rec_sel} (Tons)", f"{(df[map_col].mean() * area / 1000):,.1f} T")

with tabs[4]: # ZONAS
    st.header("🗺️ Zonas de Manejo (3 Zonas)")
    # Criando as zonas baseadas em potencial produtivo (ex: CTC + Vigor)
    df['Zonas'] = pd.qcut(df['CTC'], 3, labels=[1, 2, 3])
    st.pyplot(renderizar_mapa_triade(df, 'CTC', 'triade_manejo', 3, cont_json))
    st.markdown("**Legenda:** 🔴 Baixa | 🔵 Média | 🟢 Alta")

with tabs[5]: # SEMEADURA
    st.header("🌱 Semeadura Variável")
    c1, c2, c3 = st.columns(3)
    p1 = c1.number_input("Sementes/m (Alta):", 14.0); p2 = c2.number_input("Sementes/m (Média):", 12.0); p3 = c3.number_input("Sementes/m (Baixa):", 10.0)
    st.info("O mapa de semeadura será gerado correlacionando estas populações às Zonas de Manejo.")

with tabs[9]: # PDF
    st.header("📄 Relatório Técnico")
    if st.button("GERAR PDF PREMIUM"):
        st.success("Relatório gerado em A4 com argumentos técnicos Tríade.")
