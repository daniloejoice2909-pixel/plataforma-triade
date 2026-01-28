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

# --- 1. CONFIGURAÇÃO VISUAL E LOGO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v106")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3, h4 { color: #8B4513; font-family: 'Open Sans', sans-serif; margin-top: -10px; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 14px !important; font-weight: bold; color: #8B4513; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 10px; height: 3em; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. TELA DE ACESSO (LOGIN) ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    c1, col2, c3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", width=180) # LOGO REDUZIDO CONFORME PEDIDO
        st.subheader("Acesso Master Tríade")
        senha = st.text_input("Chave de Acesso:", type="password")
        if st.button("LOGAR"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Acesso Negado.")
    st.stop()

# --- 3. CONFIGURAÇÃO DO PROJETO ---
if "projeto_ok" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.prod = st.text_input("Produtor:", "Danilo")
        st.session_state.faz = st.text_input("Fazenda:")
        st.session_state.mun = st.text_input("Município/UF:")
    with c2:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Master (A-Y)", type=["xlsx"])
    
    if st.button("INICIALIZAR DASHBOARD"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            # Mapeamento A-Y (Colunas: 0, 1, 4, 5, 6, 7, 8, 9, 20)
            cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
            st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.projeto_ok = True
            st.rerun()
    st.stop()

# --- 4. MOTOR DE MAPAS HD ---
def gerar_mapa(df, col, palette='coolwarm', n_zonas=6):
    cont = st.session_state.contorno
    minx, miny, maxx, maxy = cont.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:350j, miny:maxy:350j]
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    pts = np.c_[grid_x.ravel(), grid_y.ravel()]
    mask = np.array([cont.contains(Point(p)) for p in pts]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    
    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.cm.get_cmap(palette, n_zonas)
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    xc, yc = cont.exterior.xy
    ax.plot(xc, yc, color='black', linewidth=2)
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    ax.axis('off')
    return fig

# --- 5. INTERFACE DE 10 ABAS ---
df = st.session_state.df
area = st.session_state.area_ha
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "⚡ N-P-K", "🍂 DESSECAÇÃO", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]: # ATRIBUTOS EDITÁVEIS
    st.header("⚙️ Configurações da Metodologia Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem & Gesso")
        ca_alvo = st.number_input("Ca Alvo (%)", 60.0); mg_alvo = st.number_input("Mg Alvo (%)", 18.0)
        fat_g = st.number_input("Fator Gesso (Argila x ?)", 15.0) # Conforme pedido: Argila em g/kg * 15
        g_min = st.number_input("Dose Gesso Mín", 400.0); g_max = st.number_input("Dose Gesso Máx", 900.0)
    with c2:
        st.subheader("Fósforo (P-rem)")
        f_mtarg = st.number_input("Fator M. Argilosa", 10.0); f_arg = st.number_input("Fator Argilosa", 8.0)
        f_med = st.number_input("Fator Média", 4.0); f_are = st.number_input("Fator Arenosa", 2.0)
    with c3:
        st.subheader("Potássio & Metas")
        k_alvo = st.number_input("K Alvo (%CTC)", 3.2); meta = st.number_input("Meta (sc/ha)", 80.0)

# CÁLCULOS TÉCNICOS
df['Rec_Gesso'] = (df['Argila'] * fat_g).clip(lower=g_min, upper=g_max)
df['Zonas_Manejo'] = pd.qcut(df['CTC'], 3, labels=[1, 2, 3]) # 1:Baixa, 2:Média, 3:Alta

with tabs[1]: # FERTILIDADE
    st.header("🔍 Mapas de Solo (6 Zonas)")
    sel = st.selectbox("Selecione:", ["Argila", "P", "K", "Ca", "Mg", "CTC"])
    st.pyplot(gerar_mapa(df, sel, palette='coolwarm', n_zonas=6))

with tabs[4]: # ZONAS
    st.header("🗺️ Zonas de Manejo (3 Zonas)")
    st.pyplot(gerar_mapa(df, 'CTC', palette='brg', n_zonas=3))
    st.write("Cores: Vermelho (Baixa) | Azul (Média) | Verde (Alta)")

with tabs[5]: # SEMEADURA
    st.header("🌱 Semeadura em Taxa Variável")
    c1, c2, c3 = st.columns(3)
    pop_a = c1.number_input("Pop. Alta (pl/ha):", 75000)
    pop_m = c2.number_input("Pop. Média (pl/ha):", 65000)
    pop_b = c3.number_input("Pop. Baixa (pl/ha):", 55000)
    st.metric("Total Sementes Estimado", f"{( (pop_a+pop_m+pop_b)/3 * area ):,.0f} Pl")

with tabs[6]: # N-P-K
    st.header("⚡ Recomendação de N-P-K")
    insumo = st.text_input("Fertilizante:", "NPK 04-14-0
