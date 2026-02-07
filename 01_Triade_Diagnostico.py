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
# 3. FUNÇÕES DE DEBUG E AUXILIARES
# ==============================================================================
def extrair_centroide_geojson(geojson_data):
    """Calcula o centro aproximado do GeoJSON para comparação"""
    try:
        coords = []
        tipo = geojson_data['features'][0]['geometry']['type']
        if tipo == 'Polygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
        elif tipo == 'MultiPolygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0][0]
        
        if not coords: return None, None
        
        # Converte para array numpy
        arr = np.array(coords)
        # GeoJSON é sempre [Lon, Lat] (X, Y)
        lon_geo = np.mean(arr[:, 0])
        lat_geo = np.mean(arr[:, 1])
        return lat_geo, lon_geo
    except:
        return None, None

def plotar_conferencia_geometria(df, geojson_data):
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # Pontos CSV
    ax.scatter(df['longitude'], df['latitude'], c='red', s=15, label='Pontos CSV', alpha=0.7, zorder=5)
    
    # GeoJSON
    try:
        tipo = geojson_data['features'][0]['geometry']['type']
        coords = []
        if tipo == 'Polygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
        elif tipo == 'MultiPolygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0][0]
            
        if coords:
            poly = MplPolygon(coords, closed=True, edgecolor='blue', facecolor='none', linewidth=2, label='GeoJSON', zorder=10)
            ax.add_patch(poly)
    except: pass

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

    # Grid com margem generosa para evitar cortes errados
    x_min, x_max = df_grouped['longitude'].min(), df_grouped['longitude'].max()
    y_min, y_max = df_grouped['latitude'].min(), df_grouped['latitude'].max()
    
    buffer_x = (x_max - x_min) * 0.2
    buffer_y = (y_max - y_min) * 0.2
    
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
# 5. GERAÇÃO DE IMAGEM
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data, grid_shape):
    df_sorted = df_plot.sort_values(by=['latitude', 'longitude'])
    
    try:
        Z = df_sorted[atributo].values.reshape(grid_shape)
        X_unique = np.sort(df_plot['longitude'].unique())
        Y_unique = np.sort(df_plot['latitude'].unique())
    except:
        pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
        Z = pivot.values
        X_unique = pivot.columns.values 
        Y_unique = pivot.index.values 

    x_min, x_max = X_unique.min(), X_unique.max()
    y_min, y_max = Y_unique.min(), Y_unique.max()

    # Recorte (Cookie Cutter)
    mask_sucesso = False
    try:
        coords = []
        tipo = geojson_data['features'][0]['geometry']['type']
        if tipo == 'Polygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
        elif tipo == 'MultiPolygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0][0]
            
        if len(coords) > 0:
            poly_path = MplPath(coords)
            XX, YY = np.meshgrid(X_unique, Y_unique)
            points = np.column_stack((XX.flatten(), YY.flatten()))
            
            mask_flat = poly_path.contains_points(points)
            mask_grid = mask_flat.reshape(Z.shape)
            
            if np.any(mask_grid): 
                Z[~mask_grid] = np.nan
                mask_sucesso = True
    except: pass

    z_min, z_max = np.nanmin(Z), np.nanmax(Z)
    if np.isnan(z_min): z_min = 0
    if np.isnan(z_max): z_max = 1
    if z_min == z_max: z_min -= 0.1; z_max += 0.1
    elif (z_max - z_min) < 0.001: z_max += 0.001

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
    
    ax.contourf(X_unique, Y_unique, Z, levels=50, cmap=cmap, norm=norm, extend='both', alpha=1.0)
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
    except:
        st.error("GeoJSON inválido."); st.stop()

    c1, c2 = st.columns(2)
    cols = list(df_raw.columns)
    idx_lat = next((i for i, c in enumerate(cols) if 'lat' in c), 0)
    idx_lon = next((i for i, c in enumerate(cols) if 'lon' in c or 'lng' in c), 1)
    
    with c1: lat_col = st.selectbox("Latitude:", cols, index=idx_lat)
    with c2: lon_col = st.selectbox("Longitude:", cols, index=idx_lon)
    
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    # ------------------------------------------------------------------
    # O TIRA-TEIMA NUMÉRICO (V73)
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("🕵️ Diagnóstico de Coordenadas")

    # 1. Tratamento Prévio para o Debug
    try:
        df_raw['latitude'] = pd.to_numeric(df_raw['latitude'].astype(str).str.replace(',', '.'), errors='coerce')
        df_raw['longitude'] = pd.to_numeric(df_raw['longitude'].astype(str).str.replace(',', '.'), errors='coerce')
        df_debug = df_raw.dropna(subset=['latitude', 'longitude'])

        # Médias do CSV
        lat_csv = df_debug['latitude'].mean()
        lon_csv = df_debug['longitude'].mean()

        # Médias do GeoJSON
        lat_geo, lon_geo = extrair_centroide_geojson(geojson_data)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.info(f"📍 **Centro do CSV:**\n\nLat: {lat_csv:.5f}\n\nLon: {lon_csv:.5f}")
        with col_d2:
            if lat_geo:
                st.info(f"🗺️ **Centro do GeoJSON:**\n\nLat: {lat_geo:.5f}\n\nLon: {lon_geo:.5f}")
                
                # Análise Automática de Erro
                dist_lat = abs(lat_csv - lat_geo)
                dist_lon = abs(lon_csv - lon_geo)
                
                if dist_lat > 1 or dist_lon > 1:
                    st.error("🚨 **ALERTA CRÍTICO:** As coordenadas estão muito distantes (>1 grau)!")
                    if abs(lat_csv) > 1000 or abs(lat_geo) > 1000:
                         st.write("👉 Parece que um dos arquivos está em **UTM (Metros)** e o outro em **Graus**. Converta tudo para Lat/Long WGS84.")
                    elif abs(lat_csv) == abs(lon_geo) and abs(lon_csv) == abs(lat_geo): # Aproximado
                         st.write("👉 Parece que **Latitude e Longitude estão invertidas**.")
                    elif (lat_csv > 0 and lat_geo < 0) or (lon_csv > 0 and lon_geo < 0):
                         st.write("👉 Parece que o **sinal (positivo/negativo)** está trocado. Tentaremos corrigir automaticamente no processamento.")
                else:
                    st.success("✅ As coordenadas parecem alinhadas.")
            else:
                st.warning("Não foi possível ler as coordenadas do GeoJSON.")

        # Gráfico
        st.pyplot(plotar_conferencia_geometria(df_debug, geojson_data))

    except Exception as e:
        st.error(f"Erro no diagnóstico: {e}")
    # ------------------------------------------------------------------

    if st.button("🚀 Processar Mapas", type="primary"):
        with st.status("Processando...", expanded=True) as status:
            st.cache_data.clear() 
            
            # Correção Automática de Sinal (Se necessário)
            if lat_csv > 0 and lat_geo < 0: df_debug['latitude'] = df_debug['latitude'] * -1
            if lon_csv > 0 and lon_geo < 0: df_debug['longitude'] = df_debug['longitude'] * -1

            df_krig, grid_shape = processar_matrizes_interpolacao(df_debug, geojson_data)
            
            if df_krig.empty:
                st.error("Tabela vazia."); st.stop()
                
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
    
    st.divider()
    csv_ponte = df_final.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Baixar Ponte", csv_ponte, "ponte.csv", "text/csv", type="primary")
    st.divider()
    
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver)
        df_plot = df_final[['latitude', 'longitude', atributo]].copy()

        if not df_plot.empty:
            try:
                img_buffer, bounds, min_max, sucesso = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'], grid_shape)
                z_min, z_max = min_max
                
                if not sucesso:
                    st.warning("⚠️ Recorte falhou. Mostrando grid completo. Verifique o diagnóstico acima.")

                centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satellite')
                
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=bounds, opacity=0.9, interactive=True, cross_origin=False, zindex=1
                ).add_to(m)
                
                folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x: {'color': 'black', 'weight': 2, 'fillOpacity': 0}).add_to(m)
                
                st_folium(m, height=500, use_container_width=True)
                
            except Exception as e:
                st.error(f"Erro visual: {e}")
