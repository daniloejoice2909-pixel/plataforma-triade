import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 2. CSS COM CONTRASTE REFORÇADO ---
def aplicar_visual_fixo(nome_imagem):
    if os.path.exists(nome_imagem):
        bin_str = get_base64(nome_imagem)
        st.markdown(f"""
        <style>
        /* Bloqueio de rolagem */
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

        .glass-panel {{
            background: rgba(0, 0, 0, 0.85); 
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            width: 850px;
            margin: auto;
        }}

        /* Textos Gerais */
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
            text-shadow: 3px 3px 6px rgba(0,0,0,0.9) !important;
        }}

        /* --- AJUSTE DOS BOTÕES "BROWSE FILES" --- */
        /* Força o fundo do botão a ser claro e o texto ESCURO */
        [data-testid="stFileUploader"] section button {{
            background-color: #EEEEEE !important;
            color: #111111 !important;
            font-weight: bold !important;
            border: 1px solid #333 !important;
        }}
        
        /* Ajuste da cor do texto informativo dentro do uploader */
        [data-testid="stFileUploader"] section div div {{
            color: #FFFFFF !important;
            font-weight: normal !important;
        }}

        /* Inputs de texto com fundo branco e letra preta */
        .stTextInput input {{
            background-color: white !important;
            color: black !important;
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

# --- PÁGINA 1: LOGIN ---
if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    st.markdown('<div style="position: absolute; top: 58%; left: 50%; transform: translateX(-50%); width: 380px; text-align: center;">', unsafe_allow_html=True)
    if os.path.exists("logoTriadetransparente.png"):
        logo_64 = get_base64("logoTriadetransparente.png")
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 10px; filter: drop-shadow(0px 0px 12px rgba(0,0,0,0.9));">', unsafe_allow_html=True)
    
    st.markdown('<div style="background: rgba(0,0,0,0.8); padding: 25px; border-radius: 15px;">', unsafe_allow_html=True)
    senha = st.text_input("Acesso", type="password", label_visibility="collapsed", placeholder="CHAVE DE ACESSO")
    if st.button("DESBLOQUEAR"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
    st.markdown('</div></div>', unsafe_allow_html=True)

# --- PÁGINA 2: CONFIGURAÇÃO ---
elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    st.write("<br><br><br>", unsafe_allow_html=True)
    _, col_central, _ = st.columns([0.1, 0.8, 0.1])
    
    with col_central:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="titulo-dourado">⚙️ CONFIGURAÇÃO DO PROJETO</div>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.text_input("PRODUTOR")
        with c2: st.text_input("FAZENDA")
        with c3: st.text_input("MUNICÍPIO / UF")
        
        st.markdown("<hr style='margin: 15px 0; opacity: 0.3;'>", unsafe_allow_
