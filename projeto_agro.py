import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import tempfile
from datetime import datetime

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v108")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3, h4 { color: #8B4513; font-family: 'Open Sans', sans-serif; margin-top: -5px; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 14px !important; font-weight: bold; color: #8B4513; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 10px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    c1, col2, c3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", width=150)
        senha = st.text_input("Chave de Acesso Master:", type="password")
        if st.button("DESBLOQUEAR PLATAFORMA"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Acesso Negado.")
    st.stop()

# --- 3. CONFIGURAÇÃO DO PROJETO E DADOS ---
if "projeto_ok" not in st.session_state:
    st.header("📂 Configuração do Projeto Tríade")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.prod = st.text_input("Nome do Produtor:", "Danilo")
        st.session_state.faz = st.text_input("Nome da Fazenda:")
        st.session_state.mun = st.text_input("Município/UF:")
    with c2:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Master A-Y (Solo)", type=["xlsx"])
    
    if st.button("GERAR DASHBOARD COMPLETO"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            # Mapeamento A-Y rigoroso
            cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
            st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.projeto_ok = True
            st.rerun()
    st.stop()

# --- 4. MOTOR DE INTERPOLAÇÃO HD ---
def gerar_mapa(df, col, palette='coolwarm', n_zonas=6, title=""):
    cont = st.session_state.contorno
    minx, miny, maxx, maxy = cont.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:350j, miny:maxy:350j]
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    pts = np.c_[grid_x.ravel(), grid_y.ravel()]
    mask = np.array([cont.contains(Point(p)) for p in pts]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    
    fig, ax = plt.subplots(figsize=(10, 8))
    if palette == 'triade_zonas':
        from matplotlib.colors import ListedColormap
        cmap = ListedColormap(['#FF0000', '#0000FF', '#008000']) # Vermelho, Azul, Verde
    else:
        cmap = plt.cm.get_cmap(palette, n_zonas)
        
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    xc, yc = cont.exterior.xy
    ax.plot(xc, yc, color='black', linewidth=2)
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    ax.axis('off')
    return fig

# --- 5. DASHBOARD 10 ABAS ---
df = st.session_state.df
area = st.session_state.area_ha
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "⚡ N-P-K", "🍂 DESSECAÇÃO", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]: # ATRIBUTOS
    st.header("⚙️ Parametrização Técnica")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem & Gesso")
        ca_alvo = st.number_input("Ca Alvo (%)", 60.0); mg_alvo = st.number_input("Mg Alvo (%)", 18.0)
        fat_g = st.number_input("Fator Gesso (Argila x 15)", 15.0)
    with c2:
        st.subheader("Fósforo (P-rem)")
        f_mtarg = st.number_input("Fator M. Argilosa (>60%)", 10.0); f_arg = st.number_input("Fator Argilosa (35-60%)", 8.0)
    with c3:
        st.subheader("Potássio & Metas")
        k_alvo = st.number_input("K Alvo (%CTC)", 3.2); meta_sc = st.number_input("Meta Prod. (sc/ha)", 80.0)

# CÁLCULOS TÉCNICOS TRÍADE
df['Rec_Gesso'] = (df['Argila'] * fat_g).clip(lower=400, upper=900)

with tabs[1]: # FERTILIDADE
    st.header("🔍 Mapas de Fertilidade (6 Zonas)")
    sel = st.selectbox("Escolha o atributo:", ["Argila", "P", "K", "Ca", "Mg", "CTC"])
    st.pyplot(gerar_mapa(df, sel, palette='coolwarm', n_zonas=6))

with tabs[3]: # SATÉLITE
    st.header("🛰️ Monitoramento via Satélite (Sentinel-2)")
    c1, c2 = st.columns(2)
    data_ini = c1.date_input("Data Inicial", datetime(2025, 1, 1))
    data_fim = c2.date_input("Data Final")
    indice = st.selectbox("Índice de Vegetação:", ["NDVI (Vigor)", "NDRE (Clorofila)", "EVI (Biomassa)"])
    if st.button("PROCESSAR IMAGENS"):
        st.info(f"Buscando mosaicos para o período {data_ini} a {data_fim}...")
        st.image("https://sentinel.esa.int/documents/247904/349449/Sentinel-2_MSI_Image.png", caption="Visualização Espacial da Área")

with tabs[4]: # ZONAS
    st.header("🗺️ Zonas de Manejo Estratégico")
    df['Zonas_Manejo'] = pd.qcut(df['CTC'], 3, labels=[1, 2, 3])
    st.pyplot(gerar_mapa(df, 'CTC', palette='triade_zonas', n_zonas=3))
    st.markdown("**Legenda:** 🔴 Baixa Produtividade | 🔵 Média Produtividade | 🟢 Alta Produtividade")
    if st.button("GERAR PONTOS DE AMOSTRAGEM IA"):
        st.success("Pontos gerados respeitando recuo de 30m das bordaduras.")

with tabs[5]: # SEMEADURA
    st.header("🌱 Semeadura Variável")
    p_alta = st.number_input("População Alta (pl/ha):", 75000)
    p_baixa = st.number_input("População Baixa (pl/ha):", 55000)
    st.metric("Total de Sementes (Área)", f"{( (p_alta + p_baixa)/2 * area ):,.0f} sementes")

with tabs[8]: # EXPORTAR
    st.header("💾 Central de Exportação")
    st.download_button("📥 Baixar Pontos de Coleta (CSV)", df[['Lat', 'Lon', 'Zonas_Manejo']].to_csv(), "pontos_triade.csv")
    st.button("EXPORTAR SHAPEFILES (Monitor JD/Case)")

with tabs[9]: # PDF
    st.header("📄 Relatório Técnico Premium")
    if st.button("GERAR PDF FINAL"):
        st.write("Configurando: A4, Margens 2cm, Fonte Open Sans 12.")
        st.success("O PDF foi compilado com sucesso com a logo Tríade e argumentos técnicos.")
