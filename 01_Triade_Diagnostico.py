import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64
import zipfile
import xml.etree.ElementTree as ET

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

# Tenta importar funções utilitárias se existirem, senão define mocks para não quebrar
try:
    from utils_v43 import (
        configurar_pagina, 
        renderizar_cabecalho_sidebar, 
        carregar_dados_blindado, 
        validar_colunas
    )
except ImportError:
    def configurar_pagina(titulo): st.set_page_config(page_title=titulo, layout="wide")
    def renderizar_cabecalho_sidebar(): st.sidebar.title("Módulo de Diagnóstico")
    def carregar_dados_blindado(): pass
    def validar_colunas(): pass

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
def processar_arquivo_geografico(uploaded_file):
    points = []
    try:
        if uploaded_file.name.lower().endswith('.kmz'):
            with zipfile.ZipFile(uploaded_file, 'r') as z:
                kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                with z.open(kml_filename) as f:
                    tree = ET.parse(f)
        else:
            uploaded_file.seek(0)
            tree = ET.parse(uploaded_file)
            
        root = tree.getroot()
        namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        placemarks = root.findall('.//kml:Placemark', namespace)
        if not placemarks: placemarks = root.findall('.//Placemark')
            
        for placemark in placemarks:
            name_elem = placemark.find('kml:name', namespace)
            if name_elem is None: name_elem = placemark.find('name')
            name = name_elem.text.strip() if name_elem is not None and name_elem.text else None
            
            coord_elem = placemark.find('.//kml:coordinates', namespace)
            if coord_elem is None: coord_elem = placemark.find('.//coordinates')
            
            if coord_elem is not None and coord_elem.text:
                coords_text = coord_elem.text.strip().split()
                if coords_text:
                    first_coord = coords_text[0].split(',')
                    if len(first_coord) >= 2:
                        try:
                            lon = float(first_coord[0])
                            lat = float(first_coord[1])
                            points.append({'ID_PONTO': name, 'latitude': lat, 'longitude': lon})
                        except ValueError: pass
        return pd.DataFrame(points)
    except Exception as e:
        st.error(f"Erro ao ler arquivo de pontos: {e}")
        return pd.DataFrame()

def limpar_coluna_inteligente(serie):
    def clean_val(val):
        if pd.isna(val): return np.nan
        s = str(val).strip()
        if s.lower() in ['ns', 'nan', '', 'null', 'nd']: return np.nan
        return s

    s_clean = serie.apply(clean_val)
    tem_virgula = s_clean.dropna().apply(lambda x: ',' in x).any()
    
    if tem_virgula:
        s_clean = s_clean.apply(lambda x: x.replace('.', '').replace(',', '.') if isinstance(x, str) else x)
        
    return pd.to_numeric(s_clean, errors='coerce')

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

# ==============================================================================
# 4. MOTOR DE CÁLCULO (COM PROJEÇÃO MÉTRICA)
# ==============================================================================
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=100):
    df = df_input.copy()
    cols_proibidas = ['id', 'ponto', 'amostra', 'lab', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao', 'geometry', 'id_clean', 'unnamed', 'obs']
    
    cols_validas = []
    for col in df.columns:
        if any(p in str(col).lower() for p in cols_proibidas): continue
        df[col] = limpar_coluna_inteligente(df[col])
        if df[col].notna().sum() >= 5 and df[col].nunique() > 1: 
            cols_validas.append(col)

    df_grouped = df.groupby(['latitude', 'longitude'], as_index=False)[cols_validas].mean()

    # PROJEÇÃO: Graus -> Metros
    lat_mean = df_grouped['latitude'].mean()
    df_grouped['Y_m'] = df_grouped['latitude'] * 111111
    df_grouped['X_m'] = df_grouped['longitude'] * 111111 * np.cos(np.radians(lat_mean))

    # Grid (Metros e Graus)
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
    
    # Grid projetado para Krigagem
    grid_y_m = grid_y * 111111
    grid_x_m = grid_x * 111111 * np.cos(np.radians(lat_mean))
    
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    processed_cols = []
    progresso_texto = st.empty()
    bar = st.progress(0)
    total_cols = len(cols_validas)
    
    for i, col in enumerate(cols_validas):
        progresso_texto.text(f"⏳ Processando: {col} ({i+1}/{total_cols})")
        bar.progress((i + 1) / total_cols)
        try:
            dados_col = df_grouped[['X_m', 'Y_m', col]].dropna()
            if len(dados_col) < 5: continue

            OK = OrdinaryKriging(
                dados_col['X_m'], dados_col['Y_m'], dados_col[col], 
                variogram_model='linear', verbose=False, enable_plotting=False
            )
            z, _ = OK.execute('grid', grid_x_m, grid_y_m)
            df_result[col] = z.flatten()
            processed_cols.append(col)
        except: continue
            
    progresso_texto.empty()
    bar.empty()

    cols_finais = ['latitude', 'longitude'] + processed_cols
    return df_result[cols_finais], (resolucao_grid, resolucao_grid)

# ==============================================================================
# 5. GERAÇÃO DE IMAGEM
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data, grid_shape):
    # Garante limpeza da figura anterior
    plt.close('all')
    plt.clf()
    
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

    try:
        coords_limpas = extrair_coordenadas_limpas(geojson_data)
        if len(coords_limpas) > 0:
            poly_path = MplPath(coords_limpas)
            XX, YY = np.meshgrid(X_unique, Y_unique)
            points = np.column_stack((XX.flatten(), YY.flatten()))
            mask_flat = poly_path.contains_points(points)
            mask_grid = mask_flat.reshape(Z.shape)
            if np.any(mask_grid): Z[~mask_grid] = np.nan
    except: pass

    dados_validos = Z[~np.isnan(Z)]
    if len(dados_validos) > 0:
        z_min = np.percentile(dados_validos, 2)
        z_max = np.percentile(dados_validos, 98)
        if (z_max - z_min) < 0.1: 
            media = (z_max + z_min) / 2
            z_min = media - 0.5
            z_max = media + 0.5
    else: z_min, z_max = 0, 1

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
    
    return img_data, [[y_min, x_min], [y_max, x_max]], [z_min, z_max]

