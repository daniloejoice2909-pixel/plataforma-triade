import streamlit as st
import pandas as pd
import os
import base64
from shapely.geometry import shape

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

# --- FUNÇÃO PARA CARREGAR IMAGEM DE FUNDO LOCAL ---
def set_bg_custom():
    # Caminho indicado por você (ajustado para o padrão de leitura do sistema)
    path_img = os.path.expanduser("~/Desktop/site triade/imagemaptriadefundo.png")
    
    if os.path.exists(path_img):
        with open(path_img, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded_string}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .stApp::before {{
            content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.4); z-index: -1;
        }}
        </style>
        """, unsafe_allow_html=True)
    else:
        st.warning("Imagem de fundo não encontrada no caminho especificado. Usando fundo padrão.")

# --- ESTILO GERAL ---
st.markdown("""
    <style>
    .login-box, .data-box {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 30px; border-radius: 15px; backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2); color: white;
    }
    h1, h2, h3 { color: #FFD700 !important; } /* Dourado para títulos */
    </style>
""", unsafe_allow_html=True)

# --- CONTROLE DE NAVEGAÇÃO ---
if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "entrada"

# ==========================================
# PAGINA 1: ENTRADA E ACESSO
# ==========================================
if not st.session_state.logado:
    set_bg_custom()
    _, col_login, _ = st.columns([1, 1, 1])
    with col_login:
        st.write("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"):
            st.image("LogoTriadeagro.png.png", use_container_width=True)
        
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>ACESSO RESTRITO</h2>", unsafe_allow_html=True)
        senha = st.text_input("Senha Mestra:", type="password")
        if st.button("DESBLOQUEAR PLATAFORMA"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
            else: st.error("Senha incorreta.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# PAGINA 2: CONFIGURAÇÃO E DADOS (COLUNAS A-Y)
# ==========================================
elif st.session_state.pagina == "entrada":
    set_bg_custom()
    st.title("📂 Configuração do Projeto e Importação")
    
    with st.container():
        st.markdown('<div class="data-box">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: nome_produtor = st.text_input("Nome do Produtor:")
        with c2: nome_fazenda = st.text_input("Nome da Fazenda:")
        with c3: municipio = st.text_input("Município/UF:")
        
        st.divider()
        
        up_geojson = st.file_uploader("Baixar Arquivo de Contorno (GeoJSON)", type=["json", "geojson"])
        up_excel = st.file_uploader("Baixar Planilha de Dados (Colunas A-Y)", type=["xlsx"])
        
        if st.button("PROCESSAR E ABRIR PLATAFORMA"):
            if up_geojson and up_excel:
                # 1. Leitura rigorosa das colunas A até Y
                df_raw = pd.read_excel(up_excel)
                # Mapeamento exato conforme seu script: A=0, B=1, ... Y=24
                col_map = {
                    0:'Lat', 1:'Lon', 4:'Argila', 5:'P_rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 
                    10:'Al', 11:'H_Al', 12:'S', 13:'B', 14:'Mn', 15:'Zn', 16:'Cu', 17:'Fe', 
                    18:'Mo', 19:'pH_CaCl2', 20:'CTC', 21:'Ca_perc', 22:'Mg_perc', 23:'K_perc', 24:'Ca_Mg'
                }
                
                df_final = pd.DataFrame()
                for idx, name in col_map.items():
                    df_final[name] = pd.to_numeric(df_raw.iloc[:, idx], errors='coerce')
                
                st.session_state.df_trabalho = df_final.dropna(subset=['Lat', 'Lon'])
                st.session_state.contorno = up_geojson
                st.session_state.info_cliente = {"produtor": nome_produtor, "fazenda": nome_fazenda, "cidade": municipio}
                
                st.session_state.pagina = "plataforma"
                st.rerun()
            else:
                st.warning("Por favor, carregue ambos os arquivos para prosseguir.")
        st.markdown('</div>', unsafe_allow_html=True)

# PÁGINA 3 (Aguardando desenvolvimento do "Olho da Mosca")
elif st.session_state.pagina == "plataforma":
    st.write(f"### Bem-vindo à Plataforma Tríade Agro 1.0 - {st.session_state.info_cliente['fazenda']}")
    st.info("Próximo passo: Desenvolver a Terceira Página - Aba Atributos.")
