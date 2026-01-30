import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
import io
from streamlit_folium import folium_static
from pykrige.ok import OrdinaryKriging
from shapely.geometry import shape, Point
import matplotlib.pyplot as plt

# --- 1. CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(layout="wide", page_title="Tríade Agro - Estratégica 1.0")

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"

# --- 2. PÁGINA DE ENTRADA (LOGIN) ---
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Solo & Precisão</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        st.info("Acesso Restrito - Consultoria Estratégica")
        senha = st.text_input("Senha", type="password")
        if st.button("ACESSAR SISTEMA"):
            if senha == "triade2026":
                st.session_state.pagina = "Upload"
                st.rerun()

# --- 3. PÁGINA DE UPLOAD (CONTORNO + DADOS) ---
elif st.session_state.pagina == "Upload":
    st.header("📂 Importação de Dados da Fazenda")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.info = {
            "produtor": st.text_input("Produtor"),
            "fazenda": st.text_input("Fazenda"),
            "municipio": st.text_input("Município")
        }
    with col2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha de Solo (A a Y)", type=['xlsx'])

    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        # Mapeamento conforme sua sequência A-Y
        df = pd.read_excel(f_dados)
        col_names = [
            'LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
            'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
            'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'
        ]
        df.columns = col_names[:len(df.columns)]
        st.session_state.dados = df
        
        if st.button("🚀 GERAR PLATAFORMA"):
            st.session_state.pagina = "Dashboard"
            st.rerun()

# --- 4. PÁGINA DASHBOARD (ABAS TÉCNICAS) ---
elif st.session_state.pagina == "Dashboard":
    tab_attr, tab_fert, tab_recom, tab_zonas, tab_relat = st.tabs([
        "⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações", "🗺️ Zonas de Manejo", "📄 Relatório & Exportação"
    ])

    df = st.session_state.dados

    # --- ABA: ATRIBUTOS (PARÂMETROS EDITÁVEIS) ---
    with tab_attr:
        st.subheader("Configuração de Insumos e Metas")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Calcário**")
            p_cao = st.number_input("CaO %", 36.0); p_mgo = st.number_input("MgO %", 9.0)
            p_prnt = st.number_input("PRNT %", 80.0); p_cadir = st.number_input("Ca% Desejado", 60.0)
            p_mgdir = st.number_input("Mg% Desejado", 18.0); p_precalc = st.number_input("Preço Calcário", 190.0)
        with c2:
            st.markdown("**Fósforo**")
            p_prodesp = st.number_input("Produtividade (sc/ha)", 80.0); p_export_p = st.number_input("Exp. P (kg/sc)", 0.8)
            p_perc_adubo = st.number_input("% P2O5 Adubo", 21.0); p_pre_p = st.number_input("Preço Adubo P", 2800.0)
            f_m_arg = st.number_input("Fator M. Argiloso", 10.0); f_arg = st.number_input("Fator Argiloso", 8.0)
        with c3:
            st.markdown("**Potássio & Gesso**")
            p_kdir = st.number_input("K% Desejado", 3.2); p_export_k = st.number_input("Exp. K (kg/sc)", 1.2)
            p_g_fator = st.number_input("Fator Gesso (Arg * F)", 15); p_g_max = st.number_input("Dose Máx Gesso", 900)

    # --- ABA: RECOMENDAÇÕES (FÓRMULAS TRÍADE) ---
    with tab_recom:
        st.subheader("Cálculo de Prescrição VRA")
        
        # Lógica Fósforo Remanescente
        def get_nc_p(prem):
            if prem <= 4: return 8.0
            elif prem <= 10: return 10.0
            elif prem <= 19: return 12.0
            elif prem <= 30: return 15.0
            elif prem <= 45: return 20.0
            else: return 25.0
        
        df['NC_P'] = df['PREM'].apply(get_nc_p)
        df['SALDO_P'] = (df['P'] - df['NC_P']).clip(lower=0)
        df['DESS_P'] = (df['NC_P'] - df['P']).clip(lower=0)
        
        # Exemplo de Cálculo de Adubo P (Dose = (Necessidade * Fator Solo) + Exportação - Saldo)
        df['REC_P_ADUBO'] = (((df['DESS_P'] * f_arg) + (p_prodesp * p_export_p) - df['SALDO_P']) * 100 / p_perc_adubo).clip(lower=0)
        
        # Calcário (Maior entre Ca e Mg)
        df['REC_CALC'] = pmax = np.maximum((p_cadir - df['CA_PERC']), (p_mgdir - df['MG_PERC'])).clip(lower=0) # Simplificado
        
        st.dataframe(df[['PONTO', 'ARGILA', 'P', 'REC_P_ADUBO', 'REC_CALC']])

    # --- ABA: MAPAS DE FERTILIDADE (KRIGAGEM ORDINÁRIA) ---
    with tab_fert:
        st.subheader("Mapas Geoestatísticos")
        attr = st.selectbox("Atributo para Mapear:", ['ARGILA', 'PH', 'P', 'K', 'CTC', 'MO'])
        
        if st.button("GERAR MAPA POR KRIGAGEM"):
            with st.spinner("Processando correlação espacial..."):
                # Motor de Krigagem Ordinária
                OK = OrdinaryKriging(df['LON'], df['LAT'], df[attr], variogram_model='spherical')
                grid_x = np.linspace(df['LON'].min(), df['LON'].max(), 100)
                grid_y = np.linspace(df['LAT'].min(), df['LAT'].max(), 100)
                z, ss = OK.execute('grid', grid_x, grid_y)
                
                fig, ax = plt.subplots()
                c = ax.imshow(z, extent=(df['LON'].min(), df['LON'].max(), df['LAT'].min(), df['LAT'].max()), origin='lower', cmap='RdYlGn')
                plt.colorbar(c)
                st.pyplot(fig)
                st.info(f"O mapa de {attr} utiliza o modelo esférico para garantir a transição suave entre os pontos de coleta.")
