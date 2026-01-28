import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="centered", page_title="Tríade Agro Estratégica 1.0", page_icon="🌱")

# --- 2. FUNÇÃO PARA CARREGAR IMAGEM DE FUNDO DO GIT/PASTA ---
def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def configurar_fundo_customizado():
    # Nome exato que você salvou no Git
    img_arquivo = "imagemaptriadefundo.png"
    
    if os.path.exists(img_arquivo):
        bin_str = get_base64(img_arquivo)
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        /* Overlay para escurecer levemente a imagem e dar leitura ao texto */
        .stApp::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.4);
            z-index: -1;
        }}
        /* Estilização da caixa de login */
        .login-box {{
            background-color: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            margin-top: 50px;
        }}
        /* Estilo do botão de entrada */
        div.stButton > button {{
            background-color: #D4AF37; /* Dourado */
            color: white;
            font-weight: bold;
            width: 100%;
            border-radius: 10px;
            border: none;
            height: 3em;
        }}
        </style>
        """, unsafe_allow_html=True)
    else:
        # Reserva caso o arquivo não seja encontrado
        st.markdown("<style>.stApp {background-color: #2c3e50;}</style>", unsafe_allow_html=True)
        st.error(f"Erro: Arquivo '{img_arquivo}' não encontrado na pasta do projeto.")

# --- 3. LÓGICA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    configurar_fundo_customizado()
    
    _, col_centro, _ = st.columns([0.5, 1, 0.5])
    
    with col_centro:
        # Exibe o logo acima da caixa de login
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", use_container_width=True)
        
        # Caixa de login
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h1 style='color: #FFD700; font-size: 24px;'>ESTRATÉGICA 1.0</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: white;'>Sistema de Gestão de Nutrição</p>", unsafe_allow_html=True)
        
        senha = st.text_input("Digite sua chave de acesso:", type="password")
        
        if st.button("DESBLOQUEAR ACESSO"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Chave incorreta. Tente novamente.")
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # Se já estiver logado, mostra o botão para prosseguir
    configurar_fundo_customizado()
    st.success("Acesso Liberado!")
    if st.button("PROSSEGUIR PARA CONFIGURAÇÃO DE DADOS"):
        st.write("Aqui entraremos na Segunda Página (Upload de Arquivos).")
