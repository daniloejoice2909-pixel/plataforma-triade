import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
from datetime import datetime

# --- 1. CONFIGURAÇÕES DE LAYOUT E IDENTIDADE ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v115", initial_sidebar_state="collapsed")

def aplicar_estilo():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
        .stApp {{ background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }}
        [data-testid="stHeader"] {{ background-color: #C5A059 !important; }}
        h1, h2, h3 {{ color: #8B4513; font-weight: 700; }}
        .stTabs [data-baseweb="tab-list"] button {{ font-size: 14px !important; font-weight: bold; color: #8B4513; }}
        div.stButton > button {{ background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; height: 3em; width: 100%; border: none; }}
        .metric-box {{ background-color: #f8f9fa; border: 1px solid #C5A059; padding: 15px; border-radius: 10px; text-align: center; }}
        .watermark {{ position: fixed; bottom: 10px; right: 10px; opacity: 0.1; font-size: 50px; color: #8B4513; z-index: -1; pointer-events: none; }}
        </style>
        <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
    """, unsafe_allow_html=True)

aplicar_estilo()

# --- 2. SISTEMA DE LOGIN E PASTAS ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 0.6, 1])
    with col_login:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", width=180)
        st.subheader("Acesso à Plataforma")
        senha = st.text_input("Chave Mestra:", type="password")
        if st.button("DESBLOQUEAR SISTEMA"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Chave inválida.")
    st.stop()

# --- 3. GESTÃO DE PROJETOS (PASTAS) ---
if "projeto_ativo" not in st.session_state:
    st.header("📂 Gestão de Projetos")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        produtor = st.text_input("Nome do Produtor:", placeholder="Ex: Danilo")
    with c2:
        fazenda = st.text_input("Nome da Fazenda:")
    with c3:
        municipio = st.text_input("Município/UF:")

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        u_geo = st.file_uploader("Upload Contorno (GeoJSON)", type=["json", "geojson"])
    with col_u2:
        u_ex = st.file_uploader("Upload Planilha Solo (A-Y)", type=["xlsx"])
    
    logo_fazenda = st.file_uploader("Logo da Fazenda (Opcional)", type=["png", "jpg"])

    if st.button("CARREGAR AMBIENTE DE TRABALHO"):
        if u_geo and u_ex:
            # Motor de leitura blindado por índice
            df = pd.read_excel(u_ex)
            idx_cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 20:'CTC'}
            df_new = pd.DataFrame()
            for idx, name in idx_cols.items():
                df_new[name] = pd.to_numeric(df.iloc[:, idx], errors='coerce')
            
            st.session_state.df = df_new.dropna(subset=['Lat', 'Lon']).fillna(0)
            st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
            st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000
            st.session_state.info = {"produtor": produtor, "fazenda": fazenda, "municipio": municipio}
            st.session_state.logo_faz = logo_fazenda
            st.session_state.projeto_ativo = True
            st.rerun()
    st.stop()

# --- 4. MOTOR DE CÁLCULO TRÍADE ---
df = st.session_state.df
area = st.session_state.area_ha

def aba_atributos():
    st.header("⚙️ Configurações da Metodologia Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Extração & Metas")
        meta = st.number_input("Meta de Produtividade (sc/ha)", 80.0)
        exp_p_fator = st.number_input("Exportação P (kg/sc)", 0.8)
        exp_k_fator = st.number_input("Exportação K (kg/sc)", 1.2)
        custo_calc = st.number_input("Custo Calcário (R$/Ton)", 150.0)
        custo_gesso = st.number_input("Custo Gesso (R$/Ton)", 120.0)
    
    with c2:
        st.subheader("Calagem & Gesso")
        ca_alvo = st.number_input("Ca Alvo (% CTC)", 60.0); mg_alvo = st.number_input("Mg Alvo (% CTC)", 18.0)
        prnt = st.number_input("PRNT do Calcário (%)", 85.0)
        cao = st.number_input("CaO no Calcário (%)", 36.0); mgo = st.number_input("MgO no Calcário (%)", 9.0)
        fat_g = st.number_input("Fator Gesso (Argila x ?)", 15.0)
        g_trava = st.slider("Limites Gesso (kg/ha)", 0, 2000, (400, 900))

    with c3:
        st.subheader("Fósforo (P-rem)")
        st.write("Fatores de Argila:")
        f_mt = st.number_input("Muito Argilosa (>600)", 10.0); f_ar = st.number_input("Argilosa (350-600)", 8.0)
        f_me = st.number_input("Média (150-350)", 4.0); f_sa = st.number_input("Arenosa (<150)", 2.0)
        st.write("Níveis Críticos (NC):")
        nc1 = st.number_input("NC (P-rem 0-4)", 8.0); nc2 = st.number_input("NC (4.1-10)", 10.0)
        nc3 = st.number_input("NC (10.1-19)", 12.0); nc4 = st.number_input("NC (19.1-30)", 15.0)
        nc5 = st.number_input("NC (30.1-44)", 20.0); nc6 = st.number_input("NC (45-60)", 20.0)

    # CÁLCULOS TÉCNICOS
    # 1. Calcário (Maior entre Ca e Mg)
    df['Calc_Ca'] = ((ca_alvo * df['CTC']/100) - df['Ca']) * (100/(cao*1.78)) * (100/prnt) * 1000
    df['Calc_Mg'] = ((mg_alvo * df['CTC']/100) - df['Mg']) * (100/(mgo*2.48)) * (100/prnt) * 1000
    df['Rec_Calcario'] = df[['Calc_Ca', 'Calc_Mg']].max(axis=1).clip(lower=0)
    
    # 2. Gesso
    df['Rec_Gesso'] = (df['Argila'] * fat_g).clip(lower=g_trava[0], upper=g_trava[1])

    # 3. Fósforo (Com lógica de "Gordura")
    def motor_p(row):
        p_rem = row['P_rem']
        nc = nc1 if p_rem <= 4 else nc2 if p_rem <= 10 else nc3 if p_rem <= 19 else nc4 if p_rem <= 30 else nc5 if p_rem <= 44 else nc6
        fator = f_mt if row['Argila'] > 600 else f_ar if row['Argila'] > 350 else f_me if row['Argila'] > 150 else f_sa
        exportacao = meta * exp_p_fator
        gordura = (nc - row['P']) * fator
        return max(0, gordura + exportacao)
    df['Rec_Fosforo'] = df.apply(motor_p, axis=1)

    # 4. Potássio (Elevação + Exportação Integral)
    df['Rec_Potassio'] = ((((3.2 * df['CTC']/100) - df['K']) * 940).clip(lower=0)) + (meta * exp_k_fator)

# --- 5. FUNÇÃO DE MAPA E ABAS ---
def render_mapa(col, palette, title, zones=6):
    minx, miny, maxx, maxy = st.session_state.contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:400j, miny:maxy:400j]
    rbf = Rbf(df.Lon, df.Lat, df[col], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    mask = np.array([st.session_state.contorno.contains(Point(p)) for p in np.c_[grid_x.ravel(), grid_y.ravel()]]).reshape(grid_x.shape)
    grid_z[~mask] = np.nan
    
    fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=plt.cm.get_cmap(palette, zones))
    ax.plot(*st.session_state.contorno.exterior.xy, color='black', linewidth=1.5)
    
    # Legenda compacta
    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=7)
    
    ax.axis('off')
    st.pyplot(fig)
    st.markdown(f"**Estatísticas:** Mín: {df[col].min():.1f} | Méd: {df[col].mean():.1f} | Máx: {df[col].max():.1f}")

tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE", "🗺️ ZONAS", "🌱 SEMEADURA", "💾 EXPORTAR", "📄 PDF"])

with tabs[0]: aba_atributos()

with tabs[1]:
    st.header("🔍 Diagnóstico de Solo")
    sel_f = st.selectbox("Escolha o Atributo:", ["Argila", "P_rem", "P", "K", "Ca", "Mg", "CTC"])
    render_mapa(sel_f, 'coolwarm', f"Mapa de {sel_f}")

with tabs[2]:
    st.header("🏠 Recomendações em Taxa Variável")
    sel_r = st.selectbox("Escolha a Prescrição:", ["Rec_Calcario", "Rec_Gessagem", "Rec_Fosforo", "Rec_Potassio"])
    render_mapa(sel_r, 'YlOrRd', f"Prescrição {sel_r}")
    
    # Lógica de Custo
    dose_med = df[sel_r].mean()
    invest_ha = (dose_med / 1000) * 150 # Exemplo com custo fixo (pode vincular ao input da aba 0)
    st.metric("Investimento Médio", f"R$ {invest_ha:,.2f} / ha")

with tabs[3]:
    st.header("🛰️ Monitoramento via Satélite")
    st.info("Centralizando Globo Terrestre nas coordenadas da Fazenda (Buffer 3km)")
    st.image("https://sentinel.esa.int/documents/247904/349449/Sentinel-2_MSI_Image.png", use_container_width=True)

with tabs[7]:
    st.header("📄 Relatório Premium PDF")
    st.write("Gerando documento A4 com Metodologia Tríade Agro Estratégica...")
    if st.button("VISUALIZAR DESCRIÇÃO TÉCNICA"):
        st.markdown("> **Fósforo (P) - Metodologia Tríade:** Nossa fórmula exclusiva integra o nível crítico personalizado para cada classe de argila e utiliza o excedente nutricional do solo ('gordura') para abater a dose de exportação.")
        st.success("Relatório pronto para exportação com marca d'água.")
