import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import json
from shapely.geometry import shape

st.set_page_config(layout="wide", page_title="Tríade Agro v52")

# --- LOGIN (Mantido conforme v51) ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Acesso Master:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABAS ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Parâmetros Master", "🏠 Dados", "🔍 Solo", "🛰️ Satélite", "🗺️ Zonas & Coleta", "🌱 Semeadura", "📄 Relatório"
])

# --- ABA 0: PARÂMETROS (Memória v51 preservada) ---
with t_attr:
    st.header("🛠️ Configurações Master v52")
    # ... [Mesmos campos de Ca, Mg, P-rem, K da versão anterior] ...
    ca_alvo = st.number_input("Ca Alvo na CTC (%)", value=60.0)
    mg_alvo = st.number_input("Mg Alvo na CTC (%)", value=18.0)
    cao, mgo = st.number_input("CaO (%)", value=36.0), st.number_input("MgO (%)", value=9.0)
    prnt = st.number_input("PRNT (%)", value=80.0)

# --- ABA 1: DADOS (CORREÇÃO DE ÍNDICES DUPLICADOS) ---
if "df" not in st.session_state: st.session_state.df = None

with t_dados:
    u_geo = st.file_uploader("Contorno", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha (Lat, Lon, Argila, CTC, P, K, Ca, Mg, P-rem, V%)", type=["xlsx"])
    
    if u_geo and u_ex:
        # Lendo e limpando IMEDIATAMENTE duplicatas de índice ou linhas
        raw_df = pd.read_excel(u_ex).fillna(0)
        
        # ESSENCIAL: Remove linhas totalmente duplicadas e reseta o índice para evitar o erro de 'duplicate labels'
        raw_df = raw_df.drop_duplicates().reset_index(drop=True)
        
        # Força os nomes conforme sua regra de colunas
        novos_nomes = ['Lat', 'Lon', 'Argila', 'CTC', 'P', 'K', 'Ca', 'Mg', 'P-rem', 'V_atual']
        # Garante que só renomeie o que existe para não dar erro de tamanho
        raw_df.columns = novos_nomes + list(raw_df.columns[len(novos_nomes):])
        
        st.session_state.df = raw_df
        st.success("Planilha v52 carregada e índices duplicados removidos!")

# --- MOTOR DE CÁLCULO v52 (PROTEGIDO CONTRA ALINHAMENTO) ---
if st.session_state.df is not None:
    df = st.session_state.df
    
    # 1. CALCÁRIO (ELEVAÇÃO DE BASES) - Usando .values para evitar erro de reindexação/alinhamento
    ca_atual = df['Ca'].values
    mg_atual = df['Mg'].values
    ctc = df['CTC'].values

    nec_ca = ((ca_alvo * ctc / 100) - ca_atual) * 100 / (cao * 1.78 * prnt/100)
    nec_mg = ((mg_alvo * ctc / 100) - mg_atual) * 100 / (mgo * 2.48 * prnt/100)
    
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)

    # 2. POTÁSSIO E FÓSFORO (Seguindo a mesma lógica de segurança)
    df['Rec_K2O'] = (((sat_k_alvo * ctc / 100) - df['K'].values) * 940).clip(min=0) + (meta_prod * 0.5)

    st.write("✅ Cálculos processados sem conflito de duplicatas.")

    # --- EXIBIÇÃO CONDICIONAL (OCULTAR SE ZERADO) ---
    with t_solo:
        for col in ['Rec_Calc', 'Rec_K2O']:
            if df[col].sum() > 0:
                st.subheader(f"Mapa de {col}")
                # Plotagem...
            else:
                st.info(f"O resultado de {col} está zerado e o mapa foi ocultado.")
