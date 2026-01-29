import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
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

# --- 2. CSS PARA DESIGN ---
def aplicar_visual_fixo(nome_imagem):
    bin_str = get_base64(nome_imagem)
    if bin_str:
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: 100% 100%;
            background-repeat: no-repeat;
        }}
        .glass-panel {{
            background: rgba(0, 0, 0, 0.85); padding: 25px; border-radius: 15px;
            backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.3);
            width: 850px; margin: auto;
        }}
        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. ABA 1: ATRIBUTOS (COM PERSISTÊNCIA) ---
def exibir_aba_atributos():
    st.markdown("## ⚙️ Painel de Atributos Estratégicos")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("⚪ Calcário")
        ca_prnt = st.number_input("PRNT %", value=80.0, key='ca_prnt')
        ca_preco = st.number_input("Preço Calcário (R$/ton)", value=190.0, key='ca_preco')
    
    with col2:
        st.subheader("🟠 Fósforo (P)")
        # Faixas de P-Rem que você solicitou
        p_rem_0_4 = st.number_input("NC 0 a 4 (P-Rem)", value=8.0, key='p04')
        p_rem_4_10 = st.number_input("NC 4.1 a 10 (P-Rem)", value=10.0, key='p410')
        p_preco = st.number_input("Preço Adubo P (R$/ton)", value=2800.0, key='ppreco')
        
    with col3:
        st.subheader("🔴 Potássio & Gesso")
        g_fator = st.number_input("Fator Gesso (Argila * 15)", value=15.0, key='gfator')
        g_preco = st.number_input("Preço Gesso (R$/ton)", value=400.0, key='gpreco')
        prod_exp = st.number_input("Produtividade Esperada (sc/ha)", value=80.0, key='prod_exp')

# --- 4. ABA 2: MAPAS FERTILIDADE (CONFIGURAÇÃO IDEAL) ---
def exibir_aba_mapas_fertilidade(df):
    st.markdown("### 🗺️ Mapas de Fertilidade (Zonas de Manejo)")
    logo_path = "LogoTriadeagro.png.png"
    logo_base64 = get_base64(logo_path)
    
    # Filtra colunas de dados
    colunas_dados = [c for c in df.columns if c not in ['LATITUDE', 'LONGITUDE', 'CAMPO', 'PONTO']]
    
    for col in colunas_dados:
        # Limpeza rigorosa para evitar o ValueError
        df_clean = df.dropna(subset=['LATITUDE', 'LONGITUDE', col])
        if df_clean.empty: continue
        
        st.markdown(f"#### Atributo: {col}")
        
        # O segredo do preenchimento e da cor:
        fig = go.Figure()
        fig.add_trace(go.Histogram2dContour(
            x=df_clean['LONGITUDE'],
            y=df_clean['LATITUDE'],
            z=df_clean[col],
            colorscale='coolwarm',
            ncontours=6,
            line_width=0,
            hoverinfo='z',
            connectgaps=True # Faz o mapa ter "forma" mesmo com poucos pontos
        ))
        
        if logo_base64:
            fig.add_layout_image(dict(
                source=f"data:image/png;base64,{logo_base64}",
                xref="paper", yref="paper", x=0.5, y=0.5,
                sizex=0.45, sizey=0.45, xanchor="center", yanchor="middle",
                opacity=0.12, layer="above"
            ))

        fig.update_layout(
            width=1000, height=600,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='white',
            margin=dict(l=20, r=20, t=40, b=20),
            coloraxis_colorbar=dict(thickness=15, title=col)
        )
        st.plotly_chart(fig, use_container_width=True)

# --- 5. ABA 3: RECOMENDAÇÕES (V43) ---
def exibir_aba_recomendacoes(df):
    st.markdown("## 💰 Recomendações e Custos por Zona")
    # Lógica de cálculo baseada nos inputs da Aba 1
    df['Dose_Gesso'] = (df['ARGILA'] * st.session_state.gfator).clip(lower=400, upper=900)
    df['Custo_HA'] = (df['Dose_Gesso']/1000) * st.session_state.gpreco
    
    # Criando as 6 zonas de investimento
    df['Zona'] = pd.qcut(df['Custo_HA'].rank(method='first'), 6, labels=["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"])
    
    resumo = df.groupby('Zona', observed=True).agg({
        'Dose_Gesso': 'mean',
        'Custo_HA': 'mean'
    }).reset_index()
    
    st.table(resumo.style.format(precision=2))

# --- 6. FLUXO DE NAVEGAÇÃO ---
if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    st.markdown('<div style="height: 55vh;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="glass-panel" style="width: 400px; text-align: center;">', unsafe_allow_html=True)
    logo_64 = get_base64("logoTriadetransparente.png")
    if logo_64: st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 300px;">', unsafe_allow_html=True)
    senha = st.text_input("Acesso", type="password", placeholder="CHAVE DE ACESSO", label_visibility="collapsed")
    if st.button("DESBLOQUEAR"):
        if senha == "triade2026": st.session_state.logado = True; st.session_state.pagina = "dados"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    st.markdown('<div style="height: 25vh;"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown("<h2 style='color:#FFD700; text-align:center;'>CONFIGURAÇÃO</h2>", unsafe_allow_html=True)
        up_excel = st.file_uploader("CARREGAR PLANILHA (.XLSX)", type=["xlsx"])
        if st.button("🚀 INICIAR"):
            if up_excel:
                st.session_state.dados_excel = pd.read_excel(up_excel)
                st.session_state.pagina = "plataforma"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{ background: white !important; overflow: auto !important; }</style>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["⚙️ ATRIBUTOS", "🗺️ FERTILIDADE", "💰 RECOMENDAÇÕES", "🛰️ SATÉLITE"])
    
    with tab1: exibir_aba_atributos()
    with tab2: exibir_aba_mapas_fertilidade(st.session_state.dados_excel)
    with tab3: exibir_aba_recomendacoes(st.session_state.dados_excel)
    with tab4: 
        st.subheader("🛰️ Integração Sentinel Hub")
        st.info("Chaves de acesso pendentes de configuração.")
