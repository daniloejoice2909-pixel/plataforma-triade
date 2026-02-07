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
from scipy.interpolate import Rbf
from scipy.interpolate import NearestNDInterpolator # Fallback de segurança
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
configurar_pagina("Tríade VRT Expert")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Sistema VRT (Expert)")

if 'dados_processados' not in st.session_state: st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state: st.session_state['geojson_data'] = None
if 'grid_shape' not in st.session_state: st.session_state['grid_shape'] = None
if 'dados_rec' not in st.session_state: st.session_state['dados_rec'] = None

# ==============================================================================
# 3. SIDEBAR DE PARÂMETROS
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parâmetros")

# A. Produtividade
with st.sidebar.expander("1. Meta de Produtividade", expanded=True):
    meta_prod = st.number_input("Meta Soja (sc/ha):", value=80.0, step=1.0)

# B. Calagem
with st.sidebar.expander("2. Calagem (Elevação Ca/Mg)", expanded=False):
    alvo_ca = st.number_input("Alvo Cálcio (%):", value=60.0, step=1.0)
    alvo_mg = st.number_input("Alvo Magnésio (%):", value=18.0, step=1.0)
    prnt_calc = st.number_input("PRNT (%):", value=80.0, step=1.0)
    teor_cao = st.number_input("Teor CaO (%):", value=60.0, step=1.0) 
    teor_mgo = st.number_input("Teor MgO (%):", value=18.0, step=1.0) 

# C. Fósforo
with st.sidebar.expander("3. Fósforo (P)", expanded=False):
    export_p_factor = st.number_input("Exportação P (kg/sc):", value=0.8, step=0.1)
    teor_p2o5_adubo = st.number_input("Teor P₂O₅ Adubo (%):", value=21.0, step=1.0)
    fator_tam_p = st.number_input("Fator Tampão (kg P₂O₅/mg):", value=5.0, step=0.5)
    st.caption("Níveis Críticos P-rem:")
    nc_p1 = st.number_input("0 - 4:", value=6.0)
    nc_p2 = st.number_input("4.1 - 10:", value=7.5)
    nc_p3 = st.number_input("10.1 - 19:", value=11.5)
    nc_p4 = st.number_input("19.1 - 30:", value=15.0)
    nc_p5 = st.number_input("> 30:", value=20.0)

# D. Potássio
with st.sidebar.expander("4. Potássio (K)", expanded=False):
    alvo_k_ctc = st.number_input("Meta K na CTC (%):", value=3.5, step=0.1)
    export_k_factor = st.number_input("Exportação K (kg/sc):", value=1.2, step=0.1)
    teor_k2o_adubo = st.number_input("Teor K₂O Adubo (%):", value=60.0, step=1.0)

# E. Gesso
with st.sidebar.expander("5. Gessagem", expanded=False):
    fator_gesso = st.number_input("Fator x Argila:", value=50.0, step=5.0)

# ==============================================================================
# 4. FUNÇÕES DE SUPORTE
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
    except: return pd.DataFrame()

def limpar_coluna_inteligente(serie):
    """Converte números brasileiros (vírgula) para Python (ponto)"""
    def clean_val(val):
        if pd.isna(val): return np.nan
        s = str(val).strip().replace(' ', '')
        if s.lower() in ['ns', 'nan', '', 'null', 'nd', '-']: return np.nan
        # Troca vírgula por ponto APENAS se for o separador decimal
        if ',' in s and '.' in s: # Ex: 1.200,50 -> Remove o ponto primeiro
            s = s.replace('.', '')
        s = s.replace(',', '.')
        try:
            return float(s)
        except:
            return np.nan

    return serie.apply(clean_val)

def extrair_coordenadas_limpas(geojson_data):
    try:
        if 'features' in geojson_data: geom = geojson_data['features'][0]['geometry']
        elif 'geometry' in geojson_data: geom = geojson_data['geometry']
        else: geom = geojson_data
        if geom['type'] == 'Polygon': return [p[:2] for p in geom['coordinates'][0]]
        elif geom['type'] == 'MultiPolygon': return [p[:2] for p in geom['coordinates'][0][0]]
        return []
    except: return []

