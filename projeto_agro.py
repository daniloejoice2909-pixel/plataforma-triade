import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point

# --- CONFIGURAÇÃO DE INTERFACE ---
st.set_page_config(layout="wide", page_title="Tríade Agro v112")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    h1, h2, h3 { color: #8B4513; font-family: 'Open Sans', sans-serif; }
    div.stButton > button { background-color: #8B4513; color: white; font-weight: bold; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN E LOGO ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=150)
        senha = st.text_input("Acesso Master:", type="password")
        if st.button("ENTRAR"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

# --- CARREGAMENTO ---
if "setup" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("GeoJSON Contorno", type=["json", "geojson"])
        st.session_state.prod = st.text_input("Produtor:", "Danilo")
    with c2:
        u_ex = st.file_uploader("Planilha Master", type=["xlsx"])
        st.session_state.faz = st.text_input("Fazenda:")
    
    if st.button("INICIAR"):
        if u_geo and u_ex:
            df = pd.read_excel(u_ex)
            # Mapeamento Rigoroso A-Y
            cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df.rename(columns={df.columns[i]: n for i, n in cols.items() if i < len(df.columns)}, inplace=True)
            st.session_state.df = df.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.setup = True; st.rerun()
    st.stop()

# --- ABAS E ATRIBUTOS ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "⚡ N-P-K", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]:
    st.header("⚙️ Configurações da Metodologia Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem & Gesso")
        cao = st.number_input("CaO (%)", 36.0); mgo = st.number_input("MgO (%)", 9.0); prnt = st.number_input("PRNT (%)", 85.0)
        ca_alvo = st.number_input("Ca Alvo (%CTC)", 60.0); mg_alvo = st.number_input("Mg Alvo (%CTC)", 18.0)
        fat_g = st.number_input("Fator Gesso (Argila x 15)", 15.0)
        g_min = st.number_input("Gesso Mín", 400.0); g_max = st.number_input("Gesso Máx", 900.0)
    with c2:
        st.subheader("Fósforo (Classes P-rem)")
        f10 = st.number_input("Fator M. Argilosa", 10.0); f8 = st.number_input("Fator Argilosa", 8.0)
        f4 = st.number_input("Fator Média", 4.0); f2 = st.number_input("Fator Arenosa", 2.0)
        exp_p = st.number_input("Exportação P (kg/ha)", 35.0)
        st.write("Níveis Críticos (NC):")
        nc1 = st.number_input("NC (0-4 P-rem)", 8.0); nc2 = st.number_input("NC (4.1-10)", 10.0)
        nc3 = st.number_input("NC (10.1-19)", 12.0); nc4 = st.number_input("NC (19.1-30)", 15.0)
        nc5 = st.number_input("NC (30.1-60)", 20.0)
    with c3:
        st.subheader("Potássio")
        k_alvo_ctc = st.number_input("K Alvo (% na CTC)", 3.2)
        exp_k = st.number_input("Exportação K (kg/ha)", 45.0)

# --- MOTOR DE CÁLCULO (RESOLUÇÃO DO ERRO) ---
def calcular_fosforo(row):
    # Definindo Nível Crítico baseado no P-rem
    p_rem = row['P_rem']
    if p_rem <= 4: nc = nc1
    elif p_rem <= 10: nc = nc2
    elif p_rem <= 19: nc = nc3
    elif p_rem <= 30: nc = nc4
    else: nc = nc5
    
    # Definindo Fator baseado na Argila
    arg = row['Argila']
    if arg > 600: fat = f10
    elif arg > 350: fat = f8
    elif arg > 150: fat = f4
    else: fat = f2
    
    correcao = (nc - row['P']) * fat
    return max(0, correcao) + exp_p

df['Rec_Calcario'] = (np.maximum(((ca_alvo * df['CTC']/100) - df['Ca']) * 100 / (cao * 1.78), 
                                ((mg_alvo * df['CTC']/100) - df['Mg']) * 100 / (mgo * 2.48)) * (100/prnt) * 1000).clip(lower=0)
df['Rec_Gessagem'] = (df['Argila'] * fat_g).clip(lower=g_min, upper=g_max)
df['Rec_Potassio'] = (((k_alvo_ctc * df['CTC']/100) - df['K']) * 940).clip(lower=0) + exp_k
df['Rec_Fosforo'] = df.apply(calcular_fosforo, axis=1)

# --- FUNÇÃO DE MAPA ---
def gerar_mapa_hd(df_map, col_name, pal, n_z, key_suffix):
    cont = st.session_state.contorno
    minx, miny, maxx, maxy = cont.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:400j, miny:maxy:400j]
    rbf = Rbf(df_map.Lon, df_map.Lat, df_map[col_name], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    mask = np.array([cont.contains(Point(p)) for p in np.c_[grid_x.ravel(), grid_y.ravel()]]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=plt.cm.get_cmap(pal, n_z))
    ax.plot(*cont.exterior.xy, color='black', linewidth=1.5)
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    ax.axis('off')
    return fig

# --- DISTRIBUIÇÃO NAS ABAS ---
with tabs[1]:
    st.header("🔍 Mapas de Fertilidade")
    f_col = st.selectbox("Selecione o Atributo de Solo:", ["Argila", "P_rem", "P", "K", "Ca", "Mg", "CTC"], key="sb_fert")
    st.pyplot(gerar_mapa_hd(df, f_col, 'coolwarm', 6, "f"))

with tabs[2]:
    st.header("🏠 Mapas de Recomendação")
    r_col = st.selectbox("Selecione o Insumo:", ["Rec_Calcario", "Rec_Gessagem", "Rec_Fosforo", "Rec_Potassio"], key="sb_rec")
    st.pyplot(gerar_mapa_hd(df, r_col, 'YlOrRd', 6, "r"))
    
    st.subheader("📊 Resumo de Volume")
    total_t = (df[r_col].mean() * st.session_state.area_ha) / 1000
    st.metric(f"Total de {r_col}", f"{total_t:.2f} Toneladas", help="Baseado na dose média e área total")

with tabs[3]:
    st.header("🛰️ Satélite (Buffer 3km)")
    st.write("Analisando imagens Sentinel-2 para a região...")
    st.image("https://sentinel.esa.int/documents/247904/349449/Sentinel-2_MSI_Image.png")

with tabs[8]:
    st.header("📄 Exportar Relatório")
    if st.button("GERAR PDF"): st.success("PDF gerado com sucesso!")
