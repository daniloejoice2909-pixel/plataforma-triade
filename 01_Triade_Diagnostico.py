import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64

# --- 1. CONFIGURAÇÃO DE BACKEND ---
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.path import Path as MplPath
from matplotlib.patches import Polygon as MplPolygon

from pykrige.ok import OrdinaryKriging
import folium
from streamlit_folium import st_folium

from utils_v43 import (
    configurar_pagina, 
    renderizar_cabecalho_sidebar, 
    carregar_dados_blindado, 
    validar_colunas
)

# ==============================================================================
# 2. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
configurar_pagina("Diagnóstico de Solo")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Diagnóstico de Fertilidade (App 1)")

if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None
if 'grid_shape' not in st.session_state:
    st.session_state['grid_shape'] = None

# ==============================================================================
# 3. FUNÇÕES AUXILIARES (GEOJSON CLEANER)
# ==============================================================================
def extrair_coordenadas_limpas(geojson_data):
    try:
        if 'features' in geojson_data:
            geom = geojson_data['features'][0]['geometry']
        elif 'geometry' in geojson_data:
            geom = geojson_data['geometry']
        else:
            geom = geojson_data
            
        coords_raw = []
        tipo = geom['type']
        
        if tipo == 'Polygon':
            coords_raw = geom['coordinates'][0]
        elif tipo == 'MultiPolygon':
            coords_raw = geom['coordinates'][0][0]
            
        # Remove Altitude (Z) se existir
        coords_limpas = [ponto[:2] for ponto in coords_raw]
        return coords_limpas
    except:
        return []

def plotar_conferencia_geometria(df, coords_geojson):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(df['longitude'], df['latitude'], c='red', s=15, label='Pontos CSV', alpha=0.7, zorder=5)
    if coords_geojson:
        poly = MplPolygon(coords_geojson, closed=True, edgecolor='blue', facecolor='none', linewidth=2, label='GeoJSON', zorder=10)
        ax.add_patch(poly)
    ax.set_title("Visualização Espacial")
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.autoscale(enable=True)
    return fig

# ==============================================================================
# 4. MOTOR DE CÁLCULO
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Calculando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    df = df_input.copy()
    
    cols_proibidas = [
        'id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 
        'x', 'y', 'data', 'hora', 'campo', 'fazenda', 
        'profundidade', 'zona', 'talhao', 'geometry'
    ]
    
    cols_validas = []
    for col in df.columns:
        if col.lower() in cols_proibidas: continue
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].notna().sum() >= 3: cols_validas.append(col)
        except: pass 

    df['longitude'] = df['longitude'].round(5)
    df['latitude'] = df['latitude'].round(5)
    df_grouped = df.groupby(['latitude', 'longitude'], as_index=False)[cols_validas].mean()

    x_min, x_max = df_grouped['longitude'].min(), df_grouped['longitude'].max()
    y_min, y_max = df_grouped['latitude'].min(), df_grouped['latitude'].max()
    
    # Buffer de 15%
    buffer_x = (x_max - x_min) * 0.15
    buffer_y = (y_max - y_min) * 0.15
    
    grid_x = np.linspace(x_min - buffer_x, x_max + buffer_x, resolucao_grid)
    grid_y = np.linspace(y_min - buffer_y, y_max + buffer_y, resolucao_grid)
    
    xx, yy = np.meshgrid(grid_x, grid_y)
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    for col in cols_validas:
        try:
            dados_col = df_grouped[['longitude', 'latitude', col]].dropna()
            if len(dados_col) < 5 or dados_col[col].nunique() <= 1:
                df_result[col] = dados_col[col].mean() if len(dados_col) > 0 else 0
                continue

            OK = OrdinaryKriging(
                dados_col['longitude'], dados_col['latitude'], dados_col[col], 
                variogram_model='linear', verbose=False, enable_plotting=False
            )
            z, _ = OK.execute('grid', grid_x, grid_y)
            df_result[col] = z.flatten()
        except: continue

    return df_result, (resolucao_grid, resolucao_grid)

