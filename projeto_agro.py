import streamlit as st
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 2. CSS COM CONTRASTE DINÂMICO ---
def aplicar_visual_fixo(nome_imagem):
    if os.path.exists(nome_imagem):
        bin_str = get_base64(nome_imagem)
        st.markdown(f"""
        <style>
        /* Trava de visualização sem rolagem */
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

        /* Painel com alto contraste para fundos claros */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.85); 
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            width: 850px;
            margin: auto;
            box-shadow: 0px 10px 40px rgba(0,0,0,0.7);
        }}

        /* Texto branco com contorno/sombra para não sumir no claro */
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

        /* Inputs visíveis em qualquer fundo */
        .stTextInput input {{
            background-color: rgba(255, 255, 255, 1) !important;
            color: #000000 !important;
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
# PÁGINA 1: LOGIN (Fundo OI_AGRISHOW.jpg)
# ==========================================
if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    
    # Bloco de Login centrado na parte inferior
    st.markdown('<div style="position: absolute; top: 58%; left: 50%; transform: translateX(-50%); width: 380px; text-align: center;">', unsafe_allow_html=True)
    
    if os.path.exists("logoTriadetransparente.png"):
        logo_64 = get_base64("logoTriadetransparente.png")
        # Inserção da imagem com fechamento correto das chaves
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 10px; filter: drop-shadow(0px 0px 12px rgba(0,0,0,0.9));">', unsafe_allow_html=True)
    
    st.markdown('<div style="background: rgba(0,0,0,0.8); padding: 25px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.2);">', unsafe_allow_html=True)
    senha = st.text_input("Acesso", type="password", label_visibility="collapsed", placeholder="DIGITE SUA SENHA")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
        else:
            st.error("CHAVE INVÁLIDA")
    st.markdown('</div></div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA 2: CONFIGURAÇÃO (Fundo imagemaptriadefundo.png)
# ==========================================
elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    
    st.write("<br><br><br>", unsafe_allow_html=True)
    _, col_central, _ = st.columns([0.1, 0.8, 0.1])
    
    with col_central:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="titulo-dourado">⚙️ CONFIGURAÇÃO DO PROJETO</div>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.text_input("NOME DO PRODUTOR")
        with c2: st.text_input("FAZENDA")
        with c3: st.text_input("MUNICÍPIO / UF")
        
        st.markdown("<hr style='margin: 15px 0; opacity: 0.3;'>", unsafe_allow_html=True)
        
        st.markdown("<h3>IMPORTAÇÃO DE ARQUIVOS (A-Y)</h3>", unsafe_allow_html=True)
        up_geojson = st.file_uploader("CARREGAR CONTORNO (.GEOJSON)", type=["json", "geojson"])
        up_excel = st.file_uploader("CARREGAR PLANILHA (.XLSX)", type=["xlsx"])
        
        if st.button("🚀 INICIAR ANÁLISE TÉCNICA"):
            if up_geojson and up_excel:
                st.session_state.pagina = "plataforma"
                st.rerun()
            else:
                st.warning("POR FAVOR, INSIRA OS ARQUIVOS.")
        st.markdown('</div>', unsafe_allow_html=True)
