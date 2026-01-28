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

# --- 3. CSS ULTRA COMPACTO ---
def configurar_layout_travado():
    img_fundo = "imagemaptriadefundo.png"
    img_logo = "logoTriadetransparente.png"
    
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
        <style>
        /* Bloqueio absoluto de rolagem em todos os níveis */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"] {{
            height: 100vh !important;
            overflow: hidden !important;
            margin: 0;
            padding: 0;
        }}
        
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            height: 100vh;
        }}

        /* Bloco posicionado do meio para baixo */
        .triade-login-container {{
            position: absolute;
            top: 60%; /* Posicionado na metade inferior */
            left: 50%;
            transform: translateX(-50%);
            width: 320px; /* Reduzido para ser minimalista */
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 9999;
        }}

        .logo-triade {{
            width: 380px;
            margin-bottom: 5px; /* Colado no login */
            filter: drop-shadow(0px 4px 8px rgba(0,0,0,0.4));
        }}

        /* Caixa de Login Minimalista */
        .login-box-compacta {{
            background-color: rgba(0, 0, 0, 0.5); /* Fundo escuro sutil para contraste */
            padding: 15px;
            border-radius: 12px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            width: 100%;
        }}

        /* Ajuste fino dos inputs para ocupar menos espaço vertical */
        .stTextInput {{ margin-bottom: -15px; }}
        
        div.stButton > button {{
            background-color: #D4AF37;
            color: #000;
            font-weight: bold;
            height: 35px;
            border-radius: 6px;
            font-size: 14px;
        }}

        /* Remove qualquer elemento que force altura */
        header, footer, [data-testid="stHeader"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        </style>
        """, unsafe_allow_html=True)
    
    return img_logo

# --- 4. EXECUÇÃO DA INTERFACE ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    logo_path = configurar_layout_travado()
    
    # Renderização HTML
    st.markdown('<div class="triade-login-container">', unsafe_allow_html=True)
    
    if os.path.exists(logo_path):
        logo_64 = get_base64(logo_path)
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" class="logo-triade">', unsafe_allow_html=True)
    
    st.markdown('<div class="login-box-compacta">', unsafe_allow_html=True)
    # Input simplificado
    senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Senha de Acesso")
    if st.button("DESBLOQUEAR"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Chave Inválida")
            
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # Cabeçalho da próxima fase
    st.markdown("<h2 style='color: white; text-align: center; padding-top: 40vh;'>Acesso Liberado.</h2>", unsafe_allow_html=True)
    if st.button("PROSSEGUIR PARA IMPORTAÇÃO DE DADOS"):
        st.session_state.pagina_atual = "config_dados"
        st.rerun()
