import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import json
from shapely.geometry import shape

st.set_page_config(layout="wide", page_title="Tríade Agro v54")

# --- LOGIN MASTER ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Acesso Master:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABAS ESTRUTURADAS ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Parâmetros Master", "🏠 Dados", "🔍 Solo", "🛰️ Satélite", "🗺️ Zonas & Coleta", "🌱 Semeadura", "📄 Relatório"
])

# --- ABA 0: RESTAURAÇÃO TOTAL DE ATRIBUTOS ---
with t_attr:
    st.header("🛠️ Painel de Controle Técnico v54")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        ca_alvo = st.number_input("Cálcio (Ca) Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio (Mg) Alvo na CTC (%)", value=18.0)
        prnt = st.number_input("PRNT do Calcário (%)", value=80.0)
        cao = st.number_input("Teor de CaO no Insumo (%)", value=36.0)
        mgo = st.number_input("Teor de MgO no Insumo (%)", value=9.0)
        calc_adic = st.number_input("Calcário Adicional Fixo (ton/ha)", value=0.0)
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")

    with c2:
        st.subheader("🌾 Fósforo (P) - Fatores de Correção")
        # Todos os fatores editáveis por classe de solo
        f_m_argilo = st.number_input("Fator Solo Muito Argiloso (>60%)", value=6.0)
        f_argilo = st.number_input("Fator Solo Argiloso (35-60%)", value=4.0)
        f_medio = st.number_input("Fator Solo Médio (15-35%)", value=2.5)
        f_arenoso = st.number_input("Fator Solo Arenoso (<15%)", value=1.5)
        
        st.write("**Níveis Críticos por P-rem (mg/dm³)**")
        nc1 = st.number_input("P-rem 0 a 4", value=8.0)
        nc2 = st.number_input("P-rem 4 a 10", value=12.0)
        nc3 = st.number_input("P-rem 10 a 19", value=20.0)
        nc4 = st.number_input("P-rem 19 a 30", value=30.0)
        nc5 = st.number_input("P-rem 30 a 45", value=40.0)
        nc6 = st.number_input("P-rem 45 a 60", value=50.0)

    with c3:
        st.subheader("🍌 Potássio & Metas")
        sat_k_alvo = st.number_input("Saturação de K Alvo na CTC (%)", value=3.2)
        meta_prod = st.number_input("Meta de Produtividade (sc/ha)", value=80.0)
        exp_p2o5 = st.number_input("Exportação P2O5 (kg/sc)", value=0.6)
        exp_k2o = st.number_input("Exportação K2O (kg/sc)", value=0.5)
        
        st.write("**Insumos de Adubação**")
        p_insumo = st.number_input("% P2O5 no Adubo", value=21.0)
        k_insumo = st.number_input("% K2O no Adubo", value=60.0)

# --- ABA 1: DADOS (LÓGICA v53 PRESERVADA) ---
if "df" not in st.session_state: st.session_state.df = None

with t_dados:
    u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha Master (Excel)", type=["xlsx"])
    
    if u_geo and u_ex:
        # Leitura integral e limpeza de duplicatas para evitar ValueError
        df_raw = pd.read_excel(u_ex).fillna(0).drop_duplicates().reset_index(drop=True)
        # Fixando colunas conforme seu padrão
        df_raw.columns = ['Lat', 'Lon', 'Argila', 'CTC', 'P', 'K', 'Ca', 'Mg', 'P-rem', 'V_atual'] + list(df_raw.columns[10:])
        st.session_state.df = df_raw
        st.success("Dados carregados. Todos os atributos estão prontos para o cálculo.")

# --- MOTOR DE CÁLCULO v54 (ARRAY BASED PARA SEGURANÇA) ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    
    # Extração de Arrays para evitar erros de alinhamento
    ctc = df['CTC'].to_numpy()
    ca_at = df['Ca'].to_numpy()
    mg_at = df['Mg'].to_numpy()
    k_at = df['K'].to_numpy()
    p_at = df['P'].to_numpy()
    arg = df['Argila'].to_numpy() # em g/kg
    prem = df['P-rem'].to_numpy()

    # 1. CALCÁRIO (ELEVAÇÃO DE BASES - MAIOR QUANTIDADE)
    # NC = (Desejado - Atual) * CTC / 100 -> convertido para ton/ha via teor insumo e PRNT
    nec_ca = ((ca_alvo * ctc / 100) - ca_at) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - mg_at) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0) + calc_adic

    # 2. POTÁSSIO (SATURAÇÃO + EXPORTAÇÃO)
    df['Rec_K2O'] = (((sat_k_alvo * ctc / 100) - k_at) * 940).clip(min=0) + (meta_prod * exp_k2o)

    # 3. FÓSFORO (CORREÇÃO POR CLASSE + EXPORTAÇÃO - RESERVA)
    # Seleção de fator por argila
    fator_p = np.select(
        [arg > 600, arg > 350, arg > 150],
        [f_m_argilo, f_argilo, f_medio], default=f_arenoso
    )
    # Seleção de NC por P-rem
    nc_p_alvo = np.select(
        [prem <= 4, prem <= 10, prem <= 19, prem <= 30, prem <= 45],
        [nc1, nc2, nc3, nc4, nc5], default=nc6
    )
    df['Rec_P2O5'] = ((nc_p_alvo - p_at) * fator_p + (meta_prod * exp_p2o5) - np.maximum(0, (p_at - nc_p_alvo) * fator_p)).clip(min=0)

    # 4. GESSO
    df['Rec_Gesso'] = arg * fator_gesso

    # --- ABA SOLO (OCULTAÇÃO DE ZERADOS) ---
    with t_solo:
        for col in ['Rec_Calc', 'Rec_P2O5', 'Rec_K2O', 'Rec_Gesso']:
            if df[col].sum() > 0:
                st.subheader(f"Mapa: {col}")
                # Plotagem...
