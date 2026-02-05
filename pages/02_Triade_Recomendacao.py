# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(page_title="Tríade VRT", layout="wide")
st.title("🚜 Tríade VRT - Motor de Recomendação")

# ==============================================================================
# 0. FUNÇÕES DE LIMPEZA E PADRONIZAÇÃO
# ==============================================================================
def limpar_e_padronizar_dados(df):
    df_novo = df.copy()
    
    # Dicionário de sinônimos para encontrar as colunas
    sinonimos = {
        'lat': ['latitude', 'lat', 'y', 'lat_wgs84'],
        'lon': ['longitude', 'long', 'lon', 'x', 'lon_wgs84'],
        'Ca': ['ca', 'calcio', 'cálcio', 'ca_cmolc', 'ca (cmolc/dm3)'],
        'Mg': ['mg', 'magnesio', 'magnésio', 'mg_cmolc', 'mg (cmolc/dm3)'],
        'K':  ['k', 'potassio', 'potássio', 'k_mg', 'k (mg/dm3)'],
        'P':  ['p mehl', 'p_mehl', 'pmehlich', 'fosforo', 'fósforo', 'p', 'p (mg/dm3)'], 
        'P_Rem': ['prem', 'p_rem', 'p-rem', 'fosforo_remanescente', 'prem.'],
        'Argila': ['argila', 'clay', 'argila_total', 'argila %'],
        'CTC': ['ctc', 't', 'ctc_ph7', 'ctc (cmolc/dm3)']
    }
    
    mapa_final = {}
    cols_originais = list(df_novo.columns)
    
    for col_real in cols_originais:
        c_clean = col_real.lower().strip()
        for padrao, lista in sinonimos.items():
            if c_clean in lista:
                mapa_final[col_real] = padrao
                break
            for s in lista:
                if c_clean == s:
                    mapa_final[col_real] = padrao
    
    if mapa_final:
        df_novo = df_novo.rename(columns=mapa_final)

    # Correção de vírgulas (12,5 -> 12.5) e conversão para número
    cols_numericas = ['Ca', 'Mg', 'K', 'P', 'P_Rem', 'Argila', 'CTC', 'lat', 'lon']
    for col in cols_numericas:
        if col in df_novo.columns:
            if df_novo[col].dtype == 'object':
                df_novo[col] = df_novo[col].astype(str).str.replace(',', '.')
            df_novo[col] = pd.to_numeric(df_novo[col], errors='coerce').fillna(0)

    return df_novo

# ==============================================================================
# 1. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("📂 Entrada de Dados")
    uploaded_file = st.file_uploader("Carregar Malha Interpolada (.csv)", type=["csv"])
    
    df_input = None

    if uploaded_file is not None:
        try:
            try:
                df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')
            except:
                df_raw = pd.read_csv(uploaded_file) 
            df_input = limpar_e_padronizar_dados(df_raw)
            st.success(f"Carregado: {len(df_input)} pontos.")
        except Exception as e:
            st.error(f"Erro: {e}")
            st.stop()
    elif 'df_interpolado' in st.session_state:
        df_raw = st.session_state['df_interpolado']
        df_input = limpar_e_padronizar_dados(df_raw)
        st.info("Usando memória.")
    else:
        st.warning("⚠️ Faça upload do CSV.")
        st.stop()

    st.markdown("---")
    st.header("⚙️ Parâmetros")
    
    with st.expander("🌱 1. Cultura & Produtividade", expanded=True):
        produtividade_alvo = st.number_input("Meta (sc/ha):", value=80.0)

    with st.expander("⚪ 2. Calagem", expanded=False):
        alvo_ca = st.number_input("Alvo Ca (% CTC):", value=60.0)
        alvo_mg = st.number_input("Alvo Mg (% CTC):", value=18.0)
        teor_cao = st.number_input("CaO Calcário (%):", value=38.0)
        teor_mgo = st.number_input("MgO Calcário (%):", value=12.0)
        prnt = st.number_input("PRNT (%):", value=85.0)

    with st.expander("🔴 3. Fósforo", expanded=False):
        p_export = st.number_input("Exportação P (kg/sc):", value=0.8)
        p_teor = st.number_input("Teor P2O5 (%):", value=52.0)
        nc_a, nc_b = 8.8, 0.76
        fct_a, fct_b = 56.5, -0.52

    with st.expander("🟣 4. Potássio", expanded=False):
        k_alvo_ctc = st.number_input("K Alvo CTC (%):", value=3.0)
        k_export = st.number_input("Exportação K (kg/sc):", value=1.2)
        k_teor = st.number_input("Teor K2O (%):", value=60.0)

    with st.expander("⚪ 5. Gesso", expanded=False):
        gesso_fator = st.number_input("Fator x Argila:", value=50.0)
        gesso_min = st.number_input("Min (kg/ha):", value=0.0)
        gesso_max = st.number_input("Max (kg/ha):", value=2000.0)
        
    st.markdown("---")
