import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 2. CSS COM CONTRASTE ADAPTATIVO ---
def aplicar_visual_fixo(nome_imagem):
    if os.path.exists(nome_imagem):
        bin_str = get_base64(nome_imagem)
        st.markdown(f"""
        <style>
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

        /* Painel com fundo mais escuro para proteger o texto em fundos claros */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.8); /* Aumentado o contraste para 80% preto */
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            width: 800px;
            margin: auto;
            box-shadow: 0px 10px 30px rgba(0,0,0,0.5);
        }}

        /* LETRAS: Branco com sombra preta (Garante leitura no fundo claro) */
        label, p, span, h3 {{
            color: #FFFFFF !important;
            font-weight: bold !important;
            text-transform: uppercase;
            font-size: 0.9rem !important;
            text-shadow: 2px 2px 4px rgba(0,0,0,1) !important;
        }}

        .titulo-dourado {{
            color: #FFD700 !important;
            font-weight: 900 !important;
            font-size: 1.8rem !important;
            text-align: center;
            margin-bottom: 20px;
            text-shadow: 2px 2px 5px rgba(0,0,0,0.8) !important;
        }}

        /* Inputs: Fundo sólido para não confundir com a imagem */
        .stTextInput input {{
            background-color: rgba(255, 255, 255, 0.9) !important;
            color: #000000 !important; /* Texto interno preto para fundo branco do input */
            font-weight: bold !important;
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
    
    st.markdown('<div style="position: absolute; top: 60%; left: 50%; transform: translateX(-50%); width: 350px; text-align: center;">', unsafe_allow_html=True)
    
    if os.path.exists("logoTriadetransparente.png"):
        logo_64 = get_base64("logoTriadetransparente.png")
        # Drop shadow no logo para não sumir no fundo claro
        st.markdown(f'<img src="data:image/png;base64,{logo_6
