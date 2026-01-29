import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- 2. CSS COM CONTRASTE REFORÇADO E BOTÕES VISÍVEIS ---
def aplicar_visual_fixo(nome_imagem):
    bin_str = get_base64(nome_imagem)
    if bin_str:
        st.markdown(f"""
        <style>
        /* Bloqueio de rolagem total */
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

        /* Painel de vidro escurecido */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.85); 
            padding: 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            width: 800px;
            margin: auto;
        }}

        /* Textos Branco e Negrito com Sombra */
        label, p, span, h3 {{
            color: #FFFFFF !important;
            font-weight: bold !important;
            text-transform: uppercase;
            font-size: 0.85rem !important;
            text-shadow: 2px 2px 4px rgba(0,0,0,1) !important;
        }}

        .titulo-dourado {{
            color: #FFD700 !important;
            font-weight: 900 !important;
            font-size: 1.6rem !important;
            text-align: center;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.9) !important;
        }}

        /* --- AJUSTE DOS BOTÕES "BROWSE FILES" --- */
        [data-testid="stFileUploader"] section button {{
            background-color: #FFFFFF !important;
            color: #000000 !important;
            font-weight: bold !important;
            border-radius: 5px !important;
        }}
        
        /* Inputs de texto Brancos com letra Preta */
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

# ==========================================
# PÁGINA 1: LOGIN (Fundo Agrishow)
# ==========================================
if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    
    st.markdown('<div style="position: absolute; top: 58%; left: 50%; transform: translateX(-50%); width: 380px; text-align: center;">', unsafe_allow_html=True)
    
    logo_64 = get_base64("logoTriadetransparente.png")
    if logo_64:
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 5px; filter: drop-shadow(0px 0px 10px rgba(0,0,0,1));">', unsafe_allow_html=True)
    
    st.markdown('<div style="background: rgba(0,0,0,0.8); padding: 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2);">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="CHAVE DE ACESSO")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
        else:
            st.error("CHAVE INVÁLIDA")
    st.markdown('</div></div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA 2: CONFIGURAÇÃO (Fundo TriadeFundo)
# ==========================================
elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    
    st.write("<br><br><br>", unsafe_allow_html=True)
    _, col_central, _ = st.columns([0.1, 0.8, 0.1])
    
    with col_central:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="titulo-dourado">⚙️ CONFIGURAÇÃO DO PROJETO</div>', unsafe_allow_html=True)
        
        c1, c2, c3 =
