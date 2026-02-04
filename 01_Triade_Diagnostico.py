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

# Inicialização de Session State
if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None

# ==============================================================================
# 2. DEFINIÇÃO DA FUNÇÃO DE KRIGAGEM (CORRIGIDA v43.2)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Processando Geoestatística (Protocolo v43)...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    """
    Executa Krigagem Ordinária com limpeza numérica automática.
    """
    # --- ETAPA 1: LIMPEZA E CONVERSÃO NUMÉRICA ---
    df = df_input.copy() 
    
    # Lista de colunas que NUNCA devem ser interpoladas (Metadados/Texto)
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao']
    
    cols_validas = []
    
    for col in df.columns:
        # Pula colunas de coordenadas ou identificação
        if col.lower() in cols_proibidas:
            continue
            
        try:
            # 1. Se for texto, tenta trocar vírgula por ponto (Padrão Brasil -> EUA)
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '.')
            
            # 2. Força converter para número (O que for texto vira NaN)
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 3. Se a coluna tiver números válidos suficientes, entra na lista
            if df[col].notna().sum() > 5:
                cols_validas.append(col)
                
        except Exception:
            pass # Se der erro na conversão, apenas ignora a coluna

    # ---------------------------------------------------------

    # Preparação do Grid
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    
    buffer = 0.001 
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    # Criação da Máscara do Polígono
    try:
        coords_poligono = geojson_data['features'][0]['geometry']['coordinates'][0]
        poligono_path = MplPath(coords_poligono)
        
        xx, yy = np.meshgrid(grid_x, grid_y)
        points_flat = np.vstack((xx.flatten(), yy.flatten())).T
        
        mask = poligono_path.contains_points(points_flat)
        mask_matrix = mask.reshape(xx.shape)
        
    except Exception as e:
        # --- CORREÇÃO DO
