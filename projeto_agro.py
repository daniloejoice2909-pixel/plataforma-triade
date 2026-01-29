import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import base64
import json

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0", initial_sidebar_state="collapsed")

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

# --- 3. ABA 1: ATRIBUTOS (LÓGICA V43) ---
def exibir_aba_atributos():
    st.markdown("## ⚙️ Atributos Estratégicos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("⚪ Solo")
        st.number_input("Ca desejado CTC (%)", value=60.0, key='at_ca_ctc')
        st.number_input("Mg desejado CTC (%)", value=18.0, key='at_mg_ctc')
        st.number_input("PRNT Calcário (%)", value=80.0, key='at_prnt')
        st.number_input("Fator Gesso (Argila * X)", value=15.0, key='at_g_fator')
    with c2:
        st.subheader("🟠 Fósforo (P-Rem)")
        st.number_input("NC 0-4", value=8.0, key='p_nc1')
        st.number_input("NC 4-10", value=10.0, key='p_nc2')
        st.number_input("NC 10-19", value=12.0, key='p_nc3')
        st.number_input("NC 19-30", value=15.0, key='p_nc4')
        st.number_input("NC 30-45", value=20.0, key='p_nc5')
        st.number_input("NC 45-60", value=25.0, key='p_nc6')
    with c3:
        st.subheader("💰 Mercado & Metas")
        st.number_input("Produtividade Meta (sc/ha)", value=80.0, key='at_prod')
        st.number_input("Preço Adubo P (R$/ton)", value=2800.0, key='at_p_preco')
        st.number_input("Preço Gesso (R$/ton)", value=400.0, key='at_g_preco')

# --- 4. ABA 2: MAPAS (RESOLVENDO O VALUEERROR) ---
def exibir_aba_mapas_fertilidade(df):
    st.markdown("### 🗺️ Mapas de Fertilidade")
    logo_base64 = get_base64("LogoTriadeagro.png.png")
    
    # Escala de cor robusta (Substitui o nome 'coolwarm' que dá erro)
    palette_coolwarm = [
        [0.0, 'rgb(58, 76, 192)'], [0.25, 'rgb(145, 185, 255)'],
        [0.5, 'rgb(240, 240, 240)'], [0.75, 'rgb(255, 160, 130)'],
        [1.0, 'rgb(179, 3, 38)']
    ]

    colunas = [c for c in df.columns if c not in ['LATITUDE', 'LONGITUDE', 'CAMPO', 'PONTO']]
    
    for col in colunas:
        df_clean = df.dropna(subset=['LATITUDE', 'LONGITUDE', col])
        if df_clean.empty: continue
        
        st.markdown(f"#### Atributo: {col}")
        fig = go.Figure(go.Histogram2dContour(
            x=df_clean['LONGITUDE'], y=df_clean['LATITUDE'], z=df_clean[col],
            colorscale=palette_coolwarm, # Usando a escala definida acima
            ncontours=6, line_width=0, connectgaps=True
        ))
        
        if logo_base64:
            fig.add_layout_image(dict(source=f"data:image/png;base64,{logo_base64}", xref="paper", yref="paper", 
                                     x=0.5, y=0.5, sizex=0.4, sizey=0.4, xanchor="center", yanchor="middle", opacity=0.15))
        
        fig.update_layout(width=1000, height=550, paper_bgcolor='white', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

# --- 5. TELA DE LOGIN E CONFIG ---
if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    st.markdown('<div style="height: 55vh;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="glass-panel" style="width: 400px; text-align: center;">', unsafe_allow_html=True)
    logo = get_base64("logoTriadetransparente.png")
    if logo: st.markdown(f'<img src="data:image/png;base64,{logo}" style="width: 300px;">', unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", placeholder="Acesso", label_visibility="collapsed")
    if st.button("ENTRAR"):
        if senha == "triade2026": st.session_state.logado = True; st.session_state.pagina = "dados"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    st.markdown('<div style="height: 20vh;"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown("<h2 style='color:#FFD700; text-align:center;'>CONFIGURAÇÃO DO PROJETO</h2>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: st.text_input("Produtor", key='prod')
        with c2: st.text_input("Fazenda", key='faz')
        with c3: st.text_input("Município", key='mun')
        
        up_geo = st.file_uploader("Contorno (.GEOJSON)", type=["geojson", "json"])
        up_xlsx = st.file_uploader("Dados (.XLSX)", type=["xlsx"])
        
        if st.button("🚀 ABRIR PLATAFORMA"):
            if up_xlsx and up_geo:
                st.session_state.dados_excel = pd.read_excel(up_xlsx)
                st.session_state.contorno_json = json.load(up_geo)
                st.session_state.pagina = "plataforma"; st.rerun()
            else: st.error("Carregue o Contorno e a Planilha.")
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{ background: white !important; overflow: auto !important; }</style>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["⚙️ ATRIBUTOS", "🗺️ FERTILIDADE", "💰 RECOMENDAÇÕES", "🛰️ SATÉLITE"])
    with tab1: exibir_aba_atributos()
    with tab2: exibir_aba_mapas_fertilidade(st.session_state.dados_excel)
    with tab3: 
        st.subheader("💰 Recomendações e Custos")
        # Exemplo da recomendação de gesso baseada na argila * fator
        df = st.session_state.dados_excel.copy()
        df['Recomendacao_Gesso'] = (df['ARGILA'] * st.session_state.at_g_fator).clip(lower=400, upper=900)
        st.write("Resumo por Pontos:")
        st.dataframe(df[['PONTO', 'ARGILA', 'Recomendacao_Gesso']].head())
    with tab4: st.write("Sentinel Hub - NDVI")
