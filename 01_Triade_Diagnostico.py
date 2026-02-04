import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
from io import BytesIO
from pykrige.ok import OrdinaryKriging
from matplotlib.path import Path as MplPath

# Importando nossa caixa de ferramentas v43
from utils_v43 import (
    configurar_pagina, 
    renderizar_cabecalho_sidebar, 
    carregar_dados_blindado, 
    validar_colunas, 
    aplicar_layout_v43, 
    adicionar_contorno_preto
)

# ==============================================================================
# 1. CONFIGURAÇÃO E INICIALIZAÇÃO
# ==============================================================================
configurar_pagina("Diagnóstico de Solo")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Diagnóstico de Fertilidade (App 1)")

if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None

# ==============================================================================
# 2. DEFINIÇÃO DA FUNÇÃO DE KRIGAGEM
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Processando Geoestatística (Protocolo v43)...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    # --- ETAPA 1: LIMPEZA NUMÉRICA ---
    df = df_input.copy() 
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao']
    cols_validas = []
    
    for col in df.columns:
        if col.lower() in cols_proibidas:
            continue
        try:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].notna().sum() > 5:
                cols_validas.append(col)
        except Exception:
            pass 

    # --- ETAPA 2: GRID E MÁSCARA ---
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    
    buffer = 0.001 
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    try:
        coords_poligono = geojson_data['features'][0]['geometry']['coordinates'][0]
        poligono_path = MplPath(coords_poligono)
        
        xx, yy = np.meshgrid(grid_x, grid_y)
        points_flat = np.vstack((xx.flatten(), yy.flatten())).T
        
        mask = poligono_path.contains_points(points_flat)
        mask_matrix = mask.reshape(xx.shape)
        
    except Exception as e:
        st.error(f"Erro ao processar contorno do GeoJSON: {e}")
        return None

    df_result = pd.DataFrame({
        'latitude': yy.flatten(),
        'longitude': xx.flatten()
    })

    # --- ETAPA 3: INTERPOLAÇÃO ---
    for col in cols_validas:
        try:
            dados_coluna = df[['longitude', 'latitude', col]].dropna()
            
            if len(dados_coluna) < 5: 
                continue

            OK = OrdinaryKriging(
                dados_coluna['longitude'], 
                dados_coluna['latitude'], 
                dados_coluna[col], 
                variogram_model='linear',
                verbose=False, 
                enable_plotting=False
            )
            
            z, ss = OK.execute('grid', grid_x, grid_y)
            z_data = z.data 
            z_data[~mask_matrix] = np.nan
