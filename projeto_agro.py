import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import base64

# --- 1. CONFIGURAÇÕES INICIAIS ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- 2. CSS DE TRAVAMENTO E VISUAL ---
def aplicar_visual_fixo(nome_imagem):
    bin_str = get_base64(nome_imagem)
    if bin_str:
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: 100% 100%;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        .glass-panel {{
            background: rgba(0, 0, 0, 0.85); 
            padding: 25px; border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        label, p, span, h3 {{ color: white !important; font-weight: bold !important; text-transform: uppercase; font-size: 0.85rem !important; }}
        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. LOGICA DE NAVEGAÇÃO ---
if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    st.markdown('<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 350px; text-align: center;">', unsafe_allow_html=True)
    logo_64 = get_base64("logoTriadetransparente.png")
    if logo_64: st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 300px; margin-bottom: 20px;">', unsafe_allow_html=True)
    senha = st.text_input("ACESSO", type="password", placeholder="SENHA")
    if st.button("ENTRAR"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "config"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- TELA DE CONFIGURAÇÃO E UPLOAD ---
elif st.session_state.pagina == "config":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    with st.container():
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.title("⚙️ CONFIGURAÇÃO DO PROJETO")
        c1, c2, c3 = st.columns(3)
        produtor = c1.text_input("PRODUTOR")
        fazenda = c2.text_input("FAZENDA")
        safra = c3.text_input("SAFRA")
        
        up_excel = st.file_uploader("PLANILHA TÉCNICA (COLUNAS A-Y)", type=["xlsx"])
        if st.button("🚀 ABRIR PLATAFORMA"):
            if up_excel:
                st.session_state.dados_excel = pd.read_excel(up_excel)
                st.session_state.pagina = "plataforma"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- TELA PRINCIPAL (ABAS) ---
elif st.session_state.pagina == "plataforma":
    # Aqui o fundo fica limpo ou neutro para facilitar a leitura dos mapas
    st.markdown("<style>body { background-color: #111; }</style>", unsafe_allow_html=True)
    
    aba1, aba2, aba3, aba4 = st.tabs(["⚙️ ATRIBUTOS", "🗺️ MAPAS FERTILIDADE", "💰 RECOMENDAÇÕES", "📄 RELATÓRIO PDF"])

    with aba1:
        st.subheader("Configurações de Recomendação")
        # Aqui você coloca os inputs de preços e fatores que discutimos
        g_fator = st.number_input("Fator Gesso (Argila * X)", value=15.0)
        p_preco = st.number_input("Preço Adubo P (R$/ton)", value=2800.0)
        # (Adicionar os outros conforme o código anterior de atributos)

    with aba2:
        st.subheader("Zonas de Manejo")
        df = st.session_state.dados_excel
        # Filtramos colunas de dados
        cols_mapa = [c for c in df.columns if c not in ['LATITUDE', 'LONGITUDE', 'CAMPO', 'PONTO']]
        for col in cols_mapa:
            if df[col].sum() > 0:
                # Lógica do mapa Plotly com 100% de preenchimento
                fig = go.Figure(go.Histogram2dContour(
                    x=df['LONGITUDE'], y=df['LATITUDE'], z=df[col],
                    colorscale='coolwarm', ncontours=6, line_width=0
                ))
                fig.update_layout(title=f"Mapa de {col}", width=800, height=500)
                st.plotly_chart(fig)
                st.markdown(f"<p style='text-align:center'>Min: {df[col].min()} | Méd: {df[col].mean():.2f} | Max: {df[col].max()}</p>", unsafe_allow_html=True)

    with aba3:
        st.write("Cálculos de Recomendação e Custos por Hectare")
        # Aqui entra a lógica de Gesso, P, K e Calcário que fizemos
