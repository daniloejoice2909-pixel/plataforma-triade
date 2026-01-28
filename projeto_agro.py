import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import plotly.express as px
from shapely.geometry import shape
from scipy.interpolate import Rbf

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 18px !important; } 
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; }
    h1, h2, h3 { color: #8B4513; }
    .stNumberInput label, .stTextInput label { font-size: 16px !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- PÁGINA 1: LOGIN ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        logo = "LogoTriadeagro.png.png"
        if os.path.exists(logo): 
            st.image(logo, width=220)
        st.markdown("<h2 style='text-align: center;'>Acesso Master</h2>", unsafe_allow_html=True)
        senha = st.text_input("Senha de Acesso:", type="password")
        if st.button("Entrar na Plataforma"):
            if senha == "triade2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("Senha incorreta.")
    st.stop()

# --- PÁGINA 2: CARREGAMENTO ---
if "df" not in st.session_state:
    st.header("📥 Configuração de Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Subir Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Subir Planilha Solo (Sequência A-Y)", type=["xlsx"])
    with c2:
        st.session_state.produtor = st.text_input("Nome do Produtor:")
        st.session_state.fazenda = st.text_input("Fazenda:")
        st.session_state.municipio = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        # MAPEAMENTO RIGOROSO A-Y
        cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 
                10:'Al', 11:'H_Al', 12:'S', 13:'B', 14:'Mn', 15:'Zn', 16:'Cu', 17:'Fe', 
                18:'Mo', 19:'pH', 20:'CTC', 21:'Ca_perc', 22:'Mg_perc', 23:'K_perc', 24:'CaMg'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        geo_data = json.load(u_geo)
        st.session_state.contorno = shape(geo_data['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        
        st.success(f"✅ Projeto {st.session_state.fazenda} carregado com {st.session_state.area_ha:.2f} ha.")
        if st.button("Abrir Painel de Controle"): st.rerun()
    st.stop()

# --- PÁGINA 3: PLATAFORMA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

# --- ABA 0: ATRIBUTOS (FÓSFORO REMANESCENTE) ---
with tabs[0]:
    st.header("🛠️ Parâmetros Técnicos")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.subheader("🧪 Calcário & Gesso")
        cao = st.number_input("CaO % (Insumo)", 36.0); mgo = st.number_input("MgO %", 9.0)
        prnt = st.number_input("PRNT %", 80.0); ca_alvo = st.number_input("Ca% Alvo na CTC", 60.0)
        mg_alvo = st.number_input("Mg% Alvo na CTC", 18.0)
        g_max = st.number_input("Limite Gesso Max (kg/ha)", 900); g_min = st.number_input("Limite Gesso Min (kg/ha)", 400)
    with col_b:
        st.subheader("🌾 Fósforo (P-rem)")
        p2o5_ad = st.number_input("% P2O5 do Adubo", 21.0); fat_p_sc = st.number_input("Fator P (kg/sc)", 0.8)
        st.write("**Fator Classe de Solo (Multiplicador):**")
        f_mtarg = st.number_input("M. Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0)
        f_med = st.number_input("Médio", 4.0); f_are = st.number_input("Arenoso", 2.0)
        st.write("**Níveis Críticos por Classe P-rem:**")
        nc1 = st.number_input("0 a 4 (P-rem)", 8.0); nc2 = st.number_input("4,1 a 10", 10.0)
        nc3 = st.number_input("10,1 a 19", 12.0); nc4 = st.number_input("19,1 a 30", 15.0)
        nc5 = st.number_input("30,1 a 45", 20.0); nc6 = st.number_input("45 a 60", 25.0)
    with col_c:
        st.subheader("🍌 Potássio & Metas")
        k2o_ad = st.number_input("% K2O Adubo", 60.0); k_alvo = st.number_input("K% Alvo na CTC", 3.2)
        prod_meta = st.number_input("Meta de Produtividade (sc/ha)", 80.0); fat_k_sc = st.number_input("Fator K (kg/sc)", 1.2)

# --- ABA 2: RECOMENDAÇÕES (O MOTOR) ---
with tabs[2]:
    st.header("🏠 Recomendações em Taxa Variável")
    adic_calc = st.number_input("Adicional de Calcário (t/ha)", 0.0)

    # 1. CÁLCULO CALCÁRIO
    nec_ca = ((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = (np.maximum(nec_ca, nec_mg) + adic_calc).clip(lower=0)

    # 2. CÁLCULO GESSO (Argila g/kg * 15)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)

    # 3. CÁLCULO POTÁSSIO (Elevação + Exportação)
    df['Rec_K2O'] = (((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (prod_meta * fat_k_sc)

    # VISUALIZAÇÃO EM 6 ZONAS
    sel = st.selectbox("Visualizar Mapa de Aplicação:", ["Rec_Calc", "Rec_Gesso", "Rec_K2O"])
    df['Zonas_Monitor'] = pd.qcut(df[sel], q=6, labels=False, duplicates='drop')
    
    fig = px.scatter_mapbox(df, lat="Lat", lon="Lon", color=df[sel], 
                            color_continuous_scale="RdYlGn_r", zoom=14, 
                            mapbox_style="carto-positron", title=f"Prescrição: {sel}")
    st.plotly_chart(fig, use_container_width=True)

# --- ABA 8: RELATÓRIO FINAL ---
with tabs[8]:
    st.header("📄 Relatório Técnico de Insumos")
    area = st.session_state.area_ha
    sumario = pd.DataFrame({
        "Insumo": ["Calcário", "Gesso", "Adubo Potássico (K2O)"],
        "Média (kg/ha)": [df['Rec_Calc'].mean()*1000, df['Rec_Gesso'].mean(), df['Rec_K2O'].mean()],
        "Total Necessário (ton)": [(df['Rec_Calc'].mean() * area), (df['Rec_Gesso'].mean() * area / 1000), (df['Rec_K2O'].mean() * area / 1000)]
    })
    st.table(sumario)
    if st.button("Gerar PDF A4"):
        st.success("PDF em processamento com justificativas técnicas...")
