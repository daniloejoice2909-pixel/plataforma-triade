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

# --- 2. CSS PARA IMAGEM FULLSCREEN E ZERO ROLAGEM ---
def aplicar_estilo_fixo():
    img_fundo = "OI_AGRISHOW.jpg"
    img_logo = "logoTriadetransparente.png"
    
    if os.path.exists(img_fundo):
        bin_str = get_base64(img_fundo)
        st.markdown(f"""
        <style>
        /* Bloqueio de rolagem e ajuste de imagem */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"] {{
            height: 100vh !important;
            width: 100vw !important;
            overflow: hidden !important;
            margin: 0; padding: 0;
        }}
        .stApp {{
            background-image: url("data:image/jpg;base64,{bin_str}");
            background-size: 100% 100%;
            background-repeat: no-repeat;
            background-position: center;
        }}
        /* Remove espaços internos do Streamlit que causam rolagem */
        [data-testid="stVerticalBlock"] {{ gap: 0; }}
        .block-container {{ padding: 0 !important; }}

        .triade-login-container {{
            position: absolute;
            top: 65%; left: 50%;
            transform: translateX(-50%);
            width: 320px;
            text-align: center;
            z-index: 1000;
        }}
        .logo-triade {{ width: 380px; filter: drop-shadow(0px 4px 10px rgba(0,0,0,0.6)); }}
        .login-box-compacta {{
            background-color: rgba(0, 0, 0, 0.65);
            padding: 15px; border-radius: 12px;
            backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)
    return img_logo

# --- 3. LÓGICA DE NAVEGAÇÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
if "pagina" not in st.session_state:
    st.session_state.pagina = "login"

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    logo_path = aplicar_estilo_fixo()
    st.markdown('<div class="triade-login-container">', unsafe_allow_html=True)
    if os.path.exists(logo_path):
        logo_64 = get_base64(logo_path)
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" class="logo-triade">', unsafe_allow_html=True)
    
    st.markdown('<div class="login-box-compacta">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Senha de Acesso")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
        else:
            st.error("Chave Inválida")
    st.markdown('</div></div>', unsafe_allow_html=True)

# --- TELA DE DADOS (PÁGINA 2) ---
elif st.session_state.pagina == "dados":
    st.markdown("""<style>.stApp { background: #1a1a1a; } .block-container { padding: 2rem !important; overflow: auto !important; }</style>""", unsafe_allow_html=True)
    
    st.title("📂 Importação de Dados - Tríade Agro")
    
    with st.expander("👤 Informações do Produtor", expanded=True):
        col1, col2, col3 = st.columns(3)
        produtor = col1.text_input("Nome do Produtor")
        fazenda = col2.text_input("Fazenda")
        municipio = col3.text_input("Município")

    with st.container():
        st.subheader("📤 Upload de Arquivos")
        up_contorno = st.file_uploader("Arquivo de Contorno (GeoJSON)", type=["json", "geojson"])
        up_planilha = st.file_uploader("Planilha de Dados (Colunas A a Y)", type=["xlsx"])

    if st.button("⚙️ PROCESSAR DADOS E ABRIR PLATAFORMA"):
        if up_contorno and up_planilha:
            # Lógica para ler a planilha respeitando A-Y
            df = pd.read_excel(up_planilha)
            st.session_state.dados_completos = df
            st.session_state.pagina = "plataforma"
            st.success("Dados carregados com sucesso!")
            st.rerun()
        else:
            st.warning("Aguardando o upload de ambos os arquivos.")
