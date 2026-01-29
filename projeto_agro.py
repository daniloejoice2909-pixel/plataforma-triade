import streamlit as st
import os
import base64
import pandas as pd

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 2. FUNÇÃO DE ESTILO DINÂMICO ---
def aplicar_estilo_por_pagina(nome_imagem, trava_rolagem=True):
    if os.path.exists(nome_imagem):
        bin_str = get_base64(nome_imagem)
        rolagem = "hidden" if trava_rolagem else "auto"
        st.markdown(f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            height: 100vh !important;
            overflow: {rolagem} !important;
        }}
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: 100% 100%;
            background-repeat: no-repeat;
            background-position: center;
        }}
        
        /* Painel de vidro da segunda página */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.75);
            padding: 40px;
            border-radius: 20px;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}

        /* FORÇAR TEXTOS EM BRANCO E NEGRITO */
        .glass-panel h2, .glass-panel h3, .glass-panel p, .glass-panel span, label {{
            color: white !important;
            font-weight: bold !important;
            font-size: 1.05rem !important;
        }}

        /* Título em Dourado Negrito */
        .titulo-dourado {{
            color: #FFD700 !important;
            font-weight: 800 !important;
            font-size: 2rem !important;
            margin-bottom: 20px;
        }}

        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. LÓGICA DE NAVEGAÇÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
if "pagina" not in st.session_state:
    st.session_state.pagina = "login"

# ==========================================
# PÁGINA 1: LOGIN (Mantém o estilo anterior)
# ==========================================
if not st.session_state.logado:
    aplicar_estilo_por_pagina("OI_AGRISHOW.jpg", trava_rolagem=True)
    
    st.markdown('<div style="position: absolute; top: 60%; left: 50%; transform: translateX(-50%); width: 350px; text-align: center;">', unsafe_allow_html=True)
    if os.path.exists("logoTriadetransparente.png"):
        logo_64 = get_base64("logoTriadetransparente.png")
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 10px;">', unsafe_allow_html=True)
    
    st.markdown('<div style="background: rgba(0,0,0,0.6); padding: 20px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.2);">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Senha de Acesso")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
    st.markdown('</div></div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA 2: CONFIGURAÇÃO (Textos Brancos e Negrito)
# ==========================================
elif st.session_state.pagina == "dados":
    aplicar_estilo_por_pagina("imagemaptriadefundo.png", trava_rolagem=False)
    
    _, col_central, _ = st.columns([0.1, 0.8, 0.1])
    
    with col_central:
        st.write("<br><br>", unsafe_allow_html=True)
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="titulo-dourado">⚙️ CONFIGURAÇÃO DO PROJETO</div>', unsafe_allow_html=True)
        
        # Dados do Produtor (Labels agora são brancos e negrito via CSS)
        c1, c2, c3 = st.columns(3)
        with c1: produtor = st.text_input("NOME DO PRODUTOR")
        with c2: fazenda = st.text_input("FAZENDA")
        with c3: municipio = st.text_input("MUNICÍPIO / UF")
        
        st.markdown("<br><hr style='opacity: 0.3;'><br>", unsafe_allow_html=True)
        
        # Uploads
        st.markdown("<h3>UPLOAD DE ARQUIVOS</h3>", unsafe_allow_html=True)
        st.markdown("<p>INSIRA O CONTORNO (GEOJSON) E A PLANILHA DE DADOS (COLUNAS A A Y)</p>", unsafe_allow_html=True)
        
        up_geojson = st.file_uploader("ARQUIVO DE CONTORNO (.GEOJSON)", type=["json", "geojson"])
        up_excel = st.file_uploader("PLANILHA DE DADOS (.XLSX)", type=["xlsx"])
        
        st.write("<br>", unsafe_allow_html=True)
        if st.button("🚀 PROCESSAR E ABRIR PLATAFORMA"):
            if up_geojson and up_excel:
                # Aqui o sistema já deve começar a ler as colunas A-Y
                st.session_state.pagina = "plataforma"
                st.rerun()
            else:
                st.warning("⚠️ POR FAVOR, CARREGUE OS DOIS ARQUIVOS.")
        
        st.markdown('</div>', unsafe_allow_html=True)
