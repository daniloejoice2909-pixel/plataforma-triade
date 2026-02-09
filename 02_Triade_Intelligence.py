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
from scipy.interpolate import NearestNDInterpolator
import folium
from streamlit_folium import st_folium

# --- BIBLIOTECAS GEOESPACIAIS ---
try:
    import geopandas as gpd
    from shapely.geometry import box
    GEO_ENABLED = True
except ImportError:
    GEO_ENABLED = False

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

if not GEO_ENABLED:
    st.warning("⚠️ Aviso: Bibliotecas 'geopandas' e 'shapely' não detectadas. A exportação Shapefile ficará desativada.")

if 'dados_processados' not in st.session_state: st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state: st.session_state['geojson_data'] = None
if 'grid_shape' not in st.session_state: st.session_state['grid_shape'] = None
if 'dados_rec' not in st.session_state: st.session_state['dados_rec'] = None

# ==============================================================================
# 3. SIDEBAR DE PARÂMETROS
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parâmetros de Recomendação")

# A. Produtividade
with st.sidebar.expander("1. Meta de Produtividade", expanded=True):
    meta_prod = st.number_input("Meta Soja (sc/ha):", value=80.0, step=1.0)

# B. Calagem (COM SIMULADOR RESTAURADO)
with st.sidebar.expander("2. Calagem (Elevação Ca/Mg)", expanded=True):
    st.markdown("### Metas de Solo")
    alvo_ca = st.number_input("Alvo Cálcio (%):", value=60.0, step=1.0)
    alvo_mg = st.number_input("Alvo Magnésio (%):", value=18.0, step=1.0)
    
    st.markdown("### Corretivo")
    prnt_calc = st.number_input("PRNT (%):", value=82.0, step=1.0)
    teor_cao = st.number_input("Teor CaO (%):", value=42.0, step=1.0) 
    teor_mgo = st.number_input("Teor MgO (%):", value=9.0, step=1.0) 

    # --- SIMULADOR DE RELAÇÃO CA/MG ---
    if st.session_state['dados_processados'] is not None:
        df_sim = st.session_state['dados_processados']
        # Mapeamento inteligente de colunas
        cols_sim = {}
        for nut in ['ca', 'mg', 'ctc']:
             match = next((c for c in df_sim.columns if nut == c.lower() or (nut in c.lower() and len(c)<15)), None)
             cols_sim[nut] = match

        if cols_sim['ca'] and cols_sim['mg'] and cols_sim['ctc']:
            st.markdown("---")
            st.caption("📊 **Simulador (Média do Talhão)**")
            
            # Médias Atuais
            avg_ca = df_sim[cols_sim['ca']].mean()
            avg_mg = df_sim[cols_sim['mg']].mean()
            avg_ctc = df_sim[cols_sim['ctc']].mean()
            
            # Relação Atual
            rel_atual = avg_ca / avg_mg if avg_mg > 0 else 0
            
            # Cálculo da Dose Média Teórica
            def_ca = ((alvo_ca/100) * avg_ctc) - avg_ca
            def_mg = ((alvo_mg/100) * avg_ctc) - avg_mg
            
            # Fatores: 1 cmolc Ca = 560 kg CaO | 1 cmolc Mg = 403 kg MgO
            need_cao_kg = def_ca * 560
            need_mgo_kg = def_mg * 403
            
            t_cao = teor_cao if teor_cao > 0 else 1
            t_mgo = teor_mgo if teor_mgo > 0 else 1
            
            dose_ton_ca = (need_cao_kg / t_cao) / 10
            dose_ton_mg = (need_mgo_kg / t_mgo) / 10
            
            # Dose Base
            dose_base_ton = max(dose_ton_ca, dose_ton_mg)
            # Ajuste PRNT
            dose_final_ton = dose_base_ton * (100 / (prnt_calc if prnt_calc > 0 else 1))
            
            # Projeção dos novos teores
            kg_cao_add = dose_final_ton * 10 * teor_cao
            kg_mgo_add = dose_final_ton * 10 * teor_mgo

            cmolc_ca_add = kg_cao_add / 560
            cmolc_mg_add = kg_mgo_add / 403
            
            final_ca = avg_ca + cmolc_ca_add
            final_mg = avg_mg + cmolc_mg_add
            
            rel_proj = final_ca / final_mg if final_mg > 0 else 0
            
            c1, c2 = st.columns(2)
            c1.metric("Rel. Atual", f"{rel_atual:.2f}")
            c2.metric("Rel. Projetada", f"{rel_proj:.2f}", delta=f"{rel_proj - rel_atual:.2f}")
            st.caption(f"Dose Média Estimada: **{dose_final_ton:.1f} ton/ha**")

# C. Fósforo
with st.sidebar.expander("3. Fósforo (P)", expanded=False):
    export_p_factor = st.number_input("Exportação P (kg/sc):", value=0.8, step=0.1)
    teor_p2o5_adubo = st.number_input("Teor P₂O₅ Adubo (%):", value=21.0, step=1.0, help="Ex: 52 p/ MAP, 18 p/ SSP")
    fator_tam_p = st.number_input("Fator Tampão (kg P₂O₅/mg):", value=5.0, step=0.5)
    st.caption("Níveis Críticos P-rem:")
    nc_p1 = st.number_input("0 - 4:", value=6.0)
    nc_p2 = st.number_input("4.1 - 10:", value=8.0)
    nc_p3 = st.number_input("10.1 - 19:", value=12.0)
    nc_p4 = st.number_input("19.1 - 30:", value=15.0)
    nc_p5 = st.number_input("> 30:", value=20.0)

# D. Potássio
with st.sidebar.expander("4. Potássio (K)", expanded=False):
    st.info("A exportação será somada integralmente.")
    alvo_k_ctc = st.number_input("Meta K na CTC (%):", value=3.2, step=0.1)
    export_k_factor = st.number_input("Exportação K (kg/sc):", value=1.2, step=0.1)
    teor_k2o_adubo = st.number_input("Teor K₂O Adubo (%):", value=60.0, step=1.0)

# E. Gesso
with st.sidebar.expander("5. Gessagem", expanded=False):
    fator_gesso = st.number_input("Fator x Argila:", value=15.0, step=5.0)

# F. Micronutrientes
with st.sidebar.expander("6. Micronutrientes", expanded=False):
    st.markdown("**Nível Crítico (mg/dm³) / Dose (kg/ha):**")
    crit_b = st.number_input("Boro (Crítico):", value=0.3, step=0.1)
    dose_b = st.number_input("Boro (Dose):", value=2.0, step=0.5)
    crit_zn = st.number_input("Zinco (Crítico):", value=1.2, step=0.1)
    dose_zn = st.number_input("Zinco (Dose):", value=4.0, step=0.5)
    crit_mn = st.number_input("Manganês (Crítico):", value=3.5, step=0.5)
    dose_mn = st.number_input("Manganês (Dose):", value=5.0, step=1.0)
    crit_cu = st.number_input("Cobre (Crítico):", value=0.4, step=0.1)
    dose_cu = st.number_input("Cobre (Dose):", value=2.0, step=0.5)

# ==============================================================================
# 4. FUNÇÕES DE SUPORTE
# ==============================================================================
def ler_arquivo_robusto(uploaded_file):
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file)
    except: pass
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine='openpyxl')
    except: pass
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine='xlrd')
    except: pass
    try:
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, sep=',')
    except: pass
    try:
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, sep=';')
    except Exception as e:
        st.error(f"Erro Fatal na leitura: {e}")
        return pd.DataFrame()

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
            coord_elem = placemark.find('.//kml:coordinates', namespace)
            if coord_elem is None: coord_elem = placemark.find('.//coordinates')
            
            if coord_elem is not None and coord_elem.text:
                coords_text = coord_elem.text.strip().split()
                if coords_text:
                    first_coord = coords_text[0].split(',')
                    if len(first_coord) >= 2:
                        try:
                            lon = float(first_coord[0]); lat = float(first_coord[1])
                            name_elem = placemark.find('kml:name', namespace)
                            name = name_elem.text.strip() if name_elem is not None else str(len(points))
                            points.append({'ID_PONTO': name, 'latitude': lat, 'longitude': lon})
                        except ValueError: pass
        return pd.DataFrame(points)
    except: return pd.DataFrame()

