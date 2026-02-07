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

# Inicialização de Estado
if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None
if 'grid_shape' not in st.session_state:
    st.session_state['grid_shape'] = None

# ==============================================================================
# 3. FUNÇÕES AUXILIARES
# ==============================================================================
def limpar_coluna_inteligente(serie):
    """Detecta numéricos mistos (BR/US) e limpa"""
    s_str = serie.astype(str).str.strip()
    # Se tiver vírgula, assume BR (remove ponto milhar, troca vírgula decimal)
    if s_str.str.contains(',', regex=False).any():
        s_str = s_str.str.replace('.', '', regex=False)
        s_str = s_str.str.replace(',', '.', regex=False)
    return pd.to_numeric(s_str, errors='coerce')

def extrair_coordenadas_limpas(geojson_data):
    try:
        if 'features' in geojson_data: geom = geojson_data['features'][0]['geometry']
        elif 'geometry' in geojson_data: geom = geojson_data['geometry']
        else: geom = geojson_data
            
        tipo = geom['type']
        if tipo == 'Polygon': coords = geom['coordinates'][0]
        elif tipo == 'MultiPolygon': coords = geom['coordinates'][0][0]
        return [p[:2] for p in coords]
    except: return []

def plotar_conferencia_geometria(df, coords_geojson):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(df['longitude'], df['latitude'], c='red', s=15, label='Pontos CSV', alpha=0.8, zorder=5)
    if coords_geojson:
        poly = MplPolygon(coords_geojson, closed=True, edgecolor='blue', facecolor='none', linewidth=2, label='GeoJSON', zorder=10)
        ax.add_patch(poly)
        
        # Auto-Zoom
        lons_g = [p[0] for p in coords_geojson]
        lats_g = [p[1] for p in coords_geojson]
        min_x = min(df['longitude'].min(), min(lons_g))
        max_x = max(df['longitude'].max(), max(lons_g))
        min_y = min(df['latitude'].min(), min(lats_g))
        max_y = max(df['latitude'].max(), max(lats_g))
        
        margem = 0.002
        ax.set_xlim(min_x - margem, max_x + margem)
        ax.set_ylim(min_y - margem, max_y + margem)

    ax.set_title("Conferência Visual")
    ax.legend(loc='upper right')
    ax.grid(True, linestyle='--', alpha=0.5)
    return fig

# ==============================================================================
# 4. MOTOR DE CÁLCULO
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Calculando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    df = df_input.copy()
    
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao', 'geometry']
    
    cols_validas = []
    for col in df.columns:
        if col.lower() in cols_proibidas: continue
        # Limpeza Forçada
        df[col] = limpar_coluna_inteligente(df[col])
        # Aceita colunas com pelo menos 1 valor válido (para não perder dados esparsos)
        if df[col].notna().sum() >= 1: 
            cols_validas.append(col)

    # Coordenadas ajustadas
    df['longitude'] = df['longitude'].round(7)
    df['latitude'] = df['latitude'].round(7)
    df_grouped = df.groupby(['latitude', 'longitude'], as_index=False)[cols_validas].mean()

    # Grid cobrindo tudo
    x_min, x_max = df_grouped['longitude'].min(), df_grouped['longitude'].max()
    y_min, y_max = df_grouped['latitude'].min(), df_grouped['latitude'].max()
    
    try:
        coords_geo = extrair_coordenadas_limpas(geojson_data)
        if coords_geo:
            lons_g = [p[0] for p in coords_geo]
            lats_g = [p[1] for p in coords_geo]
            x_min = min(x_min, min(lons_g))
            x_max = max(x_max, max(lons_g))
            y_min = min(y_min, min(lats_g))
            y_max = max(y_max, max(lats_g))
    except: pass

    grid_x = np.linspace(x_min, x_max, resolucao_grid)
    grid_y = np.linspace(y_min, y_max, resolucao_grid)
    
    xx, yy = np.meshgrid(grid_x, grid_y)
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    processed_cols = []
    for col in cols_validas:
        try:
            dados_col = df_grouped[['longitude', 'latitude', col]].dropna()
            
            # Se for constante ou vazio
            if len(dados_col) == 0:
                continue
            if len(dados_col) < 5 or dados_col[col].nunique() <= 1:
                df_result[col] = dados_col[col].mean()
                processed_cols.append(col)
                continue

            OK = OrdinaryKriging(
                dados_col['longitude'], dados_col['latitude'], dados_col[col], 
                variogram_model='linear', verbose=False, enable_plotting=False
            )
            z, _ = OK.execute('grid', grid_x, grid_y)
            df_result[col] = z.flatten()
            processed_cols.append(col)
        except Exception as e:
            print(f"Erro ao processar {col}: {e}")
            continue

    # Remove colunas que não foram processadas
    cols_finais = ['latitude', 'longitude'] + processed_cols
    return df_result[cols_finais], (resolucao_grid, resolucao_grid)

