import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
from math import ceil

# --- 1. CONFIGURAÇÃO DE TELA E IDENTIDADE VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica", initial_sidebar_state="collapsed")

def aplicar_identidade():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
        .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
        [data-testid="stHeader"] { background-color: #C5A059 !important; }
        h1, h2, h3 { color: #8B4513; font-weight: 700; }
        .stTabs [data-baseweb="tab-list"] button { font-size: 14px !important; font-weight: bold; color: #8B4513; }
        div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; border: none; }
        .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.08; font-size: 40px; color: #8B4513; z-index: -1; pointer-events: none; }
        </style>
        <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
    """, unsafe_allow_html=True)

aplicar_identidade()

# --- 2. TELA DE LOGIN COM LOGO ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 0.6, 1])
    with col_login:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", width=180)
        else:
            st.warning("Arquivo 'LogoTriadeagro.png.png' não encontrado no diretório.")
        
        st.subheader("Acesso Master")
        senha = st.text_input("Chave de Acesso:", type="password")
        if st.button("DESBLOQUEAR SISTEMA"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Chave incorreta.")
    st.stop()

# --- 3. GESTÃO DE PROJETOS E PASTAS ---
if "projeto_ativo" not in st.session_state:
    # Logo pequeno no topo da gestão de arquivos
    if os.path.exists("LogoTriadeagro.png.png"):
        st.image("LogoTriadeagro.png.png", width=120)
    
    st.header("📂 Gestão de Projetos e Pastas")
    c1, c2, c3 = st.columns(3)
    with c1: produtor = st.text_input("Produtor:", "Danilo")
    with c2: fazenda = st.text_input("Fazenda:")
    with c3: municipio = st.text_input("Município/UF:")

    col_u1, col_u2 = st.columns(2)
    with col_u1: u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    with col_u2: u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    
    if st.button("INICIALIZAR AMBIENTE TRÍADE"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            # Motor Blindado por Índice (E=4, F=5, G=6, H=7, I=8, J=9, U=20)
            map_idx = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in map_idx.items():
                df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.projeto_ativo = True
            st.rerun()
    st.stop()

# --- 4. DASHBOARD COM TODAS AS ABAS REVISADAS ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Configurações e Custos")
    # Inclusão dos campos de custo e concentração que faltavam
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Fósforo (P)")
        prod_meta = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
        conc_p = st.number_input("% P2O5 no Adubo (ex: 46%)", 46.0)
        custo_p = st.number_input("Custo P (R$/Ton)", 3800.0)
        exp_p = st.number_input("Exportação P (kg/sc)", 0.8)
    with c2:
        st.subheader("Potássio (K)")
        k_alvo = st.number_input("K Alvo na CTC (%)", 3.2)
        conc_k = st.number_input("% K2O no Adubo (ex: 60%)", 60.0)
        custo_k = st.number_input("Custo K (R$/Ton)", 3200.0)
        exp_k = st.number_input("Exportação K (kg/sc)", 1.2)
    with c3:
        st.subheader("Sementes & Logística")
        pob_alvo = st.number_input("Sementes/ha (Média)", 280000)
        custo_bag = st.number_input("Custo por Big Bag (5mi)", 4500.0)

    # REGRAS DE CÁLCULO TRÍADE (Sincronizadas com os nomes das colunas)
    df['Rec_Calcario'] = (np.maximum(((60 * df['CTC']/100) - df['Ca']) * 100/36, 
                                     ((18 * df['CTC']/100) - df['Mg']) * 100/9) * 1000).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(400, 900)
    
    # Fósforo com Gordura convertido para produto comercial (kg/ha)
    def calc_p_comercial(row):
        nc = 12 # Matriz P-rem simplificada para o motor
        fator = 10 if row['Argila'] > 600 else 8
        dose_p2o5 = max(0, ((nc - row['P']) * fator) + (prod_meta * exp_p))
        return (dose_p2o5 * 100) / conc_p
    df['Rec_Fosforo_Comercial'] = df.apply(calc_p_comercial, axis=1)

    # Potássio convertido para produto comercial (kg/ha)
    df['Rec_Potassio_Comercial'] = (((((k_alvo * df['CTC']/100) - df['K']) * 940).clip(lower=0)) + (prod_meta * exp_k)) * 100 / conc_k

# --- 5. FUNÇÃO DE MAPA HD (CORREÇÃO DE REPETIÇÃO) ---
def plot_mapa_hd(coluna, cmap, titulo, key_map):
    plt.clf()
    plt.close('all') # Garante que não há figuras presas na memória
    fig, ax = plt.subplots(figsize=(8, 6), dpi=110)
    
    minx, miny, maxx, maxy = st.session_state.contorno.bounds
    gx, gy = np.mgrid[minx:maxx:350j, miny:maxy:350j]
    rbf = Rbf(df.Lon, df.Lat, df[coluna], function='linear')
    gz = rbf(gx, gy)
    
    mask = np.array([st.session_state.contorno.contains(Point(p)) for p in np.c_[gx.ravel(), gy.ravel()]]).reshape(gx.shape)
    gz[~mask] = np.nan
    
    im = ax.imshow(gz.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=plt.get_cmap(cmap, 6))
    ax.plot(*st.session_state.contorno.exterior.xy, color='black', linewidth=1.2)
    
    # Legenda fina e estatísticas
    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=8)
    ax.axis('off')
    
    st.pyplot(fig, clear_figure=True)
    st.write(f"📊 **{titulo}** | Mín: {df[coluna].min():.1f} | Méd: {df[coluna].mean():.1f} | Máx: {df[coluna].max():.1f}")

with tabs[1]:
    sel_f = st.selectbox("Selecione o Atributo:", ["Argila", "P_rem", "P", "K", "CTC"], key="sb_f")
    plot_mapa_hd(sel_f, 'coolwarm', f"Análise de {sel_f}", "map_f")

with tabs[2]:
    sel_r = st.selectbox("Selecione a Recomendação (kg/ha):", ["Rec_Calcario", "Rec_Gesso", "Rec_Fosforo_Comercial", "Rec_Potassio_Comercial"], key="sb_r")
    plot_mapa_hd(sel_r, 'YlOrRd', f"Aplicação de {sel_r}", "map_r")
    
    # Sumário Financeiro e Logístico
    dose_med = df[sel_r].mean()
    total_t = (dose_med * st.session_state.area_ha) / 1000
    st.metric(f"Total de {sel_r}", f"{total_t:.2f} Toneladas")

with tabs[5]: # ABA SEMEADURA
    st.header("🌱 Planejamento de Semeadura")
    total_sem = pob_alvo * st.session_state.area_ha
    bags = ceil(total_sem / 5000000)
    st.info(f"População Média: {pob_alvo:,} sementes/ha")
    st.success(f"Logística: Compra de {bags} Big Bags (5 milhões de sementes cada).")
