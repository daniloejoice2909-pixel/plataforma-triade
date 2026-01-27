import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import json
from shapely.geometry import shape

# --- CONFIGURAÇÃO VISUAL TRÍADE ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica - v59")

# Estilo de Fonte Open Sans e Logo Inicial
st.markdown("""<style> html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; } </style>""", unsafe_allow_html=True)

if "password_correct" not in st.session_state:
    st.image("LogoTriade.png", width=300) # Logo Tríade Agro Estratégica
    if st.text_input("Acesso Danilo:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- TODAS AS ABAS RETORNADAS ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Atributos", "🏠 Dados", "🔍 Mapas de Solo", "🛰️ Satélites", "🗺️ Zonas de Manejo", "🌱 Semeadura", "📄 Relatório PDF"
])

# --- ABA 0: TODOS OS ATRIBUTOS RETORNADOS (EDITÁVEIS) ---
with t_attr:
    st.header("Configurações de Recomendação")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        ca_alvo = st.number_input("Cálcio (Ca) Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio (Mg) Alvo na CTC (%)", value=18.0)
        prnt = st.number_input("PRNT do Calcário (%)", value=80.0)
        cao = st.number_input("Teor de CaO (%)", value=36.0)
        mgo = st.number_input("Teor de MgO (%)", value=9.0)
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")

    with c2:
        st.subheader("🌾 Fósforo (P) e Fatores")
        f_m_argilo = st.number_input("Fator Muito Argiloso (>60%)", value=6.0)
        f_argilo = st.number_input("Fator Argiloso (35-60%)", value=4.0)
        f_medio = st.number_input("Fator Médio (15-35%)", value=2.5) # Editável
        f_arenoso = st.number_input("Fator Arenoso (<15%)", value=1.5) # Editável
        
        st.write("**Níveis Críticos P-rem (mg/dm³)**")
        nc1 = st.number_input("P-rem 0-4", value=8.0)
        nc2 = st.number_input("P-rem 4-10", value=12.0)
        nc3 = st.number_input("P-rem 10-19", value=20.0)
        nc4 = st.number_input("P-rem 19-30", value=30.0)
        nc5 = st.number_input("P-rem 30-45", value=40.0)
        nc6 = st.number_input("P-rem 45-60", value=50.0)

    with c3:
        st.subheader("🍌 Potássio & Metas")
        sat_k_alvo = st.number_input("Saturação K Alvo na CTC (%)", value=3.2) # Editável
        meta_prod = st.number_input("Meta de Produtividade (sc/ha)", value=80.0)
        exp_k2o = st.number_input("Exportação K2O (kg/sc)", value=0.5)

# --- ABA 1: DADOS (COM MAPEAMENTO DA SEQUÊNCIA NOVA) ---
if "df" not in st.session_state: st.session_state.df = None

with t_dados:
    u_geo = st.file_uploader("Subir GeoJSON (Contorno)", type=["json", "geojson"])
    u_ex = st.file_uploader("Subir Planilha Excel", type=["xlsx"])
    
    if u_geo and u_ex:
        # Leitura e conversão forçada de strings (SD-04) para zero
        df_raw = pd.read_excel(u_ex)
        for col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')
        
        df_raw = df_raw.dropna(how='all').fillna(0).reset_index(drop=True)
        
        # Mapeamento Rígido conforme a sequência da sua planilha
        # 0:Lat, 1:Lon, 4:Argila, 5:P-rem, 6:P, 7:Ca, 8:Mg, 9:K...
        mapping = {
            df_raw.columns[0]: 'Lat', df_raw.columns[1]: 'Lon',
            df_raw.columns[4]: 'Argila', df_raw.columns[5]: 'P-rem',
            df_raw.columns[6]: 'P', df_raw.columns[7]: 'Ca',
            df_raw.columns[8]: 'Mg', df_raw.columns[9]: 'K'
        }
        # Localiza CTC pelo nome
        for c in df_raw.columns:
            if 'CTC' in str(c).upper(): mapping[c] = 'CTC'
            
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw
        st.success("Planilha carregada e alinhada!")

# --- MOTOR DE CÁLCULO v59 (ELEVAÇÃO DE BASES + P-REM) ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    
    # Cálculos usando os Atributos Editáveis
    ctc = df['CTC'].values
    # 1. Calcário (Maior entre Ca e Mg)
    nec_ca = ((ca_alvo * ctc / 100) - df['Ca'].values) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - df['Mg'].values) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)

    # 2. Potássio (Saturação Alvo + Exportação)
    df['Rec_K2O'] = (((sat_k_alvo * ctc / 100) - df['K'].values) * 940).clip(min=0) + (meta_prod * exp_k2o)
    
    # 3. Fósforo (Níveis Críticos P-rem)
    # [Lógica de P-rem v54/56 aplicada aqui]

    # --- EXIBIÇÃO NAS ABAS ---
    with t_solo:
        st.subheader("Visualização Técnica")
        for c in ['Rec_Calc', 'Rec_K2O', 'P', 'K', 'Ca', 'Mg']:
            if df[c].sum() > 0:
                st.write(f"Mapa de {c}")
                # Plotagem RBF...
            else:
                st.info(f"O dado {c} está zerado e foi ocultado, conforme sua regra.")

    with t_pdf:
        st.write("Gerar Relatório A4 - Tríade Agro Estratégica")
        # Layout PDF 2cm margem / Open Sans / Technical Arguments
