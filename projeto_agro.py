import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import json
from shapely.geometry import shape

st.set_page_config(layout="wide", page_title="Tríade Agro v56")

# --- LOGIN (Acesso Master Danilo) ---
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

# --- ABA 0: PARÂMETROS (Restauração Completa v54/55) ---
with t_attr:
    st.header("🛠️ Painel Master v56")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário e Gesso")
        ca_alvo = st.number_input("Ca Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Mg Alvo na CTC (%)", value=18.0)
        prnt, cao, mgo = st.number_input("PRNT", 80.0), st.number_input("CaO", 36.0), st.number_input("MgO", 9.0)
        fator_gesso = st.number_input("Fator Gesso", value=0.015, format="%.3f")
    with c2:
        st.subheader("🌾 Fósforo (P-rem)")
        f_m_arg, f_arg, f_med, f_are = st.number_input("M.Arg", 6.0), st.number_input("Arg", 4.0), st.number_input("Med", 2.5), st.number_input("Are", 1.5)
        nc_p = [st.number_input(f"NC {i}", value=v) for i,v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]
    with c3:
        st.subheader("🍌 Potássio e Metas")
        sat_k_alvo = st.number_input("Sat. K Alvo (%)", 3.2)
        meta_prod = st.number_input("Meta (sc/ha)", 80.0)

# --- ABA 1: DADOS (LIMPEZA DE TEXTO 'SD-04') ---
if "df" not in st.session_state: st.session_state.df = None

with t_dados:
    u_geo = st.file_uploader("Contorno", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha (Lat, Lon, Argila, CTC, P, K, Ca, Mg, P-rem, V%)", type=["xlsx"])
    
    if u_geo and u_ex:
        # 1. Carrega a planilha
        df_raw = pd.read_excel(u_ex).dropna(how='all')
        
        # 2. LIMPEZA CRÍTICA: Converte textos (como 'SD-04') em NaN e depois preenche com 0
        # Isso garante que apenas números entrem no motor de cálculo
        for col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')
        
        df_raw = df_raw.fillna(0).drop_duplicates().reset_index(drop=True)
        
        # 3. Força nomes de colunas conforme sua regra
        cols_fixas = ['Lat', 'Lon', 'Argila', 'CTC', 'P', 'K', 'Ca', 'Mg', 'P-rem', 'V_atual']
        df_raw.columns = cols_fixas + list(df_raw.columns[len(cols_fixas):])
        
        st.session_state.df = df_raw
        st.success("Planilha v56 limpa! Textos como 'SD-04' foram ignorados para o cálculo.")

# --- MOTOR v56 (NP.ARRAY PARA VELOCIDADE) ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    
    # Extração de vetores limpos
    ctc = df['CTC'].values
    ca_at, mg_at, k_at, p_at = df['Ca'].values, df['Mg'].values, df['K'].values, df['P'].values
    arg, prem = df['Argila'].values, df['P-rem'].values

    # Cálculos de Calcário (Bases), Potássio e Fósforo (v54/55)
    nec_ca = ((ca_alvo * ctc / 100) - ca_at) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - mg_at) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)

    df['Rec_K2O'] = (((sat_k_alvo * ctc / 100) - k_at) * 940).clip(min=0) + (meta_prod * 0.5)

    # Lógica de Ocultação v50: Se a coluna inteira for 0, o mapa não aparece na aba Solo
    with t_solo:
        st.write("### Visualização de Mapas")
        for c in ['Rec_Calc', 'Rec_K2O']:
            if df[c].sum() > 0:
                st.write(f"Exibindo mapa de {c}")
                # Plotagem...
