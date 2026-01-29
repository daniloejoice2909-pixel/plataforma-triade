import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import base64

# --- CONFIGURAÇÕES TÉCNICAS ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- DESIGN E ESTILO ---
def aplicar_estilo_v43(imagem_fundo):
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

# --- ENGINE DE MAPAS COM CONTORNO ---
def renderizar_mapa_com_contorno(df, coluna, geojson_data):
    try:
        # Limpeza de dados
        df_c = df.dropna(subset=['LATITUDE', 'LONGITUDE', coluna]).copy()
        df_c[coluna] = pd.to_numeric(df_c[coluna], errors='coerce')
        df_c = df_c.dropna(subset=[coluna])
        
        if df_c.empty: return

        fig = go.Figure()

        # 1. Camada de Fertilidade (Histogram2dContour)
        fig.add_trace(go.Histogram2dContour(
            x=df_c['LONGITUDE'], y=df_c['LATITUDE'], z=df_c[coluna],
            colorscale='RdBu_r', ncontours=6, line_width=0, hoverinfo='z'
        ))

        # 2. Camada de Contorno do Talhão (GeoJSON)
        if geojson_data:
            for feature in geojson_data['features']:
                coords = feature['geometry']['coordinates'][0]
                if isinstance(coords[0], list) and len(coords[0]) > 2: # Caso de Polígonos complexos
                    coords = coords[0]
                lons, lats = zip(*coords)
                fig.add_trace(go.Scatter(
                    x=lons, y=lats, mode='lines',
                    line=dict(color='black', width=3),
                    fill='toself', fillcolor='rgba(0,0,0,0)',
                    showlegend=False, hoverinfo='skip'
                ))
            # Ajuste de zoom automático no contorno
            fig.update_xaxes(range=[min(lons)-0.0005, max(lons)+0.0005])
            fig.update_yaxes(range=[min(lats)-0.0005, max(lats)+0.0005])

        # 3. Logo Triadeagro (Marca d'água)
        logo_b64 = get_base64("LogoTriadeagro.png.png")
        if logo_b64:
            fig.add_layout_image(dict(
                source=f"data:image/png;base64,{logo_b64}",
                xref="paper", yref="paper", x=0.5, y=0.5,
                sizex=0.2, sizey=0.2, xanchor="center", yanchor="middle", opacity=0.15
            ))

        fig.update_layout(
            title=f"Distribuição Espacial: {coluna}",
            height=600, paper_bgcolor='white', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1)
        )
        
        st.plotly_chart(fig, use_container_width=True, key=f"map_{coluna}")
    except Exception as e:
        st.error(f"Erro ao gerar mapa de {coluna}: {e}")

# --- LÓGICA DE NAVEGAÇÃO ---
if "logado" not in st.session_state: st.session_state.logado = False
if "passo" not in st.session_state: st.session_state.passo = "login"

if not st.session_state.logado:
    aplicar_estilo_v43("OI_AGRISHOW.jpg")
    st.markdown('<div class="glass-card" style="width:400px; margin:20vh auto; text-align:center;">', unsafe_allow_html=True)
    st.image("logoTriadetransparente.png", width=250) if os.path.exists("logoTriadetransparente.png") else st.title("Tríade Agro")
    senha = st.text_input("Chave de Acesso", type="password")
    if st.button("DESBLOQUEAR"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

else:
    if "dados" not in st.session_state:
        aplicar_estilo_v43("imagemaptriadefundo.png")
        st.markdown('<div class="glass-card" style="margin-top:10vh;">', unsafe_allow_html=True)
        st.subheader("📂 Configuração do Talhão")
        c1, c2 = st.columns(2)
        with c1: f_geo = st.file_uploader("Arquivo de Contorno (.geojson)", type=['geojson', 'json'])
        with c2: f_xls = st.file_uploader("Planilha de Solo (.xlsx)", type=['xlsx'])
        
        if f_geo and f_xls:
            if st.button("CARREGAR PLATAFORMA"):
                st.session_state.dados = pd.read_excel(f_xls)
                st.session_state.geo = json.load(f_geo)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # --- DASHBOARD PRINCIPAL ---
        st.markdown("<style>[data-testid='stAppViewContainer']{background:white !important;}</style>", unsafe_allow_html=True)
        t = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÃO", "🛰️ SATÉLITE"])
        
        with t[0]:
            st.markdown("### Configurações Técnicas V43")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.number_input("Gesso: Argila g/kg * X", value=15.0, key='f_gesso')
            with col2:
                st.write("Níveis Críticos P-Rem:")
                st.number_input("0-4 mg/dm³", value=8.0, key='nc1')
            with col3:
                st.number_input("Meta Produtividade (sc/ha)", value=80.0)

        with t[1]:
            df = st.session_state.dados
            geo = st.session_state.geo
            colunas_mapa = ['ARGILA', 'P-REM', 'P', 'K', 'CA', 'MG', 'CTC', 'V%']
            for c in colunas_mapa:
                if c in df.columns:
                    renderizar_mapa_com_contorno(df, c, geo)

        with t[2]:
            st.info("Cálculos de Recomendação processando com base nos Atributos...")