# ==============================================================================
# 5. MOTOR GRÁFICO E INTERPOLAÇÃO
# ==============================================================================
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=100):
    df = df_input.copy()
    
    # Normaliza Coordenadas
    if 'latitude_y' in df.columns: df.rename(columns={'latitude_y': 'latitude', 'longitude_y': 'longitude'}, inplace=True)
    elif 'latitude_x' in df.columns and 'latitude' not in df.columns: df.rename(columns={'latitude_x': 'latitude', 'longitude_x': 'longitude'}, inplace=True)
    
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude'])

    # Limpeza de Dados
    cols_ignorar = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'geometry', 'id_clean']
    cols_validas = []
    
    for col in df.columns:
        if any(x in str(col).lower() for x in cols_ignorar): continue
        df[col] = limpar_coluna_inteligente(df[col])
        if df[col].notna().sum() >= 3: # Mínimo 3 pontos para criar um plano
            cols_validas.append(col)

    if not cols_validas: return pd.DataFrame(), None

    # Grid
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    
    # Expande um pouco as bordas
    margin_x = (x_max - x_min) * 0.1
    margin_y = (y_max - y_min) * 0.1
    
    grid_x = np.linspace(x_min - margin_x, x_max + margin_x, resolucao_grid)
    grid_y = np.linspace(y_min - margin_y, y_max + margin_y, resolucao_grid)
    xx, yy = np.meshgrid(grid_x, grid_y)
    
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    # Fator de conversão aproximado para metros (para o cálculo RBF não distorcer)
    lat_mean = df['latitude'].mean()
    scale_x = 111111 * np.cos(np.radians(lat_mean))
    scale_y = 111111

    progresso = st.progress(0)
    for i, col in enumerate(cols_validas):
        progresso.progress((i + 1) / len(cols_validas))
        try:
            dados = df[['longitude', 'latitude', col]].dropna()
            
            X_m = dados['longitude'] * scale_x
            Y_m = dados['latitude'] * scale_y
            
            # Tenta RBF Linear (Visual InCeres)
            try:
                interp = Rbf(X_m, Y_m, dados[col], function='linear', smooth=0)
                z = interp(xx * scale_x, yy * scale_y)
            except:
                # Fallback para Vizinho Mais Próximo (Garante mapa)
                interp = NearestNDInterpolator(list(zip(X_m, Y_m)), dados[col])
                z = interp(xx * scale_x, yy * scale_y)

            # Limita valores ao range real (evita explosão matemática)
            z = np.clip(z, dados[col].min(), dados[col].max())
            df_result[col] = z.flatten()
        except: continue
        
    progresso.empty()
    cols_finais = ['latitude', 'longitude'] + [c for c in cols_validas if c in df_result.columns]
    return df_result[cols_finais], (resolucao_grid, resolucao_grid)

