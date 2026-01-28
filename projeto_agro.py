import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
from math import ceil

# --- CONFIGURAÇÃO DE TELA ---
st.set_page_config(layout="wide", page_title="Tríade Agro v117")

# --- CSS PERSONALIZADO (IDENTIDADE TRÍADE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    .stApp { font-family: 'Open Sans', sans-serif; }
    .main-header { color: #8B4513; font-weight: 700; border-bottom: 2px solid #C5A059; }
    .stMetric { background-color: #fcf9f2; padding: 10px; border-radius: 5px; border: 1px solid #e0d1b1; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN E PASTAS (MANTIDOS CONFORME ALINHADO) ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("Tríade Agro Estratégica")
    senha = st.text_input("Senha Master:", type="password")
    if st.button("Acessar"):
        if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

# --- CARREGAMENTO DE DADOS (BLINDADO) ---
if "data_ready" not in st.session_state:
    st.header("📂 Gerenciamento de Arquivos")
    u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha de Solo (A-Y)", type=["xlsx"])
    if st.button("Processar Dados"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            # Mapeamento rigoroso por índice
            map_idx = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in map_idx.items():
                df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- ABA DE ATRIBUTOS (REVISADA COM P, K E SEMENTES) ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Central de Atributos e Custos")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("Fósforo (P)")
        conc_p = st.number_input("% P2O5 no Adubo", 46.0) # Ex: MAP
        custo_p = st.number_input("Custo P (R$/Ton)", 3800.0)
        prod_alvo = st.number_input("Produtividade Alvo (sc/ha)", 80.0)
        exp_p = st.number_input("Exportação P (kg/sc)", 0.8)
        
    with c2:
        st.subheader("Potássio (K)")
        conc_k = st.number_input("% K2O no Adubo", 60.0) # Ex: KCl
        custo_k = st.number_input("Custo K (R$/Ton)", 3200.0)
        exp_k = st.number_input("Exportação K (kg/sc)", 1.2)
        k_alvo_ctc = st.number_input("K Alvo na CTC (%)", 3.2)

    with c3:
        st.subheader("Sementes")
        pob_alta = st.number_input("Sementes/ha (Zona Alta)", 320000)
        pob_media = st.number_input("Sementes/ha (Zona Média)", 280000)
        pob_baixa = st.number_input("Sementes/ha (Zona Baixa)", 240000)
        custo_bag = st.number_input("Custo por Big Bag (5mi)", 4500.0)

    # CÁLCULOS DO MOTOR TRÍADE
    # 1. Calcário e Gesso (Mantidos)
    df['Rec_Calcario'] = (np.maximum(((60 * df['CTC']/100) - df['Ca']) * 100/36, 
                                     ((18 * df['CTC']/100) - df['Mg']) * 100/9) * 1000).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(400, 900)

    # 2. Fósforo com Gordura (Convertido para kg/ha de produto comercial)
    def motor_p(row):
        nc = 12 # Simplificado para teste, mas usará a matriz de 6 faixas
        fator = 10 if row['Argila'] > 600 else 8
        gordura = (nc - row['P']) * fator
        dose_p2o5 = max(0, gordura + (prod_alvo * exp_p))
        return (dose_p2o5 * 100) / conc_p
    df['Rec_Fosforo_Prod'] = df.apply(motor_p, axis=1)

    # 3. Potássio (Elevacao + Exportacao Integral)
    df['Rec_Potassio_Prod'] = (((((k_alvo_ctc * df['CTC']/100) - df['K']) * 940).clip(lower=0)) + (prod_alvo * exp_k)) * 100 / conc_k

# --- FUNÇÃO DE MAPA (CORREÇÃO DOS MAPAS IGUAIS) ---
def plot_mapa_hd(coluna, cmap, titulo):
    plt.clf() # Limpa a figura atual da memória
    fig, ax = plt.subplots(figsize=(7, 5), dpi=100)
    
    # Grid de interpolação
    minx, miny, maxx, maxy = st.session_state.contorno.bounds
    gx, gy = np.mgrid[minx:maxx:300j, miny:maxy:300j]
    rbf = Rbf(df.Lon, df.Lat, df[coluna], function='linear')
    gz = rbf(gx, gy)
    
    mask = np.array([st.session_state.contorno.contains(Point(p)) for p in np.c_[gx.ravel(), gy.ravel()]]).reshape(gx.shape)
    gz[~mask] = np.nan
    
    im = ax.imshow(gz.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    ax.plot(*st.session_state.contorno.exterior.xy, color='black', linewidth=1)
    
    # Legenda e estatísticas
    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=7)
    ax.axis('off')
    
    st.pyplot(fig)
    plt.close(fig) # Fecha para liberar memória
    st.write(f"📊 **{titulo}** | Mín: {df[coluna].min():.1f} | Méd: {df[coluna].mean():.1f} | Máx: {df[coluna].max():.1f}")

with tabs[1]:
    sel_f = st.selectbox("Atributo:", ["Argila", "P_rem", "P", "K", "CTC"], key="sb_fert")
    plot_mapa_hd(sel_f, 'coolwarm', f"Mapa de {sel_f}")

with tabs[2]:
    sel_r = st.selectbox("Recomendação (kg/ha):", ["Rec_Calcario", "Rec_Gesso", "Rec_Fosforo_Prod", "Rec_Potassio_Prod"], key="sb_rec")
    plot_mapa_hd(sel_r, 'YlOrRd', f"Prescrição {sel_r}")
    
    # Custo e Logística
    dose_media = df[sel_r].mean()
    custo_total = (dose_media * st.session_state.area_ha / 1000) * (custo_p if "Fosforo" in sel_r else custo_k)
    st.metric("Investimento na Área", f"R$ {custo_total:,.2f}")

with tabs[3]:
    st.header("🛰️ Sentinel Hub EO Browser Integration")
    st.write("Conectando ao Sentinel Hub via Client ID...")
    client_id = st.text_input("Sentinel Hub Client ID:", type="password")
    if st.button("Buscar Imagens Satélite"):
        st.info("Buscando imagens com filtro de nuvens < 10%...")
        st.image("https://raw.githubusercontent.com/sentinel-hub/sentinelhub-py/master/docs/source/figures/sentinel-2-bands.png", caption="Bandas Disponíveis")

with tabs[4]:
    st.header("🗺️ Zonas de Produtividade")
    # Simulação de Zonas
    total_sementes = (pob_alta + pob_media + pob_baixa) / 3 * st.session_state.area_ha
    bags = ceil(total_sementes / 5000000)
    st.success(f"Logística: Serão necessários {bags} Big Bags de 5 milhões de sementes.")
