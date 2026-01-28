import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro v127", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
    .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.1; font-size: 30px; color: #8B4513; z-index: -1; pointer-events: none; }
    h1, h2, h3 { color: #8B4513; font-weight: bold; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; height: 3em; }
    </style>
    <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
""", unsafe_allow_html=True)

# --- 2. ACESSO ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col, _ = st.columns([1, 0.6, 1])
    with col:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=250)
        senha = st.text_input("Senha Master:", type="password")
        if st.button("ACESSAR PLATAFORMA"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

# --- 3. CARREGAMENTO DE DADOS (PÁGINA 2) ---
if "data_ready" not in st.session_state:
    st.header("📂 Configuração de Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor:", "Danilo")
    with c2: faz = st.text_input("Fazenda:")
    with c3: muni = st.text_input("Município/UF:")
    
    u_geo = st.file_uploader("Contorno GeoJSON", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha de Solo (Colunas A-Y)", type=["xlsx"])
    
    if st.button("INICIAR PROVIMENTO DE DADOS"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            # Mapeamento Tríade: 0:Lat, 1:Lon, 4:Arg, 5:Prem, 6:P, 7:Ca, 8:Mg, 9:K, 20:CTC
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in idx_cols.items(): df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df_base = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.data_ready = True; st.rerun()
    st.stop()

# --- 4. TABS E MOTOR DINÂMICO ---
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Parametrização Editável")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Calagem e Metas")
        meta_sc = st.number_input("Meta Produtividade (sc/ha)", 80.0)
        ca_alvo = st.number_input("Alvo Ca na CTC (%)", 50.0)
        mg_alvo = st.number_input("Alvo Mg na CTC (%)", 15.0)
        prnt = st.number_input("PRNT Calcário (%)", 85.0)
        c_calc = st.number_input("R$/Ton Calcário", 220.0)
        c_gesso = st.number_input("R$/Ton Gesso", 140.0)
    with col2:
        st.subheader("Fósforo (Classes Argila e NC)")
        f_ma = st.number_input("Fator Muito Argiloso", 10.0)
        f_a = st.number_input("Fator Argiloso", 8.0)
        f_m = st.number_input("Fator Médio", 6.0)
        nc_p = [st.number_input(f"NC P-rem F{i+1}", v) for i, v in enumerate([8, 10, 12, 15, 20, 25])]
        c_p2o5 = st.number_input("R$/Ton Adubo Fosfatado", 3800.0)
    with col3:
        st.subheader("Potássio e Sementes")
        k_alvo_ctc = st.number_input("Alvo K na CTC (%)", 3.2)
        c_k2o = st.number_input("R$/Ton Cloreto", 3200.0)
        pob_alvo = st.number_input("Sementes/ha", 280000)
        c_bag = st.number_input("R$/Big Bag (5mi)", 4500.0)

# FUNÇÃO DE CÁLCULO REATIVA (Sempre atualizada)
def get_df_calculado():
    df = st.session_state.df_base.copy()
    # Gesso
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(400, 900)
    # Calcário (Maior Dose)
    def calc_cal(r):
        d_ca = max(0.0, ((ca_alvo * r['CTC']/100) - r['Ca']) * 100/36)
        d_mg = max(0.0, ((mg_alvo * r['CTC']/100) - r['Mg']) * 100/9)
        return max(d_ca, d_mg) * (100/prnt) * 1000
    df['Rec_Calcario'] = df.apply(calc_cal, axis=1)
    # Fósforo
    def calc_p(r):
        pr = r['P_rem']
        nc = nc_p[0] if pr <= 4 else nc_p[1] if pr <= 10 else nc_p[2] if pr <= 19 else nc_p[3] if pr <= 30 else nc_p[4] if pr <= 45 else nc_p[5]
        fator = f_ma if r['Argila'] > 600 else f_a if r['Argila'] > 350 else f_m
        return max(0.0, (nc - r['P']) * fator + (meta_sc * 0.8)) * 100 / 46
    df['Rec_Fosforo'] = df.apply(calc_p, axis=1)
    # Potássio
    df['Rec_Potassio'] = (max(0.0, ((k_alvo_ctc * df['CTC']/100) - df['K']) * 940) + (meta_sc * 1.2)) * 100 / 60
    return df

df_final = get_df_calculado()

# --- 5. VISUALIZAÇÃO ---
def plot_mapa(col, cmap):
    fig, ax = plt.subplots(figsize=(7, 5))
    minx, miny, maxx, maxy = st.session_state.contorno.bounds
    gx, gy = np.mgrid[minx:maxx:150j, miny:maxy:150j]
    rbf = Rbf(df_final.Lon, df_final.Lat, df_final[col], function='linear')
    gz = rbf(gx, gy)
    mask = np.array([st.session_state.contorno.contains(Point(p)) for p in np.c_[gx.ravel(), gy.ravel()]]).reshape(gx.shape)
    gz[~mask] = np.nan
    im = ax.imshow(gz.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    plt.colorbar(im, ax=ax, shrink=0.8)
    ax.plot(*st.session_state.contorno.exterior.xy, color='black')
    ax.axis('off')
    st.pyplot(fig)

with tabs[1]:
    s_fert = st.selectbox("Atributo:", ["Argila", "P_rem", "P", "K", "CTC"])
    plot_mapa(s_fert, 'coolwarm')

with tabs[2]:
    s_rec = st.selectbox("Recomendação:", ["Rec_Calcario", "Rec_Gesso", "Rec_Fosforo", "Rec_Potassio"])
    plot_mapa(s_rec, 'YlOrRd')

with tabs[3]:
    st.header("🛰️ Sentinel Hub")
    st.text_input("Client ID:", type="password")
    st.text_input("Client Secret:", type="password")
    st.button("Sincronizar Satélite")

with tabs[4]:
    st.header("🗺️ Zonas de Produtividade")
    c_z1, c_z2, c_z3 = st.columns(3)
    p_a = c_z1.number_input("Pontos Alta", 5)
    p_m = c_z2.number_input("Pontos Média", 3)
    p_b = c_z3.number_input("Pontos Baixa", 2)
    st.button("PLANEJAR AMOSTRAGEM IA")
    st.data_editor(df_final[['Lat', 'Lon']].head(p_a+p_m+p_b))

with tabs[5]:
    st.header("💾 Exportação Maquinário")
    for m in ["John Deere", "Stara", "Case/NH", "Massey Ferguson"]:
        st.button(f"Exportar ISO/SHP para {m}")

with tabs[6]:
    st.header("📄 Relatório Financeiro Tríade")
    c_cor = (df_final['Rec_Calcario'].mean() * c_calc/1000) + (df_final['Rec_Gesso'].mean() * c_gesso/1000)
    c_fer = (df_final['Rec_Fosforo'].mean() * c_p2o5/1000) + (df_final['Rec_Potassio'].mean() * c_k2o/1000)
    c_sem = (pob_alvo / 5000000) * c_bag
    
    resumo = pd.DataFrame({
        "Natureza": ["Corretivos", "Fertilizantes", "Sementes", "TOTAL"],
        "Investimento (R$/ha)": [c_cor, c_fer, c_sem, c_cor+c_fer+c_sem],
        "Total Área (R$)": [c*st.session_state.area_ha for c in [c_cor, c_fer, c_sem, c_cor+c_fer+c_sem]]
    })
    st.table(resumo.style.format({"Investimento (R$/ha)": "R$ {:.2f}", "Total Área (R$)": "R$ {:,.2f}"}))
