import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

# --- 2. FUNÇÃO PARA CARREGAR IMAGEM DE FUNDO ---
def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def configurar_layout_sem_rolagem():
    img_fundo = "imagemaptriadefundo.png"
    img_logo = "logoTriadetransparente.png"
    
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
        <style>
        /* Remove rolagem e fixa o fundo */
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            height: 100vh;
            overflow: hidden;
        }}
        
        /* Container Principal posicionado na metade inferior */
        .main-container {{
            position: absolute;
            bottom: 5vh; /* Distância do fundo da tela */
            left: 50%;
            transform: translateX(-50%);
            width: 400px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        /* Estilo da Logo para destaque em fundo claro */
        .logo-triade {{
            width: 280px;
            margin-bottom: 20px;
            filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.2)); /* Leve sombra para dar contraste caso o fundo seja muito claro */
        }}

        /* Caixa de Login Translúcida */
        .login-box {{
            background-color: rgba(0, 0, 0, 0.4); /* Escurecido para ler o input branco */
            padding: 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            width: 100%;
        }}

        /* Esconder cabeçalhos padrão do Streamlit para ganhar espaço */
        header {{visibility: hidden;}}
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
        """, unsafe_allow_html=True)
    
    return img_logo

# --- 3. EXECUÇÃO DA TELA ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    logo_path = configurar_layout_sem_rolagem()
    
    # Criando o container HTML na metade inferior
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    # Exibe o logo (se existir)
    if os.path.exists(logo_path):
        # Usamos HTML direto para o logo para controle total de posição no container customizado
        logo_base64 = get_base64(logo_path)
        st.markdown(f'<img src="data:image/png;base64,{logo_base64}" class="logo-triade">', unsafe_allow_html=True)
    
    # Caixa de login
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown("<h2 style='color: #FFD700; margin-top:0;'>ESTRATÉGICA 1.0</h2>", unsafe_allow_html=True)
    
    # Inputs do Streamlit (dentro da div)
    senha = st.text_input("Chave de Acesso", type="password", label_visibility="collapsed", placeholder="Senha de Acesso")
    if st.button("DESBLOQUEAR"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Incorreto")
            
    st.markdown('</div>', unsafe_allow_html=True) # Fecha login-box
    st.markdown('</div>', unsafe_allow_html=True) # Fecha main-container

else:
    st.info("Acesso liberado. Aguardando a Segunda Página...")
