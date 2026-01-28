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
    </style>
    """, unsafe_allow_html=True)

# --- 2. PÁGINA DE ENTRADA (LOGIN) ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists("LogoTriadeagro.png"):
            st.image("LogoTriadeagro.png", use_container_width=True)
        else:
            st.markdown("<h1 style='text-align: center; color: #8B4513;'>TRÍADE AGRO</h1>", unsafe_allow_html=True)
        
        st.subheader("Acesso Restrito")
        senha = st.text_input("Senha de Acesso:", type="password")
        if st.button("Entrar"):
            if senha == "triade2026":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

# --- 3. SEGUNDA PÁGINA: CARREGAMENTO ---
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
        # MAPEAMENTO RIGOROSO (A=0 até Y=24)
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
        st.success("✅ Dados alinhados!")
        if st.button("Abrir Plataforma"):
            st.rerun()
    st.stop()

# --- 4. PLATAFORMA ABERTA (ABAS) ---
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações", "🛰️ Satélite", 
                "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório Final"])

with tabs[0]: # Atributos
    st.header("Parâmetros Técnicos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        cao_p = st.number_input("CaO%", 36.0)
        mgo_p = st.number_input("MgO%", 9.0)
        prnt_p = st.number_input("PRNT%", 80.0)
        ca_alvo = st.number_input("Ca% alvo na CTC", 60.0)
        mg_alvo = st.number_input("Mg% alvo na CTC", 18.0)
        g_max = st.number_input("Gesso Max (kg/ha)", 900)
    with c2:
        st.subheader("🌾 Fósforo")
        f_mt_arg = st.number_input("Fator Muito Argiloso", 10.0)
        f_arg = st.number_input("Fator Argiloso", 8.0)
        f_med = st.number_input("Fator Médio", 4.0)
        f_are = st.number_input("Fator Arenoso", 2.0)
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k_alvo = st.number_input("K% alvo na CTC", 3.2)
        prod_meta = st.number_input("Meta Produtividade (sc/ha)", 80.0)
        fator_k = st.number_input("Fator K (kg/sc)", 1.2)

with tabs[2]: # Recomendações
    st.header("Motor de Recomendações")
    df = st.session_state.df
    ctc = df['CTC']
    
    # Calcário: Maior dose entre Elevação de Ca e Mg
    nec_ca = ((ca_alvo * ctc / 100) - df['Ca']) * 100 / (cao_p * 1.78 * prnt_p / 100)
    nec_mg = ((mg_alvo * ctc / 100) - df['Mg']) * 100 / (mgo_p * 2.48 * prnt_p / 100)
    df['Rec_Calcario'] = np.maximum(nec_ca, nec_mg).clip(min=0)
    
    # Gesso: Argila (g/kg) * 15
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(upper=g_max)
    
    # Potássio: Elevação + Exportação
    df['Rec_K2O'] = (((k_alvo * ctc / 100) - df['K']) * 940).clip(min=0) + (prod_meta * fator_k)
    
    st.write("Cálculos de recomendação processados com sucesso.")
    st.dataframe(df[['Lat', 'Lon', 'Rec_Calcario', 'Rec_Gesso', 'Rec_K2O']].head())

with tabs[3]: # Satélite
    st.subheader("🛰️ Integração Sentinel-2")
    st.date_input("Data Inicial")
    st.date_input("Data Final")
    st.info("O sistema buscará imagens para as coordenadas da fazenda.")

with tabs[8]: # Relatório
    st.subheader("📄 Exportação")
    if st.button("Gerar Relatório Técnico"):
        st.success("PDF pronto para download.")
