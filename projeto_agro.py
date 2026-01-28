import streamlit as st
import os
import base64

# --- CONFIGURAÇÃO ---
st.set_page_config(layout="centered", page_title="Tríade Agro 1.0")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- BUSCA DINÂMICA DO LOGO ---
# O código vai tentar estas variações comuns
nomes_possiveis = ["logoTriadetransparente.png", "logoTriadetransparente.PNG", "logoTriadetransparente.png.png"]
logo_encontrado = None

for nome in nomes_possiveis:
    if os.path.exists(nome):
        logo_encontrado = nome
        break

# --- INTERFACE ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    # Aplicar Fundo
    img_fundo = "imagemaptriadefundo.png"
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{bin_str}");
                background-size: cover;
            }}
            .login-box {{
                background-color: rgba(255, 255, 255, 0.15);
                padding: 30px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                text-align: center;
                border: 1px solid rgba(255,255,255,0.2);
            }}
            </style>
        """, unsafe_allow_html=True)

    _, col_centro, _ = st.columns([0.5, 1, 0.5])
    with col_centro:
        st.write("<br><br>", unsafe_allow_html=True)
        
        # EXIBIÇÃO DO LOGO COM TRATAMENTO DE ERRO
        if logo_encontrado:
            st.image(logo_encontrado, use_container_width=True)
        else:
            st.error("⚠️ O arquivo do logo não foi detectado na pasta.")
            st.write("Arquivos encontrados no seu diretório:", os.listdir(".")) 
            # Essa linha acima vai te mostrar o nome exato do arquivo para corrigirmos

        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h2 style='color: #FFD700;'>ESTRATÉGICA 1.0</h2>", unsafe_allow_html=True)
        senha = st.text_input("Senha:", type="password")
        if st.button("ENTRAR"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
