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

# --- 3. CSS TRAVADO (ZERO ROLAGEM) ---
def configurar_layout_travado():
    img_fundo = "OI_AGRISHOW.jpg" # Nome da sua nova imagem
    img_logo = "logoTriadetransparente.png"
    
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
        <style>
        /* Bloqueio absoluto de rolagem */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"] {{
            height: 100vh !important;
            overflow: hidden !important;
            margin: 0;
            padding: 0;
        }}
        
        .stApp {{
            background-image: url("data:image/jpg;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            height: 100vh;
        }}

        /* Bloco centralizado do MEIO para BAIXO */
        .triade-login-container {{
            position: absolute;
            top: 62%; /* Ajuste fino para a metade inferior */
            left: 50%;
            transform: translateX(-50%);
            width: 320px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 9999;
        }}

        .logo-triade {{
            width: 380px;
            margin-bottom: 5px;
            filter: drop-shadow(0px 4px 10px rgba(0,0,0,0.5));
        }}

        /* Caixa de Login Minimalista */
        .login-box-compacta {{
            background-color: rgba(0, 0, 0, 0.6); /* Escurecido para dar contraste com a foto */
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

        /* Remove cabeçalhos e menus do Streamlit */
        header, footer, [data-testid="stHeader"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        </style>
        """, unsafe_allow_html=True)
    else:
        st.error(f"Arquivo '{img_fundo}' não encontrado. Verifique o nome no GitHub.")
    
    return img_logo

# --- 4. EXECUÇÃO DA INTERFACE ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    logo_path = configurar_layout_travado()
    
    st.markdown('<div class="triade-login-container">', unsafe_allow_html=True)
    
    if os.path.exists(logo_path):
        logo_64 = get_base64(logo_path)
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" class="logo-triade">', unsafe_allow_html=True)
    
    st.markdown('<div class="login-box-compacta">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Digite a Senha de Acesso")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Senha Incorreta")
            
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # PROSSEGUIR PARA A SEGUNDA PÁGINA
    st.markdown("<h2 style='color: white; text-align: center; padding-top: 45vh;'>Acesso Liberado.</h2>", unsafe_allow_html=True)
    if st.button("ABRIR IMPORTAÇÃO DE DADOS (A-Y)"):
        st.session_state.pagina_atual = "config_dados"
        st.rerun()
