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

# Scipy RBF para interpolação suave (Padrão InCeres)
from scipy.interpolate import Rbf
import folium
from streamlit_folium import st_folium

# Tenta importar funções utilitárias
try:
    from utils_v43 import (
        configurar_pagina, renderizar_cabecalho_sidebar, 
        carregar_dados_blindado, validar_colunas
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

st.title("🚜 Tríade: Diagnóstico & VRT (Micros)")

if 'dados_processados' not in st.session_state: st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state: st.session_state['geojson_data'] = None
if 'grid_shape' not in st.session_state: st.session_state['grid_shape'] = None

# ==============================================================================
# 3. FUNÇÕES AUXILIARES
# ==============================================================================
def processar_arquivo_geografico(uploaded_file):
    points = []
    try:
        if uploaded_file.name.lower().endswith('.kmz'):
            with zipfile.ZipFile(uploaded_file, 'r') as z:
                kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                with z.open(kml_filename) as f: tree = ET.parse(f)
        else:
            uploaded_file.seek(0); tree = ET.parse(uploaded_file)
            
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
                            lon = float(first_coord[0]); lat = float(first_coord[1])
                            points.append({'ID_PONTO': name, 'latitude': lat, 'longitude': lon})
                        except ValueError: pass
        return pd.DataFrame(points)
    except Exception as e:
        st.error(f"Erro KML: {e}"); return pd.DataFrame()

def limpar_coluna_inteligente(serie):
    def clean_val(val):
        if pd.isna(val): return np.nan
        s = str(val).strip()
        if s.lower() in ['ns', 'nan', '', 'null', 'nd']: return np.nan
        return s
    s_clean = serie.apply(clean_val)
    if s_clean.dropna().apply(lambda x: ',' in x).any():
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
# 4. MOTOR DE CÁLCULO (RBF LINEAR - SEM OLHO DE BOI)
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

    # Projeção Aproximada (Graus -> Metros)
    lat_mean = df_grouped['latitude'].mean()
    df_grouped['Y_m'] = df_grouped['latitude'] * 111111
    df_grouped['X_m'] = df_grouped['longitude'] * 111111 * np.cos(np.radians(lat_mean))

    x_min, x_max = df_grouped['longitude'].min(), df_grouped['longitude'].max()
    y_min, y_max = df_grouped['latitude'].min(), df_grouped['latitude'].max()
    
    try:
        coords_geo = extrair_coordenadas_limpas(geojson_data)
        if coords_geo:
            lons_g = [p[0] for p in coords_geo]; lats_g = [p[1] for p in coords_geo]
            x_min = min(x_min, min(lons_g)); x_max = max(x_max, max(lons_g))
            y_min = min(y_min, min(lats_g)); y_max = max(y_max, max(lats_g))
    except: pass

    grid_x = np.linspace(x_min, x_max, resolucao_grid)
    grid_y = np.linspace(y_min, y_max, resolucao_grid)
    xx, yy = np.meshgrid(grid_x, grid_y)
    
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    processed_cols = []
    progresso = st.progress(0)
    
    for i, col in enumerate(cols_validas):
        progresso.progress((i + 1) / len(cols_validas))
        try:
            dados_col = df_grouped[['longitude', 'latitude', col]].dropna()
            if len(dados_col) < 5: continue
            
            # RBF Linear para continuidade visual
            interpolator = Rbf(dados_col['longitude'], dados_col['latitude'], dados_col[col], function='linear')
            z = interpolator(xx, yy)
            z = np.clip(z, dados_col[col].min(), dados_col[col].max())
            
            df_result[col] = z.flatten()
            processed_cols.append(col)
        except: continue
    
    progresso.empty()
    cols_finais = ['latitude', 'longitude'] + processed_cols
    return df_result[cols_finais], (resolucao_grid, resolucao_grid)

# ==============================================================================
# 5. GERAÇÃO DE IMAGEM (PALETA 6 FAIXAS - INCERES STYLE)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data, grid_shape):
    plt.close('all'); plt.clf()
    
    df_sorted = df_plot.sort_values(by=['latitude', 'longitude'])
    try:
        Z = df_sorted[atributo].values.reshape(grid_shape)
        X_unique = np.sort(df_plot['longitude'].unique())
        Y_unique = np.sort(df_plot['latitude'].unique())
    except: return None, None, [0, 1]

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
        z_min, z_max = np.nanmin(dados_validos), np.nanmax(dados_validos)
        if z_min == z_max: z_min -= 0.1; z_max += 0.1
    else: z_min, z_max = 0, 1

    fig = plt.figure(figsize=(10, 10 * (x_max-x_min)/(y_max-y_min)))
    fig.patch.set_alpha(0.0); ax = plt.axes([0,0,1,1]); ax.set_axis_off()
    
    # Paleta Vermelho -> Azul (6 cores)
    cores = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#4575b4']
    cmap = mcolors.ListedColormap(cores)
    boundaries = np.linspace(z_min, z_max, 7)
    norm = mcolors.BoundaryNorm(boundaries, cmap.N, clip=True)
    
    ax.contourf(X_unique, Y_unique, Z, levels=boundaries, cmap=cmap, norm=norm, extend='both', alpha=0.9)
    ax.set_xlim(x_min, x_max); ax.set_ylim(y_min, y_max)
    
    img_data = BytesIO()
    plt.savefig(img_data, format='png', transparent=True, dpi=100)
    plt.close(fig); img_data.seek(0)
    return img_data, [[y_min, x_min], [y_max, x_max]], [z_min, z_max]

# ==============================================================================
# 6. INTERFACE PRINCIPAL
# ==============================================================================
aba1, aba2 = st.tabs(["🗺️ Diagnóstico Visual", "🚜 Recomendação (VRT)"])

# --- ABA 1: DIAGNÓSTICO ---
with aba1:
    st.header("1. Importação de Dados")
    c1, c2, c3 = st.columns(3)
    file_lab = c1.file_uploader("Dados Lab (Excel/CSV)", type=["csv", "xlsx"])
    file_geo = c2.file_uploader("Pontos (.KMZ/.KML)", type=["kmz", "kml"])
    file_geojson = c3.file_uploader("Contorno (.geojson)", type=["geojson", "json"])

    if file_lab and file_geo and file_geojson:
        if st.button("🚀 Processar Ponte de Dados", type="primary"):
            try:
                # 1. Ler Lab
                if file_lab.name.lower().endswith('.csv'):
                    try: df_lab = pd.read_csv(file_lab)
                    except: file_lab.seek(0); df_lab = pd.read_csv(file_lab, sep=';')
                else: df_lab = pd.read_excel(file_lab)
                
                # 2. Ler Geo
                df_geo_points = processar_arquivo_geografico(file_geo)
                
                # 3. Ler Contorno
                file_geojson.seek(0); st.session_state['geojson_data'] = json.load(file_geojson)

                # 4. Fazer a Ponte (Merge)
                if not df_lab.empty and not df_geo_points.empty:
                    col_id = next((c for c in df_lab.columns if str(c).lower().strip() in ['id', 'ponto', 'amostra', 'codigo']), df_lab.columns[0])
                    df_lab['id_clean'] = df_lab[col_id].apply(lambda x: str(x).split('.')[0].strip())
                    df_geo_points['id_clean'] = df_geo_points['ID_PONTO'].apply(lambda x: str(x).split('.')[0].strip())
                    
                    df_merged = pd.merge(df_lab, df_geo_points, on='id_clean', how='inner')
                    
                    if not df_merged.empty:
                        df_krig, shape = processar_matrizes_interpolacao(df_merged, st.session_state['geojson_data'], 100)
                        st.session_state['dados_processados'] = df_krig
                        st.session_state['grid_shape'] = shape
                        st.success(f"Sucesso! {len(df_merged)} pontos processados.")
                    else: st.error("Erro: IDs não batem entre Planilha e Mapa.")
            except Exception as e: st.error(f"Erro crítico: {e}")

    # Visualização Diagnóstico
    if st.session_state['dados_processados'] is not None:
        st.divider()
        cols_mapas = [c for c in st.session_state['dados_processados'].columns if c not in ['latitude', 'longitude']]
        atributo = st.selectbox("Selecione o Nutriente:", cols_mapas)
        
        img, bounds, minmax = gerar_imagem_overlay(
            st.session_state['dados_processados'], atributo, 
            st.session_state['geojson_data'], st.session_state['grid_shape']
        )
        
        if img:
            m = folium.Map(location=[bounds[0][0], bounds[0][1]], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
            img_b64 = base64.b64encode(img.getvalue()).decode()
            folium.raster_layers.ImageOverlay(
                image=f"data:image/png;base64,{img_b64}", bounds=bounds, opacity=0.8
            ).add_to(m)
            folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x: {'color':'black','fillOpacity':0}).add_to(m)
            
            legend = f"""<div style="position:fixed; bottom:30px; right:30px; z-index:9999; background:white; padding:10px; border:1px solid black;">
            <b>{atributo}</b><br>
            <div style="display:flex; width:150px; height:10px;">
                <div style="flex:1; background:#d73027;"></div><div style="flex:1; background:#fc8d59;"></div>
                <div style="flex:1; background:#fee08b;"></div><div style="flex:1; background:#d9ef8b;"></div>
                <div style="flex:1; background:#91cf60;"></div><div style="flex:1; background:#4575b4;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:10px;"><span>{minmax[0]:.2f}</span><span>{minmax[1]:.2f}</span></div>
            </div>"""
            m.get_root().html.add_child(folium.Element(legend))
            st_folium(m, height=500, use_container_width=True, key=f"mapa_diag_{atributo}")

# --- ABA 2: RECOMENDAÇÃO VRT ---
with aba2:
    st.header("🚜 Mapas de Recomendação")
    
    if st.session_state['dados_processados'] is None:
        st.warning("⚠️ Processe os dados na aba 'Diagnóstico' primeiro.")
    else:
        df_vrt = st.session_state['dados_processados'].copy()
        
        # --- 1. CORRETIVOS ---
        st.subheader("1. Corretivos (Calcário/Gesso)")
        c1, c2 = st.columns(2)
        with c1.expander("🟣 Calagem", expanded=False):
            v_alvo = st.number_input("V% Alvo:", value=60.0)
            prnt = st.number_input("PRNT:", value=85.0)
            col_v = next((c for c in df_vrt.columns if 'v%' in c.lower()), None)
            col_ctc = next((c for c in df_vrt.columns if 'ctc' in c.lower()), None)
            if col_v and col_ctc:
                df_vrt['Calcario_Ton'] = ((v_alvo - df_vrt[col_v]) * df_vrt[col_ctc] / 100) * (100 / prnt)
                df_vrt['Calcario_Ton'] = df_vrt['Calcario_Ton'].apply(lambda x: x if x > 0 else 0)

        with c2.expander("⚪ Gessagem", expanded=False):
            col_argila = next((c for c in df_vrt.columns if 'argila' in c.lower()), None)
            if col_argila:
                df_vrt['Gesso_Ton'] = (df_vrt[col_argila] * 50) / 1000

        # --- 2. MICRONUTRIENTES (NOVO) ---
        st.subheader("2. Micronutrientes (Padrão Cerrado)")
        
        # Dicionário de Configuração Padrão (Base Embrapa)
        # Nutriente: [Nível Crítico (Baixo), Dose Recomendada (kg/ha)]
        micros_config = {
            'Boro (B)':   {'col': 'b',  'critico': 0.3, 'dose': 2.0},
            'Zinco (Zn)': {'col': 'zn', 'critico': 1.2, 'dose': 4.0},
            'Cobre (Cu)': {'col': 'cu', 'critico': 0.5, 'dose': 2.0},
            'Mang. (Mn)': {'col': 'mn', 'critico': 4.0, 'dose': 5.0}
        }
        
        cm1, cm2 = st.columns(2)
        count = 0
        for nome, cfg in micros_config.items():
            # Tenta achar a coluna na planilha (ex: 'B', 'Boro', 'Zn', 'Zinco')
            col_real = next((c for c in df_vrt.columns if cfg['col'] == c.lower() or cfg['col'] == c.lower().split(' ')[0]), None)
            
            if col_real:
                with (cm1 if count % 2 == 0 else cm2).expander(f"💊 {nome}", expanded=True):
                    critico = st.number_input(f"Nível Crítico {nome} (mg/dm³):", value=cfg['critico'], key=f"crit_{nome}")
                    dose_rec = st.number_input(f"Dose a aplicar (kg/ha):", value=cfg['dose'], key=f"dose_{nome}")
                    
                    # Lógica de Recomendação (Simples):
                    # Se Valor < Crítico -> Aplica Dose. Se Maior -> Aplica 0.
                    nome_mapa = f"Rec_{nome.split()[0]}_kg_ha"
                    
                    # np.where é mais rápido que apply
                    df_vrt[nome_mapa] = np.where(df_vrt[col_real] < critico, dose_rec, 0.0)
                count += 1
        
        st.divider()
        
        # --- VISUALIZAÇÃO VRT ---
        mapas_vrt = [c for c in df_vrt.columns if 'ton' in c.lower() or 'kg_ha' in c.lower()]
        
        if mapas_vrt:
            escolha_vrt = st.selectbox("Selecione o Mapa de Aplicação:", mapas_vrt)
            
            # Filtra apenas onde tem dose > 0 para estatística
            dose_media = df_vrt[df_vrt[escolha_vrt] > 0][escolha_vrt].mean()
            if pd.isna(dose_media): dose_media = 0
            
            c_info1, c_info2 = st.columns(2)
            c_info1.info(f"Dose Média (nas áreas de aplicação): {dose_media:.2f}")
            c_info2.info(f"Área com Deficiência: {(len(df_vrt[df_vrt[escolha_vrt]>0])/len(df_vrt))*100:.1f}% do talhão")
            
            img_vrt, bounds_vrt, minmax_vrt = gerar_imagem_overlay(
                df_vrt, escolha_vrt, 
                st.session_state['geojson_data'], st.session_state['grid_shape']
            )
            
            if img_vrt:
                m_vrt = folium.Map(location=[bounds_vrt[0][0], bounds_vrt[0][1]], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                img_b64_vrt = base64.b64encode(img_vrt.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64_vrt}", bounds=bounds_vrt, opacity=0.8
                ).add_to(m_vrt)
                folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x: {'color':'black','fillOpacity':0}).add_to(m_vrt)
                
                legend_vrt = f"""<div style="position:fixed; bottom:30px; right:30px; z-index:9999; background:white; padding:10px; border:1px solid black;">
                <b>{escolha_vrt}</b><br>
                <div style="display:flex; width:150px; height:10px;">
                    <div style="flex:1; background:#d73027;"></div><div style="flex:1; background:#fc8d59;"></div>
                    <div style="flex:1; background:#fee08b;"></div><div style="flex:1; background:#d9ef8b;"></div>
                    <div style="flex:1; background:#91cf60;"></div><div style="flex:1; background:#4575b4;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:10px;"><span>{minmax_vrt[0]:.2f}</span><span>{minmax_vrt[1]:.2f}</span></div>
                </div>"""
                m_vrt.get_root().html.add_child(folium.Element(legend_vrt))
                
                st_folium(m_vrt, height=500, use_container_width=True, key=f"mapa_vrt_{escolha_vrt}")
