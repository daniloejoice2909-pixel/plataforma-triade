import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os
from math import ceil

# --- 1. CONFIGURAÇÃO DE IDENTIDADE E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v120", initial_sidebar_state="collapsed")

def aplicar_estilo():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
        .stApp { background-color: #FFFFFF; font-family: 'Open Sans', sans-serif; }
        [data-testid="stHeader"] { background-color: #C5A059 !important; }
        h1, h2, h3 { color: #8B4513; font-weight: 700; }
        .stTabs [data-baseweb="tab-list"] button { font-size: 14px !important; font-weight: bold; color: #8B4513; }
        div.stButton > button { background-color: #8B4513; color: white; border-radius: 8px; font-weight: bold; border: none; height: 3em; }
        .watermark { position: fixed; bottom: 10px; right: 10px; opacity: 0.08; font-size: 40px; color: #8B4513; z-index: -1; pointer-events: none; }
        .finance-card { background-color: #fcf9f2; border: 1px solid #C5A059; padding: 15px; border-radius: 10px; }
        </style>
        <div class="watermark">TRÍADE AGRO ESTRATÉGICA</div>
    """, unsafe_allow_html=True)

aplicar_estilo()

# --- 2. LOGIN E GESTÃO DE PASTAS ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 0.6, 1])
    with col_login:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=180)
        st.subheader("Acesso Master")
        senha = st.text_input("Chave:", type="password")
        if st.button("DESBLOQUEAR"):
            if senha == "triade2026": st.session_state.logado = True; st.rerun()
    st.stop()

if "ambiente_pronto" not in st.session_state:
    st.header("📂 Hierarquia de Dados: Produtor e Fazenda")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_
