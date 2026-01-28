import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from shapely.geometry import shape

# --- 1. IDENTIDADE VISUAL & ESTILO (FUNDO BRANCO) ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; } /* Fundo Branco conforme solicitado */
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. PÁGINA DE ENTRADA (LOGIN) ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Nome do arquivo atualizado conforme informado
        logo_path = "LogoTriadeagro.png.png"
        
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.markdown("<h1 style='text-align: center; color: #8B4513;'>TRÍADE AGRO</h1>", unsafe_allow_html=True)
            st.info(f"Aguardando logo: {logo_path}")
        
        st.subheader("Acesso Restrito")
        senha = st.text_input("Senha de Acesso:", type="password")
        if st.button("Entrar"):
            if senha == "triade2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# --- 3. SEGUNDA PÁGINA: CARREGAMENTO (SEQUÊNCIA A-Y) ---
if "df" not in st.session_state:
    st.header("📥 Configuração de Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Subir Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Subir Planilha (Sequência A-Y)", type=["xlsx"])
    with c2:
        produtor = st.text_input("Nome do Produtor:")
        fazenda = st.text_input("Fazenda:")
        municipio = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        # Mapeamento rigoroso conforme script 1.0
        mapping = {
            df_raw.columns[0]: 'Lat', df_raw.columns[1]: 'Lon',
            df_raw.columns[4]: 'Argila', df_raw.columns[5]: 'P-rem',
            df_raw.columns[6]: 'P', df_raw.columns[7]: 'Ca',
            df_raw.columns[8]: 'Mg', df_raw.columns[9]: 'K',
            df_raw.columns[20]: 'CTC'
        }
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        geo_data = json.load(u_geo)
        st.session_state.contorno = shape(geo_data['features'][0]['geometry'])
        st.success("✅ Dados e Logo configurados!")
        if st.button("Abrir Plataforma"):
            st.rerun()
    st.stop()

# --- 4. PLATAFORMA ABERTA (RESTAURADO) ---
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações", "🛰️ Satélite", 
                "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório Final"])

# ... O restante do motor de cálculo segue com a correção .clip(lower=0) ...
