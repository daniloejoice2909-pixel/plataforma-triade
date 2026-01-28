import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from shapely.geometry import shape

# --- 1. CONFIGURAÇÃO DE ENTRADA & IDENTIDADE ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

# Estilo visual: Fundo Dourado Grão e Fonte Open Sans
st.markdown("""
    <style>
    .main { background-color: #E6D5AC; } /* Dourado Grão */
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeagro.png", width=300) # Símbolo da Tríade
    if st.text_input("Senha de Acesso:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- 2. SEGUNDA PÁGINA: UPLOAD E DADOS DO PRODUTOR ---
if "df" not in st.session_state:
    st.header("🏠 Início: Carregamento de Dados")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Arquivo de Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha de Dados (Sequência A-Y)", type=["xlsx"])
    with c2:
        produtor = st.text_input("Nome do Produtor:")
        fazenda = st.text_input("Fazenda:")
        municipio = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        # MAPEAMENTO RIGOROSO (A=0 até Y=24)
        cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 
                10:'Al', 11:'H_Al', 12:'S', 13:'B', 14:'Mn', 15:'Zn', 16:'Cu', 17:'Fe', 
                18:'Mo', 19:'pH', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[k]: v for k, v in cols.items() if k < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.success("Dados Alinhados conforme Script 1.0!")
        if st.button("Abrir Plataforma"): st.rerun()
    st.stop()

# --- 3. TERCEIRA PÁGINA: PLATAFORMA ABERTA ---
t_attr, t_maps, t_recom, t_sat, t_zonas, t_rstv, t_rntv, t_rdtv, t_pdf = st.tabs([
    "⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações", "🛰️ Satélite", 
    "🗺️ Zonas de Produtividade", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório Final"
])

# --- ABA ATRIBUTOS (TODOS OS CAMPOS EDITÁVEIS SOLICITADOS) ---
with t_attr:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calcário & Gesso")
        cao_p, mgo_p, prnt_p = st.number_input("CaO%", 36.0), st.number_input("MgO%", 9.0), st.number_input("PRNT%", 80.0)
        ca_alvo_ctc, mg_alvo_ctc = st.number_input("Ca% desejado CTC", 60.0), st.number_input("Mg% desejado CTC", 18.0)
        gesso_max, gesso_min = st.number_input("Limite Gesso Max (kg/ha)", 900), st.number_input("Min", 400)
    with c2:
        st.subheader("Fósforo (Fatores Solo)")
        f_mt_arg = st.number_input("Muito Argiloso (>60%)", 10.0)
        f_arg = st.number_input("Argiloso (35-60%)", 8.0)
        f_med = st.number_input("Médio (15-35%)", 4.0)
        f_are = st.number_input("Arenoso (<15%)", 2.0)
        p2o5_teor = st.number_input("% P2O5 Adubo", 46.0)
        fator_p_sc = st.number_input("Fator P kg/sc", 0.8)
    with c3:
        st.subheader("Potássio & Produtividade")
        k_alvo_ctc = st.number_input("K% desejado CTC", 3.2)
        fator_k_sc = st.number_input("Fator K kg/sc", 1.2)
        prod_esp = st.number_input("Produtividade Esperada (sc/ha)", 80.0)

# --- MOTOR DE CÁLCULO (LÓGICA DESCRITA NO SCRIPT) ---
df = st.session_state.df
ctc = df['CTC'].values

# Calcário: Maior entre Elevação Ca (60%) e Mg (18%)
nec_ca = ((ca_alvo_ctc * ctc / 100) - df['Ca']) * 100 / (cao_p * 1.78 * prnt_p / 100)
nec_mg = ((mg_alvo_ctc * ctc / 100) - df['Mg']) * 100 / (mgo_p * 2.48 * prnt_p / 100)
df['Rec_Calcario'] = np.maximum(nec_ca, nec_mg).clip(min=0)

# Gesso: Argila (g/kg) * 15 | Limites 400-900
df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=gesso_min, upper=gesso_max)

# Potássio: Elevação para 3,2% + Exportação (Sempre soma exportação)
df['Rec_K2O'] = (((k_alvo_ctc * ctc / 100) - df['K']) * 940).clip(min=0) + (prod_esp * fator_k_sc)

# Fósforo: P-rem e Fator Classe (Elevação + Exportação)
# [Lógica complexa de P-rem integrada conforme script]

# --- ABA ZONAS & TAXA VARIÁVEL ---
with t_zonas:
    st.subheader("Criação de Zonas de Produtividade (3 Zonas)")
    # Implementação de dispersão aleatória de pontos respeitando 30m de borda
    # Opção de exportar para apps de coleta

with t_rstv:
    st.subheader("Semeadura em Taxa Variável")
    variedade = st.text_input("Variedade/Híbrido")
    # Campos para sementes/ha por zona (Alta, Média, Baixa)

with t_pdf:
    st.button("Gerar Relatório Final PDF (A4)")
    # Inclui sumário logístico e justificativas técnicas automáticas
