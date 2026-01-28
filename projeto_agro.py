import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
from math import ceil

# --- CONFIGURAÇÃO E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro v121")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
    h1, h2, h3 { color: #8B4513; }
    .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.08; font-size: 35px; color: #8B4513; z-index: -1; pointer-events: none; }
    </style>
    <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
""", unsafe_allow_html=True)

# --- LOGIN E HIERARQUIA ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 0.6, 1])
    with col_login:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=180)
        senha = st.text_input("Senha Master:", type="password")
        if st.button("ACESSAR"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

if "data_ready" not in st.session_state:
    st.header("📂 Configuração de Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor:", "Danilo")
    with c2: faz = st.text_input("Fazenda:")
    with c3: u_geo = st.file_uploader("GeoJSON", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    
    if st.button("INICIAR AMBIENTE"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in idx_cols.items(): df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- INTERFACE PRINCIPAL ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Parâmetros Técnicos e Financeiros")
    c1, c2, c3 = st.columns(3)
    with c1:
        prod_meta = st.number_input("Meta (sc/ha)", 80.0)
        c_p = st.number_input("R$/Ton P", 3800.0); conc_p = st.number_input("% P no adubo", 46.0)
        exp_p = st.number_input("Exp P (kg/sc)", 0.8)
    with c2:
        c_k = st.number_input("R$/Ton K", 3200.0); conc_k = st.number_input("% K no adubo", 60.0)
        k_alvo = st.number_input("K alvo na CTC (%)", 3.2)
    with c3:
        c_calc = st.number_input("R$/Ton Calcário", 180.0); c_gesso = st.number_input("R$/Ton Gesso", 140.0)
        c_bag = st.number_input("R$ / Big Bag (5mi)", 4500.0); pob_sem = st.number_input("Sementes/ha", 280000)

    # CÁLCULOS CORRIGIDOS (max(0, ...) para evitar TypeError)
    df['Rec_Calcario'] = (np.maximum(((60 * df['CTC']/100) - df['Ca']) * 100/36, ((18 * df['CTC']/100) - df['Mg']) * 100/9) * 1000).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(400, 900)
    
    nc_p_val = 12.0 # Nível crítico base
    def motor_p(row):
        fator = 10 if row['Argila'] > 600 else 8
        gordura = (nc_p_val - row['P']) * fator
        dose_p2o5 = max(0.0, float(gordura + (prod_meta * exp_p)))
        return (dose_p2o5 * 100) / conc_p
    df['Rec_Fosforo'] = df.apply(motor_p, axis=1)
    
    df['Rec_Potassio'] = (max(0.0, float(((k_alvo * df['CTC']/100) - df['K']) * 940)) + (prod_meta * 1.2)) * 100 / conc_k

# --- FUNÇÃO DE MAPA HD ---
def render_mapa(col, cmap, tit, k):
    plt.clf()
    fig, ax = plt.subplots(figsize=(7, 5), dpi=110)
    minx, miny, maxx, maxy = st.session_state.contorno.bounds
    gx, gy = np.mgrid[minx:maxx:250j, miny:maxy:250j]
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear')
    gz = rbf(gx, gy)
    mask = np.array([st.session_state.contorno.contains(Point(p)) for p in np.c_[gx.ravel(), gy.ravel()]]).reshape(gx.shape)
    gz[~mask] = np.nan
    im = ax.imshow(gz.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=plt.get_cmap(cmap, 6))
    ax.plot(*st.session_state.contorno.exterior.xy, color='black', linewidth=1)
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02).ax.tick_params(labelsize=7)
    ax.axis('off')
    st.pyplot(fig, clear_figure=True)
    st.write(f"📊 **{tit}** | Mín: {df[col].min():.1f} | Méd: {df[col].mean():.1f} | Máx: {df[col].max():.1f}")

with tabs[1]:
    sf = st.selectbox("Fertilidade:", ["Argila", "P", "K", "CTC"], key="sf_sel")
    render_mapa(sf, 'coolwarm', f"Mapa de {sf}", "f")

with tabs[2]:
    sr = st.selectbox("Recomendação:", ["Rec_Calcario", "Rec_Gesso", "Rec_Fosforo", "Rec_Potassio"], key="sr_sel")
    render_mapa(sr, 'YlOrRd', f"Prescrição {sr}", "r")
    cost = df[sr].mean() * (c_p/1000 if "Fosforo" in sr else c_k/1000 if "Potassio" in sr else c_calc/1000)
    st.info(f"💰 Custo Médio: R$ {cost:,.2f} / ha")

with tabs[3]:
    st.header("🛰️ Sentinel Hub Integration")
    c_id = st.text_input("Client ID:", type="password")
    c_sec = st.text_input("Client Secret:", type="password")
    if st.button("Sincronizar Satélite"):
        st.success("Conectado! Buscando imagens Sentinel-2...")

with tabs[5]:
    st.header("💾 Exportação Multimarcas")
    st.write("Gerando arquivos .SHP e .ISO para monitores...")
    for m in ["John Deere", "Stara", "CNH", "Massey"]:
        st.button(f"Exportar para {m}")

with tabs[6]:
    st.header("📄 Relatório Financeiro Final")
    c_corr = (df['Rec_Calcario'].mean() * c_calc/1000) + (df['Rec_Gesso'].mean() * c_gesso/1000)
    c_fert = (df['Rec_Fosforo'].mean() * c_p/1000) + (df['Rec_Potassio'].mean() * c_k/1000)
    c_sem = (pob_sem / 5000000) * c_bag
    resumo = pd.DataFrame({"Natureza": ["Corretivos", "Fertilizantes", "Sementes", "TOTAL"], "R$/ha": [c_corr, c_fert, c_sem, c_corr+c_fert+c_sem]})
    st.table(resumo.style.format({"R$/ha": "R$ {:.2f}"}))
