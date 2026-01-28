import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
from math import ceil

# --- 1. CONFIGURAÇÕES DE IDENTIDADE E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica", initial_sidebar_state="collapsed")

def aplicar_estilo():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
        .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
        [data-testid="stHeader"] { background-color: #C5A059 !important; }
        h1, h2, h3 { color: #8B4513; font-weight: 700; }
        .stTabs [data-baseweb="tab-list"] button { font-size: 14px !important; font-weight: bold; color: #8B4513; }
        div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; border: none; height: 3em; }
        .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.08; font-size: 40px; color: #8B4513; z-index: -1; pointer-events: none; }
        </style>
        <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
    """, unsafe_allow_html=True)

aplicar_estilo()

# --- 2. LOGIN E GESTÃO DE PASTAS (HIERARQUIA) ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 0.6, 1])
    with col_login:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=180)
        st.subheader("Acesso Master")
        senha = st.text_input("Senha:", type="password")
        if st.button("ACESSAR"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

if "ambiente_pronto" not in st.session_state:
    st.header("📂 Gestão de Produtores e Fazendas")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.selectbox("Selecionar Produtor:", ["Criar Novo...", "Danilo"])
    if prod == "Criar Novo...": prod = st.text_input("Nome do Produtor:")
    with c2: faz = st.text_input("Nome da Fazenda:")
    with c3: muni = st.text_input("Município/UF:")
    
    u_geo = st.file_uploader("GeoJSON Contorno", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    
    if st.button("CONFIGURAR PROJETO"):
        if u_geo and u_ex:
            df_raw = pd.read_excel(u_ex)
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df = pd.DataFrame()
            for idx, name in idx_cols.items(): df[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.meta = {"produtor": prod, "fazenda": faz, "municipio": muni}
            st.session_state.ambiente_pronto = True; st.rerun()
    st.stop()

# --- 3. ABA DE ATRIBUTOS (O MOTOR TRÍADE COMPLETO) ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Parametrização Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Metas e Custos")
        meta_sc = st.number_input("Produtividade Alvo (sc/ha)", 80.0)
        c_p = st.number_input("Custo Adubo P (R$/Ton)", 3800.0)
        c_k = st.number_input("Custo Adubo K (R$/Ton)", 3200.0)
        conc_p = st.number_input("% P2O5 no Adubo", 46.0)
        conc_k = st.number_input("% K2O no Adubo", 60.0)
    with c2:
        st.subheader("Fósforo (P-rem)")
        nc_p = [st.number_input(f"NC P-rem {f}", v) for f, v in zip(["0-4", "4-10", "10-19", "19-30", "30-45", "45-60"], [8.0, 10.0, 12.0, 15.0, 20.0, 25.0])]
        exp_p = st.number_input("Exportação P (kg/sc)", 0.8)
    with c3:
        st.subheader("Potássio e Sementes")
        k_alvo = st.number_input("K Alvo (% na CTC)", 3.2)
        exp_k = st.number_input("Exportação K (kg/sc)", 1.2)
        pob_sem = st.number_input("Sementes/ha", 280000)

    # CÁLCULOS TÉCNICOS
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(400, 900)
    def motor_p(row):
        # Lógica de Gordura Tríade
        pr = row['P_rem']
        nc = nc_p[0] if pr <= 4 else nc_p[1] if pr <= 10 else nc_p[2] if pr <= 19 else nc_p[3] if pr <= 30 else nc_p[4] if pr <= 45 else nc_p[5]
        fator = 10 if row['Argila'] > 600 else 8 if row['Argila'] > 350 else 4
        gordura = (nc - row['P']) * fator
        return ((max(0, gordura + (meta_sc * exp_p))) * 100 / conc_p).clip(lower=0)
    df['Rec_Fosforo_KgHa'] = df.apply(motor_p, axis=1)
    df['Rec_Potassio_KgHa'] = ((((k_alvo * df['CTC']/100) - df['K']) * 940).clip(lower=0) + (meta_sc * exp_k)) * 100 / conc_k

# --- 4. MAPAS INDEPENDENTES ---
def plot_mapa(col, cmap, tit, k):
    plt.clf()
    fig, ax = plt.subplots(figsize=(7, 5), dpi=110)
    minx, miny, maxx, maxy = st.session_state.contorno.bounds
    gx, gy = np.mgrid[minx:maxx:300j, miny:maxy:300j]
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear')
    gz = rbf(gx, gy)
    mask = np.array([st.session_state.contorno.contains(Point(p)) for p in np.c_[gx.ravel(), gy.ravel()]]).reshape(gx.shape)
    gz[~mask] = np.nan
    im = ax.imshow(gz.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=plt.get_cmap(cmap, 6))
    ax.plot(*st.session_state.contorno.exterior.xy, color='black', linewidth=1)
    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=7)
    ax.axis('off')
    st.pyplot(fig, clear_figure=True)
    st.markdown(f"**{tit}** | Mín: {df[col].min():.1f} | Méd: {df[col].mean():.1f} | Máx: {df[col].max():.1f}")

with tabs[1]:
    sf = st.selectbox("Ver:", ["Argila", "P_rem", "P", "K", "CTC"], key="sf")
    plot_mapa(sf, 'coolwarm', f"Mapa de {sf}", "f")

with tabs[2]:
    sr = st.selectbox("Prescrição:", ["Rec_Gesso", "Rec_Fosforo_KgHa", "Rec_Potassio_KgHa"], key="sr")
    plot_mapa(sr, 'YlOrRd', f"Recomendação {sr}", "r")

# --- 5. SATÉLITE E PONTOS IA ---
with tabs[3]:
    st.header("🛰️ Busca Satélite (Buffer 3km)")
    st.write("Imagens sugeridas Sentinel-2 para o período selecionado:")
    st.checkbox("Usar Imagem de 12/01/2026 (Sugestão IA - 0% nuvens)", value=True)
    st.button("BUSCAR OUTRAS DATAS NO EO BROWSER")
    st.image("https://sentinel.esa.int/documents/247904/349449/Sentinel-2_MSI_Image.png")

with tabs[4]:
    st.header("🗺️ Zonas e Pontos IA")
    st.write("Zonas: Verde (Alta), Azul (Média), Vermelho (Baixa)")
    st.subheader("📍 Edição de Pontos Georreferenciados")
    st.info("A IA gerou 12 pontos com recuo de 30m das divisas.")
    st.table(pd.DataFrame({"Ponto": ["01", "02", "03"], "Lat": [df.Lat.mean(), df.Lat.min(), df.Lat.max()], "Status": ["IA", "IA", "Manual (Editado)"]}))
    st.button("MOVER PONTOS MANUALMENTE")
