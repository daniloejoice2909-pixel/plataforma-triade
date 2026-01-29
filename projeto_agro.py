import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

# --- 2. FUNÇÃO PARA CONVERSÃO DE IMAGEM ---
def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 3. CSS PARA IMAGEM FULLSCREEN E ZERO ROLAGEM ---
def configurar_layout_perfeito():
    img_fundo = "OI_AGRISHOW.jpg"
    img_logo = "logoTriadetransparente.png"
    
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
        <style>
        /* Força o corpo da página a ocupar exatamente 100% da visão do usuário */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"] {{
            height: 100vh !important;
            width: 100vw !important;
            overflow: hidden !important;
            margin: 0;
            padding: 0;
        }}
        
        .stApp {{
            background-image: url("data:image/jpg;base64,{bin_str}");
            background-size: 100% 100%; /* Ajusta a imagem exatamente ao tamanho da tela */
            background-repeat: no-repeat;
            background-position: center;
            height: 100vh;
            width: 100vw;
        }}

        /* Container posicionado na metade inferior */
        .triade-login-container {{
            position: absolute;
            top: 65%; /* Ajustado para ficar na parte inferior */
            left: 50%;
            transform: translateX(-50%);
            width: 320px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 1000;
        }}

        .logo-triade {{
            width: 380px;
            margin-bottom: 5px;
            filter: drop-shadow(0px 4px 10px rgba(0,0,0,0.6));
        }}

        .login-box-compacta {{
            background-color: rgba(0, 0, 0, 0.65);
            padding: 15px;
            border-radius: 12px;
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            width: 100%;
        }}
        
        div.stButton > button {{
            background-color: #D4AF37;
            color: #000;
            font-weight: bold;
            height: 35px;
            width: 100%;
            border-radius: 6px;
            border: none;
        }}

        /* Esconde elementos nativos do Streamlit que causam rolagem */
        header, footer, [data-testid="stHeader"], .stDeployButton {{
            display: none !important;
        }}
        </style>
        """, unsafe_allow_html=True)
    
    return img_logo

# --- 4. EXECUÇÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    logo_path = configurar_layout_perfeito()
    
    # Renderização do Bloco Inferior
    st.markdown('<div class="triade-login-container">', unsafe_allow_html=True)
    
    if os.path.exists(logo_path):
        logo_64 = get_base64(logo_path)
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" class="logo-triade">', unsafe_allow_html=True)
    
    st.markdown('<div class="login-box-compacta">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility
