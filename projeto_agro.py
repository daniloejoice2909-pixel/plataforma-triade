import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="centered", page_title="Tríade Agro Estratégica 1.0", page_icon="🌱")

# --- 2. FUNÇÃO PARA CARREGAR IMAGEM DE FUNDO DO GIT ---
def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def configurar_visual_triade():
    # Caminho das imagens no seu repositório
    img_fundo = "imagemaptriadefundo.png"
    img_logo = "logoTriadetransparente.png" # Nome atualizado conforme você salvou
    
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        /* Estilo para garantir que o logo e containers fiquem limpos */
        [data-testid="stImage"] img {{
            background-color: transparent !important;
        }}
        .login-box {{
            background-color: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}
        div.stButton > button {{
            background-color: #D4AF37;
            color: white;
            font-weight: bold;
            width: 100%;
            border-radius: 10px;
            border: none;
            height: 3em;
        }}
        </style>
        """, unsafe_allow_html=True)
    
    return img_logo

# --- 3. EXECUÇÃO DA TELA ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    logo_path = configurar_visual_triade()
    
    _, col_centro, _ = st.columns([0.5, 1, 0.5])
    
    with col_centro:
        st.write("<br><br>", unsafe_allow_html=True)
        # Exibe o logo transparente
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h1 style='color: #FFD700; font-size: 26px;'>ESTRATÉGICA 1.0</h1>", unsafe_allow_html=True)
        
        senha = st.text_input("Chave de Acesso:", type="password")
        
        if st.button("DESBLOQUEAR PLATAFORMA"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Chave incorreta.")
        st.markdown('</div>', unsafe_allow_html=True)
