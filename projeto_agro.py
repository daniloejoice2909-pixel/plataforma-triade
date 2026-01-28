import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from shapely.geometry import shape

# --- 1. IDENTIDADE VISUAL & ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

st.markdown("""
    <style>
    .stApp { background-color: #E6D5AC; } /* Fundo Dourado Grão */
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. PÁGINA DE ENTRADA (LOGIN) ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists("LogoTriadeagro.png"):
            st.image("LogoTriadeagro.png", use_container_width=True)
        else:
            st.title("TRÍADE AGRO ESTRATÉGICA")
        
        st.subheader("Acesso Restrito")
        senha = st.text_input("Senha de Acesso:", type="password")
        if st.button("Entrar"):
            if senha == "triade2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# --- 3. SEGUNDA PÁGINA: CARREGAMENTO E DADOS DO PRODUTOR ---
if "df" not in st.session_state:
    st.header("📥 Configuração de Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Subir Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Subir Planilha (Sequência A-Y)", type=["xlsx"])
    with c2:
        st.session_state.produtor = st.text_input("Nome do Produtor:")
        st.session_state.fazenda = st.text_input("Fazenda:")
        st.session_state.municipio = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        # MAPEAMENTO RIGOROSO DO SCRIPT 1.0 (A=0 até Y=24)
        mapping = {
            df_raw.columns[0]: 'Lat', df_raw.columns[1]: 'Lon', df_raw.columns[2]: 'Campo',
            df_raw.columns[3]: 'Ponto', df_raw.columns[4]: 'Argila', df_raw.columns[5]: 'P-rem',
            df_raw.columns[6]: 'P', df_raw.columns[7]: 'Ca', df_raw.columns[8]: 'Mg',
            df_raw.columns[9]: 'K', df_raw.columns[20]: 'CTC'
        }
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        # Área do Contorno
        geo_data = json.load(u_geo)
        st.session_state.contorno = shape(geo_data['features'][0]['geometry'])
        st.success("✅ Dados alinhados com sucesso!")
        if st.button("Iniciar Consultoria"): st.rerun()
    st.stop()

# --- 4. PLATAFORMA ABERTA (ABAS) ---
t_attr, t_fert, t_recom, t_sat, t_zonas, t_rstv, t_rntv, t_rdtv, t_pdf = st.tabs([
    "⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações", "🛰️ Satélite", 
    "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório Final"
])

# --- ABA ATRIBUTOS (FÓRMULAS E VALORES DO SCRIPT) ---
with t_attr:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        cao_p, mgo_p, prnt_p = st.number_input("CaO%", 36.0), st.number_input("MgO%", 9.0), st.number_input("PRNT%", 80.0)
        ca_alvo, mg_alvo = st.number_input("Ca% desejado (CTC)", 60.0), st.number_input("Mg% desejado (CTC)", 18.0)
        g_max, g_min = st.number_input("Gesso Max (kg/ha)", 900), st.number_input("Gesso Min (kg/ha)", 400)
    with c2:
        st.subheader("🌾 Fósforo (Fatores Solo)")
        f_mt_arg, f_arg, f_med, f_are = st.number_input("M. Arg", 10.0), st.number_input("Arg", 8.0), st.number_input("Méd", 4.0), st.number_input("Are", 2.0)
        p2o5_adubo = st.number_input("% P2O5 Adubo", 46.0)
        fator_p = st.number_input("Fator P kg/sc", 0.8)
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k_ctc_alvo = st.number_input("K% desejado (CTC)", 3.2)
        prod_meta = st.number_input("Produtividade (sc/ha)", 80.0)
        fator_k = st.number_input("Fator K kg/sc", 1.2)

# --- MOTOR DE CÁLCULO (LÓGICA DESCRITA NO SEU TEXTO) ---
df = st.session_state.df
ctc = df['CTC']

# CALCÁRIO: Maior entre Ca e Mg | ADICIONAL EDITÁVEL
adicional_calc = st.sidebar.number_input("Adicional Calcário (t/ha)", 0.0)
nec_ca = ((ca_alvo * ctc / 100) - df['Ca']) * 100 / (cao_p * 1.78 * prnt_p / 100)
nec_mg = ((mg_alvo * ctc / 100) - df['Mg']) * 100 / (mgo_p * 2.48 * prnt_p / 100)
df['Rec_Calcario'] = (np.maximum(nec_ca, nec_mg) + adicional_calc).clip(min=0)

# GESSO: Argila (g/kg) * 15 | Limites 400-900
df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)

# POTÁSSIO: Elevação + Exportação (Sempre soma a exportação)
df['Rec_K2O'] = (((k_ctc_alvo * ctc / 100) - df['K']) * 940).clip(min=0) + (prod_meta * fator_k)

# --- ABA SATÉLITE (SENTINEL-2) ---
with t_sat:
    st.subheader("🛰️ Busca de Imagens Sentinel-2")
    c_dat1, c_dat2 = st.columns(2)
    data_i = c_dat1.date_input("Data Inicial")
    data_f = c_dat2.date_input("Data Final")
    st.selectbox("Seletor de Imagens (Menor interferência de nuvens)", ["Buscando imagens..."])
    st.radio("Índice:", ["NDVI", "NDVI Contrastado", "NDRE", "Brilho de Solo"])

# --- ABA RELATÓRIO PDF ---
with t_pdf:
    st.subheader("📄 Geração de Relatório Técnico")
    if st
