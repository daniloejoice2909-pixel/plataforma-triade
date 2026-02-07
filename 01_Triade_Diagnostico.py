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
    # Mock para caso o arquivo utils_v43 não esteja no mesmo diretório
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
# 3. FUNÇÕES AUXILIARES (GEOMETRIA E PARSER)
# ==============================================================================
def processar_arquivo_geografico(uploaded_file):
    """
    Lê arquivos KML ou KMZ e retorna um DataFrame com ID_PONTO, latitude, longitude.
    """
    points = []
    
    try:
        # Verifica se é KMZ (ZIP)
        if uploaded_file.name.lower().endswith('.kmz'):
            with zipfile.ZipFile(uploaded_file, 'r') as z:
                # Pega o primeiro KML dentro do ZIP
                kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                with z.open(kml_filename) as f:
                    tree = ET.parse(f)
        # Verifica se é KML (XML direto)
        else:
            uploaded_file.seek(0)
            tree = ET.parse(uploaded_file)
            
        root = tree.getroot()
        
        # Namespaces comuns do KML
        namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Tenta encontrar Placemarks com ou sem namespace
        placemarks = root.findall('.//kml:Placemark', namespace)
        if not placemarks:
            placemarks = root.findall('.//Placemark')
            
        for placemark in placemarks:
            # Extrair Nome (ID)
            name_elem = placemark.find('kml:name', namespace)
            if name_elem is None: name_elem = placemark.find('name')
            name = name_elem.text.strip() if name_elem is not None and name_elem.text else None
            
            # Extrair Coordenadas
            coord_elem = placemark.find('.//kml:coordinates', namespace)
            if coord_elem is None: coord_elem = placemark.find('.//coordinates')
            
            if coord_elem is not None and coord_elem.text:
                # KML padrão: lon,lat,alt (separados por espaço se houver vários)
                coords_text = coord_elem.text.strip().split()
                if coords_text:
                    # Pega a primeira coordenada
                    first_coord = coords_text[0].split(',')
                    if len(first_coord) >= 2:
                        try:
                            lon = float(first_coord[0])
                            lat = float(first_coord[1])
                            points.append({'ID_PONTO': name, 'latitude': lat, 'longitude': lon})
                        except ValueError:
                            pass
                            
        return pd.DataFrame(points)

    except Exception as e:
        st.error(f"Erro ao ler arquivo de pontos: {e}")
        return pd.DataFrame()

def limpar_coluna_inteligente(serie):
    """Detecta numéricos mistos (BR/US), remove 'ns' e limpa"""
    # Converte para string, remove espaços e força minúsculo para detectar 'ns'
    s_str = serie.astype(str).str.strip()
    
    # Substitui 'ns' (não amostrado) por NaN
    s_str = s_str.replace(['ns', 'NS', 'nan', 'NaN'], np.nan)
    
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

# ==============================================================================
# 4. MOTOR DE CÁLCULO
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Calculando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    df = df_input.copy()
    
    # Adicionado 'id_clean' para não tentar interpolar o ID
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao', 'geometry', 'id_clean']
    
    cols_validas = []
    for col in df.columns:
        if col.lower() in cols_proibidas: continue
        # Limpeza Forçada
        df[col] = limpar_coluna_inteligente(df[col])
        # Aceita colunas com pelo menos 5 valores válidos para ter o que interpolar
        if df[col].notna().sum() >= 5: 
            cols_validas.append(col)

    # Coordenadas ajustadas
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
            if len(dados_col) == 0: continue
            if dados_col[col].nunique() <= 1:
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
            # st.warning(f"Não foi possível interpolar {col}: {e}")
            continue

    cols_finais = ['latitude', 'longitude'] + processed_cols
    return df_result[cols_finais], (resolucao_grid, resolucao_grid)

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

    # Escala
    dados_validos = Z[~np.isnan(Z)]
    if len(dados_validos) > 0:
        z_min = np.percentile(dados_validos, 2)
        z_max = np.percentile(dados_validos, 98)
        if z_min == z_max: z_min -= 0.1; z_max += 0.1
        elif (z_max - z_min) < 0.01: z_max += 0.01
    else: z_min, z_max = 0, 1

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
# 6. INTERFACE DE UPLOAD E FUSÃO (Atualizado e Blindado)
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")

