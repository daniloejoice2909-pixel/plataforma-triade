import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 2. CSS PARA TRAVAMENTO TOTAL (DUAS TELAS) ---
def aplicar_visual_fixo(nome_imagem):
    if os.path.exists(nome_imagem):
        bin_str = get_base64(nome_imagem)
        st.markdown(f"""
        <style>
        /* Bloqueio absoluto de rolagem */
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
            display: flex;
            justify-content: center;
            align-items: center;
        }}

        /* Painel de vidro compacto para a segunda página */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.75);
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            width: 800px;
            margin: auto;
        }}

        /* Textos em Branco e Negrito conforme solicitado */
        label, p, span, h3 {{
            color: white !important;
            font-weight: bold !important;
            text-transform: uppercase;
            font-size: 0.9rem !important;
        }}

        .titulo-dourado {{
            color: #FFD700 !important;
            font-weight: 900 !important;
            font-size: 1.8rem !important;
            text-align: center;
            margin-bottom: 20px;
        }}

        /* Esconde elementos nativos */
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
    
    # Bloco de Login
    st.markdown('<div style="position: absolute; top: 60%; left: 50%; transform: translateX(-50%); width: 350px; text-align: center;">', unsafe_allow_html=True)
    
    if os.path.exists("logoTriadetransparente.png"):
        logo_64 = get_base64("logoTriadetransparente.png")
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 10px;">', unsafe_allow_html=True)
    
    st.markdown('<div style="background: rgba(0,0,0,0.6); padding: 20px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1);">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="DIGITE A SENHA")
    if st.button("DESBLOQUEAR ACESSO"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
        else:
            st.error("SENHA INCORRETA")
    st.markdown('</div></div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA 2: CONFIGURAÇÃO (Fundo TriadeFundo)
# ==========================================
elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    
    # Centralização forçada do formulário
    st.write("<br><br><br>", unsafe_allow_html=True)
    _, col_central, _ = st.columns([0.1, 0.8, 0.1])
    
    with col_central:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="titulo-dourado">CONFIGURAÇÃO DO PROJETO</div>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.text_input("NOME DO PRODUTOR")
        with c2: st.text_input("FAZENDA")
        with c3: st.text_input("MUNICÍPIO / UF")
        
        st.markdown("<hr style='margin: 20px 0; opacity: 0.2;'>", unsafe_allow_html=True)
        
        st.markdown("<h3>IMPORTAÇÃO DE ARQUIVOS TÉCNICOS</h3>", unsafe_allow_html=True)
        up_geojson = st.file_uploader("CONTORNO DA ÁREA (.GEOJSON)", type=["json", "geojson"])
        up_excel = st.file_uploader("PLANILHA DE DADOS (COLUNAS A-Y)", type=["xlsx"])
        
        if st.button("🚀 INICIAR ANÁLISE ESTRATÉGICA"):
            if up_geojson and up_excel:
                st.session_state.pagina = "plataforma"
                st.rerun()
            else:
                st.warning("CARREGUE OS DOIS ARQUIVOS PARA CONTINUAR.")
        
        st.markdown('</div>', unsafe_allow_html=True)
