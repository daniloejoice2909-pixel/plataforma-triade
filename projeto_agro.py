import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import base64

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(layout="wide", page_title="Tríade Agro V1.0")

# Função segura para carregar imagens
def get_base64(bin_file):
    try:
        if os.path.exists(bin_file):
            with open(bin_file, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode()
    except:
        return ""
    return ""

# --- 2. DESIGN ---
def aplicar_css(imagem):
    b64 = get_base64(imagem)
    if b64:
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{b64}");
            background-size: cover;
        }}
        .glass {{
            background: rgba(0,0,0,0.8); padding: 20px; border-radius: 10px; border: 1px solid gold;
        }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. ABA ATRIBUTOS (V43) ---
def render_atributos():
    st.markdown("### ⚙️ Parâmetros Técnicos")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.info("⚪ Solo & Corretivos")
        st.number_input("CaO %", 36.0, key='a_cao')
        st.number_input("MgO %", 9.0, key='a_mgo')
        st.number_input("PRNT %", 80.0, key='a_prnt')
        st.number_input("Ca Desejado CTC %", 60.0, key='a_ca_ctc')
        st.number_input("Mg Desejado CTC %", 18.0, key='a_mg_ctc')
        st.number_input("Preço Calcário (R$/t)", 190.0, key='a_price_ca')
        st.markdown("---")
        st.write("**Gesso**")
        st.number_input("Fator (Argila x ?)", 15.0, key='a_fator_g')
        st.number_input("Dose Mínima", 400.0, key='a_g_min')
        st.number_input("Dose Máxima", 900.0, key='a_g_max')

    with c2:
        st.info("🟠 Fósforo (P-Rem)")
        st.write("Níveis Críticos (mg/dm³):")
        st.number_input("NC 0-4", 8.0, key='p_nc1')
        st.number_input("NC 4-10", 10.0, key='p_nc2')
        st.number_input("NC 10-19", 12.0, key='p_nc3')
        st.number_input("NC 19-30", 15.0, key='p_nc4')
        st.number_input("NC 30-45", 20.0, key='p_nc5')
        st.number_input("NC 45-60", 25.0, key='p_nc6')
        st.write("Correção:")
        st.number_input("P Exportação (kg/sc)", 0.8, key='p_exp')
        st.number_input("% P2O5 Adubo", 21.0, key='p_teor')

    with c3:
        st.info("🔴 Potássio & Metas")
        st.number_input("K% CTC Desejado", 3.2, key='k_ctc')
        st.number_input("K Exportação (kg/sc)", 1.2, key='k_exp')
        st.number_input("Produtividade (sc/ha)", 80.0, key='k_prod')
        st.number_input("Preço K (R$/t)", 2800.0, key='k_price')
        st.number_input("Preço Gesso (R$/t)", 400.0, key='g_price')

# --- 4. MAPAS (MODO SEGURO) ---
def render_mapas(df):
    st.markdown("### 🗺️ Análise de Fertilidade")
    
    # Lista de colunas para processar
    cols = ['ARGILA', 'P-REM', 'P', 'CA', 'MG', 'K', 'CTC', 'CA%', 'MG%', 'K%', 'PH_CACL2', 'V%']
    
    logo = get_base64("LogoTriadeagro.png.png")
    
    for col in cols:
        try:
            # Verifica se coluna existe e tem dados
            if col not in df.columns: continue
            
            # Limpeza de dados
            df_safe = df.dropna(subset=['LATITUDE', 'LONGITUDE', col])
            df_safe = df_safe[pd.to_numeric(df_safe[col], errors='coerce').notnull()]
            
            if df_safe.empty or df_safe[col].sum() == 0: continue

            st.markdown(f"**{col}**")
            
            # CRIAÇÃO DO MAPA
            fig = go.Figure()
            
            # Usando 'RdBu_r' que é nativo (Red-Blue Reversed = Azul->Vermelho)
            # Isso evita o erro de validação de cores manuais
            fig.add_trace(go.Histogram2dContour(
                x=df_safe['LONGITUDE'],
                y=df_safe['LATITUDE'],
                z=df_safe[col],
                colorscale='RdBu_r', 
                ncontours=6,
                line_width=0,
                connectgaps=True,
                hoverinfo='x+y+z'
            ))
            
            # Adiciona Logo se existir
            if logo:
                fig.add_layout_image(dict(
                    source=f"data:image/png;base64,{logo}",
                    xref="paper", yref="paper", x=0.5, y=0.5,
                    sizex=0.3, sizey=0.3, opacity=0.15, layer="above"
                ))

            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                height=500,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, zeroline=False, visible=False),
                yaxis=dict(showgrid=False, zeroline=False, visible=False)
            )
            
            # Key única baseada na coluna para evitar conflito de Node
            st.plotly_chart(fig, use_container_width=True, key=f"chart_{col}")
            
        except Exception as e:
            st.warning(f"Não foi possível gerar o mapa de {col}. Erro: {e}")

# --- 5. LOGICA PRINCIPAL ---
if "logado" not in st.session_state: st.session_state.logado = False

# TELA 1: LOGIN
if not st.session_state.logado:
    aplicar_css("OI_AGRISHOW.jpg")
    st.markdown('<div style="height: 20vh;"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown('<div class="glass" style="text-align:center;">', unsafe_allow_html=True)
        logo_login = get_base64("logoTriadetransparente.png")
        if logo_login:
            st.markdown(f'<img src="data:image/png;base64,{logo_login}" width="250">', unsafe_allow_html=True)
        
        senha = st.text_input("SENHA DE ACESSO", type="password")
        if st.button("ACESSAR SISTEMA"):
            if senha == "triade2026":
                st.session_state.logado = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# TELA 2: CONFIGURAÇÃO & PLATAFORMA
else:
    # Verifica se os arquivos foram carregados
    if "dados_df" not in st.session_state:
        aplicar_css("imagemaptriadefundo.png")
        st.markdown('<div style="height: 10vh;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.title("📂 Upload de Dados")
        
        c1, c2 = st.columns(2)
        with c1:
            produtor = st.text_input("Produtor")
            fazenda = st.text_input("Fazenda")
        with c2:
            municipio = st.text_input("Município")
        
        f_geo = st.file_uploader("1. Arquivo de Contorno (.geojson)", type=['json', 'geojson'])
        f_xls = st.file_uploader("2. Dados de Solo (.xlsx)", type=['xlsx'])
        
        if f_xls and f_geo:
            if st.button("PROCESSAR DADOS"):
                try:
                    st.session_state.dados_df = pd.read_excel(f_xls)
                    st.session_state.geo_json = json.load(f_geo)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao ler arquivos: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    # TELA 3: O DASHBOARD
    else:
        # Fundo branco para visualização técnica
        st.markdown("<style>[data-testid='stAppViewContainer'] { background-color: white; }</style>", unsafe_allow_html=True)
        
        tab1, tab2, tab3, tab4 = st.tabs(["⚙️ ATRIBUTOS", "🗺️ MAPAS", "💰 RECOMENDAÇÃO", "🛰️ SATÉLITE"])
        
        with tab1:
            render_atributos()
            
        with tab2:
            render_mapas(st.session_state.dados_df)
            
        with tab3:
            st.info("Aguardando definição final das fórmulas de VRT.")
            
        with tab4:
            st.info("Módulo Sentinel Hub em espera.")
