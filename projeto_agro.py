import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import json
from shapely.geometry import shape

st.set_page_config(layout="wide", page_title="Tríade Agro v55")

# --- LOGIN (Acesso Master Danilo) ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Acesso Master:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABAS (Configuração v54/55) ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Parâmetros Master", "🏠 Dados", "🔍 Solo", "🛰️ Satélite", "🗺️ Zonas & Coleta", "🌱 Semeadura", "📄 Relatório"
])

with t_attr:
    st.header("🛠️ Painel de Controle Técnico v55")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        ca_alvo = st.number_input("Ca Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Mg Alvo na CTC (%)", value=18.0)
        prnt = st.number_input("PRNT (%)", value=80.0)
        cao, mgo = st.number_input("CaO (%)", value=36.0), st.number_input("MgO (%)", value=9.0)
        calc_adic = st.number_input("Calcário Adicional", value=0.0)
        fator_gesso = st.number_input("Fator Gesso", value=0.015, format="%.3f")
    with c2:
        st.subheader("🌾 Fósforo (Fatores e P-rem)")
        f_m_arg = st.number_input("Fator M. Argiloso", value=6.0)
        f_arg = st.number_input("Fator Argiloso", value=4.0)
        f_med = st.number_input("Fator Médio", value=2.5)
        f_are = st.number_input("Fator Arenoso", value=1.5)
        nc_p = [st.number_input(f"NC P-rem {i}", value=v) for i,v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]
    with c3:
        st.subheader("🍌 Potássio & Metas")
        sat_k_alvo = st.number_input("Sat. K Alvo (%)", value=3.2)
        meta_prod = st.number_input("Meta (sc/ha)", value=80.0)
        exp_p, exp_k = st.number_input("Exp. P2O5", value=0.6), st.number_input("Exp. K2O", value=0.5)

# --- ABA 1: DADOS (LIMPEZA DE MATRIZ) ---
if "df" not in st.session_state: st.session_state.df = None

with t_dados:
    u_geo = st.file_uploader("Contorno", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha (Lat, Lon, Argila, CTC, P, K, Ca, Mg, P-rem, V%)", type=["xlsx"])
    if u_geo and u_ex:
        # LER E LIMPAR: Remove linhas e colunas totalmente vazias que causam o erro de tamanho de array
        df_raw = pd.read_excel(u_ex).dropna(how='all').dropna(axis=1, how='all').fillna(0)
        df_raw = df_raw.drop_duplicates().reset_index(drop=True)
        
        # Forçar nomes e garantir que temos dados
        cols_fixas = ['Lat', 'Lon', 'Argila', 'CTC', 'P', 'K', 'Ca', 'Mg', 'P-rem', 'V_atual']
        df_raw.columns = cols_fixas + list(df_raw.columns[len(cols_fixas):])
        st.session_state.df = df_raw
        st.success("Dados alinhados e limpos com sucesso!")

# --- MOTOR v55 (PROTEÇÃO DE BROADCAST) ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    
    # Extração garantindo o mesmo tamanho para todos os vetores
    try:
        ctc = df['CTC'].to_numpy(dtype=float)
        ca_at = df['Ca'].to_numpy(dtype=float)
        mg_at = df['Mg'].to_numpy(dtype=float)
        k_at = df['K'].to_numpy(dtype=float)
        p_at = df['P'].to_numpy(dtype=float)
        arg = df['Argila'].to_numpy(dtype=float)
        prem = df['P-rem'].to_numpy(dtype=float)

        # 1. CALCÁRIO
        nec_ca = ((ca_alvo * ctc / 100) - ca_at) * 100 / (cao * 1.78 * prnt / 100)
        nec_mg = ((mg_alvo * ctc / 100) - mg_at) * 100 / (mgo * 2.48 * prnt / 100)
        df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0) + calc_adic

        # 2. POTÁSSIO
        df['Rec_K2O'] = (((sat_k_alvo * ctc / 100) - k_at) * 940).clip(min=0) + (meta_prod * exp_k)

        # 3. FÓSFORO
        fator_p = np.select([arg > 600, arg > 350, arg > 150], [f_m_arg, f_arg, f_med], default=f_are)
        nc_alvo = np.select([prem <= 4, prem <= 10, prem <= 19, prem <= 30, prem <= 45], nc_p[:5], default=nc_p[5])
        df['Rec_P2O5'] = ((nc_alvo - p_at) * fator_p + (meta_prod * exp_p) - np.maximum(0, (p_at - nc_alvo) * fator_p)).clip(min=0)

        # 4. GESSO
        df['Rec_Gesso'] = arg * fator_gesso
        st.success("Cálculos da v55 processados.")
    except Exception as e:
        st.error(f"Erro no alinhamento: {e}. Verifique se a planilha segue a ordem das colunas.")
