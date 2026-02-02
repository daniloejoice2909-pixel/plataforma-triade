import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
from fpdf import FPDF
import json
import io
import zipfile

# --- 1. CONFIGURAÇÃO E ESTADO ---
st.set_page_config(page_title="Tríade Agro V43 (Gold)", layout="wide", page_icon="🌱")

# Inicialização de Variáveis de Sessão (Persistência)
if 'cadastros' not in st.session_state:
    st.session_state['cadastros'] = {
        "Produtores": ["Gilson Berneck", "AgroMoreira", "Tríade Demo"],
        "Fazendas": ["Brasnorte", "Santa Fé", "Gleba A"],
        "Talhoes": ["T1", "T2", "Pivo 03"]
    }
if 'fert_ok' not in st.session_state: st.session_state['fert_ok'] = False
if 'vrt_ok' not in st.session_state: st.session_state['vrt_ok'] = False
if 'df_proc' not in st.session_state: st.session_state['df_proc'] = None

# --- 2. ESTILO VISUAL PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #ffffff; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #2e7d32; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center; margin-bottom: 10px;
    }
    .kpi-val { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .kpi-lbl { font-size: 12px; color: #666; text-transform: uppercase; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; height: 3.5em; background-color: #1e3d59; color: white; border: none; }
    .stButton>button:hover { background-color: #2c567a; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INTERFACE DINÂMICA (HIERARQUIA + PARÂMETROS) ---
def gerenciar_cadastro(label, chave):
    lista = st.session_state['cadastros'][chave]
    selecao = st.sidebar.selectbox(label, lista + ["+ Adicionar Novo"])
    if selecao == "+ Adicionar Novo":
        novo = st.sidebar.text_input(f"Nome do Novo {label}")
        if st.sidebar.button(f"💾 Salvar {label}") and novo:
            st.session_state['cadastros'][chave].append(novo)
            st.rerun()
        return novo if novo else lista[0]
    return selecao

def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### 📍 Gestão do Cliente")
    
    prod = gerenciar_cadastro("Produtor", "Produtores")
    faz = gerenciar_cadastro("Fazenda", "Fazendas")
    tal = gerenciar_cadastro("Talhão", "Talhoes")

    st.sidebar.divider()
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        meta = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_pr = st.number_input("R$/Ton Calcário", value=190.0, step=1.0)
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0); c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1); c_mgo = st.number_input("MgO %", value=9.0, step=0.1)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0); c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)

    with st.sidebar.expander("🧪 Fósforo"):
        p_pr = st.number_input("R$/Ton MAP/Super", value=2200.0, step=10.0)
        nc = [st.number_input(f"NC {f}", v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        f_arg = [st.number_input(f, v, step=0.1) for f, v in zip(["M.Arg", "Arg", "Med", "Are"], [10.0, 8.0, 4.0, 2.0])]
        p_t = st.number_input("Teor P %", value=21.0, step=0.1); p_e = st.number_input("Exp P (kg/sc)", value=0.8, step=0.01)

    with st.sidebar.expander("🍌 Potássio"):
        k_pr = st.number_input("R$/Ton KCl", value=2800.0, step=10.0)
        k_t = st.number_input("Alvo K % CTC", value=3.2, step=0.1); k_e = st.number_input("Exp K (kg/sc)", value=1.2, step=0.01)
        k_teor = st.number_input("Teor K %", value=60.0, step=0.1)

    with st.sidebar.expander("📦 Gesso"):
        g_pr = st.number_input("R$/Ton Gesso", value=400.0, step=1.0)
        g_f = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_mi = st.number_input("Mín kg/ha", value=400.0, step=10.0); g_ma = st.number_input("Máx kg/ha", value=900.0, step=10.0)

    return {
        "meta": {"prod": prod, "faz": faz, "tal": tal, "alvo": meta},
        "calc": {"pr": c_pr, "prnt": c_prnt, "res": c_res, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg},
        "fosf": {"pr": p_pr, "nc": nc, "f_arg": f_arg, "teor": p_t, "exp": p_e},
        "pot": {"pr": k_pr, "target": k_t, "exp": k_e, "teor": k_teor},
        "gesso": {"pr": g_pr, "fator": g_f, "min": g_mi, "max": g_ma}
    }

# --- 4. MOTOR LÓGICO V43 (BLINDAGEM DUPLICATAS + MAPEAMENTO) ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    
    # 1. Normalização de Nomes
    df.columns = df.columns.str.strip().str.lower().str.replace('ç','c').str.replace('ã','a').str.replace('%','')
    
    # 2. BLINDAGEM CONTRA DUPLICATAS (SOLUÇÃO DO ERRO)
    df = df.loc[:, ~df.columns.duplicated()]
    
    # 3. Dicionário de Sinônimos
    de_para = {
        'ph': ['ph', 'ph_h2o', 'ph agua'],
        'argila': ['argila', 'clay', 'argila_total'],
        'ca_p': ['ca', 'calcio', 'ca_cmolc'],
        'mg_p': ['mg', 'magnesio', 'mg_cmolc'],
        'k_p': ['k', 'potassio', 'k_cmolc'],
        'al_p': ['al', 'aluminio', 'acidez'],
        'prem': ['p_rem', 'prem', 'p-rem'],
        'p_mehl': ['p', 'fosforo', 'p_mehlich', 'fosforo_mehlich'],
        'v_p': ['v', 'sat_bases', 'v_sat'],
        'ctc': ['t', 'ctc_total', 'ctc', 'ctc_ph7']
    }
    
    for padrao, variantes in de_para.items():
        for v in variantes:
            if v in df.columns:
                df[padrao] = df[v]
                break # Encontrou, para e vai para o próximo padrão
    
    # 4. Validação Básica
    erros = []
    if 'argila' not in df.columns: erros.append("ATENÇÃO: Coluna 'Argila' não encontrada.")

    # 5. CÁLCULOS
    # Gesso
    if 'argila' in df.columns:
        df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])
    
    # Calagem
