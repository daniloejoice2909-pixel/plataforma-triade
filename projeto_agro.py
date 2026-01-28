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

# --- 3. CSS PARA TRAVAR TELA E POSICIONAR ---
def configurar_layout_estatico():
    img_fundo = "imagemaptriadefundo.png"
    img_logo = "logoTriadetransparente.png"
    
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
        <style>
        /* Bloqueio Total de Rolagem */
        html, body, [data-testid="stAppViewContainer"] {{
            height: 100vh;
            overflow: hidden !important;
        }}
        
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            height: 100vh;
        }}

        /* Container que inicia no MEIO e vai para BAIXO */
        .triade-login-container {{
            position: absolute;
            top: 55%; /* Começa um pouco abaixo do meio */
            left: 50%;
            transform: translateX(-50%);
            width: 450px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 1000;
        }}

        /* Logo maior conforme solicitado */
        .logo-triade {{
            width: 380px; /* Aumentado */
            margin-bottom: 10px;
            filter: drop-shadow(0px 4px 8px rgba(0,0,0,0.3));
        }}

        /* Caixa de Login */
        .login-box-final {{
            background-color: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            width: 100%;
        }}

        /* Estilo do Botão */
        div.stButton > button {{
            background-color: #D4AF37;
            color: #4B3621;
            font-weight: bold;
            width: 100%;
            border: none;
            border-radius: 8px;
        }}

        /* Esconder Elementos do Streamlit */
        header, footer {{visibility: hidden !important;}}
        [data-testid="stHeader"] {{display: none !important;}}
        </style>
        """, unsafe_allow_html=True)
    
    return img_logo

# --- 4. EXECUÇÃO DA INTERFACE ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    logo_path = configurar_layout_estatico()
    
    # Montagem do Layout em HTML
    st.markdown('<div class="triade-login-container">', unsafe_allow_html=True)
    
    # Exibe o logo ampliado
    if os.path.exists(logo_path):
        logo_64 = get_base64(logo_path)
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" class="logo-triade">', unsafe_allow_html=True)
    
    # Caixa de senha
    st.markdown('<div class="login-box-final">', unsafe_allow_html=True)
    st.markdown("<h3 style='color: #FFD700; margin-bottom: 15px;'>ACESSO ESTRATÉGICO 1.0</h3>", unsafe_allow_html=True)
    
    senha = st.text_input("Chave", type="password", label_visibility="collapsed", placeholder="Digite sua senha")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Chave Inválida")
            
    st.markdown('</div>', unsafe_allow_html=True) # Fim login-box
    st.markdown('</div>', unsafe_allow_html=True) # Fim container

else:
    # Se já logou, entramos na Segunda Página
    st.markdown("<h1 style='color: white; text-align: center; margin-top: 10vh;'>Acesso Autorizado.</h1>", unsafe_allow_html=True)
    if st.button("IR PARA CONFIGURAÇÃO DE DADOS"):
        st.session_state.pagina_atual = "config_dados"
        st.rerun()