# ==============================================================================
# 5. GERAÇÃO DE IMAGEM (V75 - ESCALA INTELIGENTE)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data, grid_shape):
    # 1. Pivotagem Rígida (Garante que os dados não embaralhem)
    # Pivot ordena automaticamente Lat e Lon crescente
    pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
    Z = pivot.values
    
    # Eixos
    X_unique = pivot.columns.values 
    Y_unique = pivot.index.values 

    x_min, x_max = X_unique.min(), X_unique.max()
    y_min, y_max = Y_unique.min(), Y_unique.max()

    # 2. Recorte (Cookie Cutter)
    mask_sucesso = False
    coords_limpas = []
    try:
        coords_limpas = extrair_coordenadas_limpas(geojson_data)
        if len(coords_limpas) > 0:
            poly_path = MplPath(coords_limpas)
            XX, YY = np.meshgrid(X_unique, Y_unique)
            points = np.column_stack((XX.flatten(), YY.flatten()))
            
            mask_flat = poly_path.contains_points(points)
            mask_grid = mask_flat.reshape(Z.shape)
            
            if np.any(mask_grid): 
                # Tudo que está FORA vira NaN
                Z[~mask_grid] = np.nan
                mask_sucesso = True
    except Exception as e:
        print(f"Erro recorte: {e}")

    # 3. ESCALA INTELIGENTE (RESOLUÇÃO DO PROBLEMA DE COR)
    # Filtra apenas valores válidos (não NaN) para calcular estatísticas
    dados_validos = Z[~np.isnan(Z)]
    
    if len(dados_validos) > 0:
        # Usa Percentil para ignorar outliers extremos (erros de krigagem)
        # Pega do 2% ao 98% (Ignora os picos extremos)
        z_min = np.percentile(dados_validos, 2)
        z_max = np.percentile(dados_validos, 98)
    else:
        z_min, z_max = 0, 1

    # Previne erro de escala igual
    if z_min == z_max:
        z_min -= 0.1
        z_max += 0.1
    elif (z_max - z_min) < 0.001:
        z_max += 0.001

    # 4. Renderização
    plt.close('all') 
    aspect_ratio = (x_max - x_min) / (y_max - y_min)
    h_fig = 10
    w_fig = h_fig * aspect_ratio
    
    fig = plt.figure(figsize=(w_fig, h_fig))
    fig.patch.set_alpha(0.0) 
    ax = plt.axes([0, 0, 1, 1]) 
    ax.set_axis_off()
    ax.patch.set_alpha(0.0)
    
    cmap = plt.get_cmap('jet', 256)
    cmap.set_bad(alpha=0) 
    norm = mcolors.Normalize(vmin=z_min, vmax=z_max)
    
    # Desenha usando os limites calculados (z_min, z_max)
    ax.contourf(X_unique, Y_unique, Z, levels=np.linspace(z_min, z_max, 50), cmap=cmap, norm=norm, extend='both', alpha=1.0)
    
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    
    img_data = BytesIO()
    plt.savefig(img_data, format='png', transparent=True, dpi=100)
    plt.close(fig)
    img_data.seek(0)
    
    return img_data, [[y_min, x_min], [y_max, x_max]], [z_min, z_max], mask_sucesso

# ==============================================================================
# 6. INTERFACE
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")
file_csv = st.sidebar.file_uploader("📂 Tabela (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno (.geojson)", type=["geojson", "json"])

if not file_csv or not file_geojson:
    if st.session_state.get('dados_processados') is not None:
        st.session_state['dados_processados'] = None
        st.session_state['geojson_data'] = None
        st.cache_data.clear()
        st.rerun()

if file_csv and file_geojson:
    # Leitura Blindada
    try:
        df_raw = pd.read_csv(file_csv)
        if len(df_raw.columns) < 2:
            file_csv.seek(0)
            df_raw = pd.read_csv(file_csv, sep=';')
        df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    except Exception as e:
        st.error(f"Erro CSV: {e}"); st.stop()

    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
        st.session_state['geojson_data'] = geojson_data
        coords_limpas = extrair_coordenadas_limpas(geojson_data)
    except:
        st.error("GeoJSON inválido."); st.stop()

    c1, c2 = st.columns(2)
    cols = list(df_raw.columns)
    idx_lat = next((i for i, c in enumerate(cols) if 'lat' in c), 0)
    idx_lon = next((i for i, c in enumerate(cols) if 'lon' in c or 'lng' in c), 1)
    
    with c1: lat_col = st.selectbox("Latitude:", cols, index=idx_lat)
    with c2: lon_col = st.selectbox("Longitude:", cols, index=idx_lon)
    
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    # --- Tira-Teima e Correção Automática ---
    st.divider()
    st.subheader("🕵️ Diagnóstico de Coordenadas")
    
    try:
        df_raw['latitude'] = pd.to_numeric(df_raw['latitude'].astype(str).str.replace(',', '.'), errors='coerce')
        df_raw['longitude'] = pd.to_numeric(df_raw['longitude'].astype(str).str.replace(',', '.'), errors='coerce')
        df_debug = df_raw.dropna(subset=['latitude', 'longitude'])

        if coords_limpas:
            lat_geo = coords_limpas[0][1]
            lon_geo = coords_limpas[0][0]
            lat_csv = df_debug['latitude'].mean()
            lon_csv = df_debug['longitude'].mean()
            
            fator_lat, fator_lon = 1, 1
            if lat_geo < 0 and lat_csv > 0: fator_lat = -1
            if lon_geo < 0 and lon_csv > 0: fator_lon = -1
            
            if fator_lat == -1 or fator_lon == -1:
                st.warning("⚠️ Corrigindo sinal positivo para negativo (Brasil).")
                df_debug['latitude'] *= fator_lat
                df_debug['longitude'] *= fator_lon

            st.pyplot(plotar_conferencia_geometria(df_debug, coords_limpas))
        else:
            st.warning("GeoJSON sem coordenadas válidas.")

    except Exception as e:
        st.error(f"Erro diagnóstico: {e}")

    if st.button("🚀 Processar Mapas", type="primary"):
        with st.status("Processando...", expanded=True) as status:
            st.cache_data.clear() 
            df_krig, grid_shape = processar_matrizes_interpolacao(df_debug, geojson_data)
            
            if df_krig.empty: st.error("Tabela vazia."); st.stop()
            
            st.session_state['dados_processados'] = df_krig
            st.session_state['grid_shape'] = grid_shape
            status.update(label="Concluído!", state="complete", expanded=False)
        st.rerun()

# ==============================================================================
# 7. VISUALIZAÇÃO
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    grid_shape = st.session_state['grid_shape']
    
    st.divider()
    csv_ponte = df_final.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Baixar Ponte", csv_pon