# ==============================================================================
# 5. GERAÇÃO DE IMAGEM
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data, grid_shape):
    df_sorted = df_plot.sort_values(by=['latitude', 'longitude'])
    
    # Tenta Reshape
    try:
        Z = df_sorted[atributo].values.reshape(grid_shape)
        X_unique = np.sort(df_plot['longitude'].unique())
        Y_unique = np.sort(df_plot['latitude'].unique())
    except:
        # Fallback Pivot
        pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
        Z = pivot.values
        X_unique = pivot.columns.values 
        Y_unique = pivot.index.values 

    x_min, x_max = X_unique.min(), X_unique.max()
    y_min, y_max = Y_unique.min(), Y_unique.max()

    mask_sucesso = False
    try:
        coords_limpas = extrair_coordenadas_limpas(geojson_data)
        if len(coords_limpas) > 0:
            poly_path = MplPath(coords_limpas)
            XX, YY = np.meshgrid(X_unique, Y_unique)
            points = np.column_stack((XX.flatten(), YY.flatten()))
            
            mask_flat = poly_path.contains_points(points)
            mask_grid = mask_flat.reshape(Z.shape)
            
            if np.any(mask_grid): 
                Z[~mask_grid] = np.nan
                mask_sucesso = True
    except: pass

    # Escala Percentil Robusta
    dados_validos = Z[~np.isnan(Z)]
    if len(dados_validos) > 0:
        z_min = np.percentile(dados_validos, 2)
        z_max = np.percentile(dados_validos, 98)
        if z_min == z_max: z_min -= 0.1; z_max += 0.1
        elif (z_max - z_min) < 0.01: z_max += 0.01
    else:
        z_min, z_max = 0, 1

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
    levels = np.linspace(z_min, z_max, 50)
    norm = mcolors.Normalize(vmin=z_min, vmax=z_max)
    
    ax.contourf(X_unique, Y_unique, Z, levels=levels, cmap=cmap, norm=norm, extend='both', alpha=1.0)
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

# --- AJUSTE FINO (PERSISTENTE) ---
st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ Ajuste Fino de Coordenadas", expanded=True):
    shift_lat = st.number_input("Deslocar Lat", value=0.00000, step=0.00010, format="%.5f")
    shift_lon = st.number_input("Deslocar Lon", value=0.00000, step=0.00010, format="%.5f")

if not file_csv or not file_geojson:
    if st.session_state.get('dados_processados') is not None:
        st.session_state['dados_processados'] = None
        st.session_state['geojson_data'] = None
        st.cache_data.clear()
        st.rerun()

