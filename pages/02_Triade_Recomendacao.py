import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Tríade VRT", layout="wide")
st.title("🚜 Tríade VRT - Motor de Recomendação")

# ==============================================================================
# 0. FUNÇÕES DE LIMPEZA (CORRETOR DE VÍRGULAS + TRADUTOR)
# ==============================================================================
def limpar_e_padronizar_dados(df):
    """
    1. Traduz nomes das colunas (P mehl -> P).
    2. Converte '12,5' para 12.5 (Correção Brasil).
    3. Garante que tudo seja número.
    """
    df_novo = df.copy()
    
    # --- ETAPA 1: TRADUÇÃO DE COLUNAS ---
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
        # Tenta match exato ou "contém"
        for padrao, lista in sinonimos.items():
            if c_clean in lista:
                mapa_final[col_real] = padrao
                break
    
    if mapa_final:
        df_novo = df_novo.rename(columns=mapa_final)

    # --- ETAPA 2: CORREÇÃO DE VÍRGULAS E NUMÉRICOS ---
    cols_numericas = ['Ca', 'Mg', 'K', 'P', 'P_Rem', 'Argila', 'CTC', 'lat', 'lon']
    
    for col in cols_numericas:
        if col in df_novo.columns:
            # Se for texto (object), troca vírgula por ponto
            if df_novo[col].dtype == 'object':
                df_novo[col] = df_novo[col].astype(str).str.replace(',', '.')
            
            # Força conversão para número (Onde for erro vira 0)
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
            # Tenta ler detectando separador (vírgula ou ponto e vírgula) automaticamente
            try:
                df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')
            except:
                df_raw = pd.read_csv(uploaded_file) 
                
            df_input = limpar_e_padronizar_dados(df_raw)
            st.success(f"Arquivo carregado! {len(df_input)} pontos.")
        except Exception as e:
            st.error(f"Erro leitura: {e}")
            st.stop()
    elif 'df_interpolado' in st.session_state:
        df_raw = st.session_state['df_interpolado']
        df_input = limpar_e_padronizar_dados(df_raw)
        st.info("Usando dados da memória.")
    else:
        st.warning("⚠️ Faça upload do CSV.")
        st.stop()

    # --- RAIO-X DOS DADOS (PARA DIAGNÓSTICO) ---
    with st.expander("🕵️ Raio-X dos Dados (Conferência)"):
        if df_input is not None:
            st.write("Colunas Identificadas:")
            cols_check = ['Ca', 'Mg', 'K', 'P', 'P_Rem', 'Argila', 'CTC']
            for c in cols_check:
                if c in df_input.columns:
                    val = df_input[c].mean()
                    # Se média for > 0, leu certo. Se for 0, pode estar zerado ou erro de leitura.
                    icon = "✅" if val > 0 else "⚠️ (Média 0)"
                    st.write(f"{icon} {c}: Média {val:.2f}")
                else:
                    st.write(f"❌ {c}: NÃO encontrada")

    st.markdown("---")
    st.header("⚙️ Parâmetros")
    
    # 1. Cultura
    with st.expander("🌱 1. Cultura & Produtividade", expanded=True):
        produtividade_alvo = st.number_input("Meta (sc/ha):", value=80.0)

    # 2. Calagem
    with st.expander("⚪ 2. Calagem", expanded=False):
        alvo_ca = st.number_input("Alvo Ca (% CTC):", value=60.0)
        alvo_mg = st.number_input("Alvo Mg (% CTC):", value=18.0)
        teor_cao = st.number_input("CaO Calcário (%):", value=38.0)
        teor_mgo = st.number_input("MgO Calcário (%):", value=12.0)
        prnt = st.number_input("PRNT (%):", value=85.0)

    # 3. Fósforo
    with st.expander("🔴 3. Fósforo", expanded=False):
        p_export = st.number_input("Exportação P (kg/sc):", value=0.8)
        p_teor = st.number_input("Teor P2O5 (%):", value=52.0)
        # Parâmetros de calibração 5ª Aprox
        nc_a = 8.8
        nc_b = 0.76
        fct_a = 56.5
        fct_b = -0.52

    # 4. Potássio
    with st.expander("🟣 4. Potássio", expanded=False):
        k_alvo_ctc = st.number_input("K Alvo CTC (%):", value=3.0)
        k_export = st.number_input("Exportação K (kg/sc):", value=1.2)
        k_teor = st.number_input("Teor K2O (%):", value=60.0)

    # 5. Gesso
    with st.expander("⚪ 5. Gesso", expanded=False):
        gesso_fator = st.number_input("Fator x Argila:", value=50.0)
        gesso_min = st.number_input("Min (kg/ha):", value=0.0)
        gesso_max = st.number_input("Max (kg/ha):", value=2000.0)

# ==============================================================================
# 2. CÁLCULO
# ==============================================================================
def calcular(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt_val, p_exp, p_teor_val, k_alvo_val, k_exp, k_teor_val, g_fat, g_min, g_max):
    dfr = df.copy()
    
    # CALAGEM
    if all(c in dfr.columns for c in ['Ca','Mg','CTC']):
        meta_ca = dfr['CTC'] * (ca_alvo / 100.0)
        meta_mg = dfr['CTC'] * (mg_alvo / 100.0)
        
        def_ca = (meta_ca - dfr['Ca']).clip(lower=0)
        def_mg = (meta_mg - dfr['Mg']).clip(lower=0)
        
        ap_ca = max((cao * 10 / 560.0) * (prnt_val / 100.0), 0.001)
        ap_mg = max((mgo * 10 / 403.0) * (prnt_val / 100.0), 0.001)
        
        dfr['Dose_Calcario'] = np.maximum(def_ca/ap_ca, def_mg/ap_mg).round(2)
        
        ca_f = dfr['Ca'] + (dfr['Dose_Calcario'] * ap_ca)
        mg_f = dfr['Mg'] + (dfr['Dose_Calcario'] * ap_mg)
        mg_f = mg_f.replace(0, 0.01)
        
        ratio = ca_f / mg_f
        dfr['Status_Calagem'] = 'OK'
        dfr.loc[ratio < 2, 'Status_Calagem'] = '⚠️ Risco: Excesso Mg'
        dfr.loc[ratio > 4, 'Status_Calagem'] = '⚠️ Risco: Falta Mg'
    else:
        dfr['Dose_Calcario'] = 0.0
        dfr['Status_Calagem'] = 'S/ Dados'

    # FÓSFORO (5ª APROX)
    if 'P_Rem' in dfr.columns and 'P' in dfr.columns:
        nc = (nc_a + nc_b * dfr['P_Rem']).clip(8, 60)
        fct = (fct_a * dfr['P_Rem']**fct_b).clip(4, 40)
        
        dose_const = np.where(nc > dfr['P'], (nc - dfr['P']) * fct,
