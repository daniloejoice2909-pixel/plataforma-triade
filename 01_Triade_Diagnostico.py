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
# 2. DEFINIÇÃO DA FUNÇÃO DE KRIGAGEM (CORRIGIDA E BLINDADA)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Processando Geoestatística (Protocolo v43)...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    """
    Executa Krigagem Ordinária com limpeza numérica automática.
    """
    # --- ETAPA 1: LIMPEZA E CONVERSÃO NUMÉRICA (O SEGREDO) ---
    df = df_input.copy() # Não altera o original
    
    # Lista de colunas que NUNCA devem ser interpoladas (Metadados)
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona']
    
    cols_validas = []
    
    for col in df.columns:
        # Pula colunas de coordenadas ou identificação
        if col.lower() in cols_proibidas:
            continue
            
        try:
            # 1. Se for texto, tenta trocar vírgula por ponto (Padrão Brasil -> EUA)
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '.')
            
            # 2. Força converter para número (O que for texto vira NaN e o sistema ignora)
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
        st.error(f"Erro ao processar contorno do GeoJSON: {e}")
        return None

    df_result = pd.DataFrame({
        'latitude': yy.flatten(),
        'longitude': xx.flatten()
    })

    # Loop de Krigagem apenas nas colunas numéricas validadas
    for col in cols_validas:
        try:
            # Pega os dados limpos (remove NaNs dessa coluna)
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
            
            df_result[col] = z_data.flatten()
            
        except Exception as e:
            print(f"Aviso: Não foi possível interpolar {col}. Erro: {e}")

    df_final = df_result.dropna(subset=cols_validas, how='all')
    return df_final

# ==============================================================================
# 3. INPUT DE DADOS (SIDEBAR)
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")

file_csv = st.sidebar.file_uploader("📂 Tabela de Solo (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno do Talhão (.geojson)", type=["geojson", "json"])

# ==============================================================================
# 4. LÓGICA DE CARREGAMENTO E MAPEAMENTO
# ==============================================================================
if file_csv and file_geojson:
    # 4.1 Carregamento CSV Blindado
    df_raw = carregar_dados_blindado(file_csv)
    
    # Limpeza básica dos nomes
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]

    # 4.2 Carregamento GeoJSON Blindado (CORREÇÃO DO JSON ERROR)
    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
    except Exception:
        try:
            file_geojson.seek(0)
            conteudo = file_geojson.getvalue().decode("utf-8")
            geojson_data = json.loads(conteudo)
        except Exception as e:
            st.error(f"❌ GeoJSON inválido/corrompido. Erro: {e}")
            st.stop()
            
    st.session_state['geojson_data'] = geojson_data

    # 4.3 Seletor Manual de Colunas (CORREÇÃO DA LATITUDE)
    st.info("📍 Confirme as colunas de coordenadas para evitar erros:")
    c1, c2 = st.columns(2)
    
    # Tenta adivinhar o index inicial
    idx_lat = list(df_raw.columns).index('latitude') if 'latitude' in df_raw.columns else 0
    idx_lon = list(df_raw.columns).index('longitude') if 'longitude' in df_raw.columns else 1 if len(df_raw.columns) > 1 else 0

    with c1:
        lat_col = st.selectbox("Coluna LATITUDE (Y):", df_raw.columns, index=idx_lat)
    with c2:
        lon_col = st.selectbox("Coluna LONGITUDE (X):", df_raw.columns, index=idx_lon)
        
    # Renomeia para o padrão do sistema
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    # 4.4 Validação Final
    valido, faltantes = validar_colunas(df_raw, ['latitude', 'longitude'])
    
    if valido:
        st.success(f"✅ Dados Prontos: {len(df_raw)} pontos mapeados.")
        
        # --- GATILHO DE PROCESSAMENTO ---
        col_btn, _ = st.columns([1, 2])
        if col_btn.button("🚀 Processar Matrizes de Solo", type="primary"):
            try:
                # Chama a função passando o GEOJSON (CORREÇÃO DE ARGUMENTO)
                df_krig = processar_matrizes_interpolacao(df_raw, geojson_data)
                st.session_state['dados_processados'] = df_krig
                st.toast("Krigagem concluída!", icon="✅")
            except Exception as e:
                st.error(f"Erro fatal na Krigagem: {e}")
    else:
        st.error(f"Faltam colunas: {faltantes}")

# ==============================================================================
# 5. VISUALIZAÇÃO E EXPORTAÇÃO
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados']
    
    st.divider()
    st.subheader("📊 Visualização de Diagnóstico")
    
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver)
        
       # Plotagem com Chave Única
        fig = go.Figure(go.Heatmap(
            lon=df_final['longitude'], 
            lat=df_final['latitude'], 
            z=df_final[atributo],
            colorscale='Jet',
            opacity=1.0,
            zsmooth='best'  # <--- O erro estava aqui (faltava fechar as aspas)
        ))