if file_csv and file_geojson:
    try:
        df_raw = pd.read_csv(file_csv)
        if len(df_raw.columns) < 2:
            file_csv.seek(0)
            df_raw = pd.read_csv(file_csv, sep=';')
        df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    except Exception as e: st.error(f"Erro CSV: {e}"); st.stop()

    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
        st.session_state['geojson_data'] = geojson_data
        coords_limpas = extrair_coordenadas_limpas(geojson_data)
    except: st.error("GeoJSON inválido."); st.stop()

    c1, c2 = st.columns(2)
    cols = list(df_raw.columns)
    idx_lat = next((i for i, c in enumerate(cols) if 'lat' in c), 0)
    idx_lon = next((i for i, c in enumerate(cols) if 'lon' in c or 'lng' in c), 1)
    
    with c1: lat_col = st.selectbox("Latitude:", cols, index=idx_lat)
    with c2: lon_col = st.selectbox("Longitude:", cols, index=idx_lon)
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    st.divider()
    st.subheader("🕵️ Pré-Visualização")
    
    # Prepara DF de Debug com o Shift Aplicado
    df_raw['latitude'] = limpar_coluna_inteligente(df_raw['latitude'])
    df_raw['longitude'] = limpar_coluna_inteligente(df_raw['longitude'])
    df_debug = df_raw.dropna(subset=['latitude', 'longitude']).copy()
    
    # Aplica Shift para visualização e processamento
    df_debug['latitude'] = df_debug['latitude'] + shift_lat
    df_debug['longitude'] = df_debug['longitude'] + shift_lon

    # Auto-Correção de Sinal
    if coords_limpas:
        lat_geo = coords_limpas[0][1]
        lat_csv = df_debug['latitude'].mean()
        if lat_geo < 0 and lat_csv > 0:
            st.warning("⚠️ Corrigindo sinal positivo para negativo.")
            df_debug['latitude'] *= -1
            df_debug['longitude'] *= -1 # Assume que lon também precisa

        st.pyplot(plotar_conferencia_geometria(df_debug, coords_limpas))

    if st.button("🚀 Processar Mapas", type="primary"):
        with st.status("Processando...", expanded=True) as status:
            st.cache_data.clear() 
            # Processa usando o DF JÁ AJUSTADO COM O SHIFT
            df_krig, grid_shape = processar_matrizes_interpolacao(df_debug, geojson_data)
            
            if df_krig.empty: st.error("Tabela vazia."); st.stop()
            
            st.session_state['dados_processados'] = df_krig
            st.session_state['grid_shape'] = grid_shape
            status.update(label="Concluído!", state="complete", expanded=False)
        st.rerun()

# ==============================================================================
# 7. RESULTADOS
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    grid_shape = st.session_state['grid_shape']
    
    # 1. Lista de mapas disponíveis (ignorando lat/lon)
    cols_mapas = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    st.divider()
    st.info(f"✅ Mapas gerados com sucesso: {', '.join(cols_mapas)}")
    
    if cols_mapas:
        st.subheader("🗺️ Visualização")
        # Seletor Dinâmico
        atributo = st.selectbox("Selecione o mapa para visualizar:", cols_mapas)
        
        df_plot = df_final[['latitude', 'longitude', atributo]].copy()

        if not df_plot.empty:
            try:
                img_buffer, bounds, min_max, sucesso = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'], grid_shape)
                z_min, z_max = min_max
                
                centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satellite')
                
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=bounds, opacity=0.9, interactive=True, cross_origin=False, zindex=1
                ).add_to(m)
                
                folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x: {'color': 'black', 'weight': 2, 'fillOpacity': 0}).add_to(m)
                
                # Legenda Atualizada
                legend_html = f"""
                <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; 
                            background: white; padding: 10px; border: 2px solid black; border-radius: 5px; font-family: sans-serif;">
                <b>{atributo}</b><br>
                <div style="background: linear-gradient(to right, #000080, #0000ff, #00ffff, #ffff00, #ff0000, #800000); height: 10px; width: 150px;"></div>
                <div style="display: flex; justify-content: space-between; width: 150px; font-size: 12px;">
                    <span>{z_min:.2f}</span>
                    <span>{z_max:.2f}</span>
                </div>
                </div>
                """
                m.get_root().html.add_child(folium.Element(legend_html))
                st_folium(m, height=500, use_container_width=True)
                
                st.write(f"**Estatísticas do Mapa ({atributo}):** Mín: {z_min:.2f} | Máx: {z_max:.2f}")
                
            except Exception as e:
                st.error(f"Erro visual: {e}")