def gerar_imagem_overlay(df_plot, atributo, geojson_data, grid_shape):
    plt.close('all'); plt.clf()
    
    # Prepara matriz
    try:
        if 'latitude' not in df_plot.columns: return None, None, [0,1]
        
        # Ordena para garantir que o reshape funcione
        df_sorted = df_plot.sort_values(by=['latitude', 'longitude'])
        
        # Tenta reshape direto (mais rápido)
        Z = df_sorted[atributo].values.reshape(grid_shape)
        X_unique = np.sort(df_plot['longitude'].unique())
        Y_unique = np.sort(df_plot['latitude'].unique())
    except:
        return None, None, [0, 1]

    # Máscara do Polígono
    try:
        coords = extrair_coordenadas_limpas(geojson_data)
        if coords:
            poly_path = MplPath(coords)
            # Cria grid de pontos para verificar dentro/fora
            XX, YY = np.meshgrid(X_unique, Y_unique)
            points = np.column_stack((XX.flatten(), YY.flatten()))
            mask = poly_path.contains_points(points).reshape(Z.shape)
            Z[~mask] = np.nan
    except: pass

    # Escala de Cores
    dados_validos = Z[~np.isnan(Z)]
    if len(dados_validos) == 0: return None, None, [0, 1]
    
    z_min, z_max = np.nanmin(dados_validos), np.nanmax(dados_validos)
    if z_min == z_max: z_min -= 0.01; z_max += 0.01

    # Plot
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes([0,0,1,1])
    ax.set_axis_off()
    
    # Paleta InCeres
    cores = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#4575b4']
    cmap = mcolors.ListedColormap(cores)
    bounds = np.linspace(z_min, z_max, 7)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)
    
    ax.contourf(X_unique, Y_unique, Z, levels=bounds, cmap=cmap, norm=norm, extend='both', alpha=0.9)
    
    # Salva
    img_data = BytesIO()
    plt.savefig(img_data, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
    img_data.seek(0)
    plt.close(fig)
    
    return img_data, [[Y_unique.min(), X_unique.min()], [Y_unique.max(), X_unique.max()]], [z_min, z_max]

# ==============================================================================
# 6. CÁLCULO DE RECOMENDAÇÃO
# ==============================================================================
def calcular_vrt(df):
    df_rec = df.copy()
    
    # Mapeamento Flexível (Aceita 'Ca', 'Ca cmolc', 'Calcio', etc)
    cols = {}
    for alvo in ['ca', 'mg', 'k', 'p', 'v%', 'ctc', 'argila', 'prem']:
        cols[alvo] = next((c for c in df_rec.columns if alvo in c.lower()), None)

    # 1. CALAGEM
    if cols['ca'] and cols['mg'] and cols['ctc']:
        def_ca = ((alvo_ca/100) * df_rec[cols['ctc']]) - df_rec[cols['ca']]
        def_mg = ((alvo_mg/100) * df_rec[cols['ctc']]) - df_rec[cols['mg']]
        
        need_cao = def_ca * 560
        need_mgo = def_mg * 403
        
        dose_ca = (need_cao / (teor_cao if teor_cao > 0 else 1)) / 10
        dose_mg = (need_mgo / (teor_mgo if teor_mgo > 0 else 1)) / 10
        
        dose_final = np.maximum(dose_ca, dose_mg) * (100 / (prnt_calc if prnt_calc > 0 else 1))
        df_rec['Calcario_Ton_ha'] = dose_final.apply(lambda x: x if x > 0 else 0)

    # 2. POTÁSSIO
    if cols['k'] and cols['ctc']:
        k_pct = (df_rec[cols['k']] / df_rec[cols['ctc']]) * 100
        def_k = ((alvo_k_ctc - k_pct)/100) * df_rec[cols['ctc']]
        
        k_repo = (def_k * 942) + (meta_prod * export_k_factor)
        df_rec['KCL_Kg_ha'] = (k_repo * (100 / (teor_k2o_adubo if teor_k2o_adubo > 0 else 1))).apply(lambda x: x if x > 0 else 0)

    # 3. FÓSFORO
    col_p = next((c for c in df_rec.columns if 'p mehl' in c.lower() or 'p_mehl' in c.lower()), cols['p'])
    if col_p and cols['prem']:
        # Tabela NC
        conds = [
            df_rec[cols['prem']] <= 4,
            (df_rec[cols['prem']] > 4) & (df_rec[cols['prem']] <= 10),
            (df_rec[cols['prem']] > 10) & (df_rec[cols['prem']] <= 19),
            (df_rec[cols['prem']] > 19) & (df_rec[cols['prem']] <= 30),
            df_rec[cols['prem']] > 30
        ]
        nc_vals = [nc_p1, nc_p2, nc_p3, nc_p4, nc_p5]
        nc_grid = np.select(conds, nc_vals, default=30)
        
        gap = nc_grid - df_rec[col_p]
        dose_p = (gap * fator_tam_p) + (meta_prod * export_p_factor)
        df_rec['MAP_Kg_ha'] = (dose_p * (100 / (teor_p2o5_adubo if teor_p2o5_adubo > 0 else 1))).apply(lambda x: x if x > 0 else 0)

    # 4. GESSO
    if cols['argila']:
        df_rec['Gesso_Ton_ha'] = (df_rec[cols['argila']] * fator_gesso) / 1000

    return df_rec

# ==============================================================================
# 7. INTERFACE
# ==============================================================================
aba1, aba2 = st.tabs(["🗺️ Diagnóstico", "🚜 Recomendação VRT"])

# --- ABA 1: DIAGNÓSTICO ---
with aba1:
    # DEBUGGER VISUAL
    with st.sidebar.expander("🔍 Ver Dados Processados"):
        if st.session_state['dados_processados'] is not None:
            st.dataframe(st.session_state['dados_processados'].head())
        else:
            st.write("Nenhum dado carregado ainda.")

    st.header("Importação")
    c1, c2, c3 = st.columns(3)
    f_lab = c1.file_uploader("Lab (CSV/XLSX)", type=["csv", "xlsx"])
    f_geo = c2.file_uploader("Pontos (KML/KMZ)", type=["kmz", "kml"])
    f_json = c3.file_uploader("Contorno (GeoJSON)", type=["geojson", "json"])

    if f_lab and f_geo and f_json:
        if st.button("🚀 Processar", type="primary"):
            try:
                # Leitura
                if f_lab.name.endswith('.csv'): 
                    try: df_lab = pd.read_csv(f_lab)
                    except: f_lab.seek(0); df_lab = pd.read_csv(f_lab, sep=';')
                else: df_lab = pd.read_excel(f_lab)
                
                df_pts = processar_arquivo_geografico(f_geo)
                f_json.seek(0); geo_data = json.load(f_json)
                
                # Merge
                col_id = next((c for c in df_lab.columns if str(c).lower().strip() in ['id', 'ponto', 'amostra']), df_lab.columns[0])
                df_lab['id_clean'] = df_lab[col_id].astype(str).str.strip().str.replace('.0', '')
                df_pts['id_clean'] = df_pts['ID_PONTO'].astype(str).str.strip().str.replace('.0', '')
                
                df_m = pd.merge(df_lab, df_pts, on='id_clean', how='inner')
                
                if not df_m.empty:
                    st.session_state['geojson_data'] = geo_data
                    # Interpolação
                    df_krig, shape = processar_matrizes_interpolacao(df_m, geo_data, 100)
                    
                    if not df_krig.empty:
                        st.session_state['dados_processados'] = df_krig
                        st.session_state['grid_shape'] = shape
                        st.success(f"Sucesso! {len(df_m)} pontos usados.")
                    else: st.error("Erro: Dados numéricos insuficientes para interpolar.")
                else: st.error("Erro: Nenhum ID coincidiu entre Planilha e Mapa.")
            except Exception as e: st.error(f"Erro no processo: {e}")

    # Visualização Aba 1
    if st.session_state['dados_processados'] is not None:
        cols = [c for c in st.session_state['dados_processados'].columns 
                if c not in ['latitude', 'longitude'] and 'Ton' not in c and 'Kg' not in c]
        if cols:
            attr = st.selectbox("Nutriente:", cols)
            
            # Exportar Ponte
            csv = st.session_state['dados_processados'].to_csv(index=False).encode('utf-8')
            st.download_button("💾 Baixar Ponte (CSV)", csv, "ponte_vrt.csv", "text/csv")
            
            img, bounds, mm = gerar_imagem_overlay(st.session_state['dados_processados'], attr, st.session_state['geojson_data'], st.session_state['grid_shape'])
            if img:
                m = folium.Map(location=[bounds[0][0], bounds[0][1]], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{base64.b64encode(img.getvalue()).decode()}", bounds=bounds, opacity=0.8).add_to(m)
                folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x:{'color':'black','fillOpacity':0}).add_to(m)
                st_folium(m, height=500, use_container_width=True, key="mapa_diag")

# --- ABA 2: VRT ---
with aba2:
    if st.session_state['dados_processados'] is None:
        st.warning("Gere o diagnóstico na Aba 1 primeiro.")
    else:
        if st.button("🔄 Gerar Recomendações"):
            st.session_state['dados_rec'] = calcular_vrt(st.session_state['dados_processados'])
            st.success("Calculado!")
            
        if st.session_state['dados_rec'] is not None:
            cols_rec = [c for c in st.session_state['dados_rec'].columns if 'Ton' in c or 'Kg' in c]
            if cols_rec:
                escolha = st.selectbox("Mapa de Aplicação:", cols_rec)
                mean_val = st.session_state['dados_rec'][escolha].mean()
                st.info(f"Média: {mean_val:.2f}")
                
                img, bounds, mm = gerar_imagem_overlay(st.session_state['dados_rec'], escolha, st.session_state['geojson_data'], st.session_state['grid_shape'])
                if img:
                    m2 = folium.Map(location=[bounds[0][0], bounds[0][1]], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                    folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{base64.b64encode(img.getvalue()).decode()}", bounds=bounds, opacity=0.8).add_to(m2)
                    folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x:{'color':'black','fillOpacity':0}).add_to(m2)
                    st_folium(m2, height=500, use_container_width=True, key="mapa_vrt")
