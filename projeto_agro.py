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
        /* Container de vidro para a segunda página */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.7);
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
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
# PÁGINA 1: LOGIN (Fundo OI_AGRISHOW)
# ==========================================
if not st.session_state.logado:
    aplicar_estilo_por_pagina("OI_AGRISHOW.jpg", trava_rolagem=True)
    
    st.markdown('<div style="position: absolute; top: 60%; left: 50%; transform: translateX(-50%); width: 350px; text-align: center;">', unsafe_allow_html=True)
    
    # Logo
    if os.path.exists("logoTriadetransparente.png"):
        logo_64 = get_base64("logoTriadetransparente.png")
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 10px;">', unsafe_allow_html=True)
    
    # Caixa de Login
    st.markdown('<div style="background: rgba(0,0,0,0.6); padding: 20px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.2);">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Senha de Acesso")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
    st.markdown('</div></div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA 2: CONFIGURAÇÃO (Fundo imagemaptriadefundo)
# ==========================================
elif st.session_state.pagina == "dados":
    aplicar_estilo_por_pagina("imagemaptriadefundo.png", trava_rolagem=False)
    
    # Centralizando o painel de configuração
    _, col_central, _ = st.columns([0.1, 0.8, 0.1])
    
    with col_central:
        st.write("<br><br>", unsafe_allow_html=True)
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown("<h2 style='color: #FFD700;'>⚙️ Configuração do Projeto</h2>", unsafe_allow_html=True)
        
        # Dados do Produtor
        c1, c2, c3 = st.columns(3)
        produtor = c1.text_input("Nome do Produtor")
        fazenda = c2.text_input("Fazenda")
        municipio = c3.text_input("Município/UF")
        
        st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)
        
        # Uploads
        st.subheader("Upload de Arquivos")
        st.write("Selecione o contorno da área e a planilha de dados (Colunas A a Y).")
        
        up_geojson = st.file_uploader("Arquivo de Contorno (GeoJSON)", type=["json", "geojson"])
        up_excel = st.file_uploader("Planilha de Dados (Excel)", type=["xlsx"])
        
        if st.button("🚀 PROCESSAR E ABRIR PLATAFORMA"):
            if up_geojson and up_excel:
                # Aqui entra o motor de leitura A-Y que definimos
                st.session_state.pagina = "plataforma"
                st.success("Dados carregados! Abrindo painel técnico...")
                st.rerun()
            else:
                st.error("Por favor, carregue ambos os arquivos para continuar.")
        
        st.markdown('</div>', unsafe_allow_html=True)
