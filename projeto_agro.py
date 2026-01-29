import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import base64
from fpdf import FPDF
from datetime import datetime

# --- 1. CONFIGURAÇÕES E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return ""

# --- 2. MOTOR DE INTERPOLAÇÃO IDW ---
def calcular_idw(x, y, z, xi, yi, p=2.5):
    dist = np.sqrt((x[:, None] - xi[None, :])**2 + (y[:, None] - yi[None, :])**2)
    dist = np.where(dist == 0, 1e-12, dist)
    weights = 1.0 / (dist**p)
    return np.dot(weights.T, z) / weights.sum(axis=0)

# --- 3. PÁGINA DE ENTRADA (LOGIN) ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<h1 style='text-align:center;'>Tríade Agro Estratégica</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        logo = "LogoTriadeagro.png.png"
        if os.path.exists(logo): st.image(logo)
        senha = st.text_input("Chave de Acesso", type="password")
        if st.button("DESBLOQUEAR"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
else:
    # --- 4. SEGUNDA PÁGINA: UPLOAD E METADADOS ---
    with st.sidebar:
        st.image("LogoTriadeagro.png.png") if os.path.exists("LogoTriadeagro.png.png") else st.title("Tríade")
        st.header("📍 Identificação")
        produtor = st.text_input("Nome do Produtor")
        fazenda = st.text_input("Nome da Fazenda")
        municipio = st.text_input("Município")
        st.markdown("---")
        f_geo = st.file_uploader("Contorno (.geojson)", type=['geojson'])
        f_xls = st.file_uploader("Dados (.xlsx)", type=['xlsx'])
        
    if not f_geo or not f_xls:
        st.info("Por favor, carregue o Contorno e a Planilha para abrir a plataforma.")
    else:
        # Processamento inicial de dados (Sequência de colunas A a Y)
        if "dados" not in st.session_state:
            df = pd.read_excel(f_xls)
            # Mapeamento conforme seu script (A=0, B=1...)
            col_map = {0:'LAT', 1:'LON', 2:'CAMPO', 3:'PONTO', 4:'ARGILA', 5:'P-REM', 6:'P', 
                       7:'CA', 8:'MG', 9:'K', 10:'AL', 11:'H_AL', 12:'S', 13:'B', 14:'MN', 
                       15:'ZN', 16:'CU', 17:'FE', 18:'MO', 19:'PH_CACL2', 20:'CTC', 
                       21:'CA_PERC', 22:'MG_PERC', 23:'K_PERC', 24:'CA_MG'}
            df.columns = [col_map.get(i, f"COL_{i}") for i in range(len(df.columns))]
            st.session_state.dados = df
            st.session_state.geo = json.load(f_geo)

        # --- 5. TERCEIRA PÁGINA: ABAS DA PLATAFORMA ---
        tabs = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

        # --- ABA ATRIBUTOS ---
        with tabs[0]:
            st.header("Configuração de Recomendação v43")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.subheader("Calcário")
                ca_desejado = st.number_input("Ca% na CTC desejado", value=60.0)
                mg_desejado = st.number_input("Mg% na CTC desejado", value=18.0)
                prnt = st.number_input("PRNT do Calcário (%)", value=80.0)
                preco_calcario = st.number_input("Preço Calcário (R$/t)", value=190.0)
                
                st.subheader("Gesso")
                fator_gesso = st.number_input("Fator Gesso (Argila * X)", value=15.0)
                gesso_max = st.number_input("Dose Máxima Gesso (kg/ha)", value=900.0)
                gesso_min = st.number_input("Dose Mínima Gesso (kg/ha)", value=400.0)
                preco_gesso = st.number_input("Preço Gesso (R$/t)", value=400.0)

            with c2:
                st.subheader("Fósforo (P-Rem)")
                prod_esperada = st.number_input("Produtividade Esperada (sc/ha)", value=80.0)
                p_export = st.number_input("P Exportação (kg/sc)", value=0.8)
                p2o5_adubo = st.number_input("% P2O5 no Adubo", value=21.0)
                preco_p = st.number_input("Preço Adubo Fosfatado (R$/t)", value=2800.0)
                
                st.write("Nível Crítico por P-Rem:")
                nc_0_4 = st.number_input("0 a 4", value=8.0)
                nc_4_10 = st.number_input("4.1 a 10", value=10.0)
                nc_10_19 = st.number_input("10.1 a 19", value=12.0)
                nc_19_30 = st.number_input("19.1 a 30", value=15.0)

            with c3:
                st.subheader("Potássio (K)")
                k_ctc_meta = st.number_input("K% na CTC Meta", value=3.2)
                k_export = st.number_input("K Exportação (kg/sc)", value=1.2)
                k2o_adubo = st.number_input("% K2O no Adubo", value=60.0)
                preco_k = st.number_input("Preço Adubo Potássico (R$/t)", value=2800.0)

        # --- ABA MAPAS DE FERTILIDADE ---
        with tabs[1]:
            st.subheader("Mapas de Variabilidade de Solo")
            df = st.session_state.dados
            geo = st.session_state.geo
            cols_map = ['ARGILA', 'PH_CACL2', 'CA', 'MG', 'P', 'P-REM', 'K', 'CTC', 'MO']
            
            sel_col = st.selectbox("Selecione o atributo", [c for c in cols_map if c in df.columns])
            
            # Cálculo de Mapa com IDW (conforme padrão memorável anterior)
            x, y, z = df['LON'].values, df['LAT'].values, df[sel_col].values
            xi = np.linspace(x.min(), x.max(), 150)
            yi = np.linspace(y.min(), y.max(), 150)
            xi_g, yi_g = np.meshgrid(xi, yi)
            zi = calcular_idw(x, y, z, xi_g.flatten(), yi_g.flatten()).reshape(150, 150)

            fig = go.Figure(data=go.Contour(z=zi, x=xi, y=yi, colorscale='coolwarm', ncontours=6))
            # (Aqui entra o loop de contorno GeoJSON para fidelidade 100%)
            st.plotly_chart(fig, use_container_width=True)

        # --- ABA RECOMENDAÇÕES (O MOTOR DE CÁLCULO) ---
        with tabs[2]:
            st.subheader("Cálculos de Taxa Variável")
            df_rec = df.copy()
            
            # CÁLCULO GESSO
            df_rec['REC_GESSO'] = (df_rec['ARGILA'] * fator_gesso).clip(gesso_min, gesso_max)
            
            # CÁLCULO CALCÁRIO (Elevação Ca ou Mg - a maior)
            nec_ca = (ca_desejado - df_rec['CA_PERC']) * df_rec['CTC'] / 100 # Exemplo simplificado da lógica
            nec_mg = (mg_desejado - df_rec['MG_PERC']) * df_rec['CTC'] / 100
            df_rec['REC_CALCARIO'] = np.maximum(nec_ca, nec_mg) * (100/prnt)
            
            # CÁLCULO POTÁSSIO (Elevação + Exportação sempre cheia)
            eleva_k = (k_ctc_meta - df_rec['K_PERC']) * df_rec['CTC'] / 100
            df_rec['REC_K2O'] = (eleva_k.clip(lower=0) + (prod_esperada * k_export)) * (100/k2o_adubo)

            st.dataframe(df_rec[['PONTO', 'REC_GESSO', 'REC_CALCARIO', 'REC_K2O']])

        # --- ABA RELATÓRIO ---
        with tabs[8]:
            if st.button("GERAR RELATÓRIO FINAL PDF"):
                # Lógica de PDF A4, margens 2cm, argumentos técnicos por mapa
                st.success("Relatório gerado com sucesso (Simulação)")
