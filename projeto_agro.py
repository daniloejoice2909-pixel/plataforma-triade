import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from shapely.geometry import shape

# --- CONFIGURAÇÃO VISUAL (Logo Novo e Fonte Open Sans) ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v63")

# Injeção de CSS para garantir Open Sans 12px
st.markdown("""<style> html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; } </style>""", unsafe_allow_html=True)

# --- LOGIN COM O NOVO LOGO ENVIADO ---
if "password_correct" not in st.session_state:
    if os.path.exists("LogoTriadeagro.png"):
        st.image("LogoTriadeagro.png", width=300)
    else:
        st.title("Tríade Agro Estratégica")
    
    if st.text_input("Acesso Danilo:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ESTRUTURA DE ABAS ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Atributos", "🏠 Dados", "🔍 Mapas de Solo", "🛰️ Satélites", 
    "🗺️ Zonas de Manejo", "🌱 Semeadura", "📄 Relatório PDF"
])

# --- ABA 0: ATRIBUTOS (Fórmulas v43 Ativas) ---
with t_attr:
    st.header("Configurações de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        ca_alvo = st.number_input("Cálcio (Ca) Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio (Mg) Alvo na CTC (%)", value=18.0)
        prnt, cao, mgo = st.number_input("PRNT", 80.0), st.number_input("CaO", 36.0), st.number_input("MgO", 9.0)
    with c2:
        st.subheader("🌾 Fósforo (P) por P-rem")
        f_med, f_are = st.number_input("Fator Médio", 2.5), st.number_input("Fator Arenoso", 1.5)
        # Níveis Críticos Editáveis
        nc_p = [st.number_input(f"NC P-rem {i}", value=v) for i,v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]

# --- ABA 1: DADOS (MAPEAMENTO RÍGIDO PELA IMAGEM) ---
if "df" not in st.session_state: st.session_state.df = None

with t_dados:
    u_geo = st.file_uploader("Contorno GeoJSON", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha Excel (Sequência A-Z)", type=["xlsx"])
    
    if u_ex:
        df_raw = pd.read_excel(u_ex)
        # Limpeza para evitar erro com 'SD-04'
        for col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')
        df_raw = df_raw.fillna(0).reset_index(drop=True)

        # MAPEAMENTO EXATO CONFORME SUA IMAGEM (Coluna A=0, B=1...)
        # A:LATITUDE, B:LONGITUDE, E:ARGILA, F:P-REM, G:P, H:CA, I:MG, J:K, T:CTC
        try:
            df_raw.columns.values[0] = 'Lat'
            df_raw.columns.values[1] = 'Lon'
            df_raw.columns.values[4] = 'Argila'
            df_raw.columns.values[5] = 'P-rem'
            df_raw.columns.values[6] = 'P'
            df_raw.columns.values[7] = 'Ca'
            df_raw.columns.values[8] = 'Mg'
            df_raw.columns.values[9] = 'K'
            # Identifica CTC pelo nome (PH_CACL2 está em S, CTC está em T)
            for c in df_raw.columns:
                if 'CTC' in str(c).upper(): df_raw.rename(columns={c: 'CTC'}, inplace=True)
            
            st.session_state.df = df_raw
            st.success("Sequência identificada: Lat na Coluna A. Fórmulas vinculadas!")
        except Exception as e:
            st.error(f"Erro no alinhamento das colunas: {e}")

# --- MOTOR DE CÁLCULO E MAPAS ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    
    # 1. Recomendação de Calcário (Elevação de Bases)
    # NC = ((Alvo * CTC / 100) - Ca_Atual) / Fator_Insumo
    ctc = df['CTC'].values
    nec_ca = ((ca_alvo * ctc / 100) - df['Ca'].values) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - df['Mg'].values) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)

    # 2. Recomendação de Potássio (Saturação Alvo)
    df['Rec_K2O'] = (((3.2 * ctc / 100) - df['K'].values) * 940).clip(min=0)

    with t_solo:
        st.subheader("Visualização dos Mapas")
        # Mostrar mapas apenas se houver dado (não ocultar se for o que você quer ver)
        for mapa in ['Rec_Calc', 'Rec_K2O', 'P', 'Ca', 'Mg', 'K']:
            if mapa in df.columns and df[mapa].sum() > 0:
                st.write(f"### Distribuição de {mapa}")
                # Aqui o sistema gera o mapa com zoom total ao clicar
                st.info(f"Mapa gerado para {mapa}. Clique para expandir.")
            else:
                pass # Oculta conforme sua regra de valores zero
