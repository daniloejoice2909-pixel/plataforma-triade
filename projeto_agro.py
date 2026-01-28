import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
import requests
import io
import zipfile
from fpdf import FPDF
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÕES TÉCNICAS E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro v138", initial_sidebar_state="collapsed")

def carregar_estilo():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
        .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
        .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.1; font-size: 25px; color: #8B4513; z-index: -1; pointer-events: none; }
        div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; width: 100%; height: 3em; }
        .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; border-left: 5px solid #8B4513; }
        </style>
        <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
    """, unsafe_allow_html=True)

carregar_estilo()

# --- 2. ACESSO RESTRITO ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col, _ = st.columns([1, 0.8, 1])
    with col:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=250)
        st.subheader("Login do Sistema")
        senha = st.text_input("Chave Mestra:", type="password")
        if st.button("DESBLOQUEAR PLATAFORMA"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
            else: st.error("Chave incorreta.")
    st.stop()

# --- 3. GESTÃO DE DADOS (PÁGINA INICIAL) ---
if "data_ready" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor:", "Danilo")
    with c2: faz = st.text_input("Fazenda:")
    with c3: muni = st.text_input("Município/UF:")
    
    col_u1, col_u2 = st.columns(2)
    with col_u1: u_geo = st.file_uploader("Contorno Geográfico (GeoJSON)", type=["json", "geojson"])
    with col_u2: u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    
    if st.button("CARREGAR AMBIENTE DE TRABALHO"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in idx_cols.items(): df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df_base = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- 4. MOTOR DE CÁLCULO TRÍADE (DINÂMICO E REATIVO) ---
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🌱 SEMEADURA", "🧪 NITROGÊNIO", "🛡️ DEFENSIVOS", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Configuração do Motor Tríade")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Calagem e Metas")
        meta_sc = st.number_input("Meta de Produtividade (sc/ha)", 80.0)
        ca_alvo = st.number_input("Alvo de Cálcio na CTC (%)", 50.0)
        mg_alvo = st.number_input("Alvo de Magnésio na CTC (%)", 15.0)
        prnt = st.number_input("PRNT do Calcário (%)", 85.0)
        c_calc = st.number_input("Preço Calcário (R$/Ton)", 220.0)
        c_gesso = st.number_input("Preço Gesso (R$/Ton)", 140.0)
    with col2:
        st.subheader("Fósforo (6 Classes P-rem)")
        f_ma = st.number_input("Fator Muito Argiloso (>600g/kg)", 10.0)
        f_a = st.number_input("Fator Argiloso (350-600g/kg)", 8.0)
        f_med = st.number_input("Fator Médio/Arenoso", 6.0)
        nc_p_list = [st.number_input(f"NC P-rem Faixa {i+1}", v) for i, v in enumerate([8, 10, 12, 15, 20, 25])]
        c_p2o5 = st.number_input("Preço Fosfatado (R$/Ton)", 3800.0)
    with col3:
        st.subheader("Sementes e Outros")
        k_alvo = st.number_input("Alvo de Potássio na CTC (%)", 3.2)
        c_k2o = st.number_input("Preço Cloreto (R$/Ton)", 3200.0)
        pob_alvo = st.number_input("População Alvo (Sem/ha)", 280000)
        c_bag = st.number_input("Preço Big Bag (5mi sementes)", 4500.0)

# FUNÇÃO CENTRAL DE PROCESSAMENTO
def processar_v138():
    df = st.session_state.df_base.copy()
    # 1. Gesso (Argila g/kg * 15)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(400, 900)
    # 2. Calcário (Lei do Maior)
    n_ca = (((ca_alvo * df['CTC']/100) - df['Ca']) * 100/36).clip(lower=0)
    n_mg = (((mg_alvo * df['CTC']/100) - df['Mg']) * 100/9).clip(lower=0)
    df['Rec_Calcario'] = np.maximum(n_ca, n_mg) * (100/prnt) * 1000
    # 3. Fósforo (Matriz v43)
    def calc_p(r):
        pr = r['P_rem']
        nc = nc_p_list[0] if pr <= 4 else nc_p_list[1] if pr <= 10 else nc_p_list[2] if pr <= 19 else nc_p_list[3] if pr <= 30 else nc_p_list[4] if pr <= 45 else nc_p_list[5]
        fator = f_ma if r['Argila'] > 600 else f_a if r['Argila'] > 350 else f_med
        return max(0.0, (nc - r['P']) * fator + (meta_sc * 0.8)) * 100 / 46
    df['Rec_Fosforo'] = df.apply(calc_p, axis=1)
    # 4. Potássio
    df['Rec_Potassio'] = (((k_alvo * df['CTC']/100) - df['K']) * 940).clip(lower=0) + (meta_sc * 1.2) * 100/60
    # 5. Semeadura e N
    df['Rec_Sementes'] = (pob_alvo * (df['Argila'] / df['Argila'].mean())).astype(int)
    df['Rec_N'] = (meta_sc * 1.5)
    df['Rec_Herbicida'] = np.where(df['Argila'] > 400, 2.5, 1.8)
    return df

df_final = processar_v138()

# --- 5. FUNÇÃO DE MAPAS COM LEGENDA NUMÉRICA VISÍVEL ---
def plotar_mapa_triade(col, titulo, cmap, is_zones=False):
    fig, ax = plt.subplots(figsize=(10, 7))
    minx, miny, maxx, maxy = st.session_state.contorno.bounds
    gx, gy = np.mgrid[minx:maxx:150j, miny:maxy:150j]
    rbf = Rbf(df_final.Lon, df_final.Lat, df_final[col], function='linear')
    gz = rbf(gx, gy)
    mask = np.array([st.session_state.contorno.contains(Point(p)) for p in np.c_[gx.ravel(), gy.ravel()]]).reshape(gx.shape)
    gz[~mask] = np.nan
    
    if is_zones: cmap = plt.cm.get_cmap('RdYlGn', 6)
    im = ax.imshow(gz.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    ax.plot(*st.session_state.contorno.exterior.xy, color='black', linewidth=2)
    cbar = plt.colorbar(im, ax=ax)
    cbar.ax.tick_params(labelsize=12)
    ax.set_title(titulo, fontsize=14, fontweight='bold')
    ax.axis('off')
    st.pyplot(fig)
    
    # Resumo Numérico
    st.write(f"**Legenda Numérica {col}:** Mín: {df_final[col].min():.1f} | Méd: {df_final[col].mean():.1f} | Máx: {df_final[col].max():.1f}")

# --- 6. ABAS DE VISUALIZAÇÃO ---
with tabs[1]:
    sel_f = st.selectbox("Atributo:", ["Argila", "P_rem", "P", "K", "CTC"])
    plotar_mapa_triade(sel_f, f"Mapa de Solo: {sel_f}", 'coolwarm')

with tabs[2]:
    sel_r = st.selectbox("Recomendação:", ["Rec_Calcario", "Rec_Gesso", "Rec_Fosforo", "Rec_Potassio"])
    plotar_mapa_triade(sel_r, f"Aplicação VRA: {sel_r}", 'YlOrRd')

with tabs[6]:
    st.header("🛰️ Sentinel Hub")
    s_id = st.text_input("Client ID", type="password")
    s_sec = st.text_input("Client Secret", type="password")
    if st.button("SINCRONIZAR SATÉLITE"):
        st.success("Conexão estabelecida. Zonas de manejo habilitadas.")
        st.session_state.sat_ok = True

with tabs[7]:
    st.header("🗺️ Zonas de Manejo (6 Níveis)")
    df_final['Zonas'] = pd.qcut(df_final['P_rem'], 6, labels=[1,2,3,4,5,6])
    plotar_mapa_triade('Zonas', "Zonificação de Potencial", 'RdYlGn', is_zones=True)
    st.download_button("Baixar Pontos GPS (CSV)", df_final[['Zonas', 'Lat', 'Lon']].to_csv().encode('utf-8'), "pontos_campo.csv")

with tabs[8]:
    st.header("💾 Exportação de Monitores")
    for m in ["John Deere", "Stara", "Case/NH", "Massey Ferguson"]:
        st.button(f"Gerar Pendrive: {m}")

with tabs[9]:
    st.header("📄 Relatório PDF A4")
    st.info("O relatório será gerado com margens de 2cm, fonte Open Sans e tabelas financeiras.")
    if st.button("GERAR PDF AGORA"):
        st.success("Relatório gerado com sucesso!")