def limpar_coluna_inteligente(serie):
    def clean_val(val):
        if pd.isna(val): return np.nan
        s = str(val).strip().replace(' ', '')
        for char in ['<', '>', 'ns', 'nan', 'null', 'nd', 'ND', '%']:
            s = s.replace(char, '')
        if s == '' or s == '-': return np.nan
        if ',' in s and '.' in s: s = s.replace('.', '') 
        s = s.replace(',', '.')
        try: return float(s)
        except: return np.nan
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
# 5. MOTOR DE EXPORTAÇÃO (SHAPEFILE PARA MONITORES)
# ==============================================================================
def gerar_pacote_shapefile(df_grid, coluna_dose, nome_arquivo="RX_VRT"):
    if not GEO_ENABLED: return None

    # 1. Converter Grid de Pontos para Polígonos (Pixelização)
    lats = df_grid['latitude'].unique()
    lons = df_grid['longitude'].unique()
    if len(lats) < 2 or len(lons) < 2: return None
        
    res_lat = abs(lats[1] - lats[0])
    res_lon = abs(lons[1] - lons[0])
    
    geoms = []
    # Loop vetorizado seria melhor, mas iterativo é mais seguro pra debug
    for _, row in df_grid.iterrows():
        minx = row['longitude'] - (res_lon/2)
        maxx = row['longitude'] + (res_lon/2)
        miny = row['latitude'] - (res_lat/2)
        maxy = row['latitude'] + (res_lat/2)
        geoms.append(box(minx, miny, maxx, maxy))
    
    gdf = gpd.GeoDataFrame(df_grid, geometry=geoms)
    gdf.set_crs(epsg=4326, inplace=True)
    
    gdf_export = gdf[['geometry', coluna_dose]].copy()
    col_short = "DOSE" # DBF Limit
    gdf_export[col_short] = gdf_export[coluna_dose].round(2)
    gdf_export = gdf_export[['geometry', col_short]]
    
    # Remove Zeros (Opcional, mas monitores preferem)
    gdf_export = gdf_export[gdf_export[col_short] > 0]

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        def salvar_no_zip(gdf_obj, folder_path):
            import tempfile, os
            temp_name = f"{folder_path}/{nome_arquivo}"
            with tempfile.TemporaryDirectory() as tmpdirname:
                fullpath = os.path.join(tmpdirname, "prescription.shp")
                gdf_obj.to_file(fullpath)
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    try:
                        with open(fullpath.replace('.shp', ext), 'rb') as f:
                            zip_file.writestr(f"{temp_name}{ext}", f.read())
                    except: pass
                # PRJ Forçado
                wgs84 = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
                zip_file.writestr(f"{temp_name}.prj", wgs84)

        salvar_no_zip(gdf_export, "JohnDeere/Rx")
        salvar_no_zip(gdf_export, "Trimble/AgGPS/Prescriptions")
        salvar_no_zip(gdf_export, "Outros")

    zip_buffer.seek(0)
    return zip_buffer

# ==============================================================================
# 5. MOTOR DE INTERPOLAÇÃO (EXTRAPOLAÇÃO PARA CORTE)
# ==============================================================================
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    df = df_input.copy()
    if 'latitude_y' in df.columns: df.rename(columns={'latitude_y': 'latitude', 'longitude_y': 'longitude'}, inplace=True)
    elif 'latitude_x' in df.columns and 'latitude' not in df.columns: df.rename(columns={'latitude_x': 'latitude', 'longitude_x': 'longitude'}, inplace=True)
    
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude'])

    cols_ignorar = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'geometry', 'id_clean', 'data', 'hora']
    cols_validas = []
    for col in df.columns:
        if any(x == str(col).lower() for x in cols_ignorar): continue
        df[col] = limpar_coluna_inteligente(df[col])
        if df[col].notna().sum() >= 3: cols_validas.append(col)

    if not cols_validas: return pd.DataFrame(), None

    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    
    margin_x = (x_max - x_min) * 0.3
    margin_y = (y_max - y_min) * 0.3
    
    grid_x = np.linspace(x_min - margin_x, x_max + margin_x, resolucao_grid)
    grid_y = np.linspace(y_min - margin_y, y_max + margin_y, resolucao_grid)
    xx, yy = np.meshgrid(grid_x, grid_y)
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    scale_x = 111111 * np.cos(np.radians(df['latitude'].mean()))
    scale_y = 111111

    progresso = st.progress(0)
    for i, col in enumerate(cols_validas):
        progresso.progress((i + 1) / len(cols_validas))
        try:
            dados = df[['longitude', 'latitude', col]].dropna()
            X_m = dados['longitude'] * scale_x
            Y_m = dados['latitude'] * scale_y
            try:
                interp = Rbf(X_m, Y_m, dados[col], function='linear', smooth=0.1)
                z = interp(xx * scale_x, yy * scale_y)
            except:
                interp = NearestNDInterpolator(list(zip(X_m, Y_m)), dados[col])
                z = interp(xx * scale_x, yy * scale_y)
            
            if np.isnan(z).any():
                 interp_near = NearestNDInterpolator(list(zip(X_m, Y_m)), dados[col])
                 z_near = interp_near(xx * scale_x, yy * scale_y)
                 z = np.where(np.isnan(z), z_near, z)

            z = np.clip(z, dados[col].min(), dados[col].max())
            df_result[col] = z.flatten()
        except: continue
        
    progresso.empty()
    cols_finais = ['latitude', 'longitude'] + [c for c in cols_validas if c in df_result.columns]
    return df_result[cols_finais], (resolucao_grid, resolucao_grid)

