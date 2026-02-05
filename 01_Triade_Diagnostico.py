import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
from pykrige.ok import OrdinaryKriging
from matplotlib.path import Path as MplPath
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
import folium
from folium import plugins
from streamlit_folium import st_folium
import base64

# Importando nossa caixa de ferramentas v43
from utils_v43 import (
    configurar_pagina, 
    renderizar_cabecalho_sidebar, 
    carregar_dados_blindado, 
    validar_colunas
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
# 2. KRIGAGEM COM EXTRAPOLAÇÃO (PREENCHIMENTO TOTAL)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Geoestatística (V57 - Preenchimento Total)...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    # --- ETAPA 1: LIMPEZA ---
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

    # --- ETAPA 2: GRID EXPANDIDO ---
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    
    # Buffer de 0.01 graus (~1km) garante que o grid seja maior que o talhão
    # para evitar bordas brancas no recorte
    buffer = 0.01 
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    xx, yy = np.meshgrid(grid_x, grid_y)
    
    df_result = pd.DataFrame({
        'latitude': yy.flatten(),
        'longitude': xx.flatten()
    })

    # --- ETAPA 3: INTERPOLAÇÃO (SEM MÁSCARA AQUI) ---
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
            
            # Executa no retângulo cheio
            z, ss = OK.execute('grid', grid_x, grid_y)
            
            df_result[col] = z.flatten()
            
        except Exception as e:
            print(f"Aviso: Falha ao interpolar {col}: {e}")

    df_final = df_result.dropna(subset=cols_validas, how='all')
    return df_final

# ==============================================================================
# 3. GERAÇÃO DE IMAGEM COM RECORTE VETORIAL (CLIPPING)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data):
    """
    Gera imagem expandida e aplica o recorte do GeoJSON.
    """
    # 1. Pivotar (Grid Expandido)
    pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values   
    
    # 2. Cores InCeres (Hard Breaks)
    colors = ['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850'] 
    cmap = mcolors.ListedColormap(colors)
    # Define os limites de classe
    bounds = np.linspace(np.nanmin(Z), np.nanmax(Z), 6)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # 3. Figura Matplotlib
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_axis_off()
    
    # 4. Desenhar Contornos (Preenchimento Total)
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both')
    
    # 5. APLICAR O CORTE (MÁSCARA DO TALHÃO)
    coords = geojson_data['features'][0]['geometry']['coordinates'][0]
    poly_path = MplPath(coords)
    
    # Cria o Patch (Máscara Vetorial)
    patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', edgecolor='black', linewidth=2)
    ax.add_patch(patch)
    
    # Aplica o Patch como Clip para o contourf (Compatível com todas as versões)
    if hasattr(cf, 'collections'):
        for collection in cf.collections:
            collection.set_clip_path(patch)
    else:
        try:
            cf.set_clip_path(patch)
        except:
            pass # Versões muito novas podem gerenciar o clip diferente, mas o patch acima já ajuda

    # 6. Ajustar limites para focar no grid
    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    
    # 7. Salvar
    img_data = BytesIO()
    plt.savefig(img_data, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=150)
    plt.close(fig)
    img_data.seek(0)
    
    return img_data, [[Y.min(), X.min()], [Y.max(), X.max()]], bounds

# ==============================================================================
# 4. INPUT E PROCESSAMENTO
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")

file_csv = st.sidebar.file_uploader("📂 Tabela de Solo (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno do Talhão (.geojson)", type=["geojson", "json"])

if file_csv and file_geojson:
    df_raw = carregar_dados_blindado(file_csv)
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]

    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
    except Exception:
        try:
            file_geojson.seek(0)
            conteudo = file_geojson.getvalue().decode("utf-8")
            geojson_data = json.loads(conteudo)
        except Exception as e:
            st.error(f"❌ GeoJSON inválido: {e}")
            st.stop()
            
    st.session_state['geojson_data'] = geojson_data

    # Validação
    st.info("📍 Validação de Coordenadas:")
    c1, c2 = st.columns(2)
    # Proteção contra lista vazia ou colunas não encontradas
    col_list = list(df_raw.columns)
    idx_lat = col_list.index('latitude') if 'latitude' in col_list else 0
    idx_lon = col_list.index('longitude') if 'longitude' in col_list else 1 if len(col_list) > 1 else 0

    with c1:
        lat_col = st.selectbox("Coluna LATITUDE (Y):", df_raw.columns, index=idx_lat)
    with c2:
        lon_col = st.selectbox("Coluna LONGITUDE (X):", df_raw.columns, index=idx_lon)
        
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    valido, faltantes = validar_colunas(df_raw, ['latitude', 'longitude'])
    
    if valido:
        col_btn, _ = st.columns([1, 2])
        if col_btn.button("🚀 Processar Matrizes de Solo", type="primary"):
            try:
                # Usa buffer expandido para garantir preenchimento total
                df_krig = processar_matrizes_interpolacao(df_raw, geojson_data, resolucao_grid=150)
                st.session_state['dados_processados'] = df_krig
                st.toast("Preenchimento Total Concluído!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Erro fatal na Krigagem: {e}")

# ==============================================================================
# 5. VISUALIZAÇÃO FOLIUM (FINAL)
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    
    st.divider()
    
    c_down1, c_down2 = st.columns([2, 1])
    with c_down1:
        st.subheader("🏁 1. Exportação")
