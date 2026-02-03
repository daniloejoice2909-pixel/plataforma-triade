import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL E BLINDAGEM DE INTERFACE
# ==============================================================================
def configurar_pagina(subtitulo):
    """
    Configura a página seguindo o padrão Tríade.
    Argumento: subtitulo (ex: "Diagnóstico" ou "Prescrição")
    """
    st.set_page_config(
        page_title=f"Tríade - {subtitulo}",
        page_icon="🚜",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # CSS de Ajuste Fino (Remove espaços em branco desnecessários no topo)
    st.markdown("""
        <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 1rem;
        }
        div[data-testid="stExpander"] div[role="button"] p {
            font-weight: bold;
            font-size: 1.1em;
        }
        </style>
    """, unsafe_allow_html=True)

def renderizar_cabecalho_sidebar():
    """Renderiza o cabeçalho padrão na barra lateral."""
    st.sidebar.markdown("## 🚜 **Tríade Agro**")
    st.sidebar.markdown("---")

# ==============================================================================
# 2. BLINDAGEM DE DADOS (Leitura Segura)
# ==============================================================================
@st.cache_data(show_spinner=False)
def carregar_dados_blindado(uploaded_file, tipo="csv"):
    """
    Carrega CSV ou Parquet com tratamento de erro Try...Except obrigatório.
    """
    try:
        if tipo == "csv":
            # Aceita qualquer delimitador comum (, ou ;)
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        elif tipo == "parquet":
            df = pd.read_parquet(uploaded_file)
        else:
            return None
        
        # Normalização de nomes de colunas (remove espaços e coloca minúsculas)
        # Opcional, mas ajuda a evitar erros de 'KeyError'
        # df.columns = [c.strip() for c in df.columns]
        
        return df

    except Exception as e:
        st.error(f"Erro Crítico na Leitura do Arquivo: {e}")
        return None

def validar_colunas(df, lista_colunas):
    """
    Verifica se as colunas existem antes de tentar plotar.
    Retorna (True, None) ou (False, lista_de_faltantes).
    """
    colunas_df = [c.lower() for c in df.columns] # Comparação case-insensitive
    faltantes = []
    
    for col in lista_colunas:
        if col.lower() not in colunas_df:
            faltantes.append(col)
            
    if faltantes:
        return False, faltantes
    return True, []

# ==============================================================================
# 3. RIGOR GEOMÉTRICO E VISUAL (Mapas)
# ==============================================================================
def aplicar_layout_v43(fig, titulo_mapa=""):
    """
    Aplica as regras estritas de layout do Protocolo v43:
    - Aspect Ratio 1:1 (não distorcer o talhão)
    - Mapbox com imagem de satélite
    - Margens otimizadas
    """
    fig.update_layout(
        title=dict(text=f"<b>{titulo_mapa}</b>", x=0.05, y=0.95),
        mapbox_style="carto-positron", # Ou "satellite-streets" se tiver token
        mapbox=dict(
            center=dict(lat=-18.0, lon=-48.0), # Será sobrescrito pelos dados
            zoom=12
        ),
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        yaxis=dict(scaleanchor="x", scaleratio=1), # Trava de Proporção 1:1
        height=600, # Altura mínima conforme protocolo
        showlegend=True
    )
    return fig

def adicionar_contorno_preto(fig, geojson_data):
    """
    Adiciona a camada de contorno preto sólido (GeoJSON) sobre o mapa.
    """
    if geojson_data:
        # Extrai coordenadas do polígono (Lógica simplificada para GeoJSON padrão)
        try:
            # Tenta pegar o primeiro polígono da feature collection
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
            lons = [pt[0] for pt in coords]
            lats = [pt[1] for pt in coords]
            
            fig.add_trace(go.Scattermapbox(
                lon=lons,
                lat=lats,
                mode='lines',
                line=dict(width=3, color='black'), # Regra: Linha preta sólida
                name='Contorno do Talhão',
                hoverinfo='none'
            ))
        except Exception as e:
            st.warning(f"Não foi possível desenhar o contorno: {e}")
    return fig

# ==============================================================================
# 4. COMPONENTES DE INTERFACE (Inputs)
# ==============================================================================
def input_numerico_seguro(label, valor_padrao, step=1.0, key=None):
    """
    Gera um st.number_input bidirecional e com limites amplos.
    """
    return st.number_input(
        label,
        min_value=0.0,
        max_value=100000.0, # Limite amplo para evitar travas
        value=float(valor_padrao),
        step=float(step),
        format="%.2f",
        key=key
    )
