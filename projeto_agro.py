import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 2. CSS PARA TRAVAMENTO TOTAL (DUAS TELAS) ---
def aplicar_visual_fixo(nome_imagem):
    if os.path.exists(nome_imagem):
        bin_str = get_base64(nome_imagem)
        st.markdown(f"""
        <style>
        /* Trava a visualização para não ter rolagem */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"] {{
            height: 100vh !important;
            width: 100vw !important;
            overflow: hidden !important;
            margin: 0; padding: 0;
        }}
        
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: 100% 100%;
            background-repeat: no-repeat;
            background-position: center;
        }}

        /* Ajuste do painel de vidro para caber sem rolar */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.75);
            padding: 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin-top: 2vh;
        }}

        /* Textos em Branco e Negrito */
        label, p, span, h3 {{
            color: white !important;
            font-weight: bold !important;
            text-transform: uppercase;
            font-size: 0.85rem !important;
        }}

        .titulo-dourado {{
            color: #FFD700 !important;
            font-weight: 900 !important;
            font-size: 1.5rem !important;
            text-align: center;
            margin-bottom: 15px;
        }}

        /* Compactar campos de upload */
        [data-testid="stFileUploader"] {{
            padding-bottom: 0px;
        }}

        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. CONTROLE DE NAVEGAÇÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
if "pagina" not in st.session_state:
    st.session_state.pagina = "login"

# ==========================================
# PÁGINA 1: LOGIN
# ==========================================
if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    
    st.markdown('<div style="position: absolute; top
