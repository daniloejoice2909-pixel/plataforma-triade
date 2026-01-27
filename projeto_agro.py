import streamlit as st
import pandas as pd
import numpy as np
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO VISUAL E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v60")

# Estilo de Fonte Open Sans e ajustes de interface visual
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN SEGURO (PROTEÇÃO CONTRA ERRO DE ARQUIVO) ---
if "password_correct" not in st.session_state:
    # Tenta carregar o logo, se falhar, usa texto para não dar erro de MediaFile
    logo_path = "LogoTriade.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)
    else:
        st.title("Tríade Agro Estratégica")
        st.info("Nota: Arquivo 'LogoTriade.png' não encontrado na pasta raiz.")
        
    if st.text_input("Acesso Danilo:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- TODAS AS ABAS RESTAURADAS ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Atributos", "🏠 Dados", "🔍 Mapas de Solo", "🛰️ Satélites", 
    "🗺️ Zonas de Manejo", "🌱 Semeadura", "📄 Relatório PDF"
])

# --- ABA 0: ATRIBUTOS COMPLETOS (CONFORME SOLICITADO) ---
with t_attr:
    st.header("Configurações Técnicas de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        ca_alvo = st.number_input("Cálcio (Ca) Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio (Mg) Alvo na CTC (%)", value=18.0)
        prnt = st.number_input("PRNT (%)", value=80.0)
        cao, mgo = st.number_input("Teor CaO (%)", 36.0), st.number_input("Teor MgO (%)", 9.0)
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")
    with c2:
        st.subheader("🌾 Fósforo (P) - Classes P-rem")
        f_m_argilo, f_argilo = st.number_input("Fator M. Arg (>60%)", 6.0), st.number_input("Fator Arg (35-60%)", 4.0)
        f_medio, f_arenoso = st.number_input("Fator Médio (15-35%)", 2.5), st.number_input("Fator Arenoso (<15%)", 1.5)
        st.write("**Níveis Críticos (mg/dm³)**")
        nc_p = [st.number_input(f"P-rem {i}", value=v) for i,v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]
    with c3:
        st.subheader("🍌 Potássio & Metas")
        sat_k_alvo = st.number_input("Saturação K Alvo (%)", value=3.2)
        meta_prod = st.number_input("Meta (sc/ha)", value=80.0)
        exp_k2o = st.number_input("Exportação K2O (kg/sc)", value=0.5)

# --- ABA 1: DADOS (BLINDAGEM CONTRA 'SD-04' E ALINHAMENTO) ---
if "df" not in st.session_state: st.session_state.df = None
with t_dados:
    u_ex = st.file_uploader("Planilha Excel (Sequência Identificada)", type=["xlsx"])
    if u_ex:
        df_raw = pd.read_excel(u_ex)
        # Limpeza de strings e normalização
        for col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')
        df_raw = df_raw.dropna(how='all').fillna(0).reset_index(drop=True)
        
        # Mapeamento por posição (evita erro de nome de coluna)
        mapping = {df_raw.columns[0]:'Lat', df_raw.columns[1]:'Lon', df_raw.columns[4]:'Argila', 
                   df_raw.columns[5]:'P-rem', df_raw.columns[6]:'P', df_raw.columns[7]:'Ca', 
                   df_raw.columns[8]:'Mg', df_raw.columns[9]:'K'}
        for c in df_raw.columns: 
            if 'CTC' in str(c).upper(): mapping[c] = 'CTC'
        
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw
        st.success("Planilha processada com sucesso!")

# --- MOTOR DE CÁLCULO v60 ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    ctc = df['CTC'].values
    
    # 1. Calcário (Bases)
    nec_ca = ((ca_alvo * ctc / 100) - df['Ca'].values) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - df['Mg'].values) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)
    
    # 2. Potássio (Saturação)
    df['Rec_K2O'] = (((sat_k_alvo * ctc / 100) - df['K'].values) * 940).clip(min=0) + (meta_prod * exp_k2o)

    # Regra de Ocultação: Se a soma for zero, não exibe mapa na aba Solo
    with t_solo:
        for c in ['Rec_Calc', 'Rec_K2O']:
            if df[c].sum() > 0:
                st.write(f"### Mapa de Recomendação: {c}")
                # Código de plotagem aqui...
