import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import base64

# --- CONFIGURAÇÃO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- ESTILIZAÇÃO ---
def aplicar_estilo(imagem_fundo):
    bin_str = get_base64(imagem_fundo)
    if bin_str:
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/png;base64,{bin_str}");
                background-size: cover;
            }}
            .glass-card {{
                background: rgba(0, 0, 0, 0.85); padding: 25px; border-radius: 15px;
                color: white; border: 1px solid #FFD700; margin-bottom: 20px;
            }}
            </style>
        """, unsafe_allow_html=True)

# --- MOTOR DE MAPAS (CORRIGIDO PARA EVITAR ERRO DE NODE) ---
def desenhar_mapa(df, coluna, titulo):
    # Limpeza rigorosa
    df_clean = df.dropna(subset=['LATITUDE', 'LONGITUDE', coluna])
    if df_clean.empty or df_clean[coluna].sum() == 0:
        return # Não renderiza se estiver vazio
    
    palette_coolwarm = [[0, 'blue'], [0.5, 'yellow'], [1, 'red']]
    
    fig = go.Figure()
    fig.add_trace(go.Histogram2dContour(
        x=df_clean['LONGITUDE'], y=df_clean['LATITUDE'], z=df_clean[coluna],
        colorscale=palette_coolwarm, ncontours=6, line_width=0, connectgaps=True
    ))
    
    # Logo Centralizada
    logo_base64 = get_base64("LogoTriadeagro.png.png")
    if logo_base64:
        fig.add_layout_image(dict(
            source=f"data:image/png;base64,{logo_base64}",
            xref="paper", yref="paper", x=0.5, y=0.5,
            sizex=0.3, sizey=0.3, xanchor="center", yanchor="middle", opacity=0.1
        ))

    fig.update_layout(
        title=titulo, width=900, height=550,
        paper_bgcolor='white', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=40, b=10)
    )
    # O segredo para não dar erro de Node: usar uma key única baseada na coluna
    st.plotly_chart(fig, use_container_width=True, key=f"map_{coluna}")

# --- ESTRUTURA DE ABAS ---
def aba_atributos():
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("⚪ Calcário & Gesso")
        st.number_input("PRNT %", value=80.0, key='p_prnt')
        st.number_input("Ca desejado CTC (%)", value=60.0, key='p_ca_ctc')
        st.number_input("Mg desejado CTC (%)", value=18.0, key='p_mg_ctc')
        st.number_input("Fator Gesso (Argila * X)", value=15.0, key='p_g_fator')
    with c2:
        st.subheader("🟠 Fósforo (P-Rem)")
        st.number_input("NC 0-4", value=8.0, key='nc1')
        st.number_input("NC 4.1-10", value=10.0, key='nc2')
        st.number_input("NC 10.1-19", value=12.0, key='nc3')
        st.number_input("NC 19.1-30", value=15.0, key='nc4')
        st.number_input("NC 30.1-45", value=20.0, key='nc5')
        st.number_input("NC 45-60", value=25.0, key='nc6')
    with c3:
        st.subheader("💰 Mercado")
        st.number_input("Produtividade Meta (sc/ha)", value=80.0, key='p_meta')
        st.number_input("Preço Adubo P (R$/ton)", value=2800.0, key='p_preco_p')
        st.number_input("Preço Gesso (R$/ton)", value=400.0, key='p_preco_g')
    st.markdown('</div>', unsafe_allow_html=True)

# --- LOGIN E NAVEGAÇÃO ---
if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

if not st.session_state.logado:
    aplicar_estilo("OI_AGRISHOW.jpg")
    st.markdown('<div class="glass-card" style="width:400px; margin:20vh auto; text-align:center;">', unsafe_allow_html=True)
    st.image("logoTriadetransparente.png", width=280)
    senha = st.text_input("Chave de Acesso", type="password")
    if st.button("DESBLOQUEAR"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "dados":
    aplicar_estilo("imagemaptriadefundo.png")
    st.markdown('<div class="glass-card" style="margin-top:10vh;">', unsafe_allow_html=True)
    st.title("⚙️ CONFIGURAÇÃO DO PROJETO")
    c1, c2, c3 = st.columns(3)
    with c1: st.text_input("Produtor", key='u_prod')
    with c2: st.text_input("Fazenda", key='u_faz')
    with c3: st.text_input("Município", key='u_mun')
    
    up_geo = st.file_uploader("Contorno (.GEOJSON)", type=["geojson", "json"])
    up_xlsx = st.file_uploader("Dados (.XLSX)", type=["xlsx"])
    
    if st.button("🚀 INICIAR"):
        if up_xlsx and up_geo:
            st.session_state.dados_excel = pd.read_excel(up_xlsx)
            st.session_state.contorno = json.load(up_geo)
            st.session_state.pagina = "plataforma"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{ background: white !important; }</style>", unsafe_allow_html=True)
    tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE"])
    
    with tabs[0]: aba_atributos()
    with tabs[1]:
        df = st.session_state.dados_excel
        # Mapeando colunas conforme o padrão A-Y enviado
        colunas_v43 = ['ARGILA', 'P-REM', 'P', 'CA', 'MG', 'K', 'PH_CACL2', 'CTC', 'CA%', 'MG%', 'K%']
        for col in colunas_v43:
            if col in df.columns:
                desenhar_mapa(df, col, f"Distribuição de {col}")
    with tabs[2]:
        st.info("Cálculos de Recomendação V43 processando...")