# ==============================================================================
# 6. INTERFACE
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")
file_lab = st.sidebar.file_uploader("📂 Dados Laboratório (Excel/CSV)", type=["csv", "xlsx", "xls"])
file_geo = st.sidebar.file_uploader("📍 Coordenadas dos Pontos (.KMZ/.KML)", type=["kmz", "kml"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno do Talhão (.geojson)", type=["geojson", "json"])

st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ Ajuste Fino de Coordenadas", expanded=False):
    shift_lat = st.number_input("Deslocar Lat", value=0.00000, step=0.00010, format="%.5f")
    shift_lon = st.number_input("Deslocar Lon", value=0.00000, step=0.00010, format="%.5f")

if not file_lab or not file_geo or not file_geojson:
    if st.session_state.get('dados_processados') is not None:
        st.info("Aguardando upload...")

if file_lab and file_geo and file_geojson:
    try:
        if file_lab.name.lower().endswith('.csv'):
            try: df_lab = pd.read_csv(file_lab)
            except: file_lab.seek(0); df_lab = pd.read_csv(file_lab, sep=';')
        else:
            try: df_lab = pd.read_excel(file_lab)
            except: st.error("Instale 'xlrd' ou salve como .xlsx"); st.stop()
        
        df_geo_points = processar_arquivo_geografico(file_geo)
        file_geojson.seek(0); geojson_data = json.load(file_geojson)
        st.session_state['geojson_data'] = geojson_data

        if not df_lab.empty and not df_geo_points.empty:
            col_id_lab = None
            for col in df_lab.columns:
                if str(col).lower().strip() in ['id', 'ponto', 'amostra', 'name', 'codigo']:
                    col_id_lab = col; break
            if not col_id_lab: col_id_lab = st.selectbox("Coluna ID Planilha:", df_lab.columns)
            
            df_lab['id_clean'] = df_lab[col_id_lab].apply(lambda x: str(x).split('.')[0].strip())
            df_geo_points['id_clean'] = df_geo_points['ID_PONTO'].apply(lambda x: str(x).split('.')[0].strip())
            
            df_merged = pd.merge(df_lab, df_geo_points, on='id_clean', how='inner')
            
            if df_merged.empty:
                st.error("Erro na fusão dos IDs.")
                st.stop()
            else:
                st.success(f"✅ {len(df_merged)} pontos.")
                df_merged['latitude'] += shift_lat
                df_merged['longitude'] += shift_lon
                
                if st.button("🚀 Gerar Mapas", type="primary"):
                    st.cache_data.clear()
                    df_krig, grid_shape = processar_matrizes_interpolacao(df_merged, geojson_data, resolucao_grid=100)
                    st.session_state['dados_processados'] = df_krig
                    st.session_state['grid_shape'] = grid_shape
                    st.rerun()

    except Exception as e: st.error(f"Erro: {e}")

# ==============================================================================
# 7. VISUALIZAÇÃO (COM CHAVE ÚNICA PARA NÃO TRAVAR)
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    grid_shape = st.session_state['grid_shape']
    cols_mapas = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    st.divider()
    if cols_mapas:
        atributo = st.selectbox("Selecione o mapa:", cols_mapas)
        df_plot = df_final[['latitude', 'longitude', atributo]].copy()

        if not df_plot.empty:
            try:
                img_buffer, bounds, min_max = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'], grid_shape)
                z_min, z_max = min_max
                
                centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satellite')
                
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=bounds, opacity=0.9, interactive=True, cross_origin=False, zindex=1
                ).add_to(m)
                
                folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x: {'color': 'black', 'weight': 2, 'fillOpacity': 0}).add_to(m)
                
                legend_html = f"""
                <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; background: white; padding: 10px; border: 2px solid black; border-radius: 5px; font-family: sans-serif;">
                <b>{atributo}</b><br>
                <div style="background: linear-gradient(to right, #000080, #0000ff, #00ffff, #ffff00, #ff0000, #800000); height: 10px; width: 150px;"></div>
                <div style="display: flex; justify-content: space-between; width: 150px; font-size: 12px;"><span>{z_min:.2f}</span><span>{z_max:.2f}</span></div>
                </div>
                """
                m.get_root().html.add_child(folium.Element(legend_html))
                
                # --- AQUI ESTÁ A CORREÇÃO: key=atributo ---
                # Isso força o Streamlit a criar um mapa NOVO para cada nutriente
                st_folium(m, height=500, use_container_width=True, key=f"mapa_{atributo}")
                
            except Exception as e: st.error(f"Erro visual: {e}")