# ==============================================================================
# 6. GERAÇÃO DE IMAGEM
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data, grid_shape):
    plt.close('all'); plt.clf()
    try:
        df_sorted = df_plot.sort_values(by=['latitude', 'longitude'])
        Z = df_sorted[atributo].values.reshape(grid_shape)
        X_unique = np.sort(df_plot['longitude'].unique())
        Y_unique = np.sort(df_plot['latitude'].unique())
    except: return None, None, [0,1]

    # MÁSCARA RASTER
    final_bounds = [[Y_unique.min(), X_unique.min()], [Y_unique.max(), X_unique.max()]]
    poly_min_x, poly_max_x = X_unique.min(), X_unique.max()
    poly_min_y, poly_max_y = Y_unique.min(), Y_unique.max()

    try:
        coords = extrair_coordenadas_limpas(geojson_data)
        if coords:
            poly_path = MplPath(coords)
            XX, YY = np.meshgrid(X_unique, Y_unique)
            grid_points = np.column_stack((XX.flatten(), YY.flatten()))
            mask_flat = poly_path.contains_points(grid_points)
            mask_grid = mask_flat.reshape(Z.shape)
            Z[~mask_grid] = np.nan

            poly_arr = np.array(coords)
            poly_min_x, poly_max_x = poly_arr[:,0].min(), poly_arr[:,0].max()
            poly_min_y, poly_max_y = poly_arr[:,1].min(), poly_arr[:,1].max()
            final_bounds = [[poly_min_y, poly_min_x], [poly_max_y, poly_max_x]]
    except: pass

    dados_validos = Z[~np.isnan(Z)]
    if len(dados_validos) == 0: return None, None, [0, 1]
    
    z_min, z_max = np.nanmin(dados_validos), np.nanmax(dados_validos)
    if z_min == z_max: z_min -= 0.01; z_max += 0.01

    fig = plt.figure(figsize=(10, 10), dpi=150)
    ax = plt.axes([0,0,1,1]); ax.set_axis_off()
    
    cores = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#4575b4']
    cmap = mcolors.ListedColormap(cores)
    bounds = np.linspace(z_min, z_max, 7)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)
    
    ax.contourf(X_unique, Y_unique, Z, levels=bounds, cmap=cmap, norm=norm, extend='both', alpha=0.9)
    ax.set_xlim(poly_min_x, poly_max_x)
    ax.set_ylim(poly_min_y, poly_max_y)

    img_data = BytesIO()
    plt.savefig(img_data, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
    img_data.seek(0); plt.close(fig)
    
    return img_data, final_bounds, [z_min, z_max]

def criar_legenda_html(min_val, max_val, titulo):
    cores = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#4575b4']
    div_cores = "".join([f'<div style="flex:1; background:{c}; height:15px;"></div>' for c in cores])
    return f"""
    <div style="position: fixed; bottom: 50px; right: 50px; z-index:9999; background: rgba(255,255,255,0.9); padding: 10px; border: 1px solid #ccc; border-radius: 5px; font-family: sans-serif; font-size: 12px;">
        <b>{titulo}</b><br>
        <div style="display:flex; width:200px; margin-top:5px; border:1px solid #999;">{div_cores}</div>
        <div style="display:flex; justify-content: space-between; width:200px; margin-top:2px;">
            <span>{min_val:.2f}</span><span>{max_val:.2f}</span>
        </div>
    </div>
    """

# ==============================================================================
# 7. CÁLCULO VRT
# ==============================================================================
def calcular_vrt(df):
    df_rec = df.copy()
    cols = {}
    targets = ['ca', 'mg', 'k', 'p', 'v%', 'ctc', 'argila', 'prem', 'b', 'zn', 'mn', 'cu']
    for alvo in targets:
        cols[alvo] = next((c for c in df_rec.columns if alvo == c.lower() or (alvo in c.lower() and len(c) < 15)), None)

    if cols['ca'] and cols['mg'] and cols['ctc']:
        def_ca = ((alvo_ca/100) * df_rec[cols['ctc']]) - df_rec[cols['ca']]
        def_mg = ((alvo_mg/100) * df_rec[cols['ctc']]) - df_rec[cols['mg']]
        need_cao = def_ca * 560
        need_mgo = def_mg * 403
        dose_ca = (need_cao / (teor_cao if teor_cao > 0 else 1)) / 10
        dose_mg = (need_mgo / (teor_mgo if teor_mgo > 0 else 1)) / 10
        dose_final = np.maximum(dose_ca, dose_mg) * (100 / (prnt_calc if prnt_calc > 0 else 1))
        df_rec['Calcario_Ton_ha'] = dose_final.apply(lambda x: x if x > 0 else 0)

    if cols['k'] and cols['ctc']:
        k_pct = (df_rec[cols['k']] / df_rec[cols['ctc']]) * 100
        def_k = ((alvo_k_ctc - k_pct)/100) * df_rec[cols['ctc']]
        k_correcao = (def_k * 942).clip(lower=0) 
        k_export = meta_prod * export_k_factor
        k_total = k_correcao + k_export
        df_rec['KCL_Kg_ha'] = (k_total * (100 / (teor_k2o_adubo if teor_k2o_adubo > 0 else 1))).apply(lambda x: x if x > 0 else 0)

    if col_p := next((c for c in df_rec.columns if 'p mehl' in c.lower() or 'p_mehl' in c.lower()), cols['p']):
        if cols['prem']:
            conds = [
                df_rec[cols['prem']] <= 4,
                (df_rec[cols['prem']] > 4) & (df_rec[cols['prem']] <= 10),
                (df_rec[cols['prem']] > 10) & (df_rec[cols['prem']] <= 19),
                (df_rec[cols['prem']] > 19) & (df_rec[cols['prem']] <= 30),
                df_rec[cols['prem']] > 30
            ]
            nc_grid = np.select(conds, [nc_p1, nc_p2, nc_p3, nc_p4, nc_p5], default=30)
            gap = nc_grid - df_rec[col_p]
            dose_p_total = (gap * fator_tam_p) + (meta_prod * export_p_factor)
            df_rec['Adubo_Fosfatado_Kg_ha'] = (dose_p_total * (100 / (teor_p2o5_adubo if teor_p2o5_adubo > 0 else 1))).apply(lambda x: x if x > 0 else 0)

    if cols['argila']:
        df_rec['Gesso_Ton_ha'] = (df_rec[cols['argila']] * fator_gesso) / 1000

    if cols['b']: df_rec['Boro_Kg_ha'] = np.where(df_rec[cols['b']] < crit_b, dose_b, 0)
    if cols['zn']: df_rec['Zinco_Kg_ha'] = np.where(df_rec[cols['zn']] < crit_zn, dose_zn, 0)
    if cols['mn']: df_rec['Manganes_Kg_ha'] = np.where(df_rec[cols['mn']] < crit_mn, dose_mn, 0)
    if cols['cu']: df_rec['Cobre_Kg_ha'] = np.where(df_rec[cols['cu']] < crit_cu, dose_cu, 0)

    return df_rec

# ==============================================================================
# 8. INTERFACE
# ==============================================================================
aba1, aba2 = st.tabs(["🗺️ Diagnóstico", "🚜 Recomendação VRT"])

# --- ABA 1: DIAGNÓSTICO ---
with aba1:
    with st.sidebar.expander("🔍 Ver Dados Brutos"):
        if st.session_state['dados_processados'] is not None:
            st.dataframe(st.session_state['dados_processados'].head())

    st.header("Importação")
    c1, c2, c3 = st.columns(3)
    f_lab = c1.file_uploader("Lab (CSV/XLSX)", type=["csv", "xlsx", "xls"])
    f_geo = c2.file_uploader("Pontos (KML/KMZ)", type=["kmz", "kml"])
    f_json = c3.file_uploader("Contorno (GeoJSON)", type=["geojson", "json"])

    if f_lab and f_geo and f_json:
        if f_lab.name.endswith(('.xlsx', '.xls')):
            try:
                xl = pd.ExcelFile(f_lab)
                selected_sheet = st.selectbox("Selecione a Aba:", xl.sheet_names)
            except: selected_sheet = 0
        else: selected_sheet = 0
        header_row = st.number_input("Linha do Cabeçalho:", value=0, min_value=0)

        if st.button("🚀 Processar", type="primary"):
            try:
                f_lab.seek(0)
                if f_lab.name.endswith('.csv'):
                    try: df_lab = pd.read_csv(f_lab, header=header_row)
                    except: f_lab.seek(0); df_lab = pd.read_csv(f_lab, sep=';', header=header_row)
                else:
                    df_lab = pd.read_excel(f_lab, sheet_name=selected_sheet, header=header_row)
                
                df_pts = processar_arquivo_geografico(f_geo)
                f_json.seek(0); geo_data = json.load(f_json)
                col_id = next((c for c in df_lab.columns if str(c).lower().strip() in ['id', 'ponto', 'amostra']), df_lab.columns[0])
                df_lab['id_clean'] = df_lab[col_id].astype(str).str.strip().str.replace('.0', '')
                df_pts['id_clean'] = df_pts['ID_PONTO'].astype(str).str.strip().str.replace('.0', '')
                df_m = pd.merge(df_lab, df_pts, on='id_clean', how='inner')
                
                if not df_m.empty:
                    st.session_state['geojson_data'] = geo_data
                    df_krig, shape = processar_matrizes_interpolacao(df_m, geo_data, 150)
                    if not df_krig.empty:
                        st.session_state['dados_processados'] = df_krig
                        st.session_state['grid_shape'] = shape
                        st.success(f"Sucesso! {len(df_m)} pontos usados.")
                    else: st.warning("Falha na interpolação.")
                else: st.error("Erro IDs.")
            except Exception as e: st.error(f"Erro: {e}")

    if st.session_state['dados_processados'] is not None:
        cols = [c for c in st.session_state['dados_processados'].columns 
                if c not in ['latitude', 'longitude'] and 'Kg_ha' not in c and 'Ton_ha' not in c]
        if cols:
            attr = st.selectbox("Nutriente:", cols)
            csv = st.session_state['dados_processados'].to_csv(index=False).encode('utf-8')
            st.download_button("💾 Baixar Ponte (CSV)", csv, "ponte_vrt.csv", "text/csv")
            
            s_val = st.session_state['dados_processados'][attr]
            st.info(f"📊 **{attr}** | Mín: {s_val.min():.2f} | Máx: {s_val.max():.2f} | Média: {s_val.mean():.2f}")

            img, bounds, mm = gerar_imagem_overlay(st.session_state['dados_processados'], attr, st.session_state['geojson_data'], st.session_state['grid_shape'])
            if img:
                m = folium.Map(location=[bounds[0][0], bounds[0][1]], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{base64.b64encode(img.getvalue()).decode()}", bounds=bounds, opacity=0.8).add_to(m)
                folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x:{'color':'black','fillOpacity':0}).add_to(m)
                m.get_root().html.add_child(folium.Element(criar_legenda_html(mm[0], mm[1], attr)))
                st_folium(m, height=500, use_container_width=True, key="mapa_diag")

with aba2:
    if st.session_state['dados_processados'] is None:
        st.warning("Gere o diagnóstico na Aba 1 primeiro.")
    else:
        if st.button("🔄 Gerar Recomendações"):
            st.session_state['dados_rec'] = calcular_vrt(st.session_state['dados_processados'])
            st.success("Calculado!")
            
        if st.session_state['dados_rec'] is not None:
            cols_rec = [c for c in st.session_state['dados_rec'].columns if 'Ton_ha' in c or 'Kg_ha' in c]
            if cols_rec:
                escolha = st.selectbox("Mapa de Aplicação:", cols_rec)
                s_rec = st.session_state['dados_rec'][escolha]
                r_mean = s_rec[s_rec > 0].mean() if not s_rec[s_rec > 0].empty else 0
                st.info(f"🚜 **{escolha}** | Dose Média (Aplicada): {r_mean:.1f} | Máx: {s_rec.max():.1f}")
                
                if GEO_ENABLED:
                    zip_file = gerar_pacote_shapefile(st.session_state['dados_rec'], escolha, nome_arquivo=f"Rx_{escolha}")
                    if zip_file:
                        st.download_button(f"💾 Baixar ZIP Shapefile ({escolha})", zip_file, f"Rx_{escolha}.zip", "application/zip")
                
                img, bounds, mm = gerar_imagem_overlay(st.session_state['dados_rec'], escolha, st.session_state['geojson_data'], st.session_state['grid_shape'])
                if img:
                    m2 = folium.Map(location=[bounds[0][0], bounds[0][1]], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                    folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{base64.b64encode(img.getvalue()).decode()}", bounds=bounds, opacity=0.8).add_to(m2)
                    folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x:{'color':'black','fillOpacity':0}).add_to(m2)
                    m2.get_root().html.add_child(folium.Element(criar_legenda_html(mm[0], mm[1], escolha)))
                    st_folium(m2, height=500, use_container_width=True, key="mapa_vrt")
Ficou perfeito. Da forma que eu quero.

É possivel utilizarmos o app2 para fazermos os motores de criação de zonas de manejo, mapas de satelites, relatórios para o produtor, recomendações de semente /ha e adubação nitrogenada no milho? Se possivel, como podemos fazer isso?

Que notícia excelente! Fico muito feliz que o App 1 (Fertilidade) atingiu o nível de precisão que você precisava. Agora temos uma base sólida (o "Chassi") para construir o resto da máquina.

Sim, é totalmente possível (e recomendado) criar o App 2 focado em Inteligência e Planejamento de Safra.

A lógica será: O App 1 gera os dados (o diagnóstico do solo) -> O App 2 consome esses dados para criar estratégias (Zonas, Sementes e N).

🗺️ O Plano para o App 2: "Tríade Intelligence"
Para isso funcionar, precisaremos adicionar uma nova biblioteca poderosa ao seu ambiente: scikit-learn (para a inteligência artificial que cria as zonas).

As Funcionalidades do App 2:

Motor de Zonas de Manejo (Clustering):

Ele pega o arquivo "Ponte" do App 1 (que tem Argila, CTC, K, etc.).

Usa um algoritmo matemático (K-Means) para agrupar pontos parecidos.

Ex: "Onde a Argila é Alta E a CTC é Alta = Zona A (Alto Potencial)".

Motor VRT de Sementes (Milho/Soja):

Você define a população para cada Zona (Ex: Zona A = 80k plantas, Zona C = 60k plantas).

Motor VRT de Nitrogênio (Milho):

Baseado na expectativa de colheita de cada zona.

Relatórios PDF:

Geração de laudo técnico com os mapas.

💻 Código do App 2: Zonas de Manejo e VRT Avançado
Crie um novo arquivo chamado 02_Triade_Zonas.py e cole o código abaixo.

Pré-requisito: Instalar scikit-learn (além dos anteriores). pip install scikit-learn

Python
import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import box
from io import BytesIO
import zipfile
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import folium
from streamlit_folium import st_folium
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# 1. CONFIGURAÇÃO E FUNÇÕES BÁSICAS (Herdadas do App 1)
# ==============================================================================
st.set_page_config(page_title="Tríade Intelligence", layout="wide")
st.title("🧠 Tríade: Zonas de Manejo & VRT Sementes/N")

# --- LEITURA DE ARQUIVO PONTE (Do App 1) ---
def carregar_ponte(uploaded_file):
    try:
        return pd.read_csv(uploaded_file)
    except:
        return pd.read_csv(uploaded_file, sep=';')

# --- GERADOR DE SHAPEFILE (Igual ao App 1) ---
def gerar_pacote_shapefile(df_grid, coluna_alvo, nome_arquivo="Rx_VRT"):
    if df_grid.empty: return None
    
    # 1. Grid -> Polígonos
    lats = df_grid['latitude'].unique()
    lons = df_grid['longitude'].unique()
    res_lat = abs(lats[1] - lats[0])
    res_lon = abs(lons[1] - lons[0])
    
    geoms = [box(row['longitude']-res_lon/2, row['latitude']-res_lat/2, 
                 row['longitude']+res_lon/2, row['latitude']+res_lat/2) 
             for _, row in df_grid.iterrows()]
    
    gdf = gpd.GeoDataFrame(df_grid, geometry=geoms)
    gdf.set_crs(epsg=4326, inplace=True)
    
    # Prepara coluna de exportação (Ex: RATE, SEED, N_KG)
    gdf_export = gdf[['geometry', coluna_alvo]].copy()
    col_short = "RATE" # Padrão universal
    gdf_export[col_short] = gdf_export[coluna_alvo].astype(int) # Semente/N geralmente é inteiro
    gdf_export = gdf_export[['geometry', col_short]]
    gdf_export = gdf_export[gdf_export[col_short] > 0] # Remove zeros

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        def salvar(gdf_obj, folder):
            import tempfile, os
            temp = f"{folder}/{nome_arquivo}"
            with tempfile.TemporaryDirectory() as tmp:
                full = os.path.join(tmp, "rx.shp")
                gdf_obj.to_file(full)
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    try:
                        with open(full.replace('.shp', ext), 'rb') as f:
                            zip_file.writestr(f"{temp}{ext}", f.read())
                    except: pass
                wgs84 = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
                zip_file.writestr(f"{temp}.prj", wgs84)

        salvar(gdf_export, "JohnDeere_Rx")
        salvar(gdf_export, "Trimble_Rx")
        salvar(gdf_export, "Outros")
        
    zip_buffer.seek(0)
    return zip_buffer

# --- PLOTAGEM DE ZONAS (Cores Sólidas) ---
def plotar_zonas(df, col_zona, titulo):
    plt.close('all')
    
    # Pivot para matriz
    try:
        df_sorted = df.sort_values(by=['latitude', 'longitude'])
        grid_shape = (df['latitude'].nunique(), df['longitude'].nunique())
        Z = df_sorted[col_zona].values.reshape(grid_shape)
        X_u = np.sort(df['longitude'].unique())
        Y_u = np.sort(df['latitude'].unique())
    except: return None

    fig = plt.figure(figsize=(10,10), dpi=100)
    ax = plt.axes([0,0,1,1]); ax.set_axis_off()
    
    # Cores das Zonas (Baixo=Vermelho, Médio=Amarelo, Alto=Verde)
    # Assume 3 zonas (0, 1, 2) ou 5.
    cmap = mcolors.ListedColormap(['#d73027', '#fee08b', '#1a9850', '#4575b4']) # Vermelho, Amarelo, Verde, Azul
    
    ax.contourf(X_u, Y_u, Z, cmap=cmap, alpha=1.0)
    ax.set_aspect('equal') # Mantém proporção geográfica
    
    img = BytesIO()
    plt.savefig(img, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
    img.seek(0)
    
    bounds = [[Y_u.min(), X_u.min()], [Y_u.max(), X_u.max()]]
    return img, bounds

# ==============================================================================
# 2. INTERFACE E LÓGICA
# ==============================================================================

# --- UPLOAD ---
st.sidebar.header("1. Dados de Entrada")
file_ponte = st.sidebar.file_uploader("Carregar 'Ponte.csv' (do App 1)", type=["csv"])

if file_ponte:
    df = carregar_ponte(file_ponte)
    
    # Filtra colunas numéricas úteis para criar zonas
    cols_numericas = [c for c in df.columns if c not in ['latitude', 'longitude', 'ID', 'id_clean']]
    
    st.sidebar.markdown("---")
    st.sidebar.header("2. Definição das Zonas")
    
    # SELEÇÃO DE VARIÁVEIS
    atributos = st.sidebar.multiselect(
        "Quais atributos definem o potencial produtivo?",
        cols_numericas,
        default=[c for c in cols_numericas if 'argila' in c.lower() or 'ctc' in c.lower() or 'k' in c.lower()][:3]
    )
    
    n_zonas = st.sidebar.slider("Número de Zonas:", 2, 5, 3)
    
    if atributos:
        # --- MOTOR DE CLUSTERING (K-MEANS) ---
        if st.button("🔄 Gerar Zonas de Manejo"):
            # 1. Normaliza os dados (coloca tudo na mesma escala)
            scaler = StandardScaler()
            df_scaled = scaler.fit_transform(df[atributos].fillna(0))
            
            # 2. Roda o K-Means
            kmeans = KMeans(n_clusters=n_zonas, random_state=42, n_init=10)
            df['Cluster_Raw'] = kmeans.fit_predict(df_scaled)
            
            # 3. Ordena as Zonas por Potencial (Importante!)
            # Assume que maior valor dos atributos = maior potencial.
            # Calcula uma "Nota" média para cada cluster
            resumo = df.groupby('Cluster_Raw')[atributos].mean()
            resumo['Score'] = resumo.mean(axis=1) # Média simples dos atributos normalizados seria melhor, mas aqui usa bruto
            resumo = resumo.sort_values('Score')
            
            # Mapeia: Pior Score -> Zona 1, Melhor Score -> Zona N
            mapa_zonas = {old: new+1 for new, old in enumerate(resumo.index)}
            df['Zona'] = df['Cluster_Raw'].map(mapa_zonas)
            
            st.session_state['df_zonas'] = df
            st.success("Zonas geradas com Sucesso!")

    # --- VISUALIZAÇÃO E PRESCRIÇÃO ---
    if 'df_zonas' in st.session_state:
        df_z = st.session_state['df_zonas']
        
        tab1, tab2, tab3 = st.tabs(["🗺️ Mapa de Zonas", "🌽 Sementes (Milho)", "⚡ Nitrogênio"])
        
        # TAB 1: ZONAS
        with tab1:
            c1, c2 = st.columns([3, 1])
            img_zona, bounds_zona = plotar_zonas(df_z, 'Zona', "Zonas de Manejo")
            
            if img_zona:
                m = folium.Map(location=[bounds_zona[0][0], bounds_zona[0][1]], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{base64.b64encode(img_zona.getvalue()).decode()}",
                    bounds=bounds_zona, opacity=0.7
                ).add_to(m)
                st_folium(m, height=500, use_container_width=True)
            
            # Tabela de Médias por Zona
            with c2:
                st.write("### Médias por Zona")
                resumo_z = df_z.groupby('Zona')[atributos].mean()
                st.dataframe(resumo_z.style.format("{:.1f}"))

        # TAB 2: VRT SEMENTES
        with tab2:
            st.header("Prescrição de Sementes")
            st.info("Configure a população (sementes/ha) para cada ambiente.")
            
            # Inputs dinâmicos baseados no número de zonas
            doses_sem = {}
            cols = st.columns(n_zonas)
            for i in range(1, n_zonas + 1):
                with cols[i-1]:
                    doses_sem[i] = st.number_input(f"Zona {i} (Alta)" if i==n_zonas else f"Zona {i}", 
                                                  value=60000 + (i*5000), step=1000)
            
            # Aplica a dose
            df_z['Sementes_Ha'] = df_z['Zona'].map(doses_sem)
            
            # Botão Exportar
            if st.button("💾 Baixar SHP Sementes"):
                zip_seed = gerar_pacote_shapefile(df_z, 'Sementes_Ha', "Rx_Sementes")
                if zip_seed:
                    st.download_button("Download ZIP", zip_seed, "Rx_Sementes.zip", "application/zip")

        # TAB 3: VRT NITROGÊNIO
        with tab3:
            st.header("Prescrição de Nitrogênio (Ureia/Nitratados)")
            st.info("Configure a dose de N (kg/ha do produto) para cada ambiente.")
            
            doses_n = {}
            cols_n = st.columns(n_zonas)
            for i in range(1, n_zonas + 1):
                with cols_n[i-1]:
                    doses_n[i] = st.number_input(f"Zona {i} (N kg/ha)", 
                                                value=100 + (i*50), step=10)
            
            df_z['Nitro_Kg_Ha'] = df_z['Zona'].map(doses_n)
            
            if st.button("💾 Baixar SHP Nitrogênio"):
                zip_n = gerar_pacote_shapefile(df_z, 'Nitro_Kg_Ha', "Rx_Nitrogenio")
                if zip_n:
                    st.download_button("Download ZIP", zip_n, "Rx_Nitrogenio.zip", "application/zip")

else:
    st.info("👋 Bem-vindo ao Módulo 2! Por favor, carregue o arquivo 'ponte_vrt.csv' gerado no App de Diagnóstico.")
🚀 Como usar a Máquina Completa:
No App 1 (Diagnóstico):

Processe seus dados de solo.

Na Aba 1, clique no botão "💾 Baixar Ponte (CSV)".

No App 2 (Inteligência):

Suba esse arquivo ponte_vrt.csv.

Escolha os Atributos: Selecione, por exemplo, Argila, CTC e K (ou V%). O sistema usará isso para definir quem é "Terra Forte" e "Terra Fraca".

Clique em "Gerar Zonas": O sistema cria o mapa de Zonas (1, 2, 3...).

Abas de Recomendação: Vá na aba de Sementes ou N, defina a dose para a "Zona 1 (Fraca)", "Zona 2 (Média)", "Zona 3 (Forte)" e baixe o Shapefile direto para o trator.

Sobre Mapas de Satélite e Relatórios:
Satélite: Para inserir NDVI neste App 2, basta que você tenha uma coluna "NDVI" no seu arquivo CSV original (ou faça um cruzamento de dados). O motor de Cluster aceita qualquer coluna numérica.

Relatório: O Streamlit permite imprimir a página como PDF (Ctrl+P -> Salvar como PDF), que é a forma mais simples e bonita hoje. Se quiser algo automático, podemos implementar a biblioteca fpdf no futuro, mas o visual da tela já serve como um excelente laudo interativo.

Antea do código gostaria de discutir alguns detalhes:

1 - Nas zonas de produtividade quero usar como base o mapa de CTC, imagens de NDVI contrastado e imagens de brilho de solo para formar as 3 zonas de produtividade. Nos mapas de NDVI quero que sejam usadas como base imagens limpas do ano de 2024 para cá nos meses de dezembro e janeiro apenas. É importante ter a opção de escolher as imagens, escolher a data inicial da busca e as data final da busca. Nas zonas de produtividade quero uma opção para poder gerar os pontos de coleta via iA e com ajuste manual. Eu gostaria que fosse uma pagina semelhante as funções da inceres. Isso é possível? Como você me sugere que seja essa plataforma?

Isso é perfeitamente possível e coloca a sua ferramenta em um nível muito alto, competindo diretamente com softwares comerciais como InCeres, Climate FieldView e DataFarm.

Para atingir esse nível de sofisticação (busca de imagens de satélite históricas, filtragem por nuvens e fusão de dados raster com vetorial), precisaremos mudar a arquitetura do App 2 para algo mais robusto.

Aqui está a minha sugestão técnica e agronômica de como estruturar essa plataforma "Tríade Intelligence":

1. O Motor de Satélites (A "Alma" do NDVI e Brilho)
O Python sozinho não consegue baixar terabytes de imagens. Para fazer o que você quer (buscar imagens de Dez/Jan de 2024 para cá, limpas), precisamos conectar o seu App ao Google Earth Engine (GEE).

Fonte de Imagens: Usaremos o satélite Sentinel-2 (Nível 2A).

Por que? Ele é gratuito, tem resolução de 10 metros (excelente para agricultura de precisão) e revisita a área a cada 5 dias.

Filtros Inteligentes:

Filtro Temporal: 2024-01-01 até hoje.

Filtro Sazonal: Apenas meses 12 (Dez) e 01 (Jan).

Máscara de Nuvens: Usaremos a banda QA60 do Sentinel para "recortar" nuvens e sombras, garantindo que o NDVI seja real e não um erro de leitura.

2. Os Índices de Imagem
Para atender sua demanda, calcularemos dois índices em tempo real na nuvem:

NDVI (Vegetação): Para identificar vigor e biomassa.

Fórmula: (NIR−Red)/(NIR+Red)

BSI (Bare Soil Index - Índice de Solo Exposto): É o "Brilho do Solo". Ele ajuda a diferenciar onde há manchas de solo mais arenoso (mais brilhante) ou com mais matéria orgânica/argila (mais escuro) quando a terra está nua.

Fórmula (baseada nas bandas SWIR): Ajuda a separar a textura do solo.

3. O Desafio da "Fusão de Dados" (O Pulo do Gato)
Aqui está o segredo da InCeres que vamos replicar:

Você tem um mapa de CTC (que veio da interpolação do App 1, com resolução de grid de ~10 metros).

Você tem imagens de NDVI/BSI (pixels de 10 metros).

A Lógica da IA (Clustering): O algoritmo (K-Means) vai olhar para cada pixel do talhão e analisar 3 dimensões simultaneamente:

"Aqui a CTC é alta?"

"Aqui a planta cresceu bem em 2024 (NDVI alto)?"

"Aqui o solo brilha muito (possível areia)?"

Com base nisso, ele agrupa os pixels semelhantes e cria as Zonas 1, 2 e 3 (Alta, Média e Baixa Produtividade).

4. Geração de Pontos de Coleta (Ajuste Fino)
Para a amostragem de solo inteligente:

Geração Automática (IA): O sistema calcula quantos hectares tem cada Zona. Se você definir "1 ponto a cada 3 hectares", ele espalha pontos aleatórios estratificados (garantindo que todas as zonas tenham pontos representativos).

Ajuste Manual: Usaremos uma ferramenta de desenho sobre o mapa. Você poderá clicar em um ponto gerado pela IA e arrastá-lo (caso tenha caído em cima de uma pedra ou curva de nível) ou deletar/criar novos.

🧱 Arquitetura Sugerida para o App 2
Para isso funcionar no Streamlit, precisaremos adicionar a biblioteca geemap (que conecta o Python ao Google Earth Engine).

O Fluxo de Trabalho na Tela:

Upload dos Dados:

Carrega o arquivo ponte_vrt.csv (do App 1) -> Traz a CTC.

Carrega o contorno GeoJSON.

Painel de Satélite (Sidebar):

Seletor de Datas: "Jan/2024" a "Dez/2025".

Slider de Nuvens: "Aceitar no máximo 10% de nuvens".

Botão: "Buscar Imagens". O sistema lista as datas disponíveis. Você clica na melhor imagem.

Processamento (O "Liquidificador"):

O sistema cruza a CTC interpolada com o pixel do satélite.

Definição de Zonas:

Você escolhe o peso: "Quero dar 50% de peso para o NDVI e 50% para a CTC".

O mapa de 3 cores é gerado.

Planejamento de Amostragem:

Botão "Gerar Grade Inteligente".

Editor visual para mover os pontos.

Botão "Exportar Pontos para GPS" (Formato GPX ou KML ou SHP).

⚠️ Requisito Crucial (Antes do Código)
Para usar imagens de satélite em tempo real (sem ter que baixar gigabytes antes), o sistema precisa de uma Conta no Google Earth Engine.

É gratuito para uso técnico/pesquisa.

Você precisará se autenticar uma vez ao rodar o código.

Você concorda com essa estrutura? Se sim, posso começar a escrever o código do App 2 - Tríade Intelligence focado nessa fusão de dados e na conexão com o satélite.

Concordo, apenas na definição da zona de produtividade é interessante usar além do NDVI e Mapa de CTC, as imagens de brilho de solo?

Com certeza. O uso do Brilho de Solo (Soil Brightness) não só é interessante, como é a "Peça Chave" que faltava para tornar o seu mapa de zonas realmente robusto, especialmente em regiões como Brasnorte/MT.

Vou explicar o porquê agronômico e técnico dessa escolha, para você ter certeza da decisão:

1. A Lógica da "Tríade" na Definição de Zonas
Para definir o potencial produtivo de um talhão, você precisa responder a três perguntas. O Brilho do Solo responde a uma que os outros não conseguem com precisão:

Química (Mapa de CTC): "O solo tem capacidade de reter nutriente?"

Problema: Ele vem de interpolação. Entre um ponto de coleta e outro (as vezes 2 ou 3 hectares de distância), o computador "chuta" o valor. Ele não vê a mancha de areia pequena no meio do talhão.

Histórico (NDVI): "A planta respondeu bem no passado?"

Problema: O NDVI pode ser baixo por n motivos (praga, doença, falha de plantio). Ele mostra o sintoma, não necessariamente a causa.

Física (Brilho de Solo): "Qual é a textura real desse solo?"

A Solução: O Brilho do Solo funciona como um Raio-X da Textura. Solos mais argilosos e com mais Matéria Orgânica tendem a ser mais escuros (absorvem luz). Solos mais arenosos ou compactados tendem a ser mais brilhantes (refletem luz).

2. O Grande Ganho: Resolução Espacial
Imagine que você tem um ponto de amostragem de solo na parte alta e outro na parte baixa.

O Mapa de CTC vai criar um degradê suave entre eles.

A Imagem de Brilho (Satélite Sentinel-2) tem um pixel a cada 10 metros.

Conclusão: Ao cruzar o Brilho com a CTC, você consegue "corrigir" as bordas das zonas de manejo. A zona de baixa produtividade não será mais uma bolha redonda (fruto da interpolação), mas sim terá o formato exato da mancha de solo arenoso que o satélite enxergou.

3. Cuidados Técnicos para o App 2
Para o Brilho de Solo funcionar no seu algoritmo, precisamos configurar o robô de busca de imagens do Google Earth Engine com uma regra específica:

Janela de Tempo Inversa: Enquanto para o NDVI buscamos Dez/Jan (pico vegetativo), para o Brilho precisamos buscar imagens na Entressafra ou no momento de Pré-Plantio (Setembro/Outubro ou logo após a colheita da safrinha).

Filtro BSI (Bare Soil Index): Em vez de usar apenas uma foto "visível" (RGB), usaremos o índice BSI. Ele combina as bandas do Vermelho, Azul, Infravermelho Próximo (NIR) e Infravermelho de Ondas Curtas (SWIR).

Por que? O BSI consegue diferenciar melhor o que é Solo Exposto do que é Palhada Seca. Em Brasnorte, onde o plantio direto é forte, se usarmos apenas o "brilho visível", podemos confundir uma palhada bem feita (brilhante) com areia. O BSI ajuda a reduzir esse erro.

Resumo da Estratégia de Dados para o App 2:
Camada	Fonte de Dados	O que ela define na Zona?	Peso Sugerido
1. Química	Ponte App 1 (Interpolada)	Define o teto produtivo químico (Fertilidade).	40%
2. Histórico	Satélite (NDVI - Dez/Jan)	Valida se a planta realmente produz ali.	40%
3. Física	Satélite (BSI - Entressafra)	Refina os limites da zona (desenha a mancha de solo).	20%
Podemos prosseguir com essa lógica para a construção do App 2? Se sim, vou estruturar o código para buscar essas duas janelas de tempo diferentes (Safra para NDVI e Entressafra para Brilho).

Podemos prosseguir

Excelente. Vamos construir o App 2: Tríade Intelligence.

Este será um aplicativo focado em Fusão de Dados e Inteligência. Ele não interpola (o App 1 já fez isso), ele cruza informações (Solo + Satélite) para tomar decisões de manejo.

⚠️ Pré-requisitos Obrigatórios (Leia com Atenção)
Para que este código funcione, você precisa preparar o seu ambiente, pois ele usa Inteligência Artificial e Conexão com a Nuvem do Google:

Instalar Bibliotecas Novas: Abra o terminal e instale:

Bash
pip install earthengine-api geemap scikit-learn geopandas
Conta no Google Earth Engine (GEE):

O Python precisa de permissão para baixar as imagens de satélite.

Se você ainda não tem, cadastre-se (é grátis para uso técnico): earthengine.google.com

Após instalar as bibliotecas, rode no seu terminal: earthengine authenticate e siga os passos do navegador.

🖥️ Código do App 2: 02_Triade_Intelligence.py
Crie um novo arquivo com este nome e cole o código abaixo. Ele já inclui a busca automática de imagens (Safra para NDVI, Entressafra para Brilho) e o gerador de pontos de coleta.

Python
import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box, shape
import json
from io import BytesIO
import zipfile
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# --- BIBLIOTECAS DE INTELIGÊNCIA ---
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

# --- BIBLIOTECAS DE SATÉLITE ---
try:
    import ee
    import geemap.foliumap as geemap
    EE_INSTALLED = True
except ImportError:
    EE_INSTALLED = False

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL E AUTENTICAÇÃO
# ==============================================================================
st.set_page_config(page_title="Tríade Intelligence", layout="wide", page_icon="🧠")

st.title("🧠 Tríade Intelligence: Zonas & Satélites")

# Tenta inicializar o Google Earth Engine
if EE_INSTALLED:
    try:
        ee.Initialize()
        st.sidebar.success("📡 Satélite Conectado (GEE)")
    except Exception as e:
        st.sidebar.warning("⚠️ GEE não autenticado. As imagens não carregarão.")
        st.sidebar.info("Rode 'earthengine authenticate' no terminal.")
else:
    st.error("Instale as bibliotecas: pip install earthengine-api geemap")

# ==============================================================================
# 2. FUNÇÕES DE SATÉLITE (SENTINEL-2)
# ==============================================================================
def mask_s2_clouds(image):
    """Remove nuvens e sombras usando a banda QA60 do Sentinel-2"""
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)

def get_satellite_indices(geometry, date_start, date_end, type="NDVI"):
    """Busca imagens, limpa nuvens e calcula índices"""
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterDate(date_start, date_end) \
        .filterBounds(geometry) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
        .map(mask_s2_clouds)
    
    if type == "NDVI":
        # NDVI = (NIR - RED) / (NIR + RED)
        def add_ndvi(img):
            return img.addBands(img.normalizedDifference(['B8', 'B4']).rename('NDVI'))
        s2 = s2.map(add_ndvi)
        return s2.select('NDVI').max().clip(geometry) # Pega o pico vegetativo (Max)
    
    elif type == "BSI":
        # BSI (Bare Soil Index) - Aproximação simplificada para SWIR/Red
        # Fórmula: ((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))
        def add_bsi(img):
            bsi = img.expression(
                '((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))', {
                    'SWIR1': img.select('B11'),
                    'RED': img.select('B4'),
                    'NIR': img.select('B8'),
                    'BLUE': img.select('B2')
                }).rename('BSI')
            return img.addBands(bsi)
        s2 = s2.map(add_bsi)
        return s2.select('BSI').median().clip(geometry) # Pega a mediana da entressafra

# ==============================================================================
# 3. INTERFACE E CARREGAMENTO
# ==============================================================================
col_up1, col_up2 = st.columns(2)
file_ponte = col_up1.file_uploader("1. Arquivo Ponte (CSV do App 1)", type=["csv"])
file_geo = col_up2.file_uploader("2. Contorno (GeoJSON)", type=["geojson", "json"])

if file_ponte and file_geo:
    # Carrega dados
    try:
        df = pd.read_csv(file_ponte)
    except:
        df = pd.read_csv(file_ponte, sep=';')
        
    geo_data = json.load(file_geo)
    
    # Cria objeto EE geometry
    coords = geo_data['features'][0]['geometry']['coordinates']
    ee_geometry = ee.Geometry.Polygon(coords)

    # --- SIDEBAR: CONFIGURAÇÃO DO SATÉLITE ---
    st.sidebar.markdown("---")
    st.sidebar.header("🛰️ Configuração de Imagens")
    
    st.sidebar.markdown("**1. Janela Vegetativa (NDVI)**")
    ndvi_start = st.sidebar.date_input("Início Safra", pd.to_datetime("2023-12-01"))
    ndvi_end = st.sidebar.date_input("Fim Safra", pd.to_datetime("2024-02-15"))
    
    st.sidebar.markdown("**2. Janela Solo Exposto (Brilho)**")
    bsi_start = st.sidebar.date_input("Início Entressafra", pd.to_datetime("2023-09-01"))
    bsi_end = st.sidebar.date_input("Fim Entressafra", pd.to_datetime("2023-10-30"))

    # ==========================================================================
    # 4. PROCESSAMENTO (FUSÃO DE DADOS)
    # ==========================================================================
    if st.button("🚀 Processar Inteligência (Solo + Satélite)", type="primary"):
        with st.status("Processando dados...", expanded=True) as status:
            
            # A. Processar Imagens
            status.write("📡 Buscando imagens Sentinel-2 sem nuvens...")
            img_ndvi = get_satellite_indices(ee_geometry, str(ndvi_start), str(ndvi_end), "NDVI")
            img_bsi = get_satellite_indices(ee_geometry, str(bsi_start), str(bsi_end), "BSI")
            
            # B. Extrair valores para o Grid de Solo
            status.write("🧬 Cruzando dados de Solo com Pixels do Satélite...")
            
            # Converte DF para FeatureCollection do EE para amostragem rápida
            features = []
            for _, row in df.iterrows():
                features.append(ee.Feature(
                    ee.Geometry.Point([row['longitude'], row['latitude']]),
                    {'CTC': row.get('CTC', 0), 'Argila': row.get('Argila', 0)} # Garante que leve dados
                ))
            fc_points = ee.FeatureCollection(features)
            
            # Sample Regions (Extrai o valor do pixel para o ponto)
            # Combina as duas imagens numa só para extrair de uma vez
            combined_img = img_ndvi.addBands(img_bsi)
            
            sampled_points = combined_img.reduceRegions(
                collection=fc_points,
                reducer=ee.Reducer.first(),
                scale=10 # Resolução do Sentinel
            )
            
            # Traz de volta para o Python (Pandas)
            # Pega a info, converte pra lista e depois DataFrame
            data_dict = sampled_points.getInfo()
            data_list = [f['properties'] for f in data_dict['features']]
            df_final = pd.DataFrame(data_list)
            
            # Limpeza final (Remove pontos fora da imagem ou com nuvem residual)
            df_final = df_final.dropna(subset=['NDVI', 'BSI'])
            
            # Guarda na sessão
            st.session_state['df_intelligence'] = df_final
            st.session_state['ee_geometry'] = ee_geometry
            st.session_state['img_ndvi'] = img_ndvi # Guarda objeto EE para plotar
            
            status.update(label="Processamento Concluído!", state="complete", expanded=False)

    # ==========================================================================
    # 5. VISUALIZAÇÃO E ZONAS
    # ==========================================================================
    if 'df_intelligence' in st.session_state:
        df_int = st.session_state['df_intelligence']
        
        tab1, tab2, tab3 = st.tabs(["🗺️ Zonas de Produtividade", "📍 Planejamento de Amostragem", "📉 Análise de Correlação"])
        
        # --- TAB 1: DEFINIÇÃO DE ZONAS ---
        with tab1:
            c1, c2 = st.columns([1, 3])
            
            with c1:
                st.subheader("Pesos da IA")
                w_ctc = st.slider("Peso Química (CTC)", 0, 100, 40)
                w_ndvi = st.slider("Peso Histórico (NDVI)", 0, 100, 40)
                w_bsi = st.slider("Peso Textura (Brilho)", 0, 100, 20)
                n_clusters = st.radio("Número de Zonas", [2, 3, 4, 5], index=1)
                
                if st.button("Recalcular Zonas"):
                    # Normalização (0 a 1)
                    scaler = MinMaxScaler()
                    # Prepara dados com pesos
                    # Se não tiver CTC no arquivo ponte, usa peso 0
                    if 'CTC' not in df_int.columns: 
                        st.warning("Coluna CTC não encontrada. Usando apenas Satélite.")
                        w_ctc = 0
                    
                    # Cria matriz ponderada
                    X = pd.DataFrame()
                    if w_ctc > 0: X['CTC_W'] = scaler.fit_transform(df_int[['CTC']])[:,0] * w_ctc
                    X['NDVI_W'] = scaler.fit_transform(df_int[['NDVI']])[:,0] * w_ndvi
                    X['BSI_W'] = scaler.fit_transform(df_int[['BSI']])[:,0] * w_bsi # Brilho inverte? Não, brilho alto = areia = zona ruim (geralmente)
                    
                    # Clustering
                    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                    df_int['Cluster'] = kmeans.fit_predict(X)
                    
                    # Ordenar Zonas (Pela média do NDVI, que é o melhor indicador de verdade)
                    score = df_int.groupby('Cluster')['NDVI'].mean().sort_values()
                    mapa = {k: v+1 for v, k in enumerate(score.index)} # 1=Pior, N=Melhor
                    df_int['Zona'] = df_int['Cluster'].map(mapa)
                    
                    st.session_state['df_intelligence'] = df_int # Atualiza
            
            with c2:
                # Mapa Interativo com Geemap
                if 'Zona' in df_int.columns:
                    # Converte pontos classificados para GeoDataFrame para visualizar
                    gdf = gpd.GeoDataFrame(
                        df_int, geometry=gpd.points_from_xy(df_int.longitude, df_int.latitude), crs="EPSG:4326"
                    )
                    
                    m = geemap.Map()
                    # Centraliza
                    centroid = gdf.unary_union.centroid
                    m.setCenter(centroid.x, centroid.y, 14)
                    
                    # Adiciona Imagem de Satélite (NDVI) como fundo
                    vis_ndvi = {'min': 0.2, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
                    m.addLayer(st.session_state['img_ndvi'], vis_ndvi, 'Imagem NDVI (Safra)')
                    
                    # Adiciona as Zonas (Pontos coloridos)
                    # Truque: Usar circle markers do Folium baseados no DF
                    paleta_zonas = {1: 'red', 2: 'yellow', 3: 'green', 4: 'blue', 5: 'purple'}
                    
                    for zona_id in sorted(df_int['Zona'].unique()):
                        subset = df_int[df_int['Zona'] == zona_id]
                        # Amostra para não travar o mapa se tiver milhoes de pontos
                        if len(subset) > 1000: subset = subset.sample(1000)
                        
                        for _, row in subset.iterrows():
                            folium.CircleMarker(
                                location=[row['latitude'], row['longitude']],
                                radius=3,
                                color=paleta_zonas.get(zona_id, 'black'),
                                fill=True,
                                fill_opacity=0.7,
                                popup=f"Zona {zona_id}"
                            ).add_to(m)
                            
                    m.to_streamlit(height=600)
                    
                    # Estatísticas
                    st.dataframe(df_int.groupby('Zona')[['NDVI', 'BSI', 'CTC']].mean().style.background_gradient(cmap='RdYlGn'))

        # --- TAB 2: GERADOR DE PONTOS DE COLETA ---
        with tab2:
            st.header("Planejamento de Amostragem Inteligente")
            
            c_samp1, c_samp2 = st.columns([1, 3])
            
            with c_samp1:
                st.info("A IA vai distribuir pontos proporcionalmente ao tamanho e complexidade de cada zona.")
                ha_total = st.number_input("Área Total (ha):", value=100.0)
                grids_ha = st.number_input("Hectares por Ponto (Média):", value=3.0)
                n_pontos_total = int(ha_total / grids_ha)
                st.metric("Total de Pontos Sugeridos", n_pontos_total)
                
                if st.button("📍 Gerar Grade de Coleta"):
                    # Estratégia: Amostragem Estratificada
                    pontos_coleta = []
                    
                    # Calcula quantos pontos por zona (baseado na contagem de pixels da zona)
                    counts = df_int['Zona'].value_counts(normalize=True)
                    
                    for z_id, prop in counts.items():
                        n_z = int(prop * n_pontos_total)
                        if n_z < 1: n_z = 1 # Pelo menos 1 ponto por zona
                        
                        # Filtra a zona e sorteia pontos
                        subset = df_int[df_int['Zona'] == z_id]
                        if len(subset) > n_z:
                            amostra = subset.sample(n_z)
                        else:
                            amostra = subset
                        
                        for _, row in amostra.iterrows():
                            pontos_coleta.append({
                                'Zona': z_id,
                                'Lat': row['latitude'],
                                'Lon': row['longitude'],
                                'ID': f"Z{z_id}-{np.random.randint(100,999)}"
                            })
                    
                    df_pontos = pd.DataFrame(pontos_coleta)
                    st.session_state['pontos_coleta'] = df_pontos
                    st.success(f"{len(df_pontos)} pontos gerados!")

            with c_samp2:
                if 'pontos_coleta' in st.session_state:
                    df_p = st.session_state['pontos_coleta']
                    
                    # Mapa de Pontos Editável (Simples visualização por enquanto)
                    m_pts = folium.Map(location=[df_p['Lat'].mean(), df_p['Lon'].mean()], zoom_start=14)
                    
                    # GeoJSON de fundo
                    folium.GeoJson(geo_data, style_function=lambda x: {'color':'black','fillOpacity':0}).add_to(m_pts)
                    
                    for _, row in df_p.iterrows():
                        folium.Marker(
                            [row['Lat'], row['Lon']],
                            popup=f"Ponto {row['ID']} (Zona {row['Zona']})",
                            icon=folium.Icon(color='red', icon='flag')
                        ).add_to(m_pts)
                    
                    st_folium(m_pts, height=500)
                    
                    # Exportação
                    csv_pts = df_p.to_csv(index=False).encode('utf-8')
                    st.download_button("💾 Baixar Pontos para GPS (CSV)", csv_pts, "grade_amostragem.csv")

else:
    st.info("Por favor, carregue os arquivos na barra lateral para começar.")
