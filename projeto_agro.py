import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import base64
import json

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

# --- 3. FUNÇÕES TÉCNICAS (ABAS) ---

def exibir_aba_atributos():
    st.markdown("## ⚙️ Painel de Atributos Estratégicos")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("⚪ Correção de Solo")
        st.number_input("CaO %", value=36.0, key='ca_cao')
        st.number_input("MgO %", value=9.0, key='ca_mgo')
        st.number_input("PRNT %", value=80.0, key='ca_prnt')
        st.number_input("Ca% desejado na CTC", value=60.0, key='ca_ctc')
        st.number_input("Preço Calcário (R$/ton)", value=190.0, key='ca_preco')
        st.number_input("Fator Gesso (Argila g/kg * X)", value=15.0, key='g_fator')

    with col2:
        st.subheader("🟠 Fósforo (P) - Níveis Críticos")
        st.number_input("NC 0-4 (P-Rem)", value=8.0, key='p_nc1')
        st.number_input("NC 4.1-10 (P-Rem)", value=10.0, key='p_nc2')
        st.number_input("NC 10.1-19 (P-Rem)", value=12.0, key='p_nc3')
        st.number_input("NC 19.1-30 (P-Rem)", value=15.0, key='p_nc4')
        st.number_input("NC 30.1-45 (P-Rem)", value=20.0, key='p_nc5')
        st.number_input("NC 45.1-60 (P-Rem)", value=25.0, key='p_nc6')
        st.number_input("Preço Adubo P (R$/ton)", value=2800.0, key='p_preco')

    with col3:
        st.subheader("🔴 Potássio & Metas")
        st.number_input("K% desejado na CTC", value=3.2, key='k_ctc')
        st.number_input("Exportação K (kg/sc)", value=1.2, key='k_exp')
        st.number_input("Produtividade Esperada (sc/ha)", value=80.0, key='prod_meta')
        st.number_input("Preço Adubo K (R$/ton)", value=2800.0, key='k_preco')
        st.number_input("Preço Gesso (R$/ton)", value=400.0, key='g_preco')

def exibir_aba_mapas_fertilidade(df):
    st.markdown("### 🗺️ Mapas de Fertilidade (Zonas de Manejo)")
    logo_base64 = get_base64("LogoTriadeagro.png.png")
    colunas = [c for c in df.columns if c not in ['LATITUDE', 'LONGITUDE', 'CAMPO', 'PONTO']]
    
    for col in colunas:
        df_clean = df.dropna(subset=['LATITUDE', 'LONGITUDE', col])
        if df_clean.empty: continue
        
        st.markdown(f"#### Atributo: {col}")
        fig = go.Figure(go.Histogram2dContour(
            x=df_clean['LONGITUDE'], y=df_clean['LATITUDE'], z=df_clean[col],
            colorscale='coolwarm', ncontours=6, line_width=0, connectgaps=True
        ))
        
        if logo_base64:
            fig.add_layout_image(dict(source=f"data:image/png;base64,{logo_base64}", xref="paper", yref="paper", 
                                     x=0.5, y=0.5, sizex=0.4, sizey=0.4, xanchor="center", yanchor="middle", opacity=0.12))
        
        fig.update_layout(width=1000, height=600, paper_bgcolor='white', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

def exibir_aba_recomendacoes(df):
    st.markdown("## 💰 Recomendações Técnicas V43")
    # Exemplo de cálculo usando o fator que você definiu (Argila * 15)
    df['Recomendacao_Gesso'] = (df['ARGILA'] * st.session_state.g_fator).clip(lower=400, upper=900)
    df['Custo_Invest'] = (df['Recomendacao_Gesso']/1000) * st.session_state.g_preco
    
    df['Zona'] = pd.qcut(df['Custo_Invest'].rank(method='first'), 6, labels=["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"])
    resumo = df.groupby('Zona', observed=True).agg({'Recomendacao_Gesso': 'mean', 'Custo_Invest': 'mean'}).reset_index()
    st.table(resumo.style.format(precision=2))

# --- 4. FLUXO DE NAVEGAÇÃO ---

if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    st.markdown('<div style="height: 55vh;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="glass-panel" style="width: 400px; text-align: center;">', unsafe_allow_html=True)
    logo = get_base64("logoTriadetransparente.png")
    if logo: st.markdown(f'<img src="data:image/png;base64,{logo}" style="width: 300px; margin-bottom: 15px;">', unsafe_allow_html=True)
    senha = st.text_input("Acesso", type="password", placeholder="SENHA", label_visibility="collapsed")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026": st.session_state.logado = True; st.session_state.pagina = "dados"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    st.markdown('<div style="height: 20vh;"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown("<h2 style='color:#FFD700; text-align:center;'>⚙️ CONFIGURAÇÃO DO PROJETO</h2>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: produtor = st.text_input("NOME DO PRODUTOR")
        with c2: fazenda = st.text_input("FAZENDA")
        with c3: municipio = st.text_input("MUNICÍPIO / UF")
        
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            up_geo = st.file_uploader("📦 ARQUIVO DE CONTORNO (.GEOJSON)", type=["geojson", "json"])
        with col_u2:
            up_xlsx = st.file_uploader("📊 PLANILHA DE DADOS (.XLSX)", type=["xlsx"])
            
        if st.button("🚀 INICIAR ANÁLISE ESTRATÉGICA"):
            if up_xlsx and up_geo:
                st.session_state.dados_excel = pd.read_excel(up_xlsx)
                st.session_state.contorno = json.load(up_geo)
                st.session_state.pagina = "plataforma"
                st.rerun()
            else:
                st.error("ERRO: Carregue o arquivo de Contorno E a Planilha de Dados.")
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{ background: white !important; overflow: auto !important; }</style>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["⚙️ ATRIBUTOS", "🗺️ FERTILIDADE", "💰 RECOMENDAÇÕES", "🛰️ SATÉLITE"])
    
    with tab1: exibir_aba_atributos()
    with tab2: exibir_aba_mapas_fertilidade(st.session_state.dados_excel)
    with tab3: exibir_aba_recomendacoes(st.session_state.dados_excel)
    with tab4:
        st.subheader("🛰️ Integração Sentinel Hub")
        st.text_input("SENTINEL_CLIENT_ID", type="password")
        st.text_input("SENTINEL_CLIENT_SECRET", type="password")
        st.button("CONECTAR SATÉLITE")
