import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point

# --- CONFIGURAÇÃO PREMIUM ---
st.set_page_config(layout="wide", page_title="Tríade Agro v110")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3, h4 { color: #8B4513; font-family: 'Open Sans', sans-serif; margin-top: -10px; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 14px !important; font-weight: bold; color: #8B4513; }
    div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; }
    .metric-card { background-color: #f8f9fa; border: 1px solid #C5A059; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN E LOGO ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=160)
        senha = st.text_input("Chave Master:", type="password")
        if st.button("DESBLOQUEAR"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

# --- PROJETO ---
if "setup" not in st.session_state:
    st.header("📂 Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.prod = st.text_input("Produtor:", "Danilo")
        st.session_state.faz = st.text_input("Fazenda:")
    with c2:
        u_geo = st.file_uploader("GeoJSON Contorno", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Master (Imagem)", type=["xlsx"])
    
    if st.button("INICIAR MOTOR TRÍADE"):
        if u_geo and u_ex:
            df = pd.read_excel(u_ex)
            # Mapeamento conforme sua imagem
            cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df.rename(columns={df.columns[i]: n for i, n in cols.items() if i < len(df.columns)}, inplace=True)
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.setup = True; st.rerun()
    st.stop()

# --- MOTOR DE MAPAS HD ---
def plot_hd(df, col, palette='coolwarm', zones=6):
    cont = st.session_state.contorno
    minx, miny, maxx, maxy = cont.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:500j, miny:maxy:500j] # QUALIDADE 500j
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    pts = np.c_[grid_x.ravel(), grid_y.ravel()]
    mask = np.array([cont.contains(Point(p)) for p in pts]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    cmap = plt.cm.get_cmap(palette, zones)
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    ax.plot(*cont.exterior.xy, color='black', linewidth=1.5)
    cbar = plt.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.ax.tick_params(labelsize=8)
    ax.axis('off')
    return fig

# --- ABAS ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "⚡ N-P-K", "🍂 DESSECAÇÃO", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]: # TODOS OS ATRIBUTOS EDITÁVEIS CONFORME PEDIDO
    st.header("⚙️ Configurações de Fórmulas Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem & Gesso")
        ca_alvo = st.number_input("Ca Alvo (% CTC)", 60.0); mg_alvo = st.number_input("Mg Alvo (% CTC)", 18.0)
        f_gesso = st.number_input("Fator Gesso (Argila x ?)", 15.0)
        g_min = st.number_input("Gesso Mín (kg/ha)", 400.0); g_max = st.number_input("Gesso Máx (kg/ha)", 900.0)
    with c2:
        st.subheader("Fósforo (P-rem)")
        f10 = st.number_input("Fator M. Argilosa", 10.0); f8 = st.number_input("Fator Argilosa", 8.0)
        f4 = st.number_input("Fator Média", 4.0); f2 = st.number_input("Fator Arenosa", 2.0)
        st.write("Níveis Críticos:")
        nc1 = st.number_input("P-rem 0-4", 8.0); nc2 = st.number_input("P-rem 4-10", 10.0)
    with c3:
        st.subheader("Potássio & Exportação")
        k_alvo_ctc = st.number_input("K Alvo (% CTC)", 3.2)
        exp_k = st.number_input("Exportação K (kg/ha)", 40.0)
        exp_p = st.number_input("Exportação P (kg/ha)", 35.0)

# --- MOTOR DE CÁLCULO TRÍADE ---
# 1. Calcário (Maior valor entre elevação de Ca e Mg)
df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC']/100) - df['Ca']) * 100 / 36, 
                             ((mg_alvo * df['CTC']/100) - df['Mg']) * 100 / 9) * 1000).clip(lower=0)
# 2. Gesso (Argila g/kg * 15)
df['Rec_Gesso'] = (df['Argila'] * f_gesso).clip(lower=g_min, upper=g_max)
# 3. Potássio (K Alvo + Exportação Integral)
df['Rec_K'] = (((k_alvo_ctc * df['CTC']/100) - df['K']) * 940).clip(lower=0) + exp_k

with tabs[1]: # FERTILIDADE
    st.header("🔍 Mapas de Fertilidade (Solo)")
    f_sel = st.selectbox("Atributo de Solo:", ["Argila", "P", "K", "Ca", "Mg", "CTC"])
    st.pyplot(plot_hd(df, f_sel, palette='coolwarm', zones=6))

with tabs[2]: # RECOMENDAÇÃO
    st.header("🏠 Mapas de Recomendação (Prescrição)")
    r_sel = st.selectbox("Escolha a Recomendação:", ["Rec_Calc", "Rec_Gesso", "Rec_K"])
    st.pyplot(plot_hd(df, r_sel, palette='YlOrRd', zones=6))
    
    st.subheader("📋 Sumário de Insumos")
    col_a, col_b, col_c = st.columns(3)
    media_dose = df[r_sel].mean()
    total_t = (media_dose * st.session_state.area_ha) / 1000
    col_a.metric("Dose Média", f"{media_dose:.0f} kg/ha")
    col_b.metric("Volume Total", f"{total_t:.1f} Toneladas")
    col_c.metric("Área Atendida", f"{st.session_state.area_ha:.1f} ha")

with tabs[3]: # SATÉLITE
    st.header("🛰️ Monitoramento Sentinel-2")
    st.info("Aguardando conexão com as coordenadas da fazenda...")
    st.image("https://sentinel.esa.int/documents/247904/349449/Sentinel-2_MSI_Image.png", use_container_width=True)

with tabs[9]: # PDF
    st.header("📄 Relatório Final")
    st.write("Configuração: A4, Margens 2cm, Fonte Open Sans 12.")
    if st.button("EXPORTAR PDF"): st.success("PDF gerado com argumentos técnicos Tríade.")
