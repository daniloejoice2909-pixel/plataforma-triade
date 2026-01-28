import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point

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
        if os.path.exists(logo): st.image(logo, width=220)
        senha = st.text_input("Senha Master:", type="password")
        if st.button("Acessar Plataforma"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. CARREGAMENTO ---
if "df" not in st.session_state:
    st.header("📥 Novo Projeto")
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
        # Mapeamento rigoroso das colunas A-Y
        cols_map = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items()}, inplace=True)
        # LIMPEZA DE DUPLICATAS (Evita o erro LinAlgError)
        df_clean = df_raw.drop_duplicates(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.df = df_clean
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Projeto Carregado!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. MOTOR DE MAPAS (SOLUÇÃO SINGULARITY MATRIX) ---
def gerar_mapa_profissional(df, atributo, contorno, label):
    # Adiciona um ruído ínfimo para evitar matriz singular
    lon = df.Lon.values + np.random.normal(0, 1e-9, len(df))
    lat = df.Lat.values + np.random.normal(0, 1e-9, len(df))
    values = df[atributo].values
    
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:150j, miny:maxy:150j]
    
    try:
        rbf = Rbf(lon, lat, values, function='linear') # 'linear' é mais estável que 'thin_plate'
        grid_z = rbf(grid_x, grid_y)
        
        # Mascaramento
        for i in range(len(grid_x)):
            for j in range(len(grid_y)):
                if not contorno.contains(Point(grid_x[i,j], grid_y[i,j])):
                    grid_z[i,j] = np.nan
                    
        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap='RdYlGn_r')
        plt.colorbar(im, ax=ax, label=label)
        ax.set_title(f"Mapa Tríade: {label}", fontsize=14)
        ax.axis('off')
        return fig
    except:
        st.error(f"Erro ao processar {label}. Verifique os pontos.")
        return None

# --- 5. PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas Solo", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

with tabs[0]: # ATRIBUTOS COMPLETOS
    st.header("⚙️ Configuração Técnica")
    c1, c2, c3 = st.columns(3)
    with c1:
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% Desejado", 60.0); mg_alvo = st.number_input("Mg% Desejado", 18.0)
    with c2:
        p2o5_ad = st.number_input("% P2O5 Adubo", 21.0)
        st.write("**Níveis Críticos P-rem:**")
        nc1 = st.number_input("NC 0-4", 8.0); nc2 = st.number_input("NC 4.1-10", 10.0)
        nc3 = st.number_input("NC 10.1-19", 12.0); nc4 = st.number_input("NC 19.1-30", 15.0)
        nc5 = st.number_input("NC 30.1-45", 20.0); nc6 = st.number_input("NC 45-60", 25.0)
    with c3:
        k_alvo = st.number_input("K% Alvo", 3.2); meta_prod = st.number_input("Meta sc/ha", 80.0)
        fat_k_sc = st.number_input("Fator K (kg/sc)", 1.2)

with tabs[2]: # RECOMENDAÇÕES
    st.header("🏠 Recomendações Profissionais")
    # Motor de Cálculo Tríade 1.0
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100))).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=400, upper=900)
    
    sel_map = st.selectbox("Escolha o Mapa:", ["Rec_Calc", "Rec_Gesso"])
    fig_rec = gerar_mapa_profissional(df, sel_map, st.session_state.contorno, sel_map)
    if fig_rec: st.pyplot(fig_rec)

with tabs[8]: # RELATÓRIO
    st.header("📄 Relatório Final PDF")
    st.write(f"Fazenda: {st.session_state.faz} | Área: {st.session_state.area_ha:.2f} ha")
    if st.button("Exportar"): st.success("Gerando PDF com Sumário de Insumos...")