# Uploads separados
file_lab = st.sidebar.file_uploader("📂 Dados Laboratório (Excel/CSV)", type=["csv", "xlsx", "xls"])
file_geo = st.sidebar.file_uploader("📍 Coordenadas dos Pontos (.KMZ/.KML)", type=["kmz", "kml"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno do Talhão (.geojson)", type=["geojson", "json"])

# --- AJUSTE FINO (PERSISTENTE) ---
st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ Ajuste Fino de Coordenadas", expanded=False):
    shift_lat = st.number_input("Deslocar Lat", value=0.00000, step=0.00010, format="%.5f")
    shift_lon = st.number_input("Deslocar Lon", value=0.00000, step=0.00010, format="%.5f")

# Reset se mudar arquivos
if not file_lab or not file_geo or not file_geojson:
    if st.session_state.get('dados_processados') is not None:
        st.info("Aguardando upload de todos os arquivos (Lab, Pontos e Contorno)...")

if file_lab and file_geo and file_geojson:
    # 1. PROCESSAR DADOS
    try:
        # A) Ler Planilha Lab (BLINDAGEM EXCEL ANTIGO)
        if file_lab.name.lower().endswith('.csv'):
            try:
                df_lab = pd.read_csv(file_lab)
                # Tenta separador ; se falhar
                if len(df_lab.columns) < 2:
                    file_lab.seek(0)
                    df_lab = pd.read_csv(file_lab, sep=';')
            except Exception as e:
                st.error(f"Erro ao ler CSV: {e}")
                st.stop()
        else:
            try:
                df_lab = pd.read_excel(file_lab)
            except ImportError as e:
                if 'xlrd' in str(e):
                    st.error("🛑 O arquivo enviado é .xls antigo. Por favor, salve como .xlsx ou .csv no Excel e tente novamente.")
                    st.stop()
                else:
                    st.error(f"Erro ao ler Excel: {e}")
                    st.stop()
        
        # B) Ler Pontos KML/KMZ
        df_geo_points = processar_arquivo_geografico(file_geo)
        
        # C) Ler Contorno GeoJSON
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
        st.session_state['geojson_data'] = geojson_data

        # 2. LÓGICA DE FUSÃO (MERGE) BLINDADA
        if not df_lab.empty and not df_geo_points.empty:
            
            # Identificação de Coluna ID no Lab
            col_id_lab = None
            possiveis = ['id', 'ponto', 'amostra', 'name', 'codigo', 'sample']
            for col in df_lab.columns:
                if str(col).lower().strip() in possiveis:
                    col_id_lab = col
                    break
            
            if not col_id_lab:
                st.warning("Não encontrei coluna 'ID' ou 'Ponto' na planilha. Selecione abaixo:")
                col_id_lab = st.selectbox("Coluna de ID na Planilha:", df_lab.columns)
            
            # --- LIMPEZA DE IDs (Resolve o erro "Can only use .str accessor") ---
            # Usa .apply(lambda x: str(x)) para garantir que tudo vire texto, sem erro de atributo
            
            # 1. Limpa IDs da Planilha
            df_lab['id_clean'] = df_lab[col_id_lab].apply(lambda x: str(x).strip() if pd.notnull(x) else "")
            # Remove decimais (.0) caso existam
            df_lab['id_clean'] = df_lab['id_clean'].apply(lambda x: x.split('.')[0])

            # 2. Limpa IDs do Mapa (KML/KMZ)
            df_geo_points['id_clean'] = df_geo_points['ID_PONTO'].apply(lambda x: str(x).strip() if pd.notnull(x) else "")
            df_geo_points['id_clean'] = df_geo_points['id_clean'].apply(lambda x: x.split('.')[0])
            
            # ---------------------------------------------------------------------
            
            # Merge (Inner Join) - Só mantém o que tem coordenada E dados de lab
            df_merged = pd.merge(df_lab, df_geo_points, on='id_clean', how='inner')
            
            if df_merged.empty:
                st.error("❌ Erro na fusão: Nenhum ID da planilha coincidiu com o arquivo de pontos.")
                st.markdown("**Diagnóstico:**")
                c1, c2 = st.columns(2)
                with c1:
                    st.write("Amostra IDs Planilha:", df_lab['id_clean'].unique()[:5])
                with c2:
                    st.write("Amostra IDs Mapa (KMZ):", df_geo_points['id_clean'].unique()[:5])
                st.stop()
            else:
                st.success(f"✅ {len(df_merged)} pontos combinados com sucesso!")
                
                # Aplica Ajuste Fino se necessário
                df_merged['latitude'] = df_merged['latitude'] + shift_lat
                df_merged['longitude'] = df_merged['longitude'] + shift_lon

                # Visualização Prévia (Mapa de Bolinhas)
                st.subheader("📍 Conferência dos Pontos")
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Mapa Simples
                    st.map(df_merged[['latitude', 'longitude']])
                with col2:
                    st.dataframe(df_merged[[col_id_lab, 'latitude', 'longitude']].head())

                # 3. BOTÃO DE PROCESSAMENTO
                if st.button("🚀 Gerar Mapas de Fertilidade", type="primary"):
                    with st.status("Processando...", expanded=True) as status:
                        st.cache_data.clear() 
                        
                        df_krig, grid_shape = processar_matrizes_interpolacao(df_merged, geojson_data)
                        
                        if df_krig.empty: 
                            st.error("Tabela vazia após processamento.")
                            st.stop()
                        
                        st.session_state['dados_processados'] = df_krig
                        st.session_state['grid_shape'] = grid_shape
                        status.update(label="Concluído!", state="complete", expanded=False)
                    st.rerun()

    except Exception as e:
        st.error(f"Erro ao processar arquivos: {e}")

# ==============================================================================
# 7. RESULTADOS
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    grid_shape = st.session_state['grid_shape']
    
    cols_mapas = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    st.divider()
    st.markdown(f"### 🗺️ Mapas Disponíveis ({len(cols_mapas)})")
    
    if cols_mapas:
        atributo = st.selectbox("Selecione o nutriente:", cols_mapas)
        
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
                
                # Legenda
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
                
            except Exception as e:
                st.error(f"Erro visual: {e}")
