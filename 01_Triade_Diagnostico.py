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
from scipy.interpolate import Rbf
import folium
from streamlit_folium import st_folium

# Tenta importar funções utilitárias se existirem, senão define mocks
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

# ==============================================================================
# 3. SIDEBAR DE PARÂMETROS AGRONÔMICOS
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parâmetros de Recomendação")

# A. Produtividade
with st.sidebar.expander("1. Meta de Produtividade", expanded=True):
    meta_prod = st.number_input("Meta Soja (sc/ha):", value=80.0, step=1.0, min_value=0.0)

# B. Calagem (Atualizado: Elevação Ca/Mg)
with st.sidebar.expander("2. Calagem (Elevação Ca/Mg)", expanded=False):
    st.markdown("**Metas na CTC (%):**")
    alvo_ca = st.number_input("Alvo Cálcio (%):", value=60.0, step=1.0)
    alvo_mg = st.number_input("Alvo Magnésio (%):", value=18.0, step=1.0)
    
    st.markdown("**Garantias do Corretivo:**")
    prnt_calc = st.number_input("PRNT (%):", value=80.0, step=1.0)
    teor_cao = st.number_input("Teor CaO (%):", value=60.0, step=1.0) 
    teor_mgo = st.number_input("Teor MgO (%):", value=18.0, step=1.0) 

# C. Fósforo (Tabela P-rem + Exportação)
with st.sidebar.expander("3. Fósforo (P)", expanded=False):
    st.markdown("**Parâmetros:**")
    export_p_factor = st.number_input("Exportação P (kg/sc):", value=0.8, step=0.1)
    teor_p2o5_adubo = st.number_input("Teor P₂O₅ Adubo (%):", value=21.0, step=1.0)
    fator_tam_p = st.number_input("Fator Tampão (kg P₂O₅/mg):", value=5.0, step=0.5, help="Qtd de adubo para subir 1 mg no solo")

    st.markdown("**Níveis Críticos (P-rem):**")
    st.caption("Conforme P-rem do solo:")
    nc_p1 = st.number_input("0 - 4 mg/dm³:", value=6.0, step=0.5)
    nc_p2 = st.number_input("4.1 - 10 mg/dm³:", value=7.5, step=0.5)
    nc_p3 = st.number_input("10.1 - 19 mg/dm³:", value=11.5, step=0.5)
    nc_p4 = st.number_input("19.1 - 30 mg/dm³:", value=15.0, step=0.5)
    nc_p5 = st.number_input("> 30 mg/dm³:", value=20.0, step=0.5)

# D. Potássio
with st.sidebar.expander("4. Potássio (K)", expanded=False):
    st.markdown("**Correção + Exportação:**")
    alvo_k_ctc = st.number_input("Meta K na CTC (%):", value=3.5, step=0.1)
    export_k_factor = st.number_input("Exportação K (kg/sc):", value=1.2, step=0.1)
    teor_k2o_adubo = st.number_input("Teor K₂O Adubo (%):", value=60.0, step=1.0)

# E. Gesso
with st.sidebar.expander("5. Gessagem", expanded=False):
    fator_gesso = st.number_input("Fator x Argila:", value=50.0, step=5.0)

# ==============================================================================
# 4. FUNÇÕES AUXILIARES
# ==============================================================================
def processar_arquivo_geografico(uploaded_file):
    points = []
    try:
        if uploaded_file.name.lower().endswith('.kmz'):
            with zipfile.ZipFile(uploaded_file, 'r') as z:
                kml_filename = [f for f in z.namelist() if f.endswith('.kml')][0]
                with z.open(kml_filename) as f: tree = ET.parse(f)
        else:
            uploaded_file.seek(0)
            tree = ET.parse(uploaded_file)
        
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
                            lon = float(first_coord[0])
                            lat = float(first_coord[1])
                            points.append({'ID_PONTO': name, 'latitude': lat, 'longitude': lon})
                        except ValueError: pass
        return pd.DataFrame(points)
    except Exception as e: st.error(f"Erro KML: {e}"); return pd.DataFrame()

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
# 5. MOTOR DE CÁLCULO (RBF LINEAR - CORRIGIDO PARA EXIBIR MAPAS)
# ==============================================================================
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=100):
    df = df_input.copy()
    
    # --- CORREÇÃO DE COLUNAS DE COORDENADAS (CRUCIAL) ---
    # Prioriza as coordenadas do KML (geralmente sufixo _y no merge)
    if 'latitude_y' in df.columns:
        df.rename(columns={'latitude_y': 'latitude', 'longitude_y': 'longitude'}, inplace=True)
    elif 'latitude_x' in df.columns and 'latitude' not in df.columns:
        df.rename(columns={'latitude_x': 'latitude', 'longitude_x': 'longitude'}, inplace=True)
        
    # Garante que latitude e longitude existem
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        st.error("Erro crítico: Coordenadas não encontradas após a fusão.")
        return pd.DataFrame(), None

    cols_proibidas = ['id', 'ponto', 'amostra', 'lab', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao', 'geometry', 'id_clean', 'unnamed', 'obs']
    
    cols_validas = []
    for col in df.columns:
        if any(p in str(col).lower() for p in cols_proibidas): continue
        df[col] = limpar_coluna_inteligente(df[col])
        if df[col].notna().sum() >= 5: # Relaxei a regra de variância para garantir que plote
            cols_validas.append(col)

    df_grouped = df.groupby(['latitude', 'longitude'], as_index=False)[cols_validas].mean()

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

    grid_y_m = grid_y * 111111
    grid_x_m = grid_x * 111111 * np.cos(np.radians(lat_mean))

    processed_cols = []
    progresso = st.progress(0)
    
    for i, col in enumerate(cols_validas):
        progresso.progress((i + 1) / len(cols_validas))
        try:
            dados_col = df_grouped[['X_m', 'Y_m', col]].dropna()
            if len(dados_col) < 5: continue
            
            interpolator = Rbf(dados_col['X_m'], dados_col['Y_m'], dados_col[col], function='linear')
            z = interpolator(grid_x_m, grid_y_m)
            # Clip robusto para evitar cores malucas
            z = np.clip(z, dados_col[col].min(), dados_col[col].max())
            
            df_result[col] = z.flatten()
            processed_cols.append(col)
        except: continue
    
    progresso.empty()
    cols_finais = ['latitude', 'longitude'] + processed_cols
    return df_result[cols_finais], (resolucao_grid, resolucao_grid)

# ==============================================================================
# 6. GERAÇÃO DE IMAGEM
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
# 7. LÓGICA DE RECOMENDAÇÃO (FÓRMULAS VRT PRO)
# ==============================================================================
def calcular_recomendacoes(df):
    df_rec = df.copy()
    
    # Mapeamento
    cols = {k: next((c for c in df_rec.columns if k in c.lower()), None) 
            for k in ['ca', 'mg', 'k', 'p', 'v%', 'ctc', 'argila', 'prem']}
    
    # --- A. CALAGEM (ELEVAÇÃO Ca e Mg - MAIOR DOSE) ---
    if cols['ca'] and cols['mg'] and cols['ctc']:
        # Deficit Ca (cmolc/dm3)
        ca_atual = df_rec[cols['ca']]
        ca_alvo_val = (alvo_ca / 100) * df_rec[cols['ctc']]
        def_ca = ca_alvo_val - ca_atual
        
        # Deficit Mg (cmolc/dm3)
        mg_atual = df_rec[cols['mg']]
        mg_alvo_val = (alvo_mg / 100) * df_rec[cols['ctc']]
        def_mg = mg_alvo_val - mg_atual
        
        # Estequiometria: 1 cmolc Ca = 560 kg CaO | 1 cmolc Mg = 403 kg MgO
        need_cao_kg = def_ca * 560
        need_mgo_kg = def_mg * 403
        
        # Conversão para Toneladas de Produto Comercial
        t_cao = teor_cao if teor_cao > 0 else 1
        t_mgo = teor_mgo if teor_mgo > 0 else 1
        
        dose_ton_ca = (need_cao_kg / t_cao) / 10
        dose_ton_mg = (need_mgo_kg / t_mgo) / 10
        
        # Maior Dose vence + PRNT
        dose_base = np.maximum(dose_ton_ca, dose_ton_mg)
        prnt_fator = 100 / prnt_calc if prnt_calc > 0 else 1
        
        df_rec['Calcario_Ton_ha'] = (dose_base * prnt_fator).apply(lambda x: x if x > 0 else 0)

    # --- B. POTÁSSIO (Correção + Exportação) ---
    if cols['k'] and cols['ctc']:
        k_pct = (df_rec[cols['k']] / df_rec[cols['ctc']]) * 100
        
        # Deficit para atingir meta (ex: 3.5%)
        def_k_cmolc = ((alvo_k_ctc - k_pct) / 100) * df_rec[cols['ctc']]
        def_k_cmolc = def_k_cmolc.apply(lambda x: x if x > 0 else 0)
        
        # Correção
        k2o_corr = def_k_cmolc * 942 
        k2o_export = meta_prod * export_k_factor
        
        total_k2o = k2o_corr + k2o_export
        t_k2o = teor_k2o_adubo if teor_k2o_adubo > 0 else 1
        
        df_rec['Adubo_K_Kg_ha'] = (total_k2o * (100 / t_k2o)).apply(lambda x: x if x > 0 else 0)

    # --- C. FÓSFORO (P-rem + Reserva descontada) ---
    col_p = next((c for c in df_rec.columns if 'p mehl' in c.lower() or 'p_mehl' in c.lower()), cols['p'])
    
    if col_p and cols['prem']:
        # Níveis Críticos (Sidebar)
        conds = [
            df_rec[cols['prem']] <= 4.0,
            (df_rec[cols['prem']] > 4.0) & (df_rec[cols['prem']] <= 10.0),
            (df_rec[cols['prem']] > 10.0) & (df_rec[cols['prem']] <= 19.0),
            (df_rec[cols['prem']] > 19.0) & (df_rec[cols['prem']] <= 30.0),
            df_rec[cols['prem']] > 30.0
        ]
        choices = [nc_p1, nc_p2, nc_p3, nc_p4, nc_p5]
        
        nc_p_grid = np.select(conds, choices, default=30.0)
            
        # Gap: Se P_solo > NC, fica negativo (Reserva)
        gap_p = nc_p_grid - df_rec[col_p]
        
        # Correção (Pode ser negativa se houver sobra)
        dose_correcao = gap_p * fator_tam_p 
        
        # Exportação (Sempre positiva)
        dose_export = meta_prod * export_p_factor
        
        # Soma Algébrica: Se dose_correcao for -20 e export for 60, aplica 40.
        dose_total_p2o5 = dose_export + dose_correcao
        
        t_p2o5 = teor_p2o5_adubo if teor_p2o5_adubo > 0 else 1
        df_rec['Adubo_P_Kg_ha'] = (dose_total_p2o5 * (100 / t_p2o5)).apply(lambda x: x if x > 0 else 0)

    # --- D. GESSO ---
    if cols['argila']:
        df_rec['Gesso_Ton_ha'] = (df_rec[cols['argila']] * fator_gesso) / 1000

    return df_rec

# ==============================================================================
# 8. INTERFACE E EXECUÇÃO
# ==============================================================================
aba1, aba2 = st.tabs(["🗺️ Diagnóstico", "🚜 Recomendação VRT"])

with aba1:
    st.header("Importação de Dados")
    c1, c2, c3 = st.columns(3)
    file_lab = c1.file_uploader("Dados Lab (CSV/Excel)", type=["csv", "xlsx"])
    file_geo = c2.file_uploader("Pontos (KMZ/KML)", type=["kmz", "kml"])
    file_geojson = c3.file_uploader("Contorno (GeoJSON)", type=["geojson", "json"])

    if file_lab and file_geo and file_geojson:
        if st.button("🚀 Processar Ponte de Dados", type="primary"):
            try:
                # 1. Load Data
                if file_lab.name.lower().endswith('.csv'):
                    try: df_lab = pd.read_csv(file_lab)
                    except: file_lab.seek(0); df_lab = pd.read_csv(file_lab, sep=';')
                else: df_lab = pd.read_excel(file_lab)
                
                df_geo_points = processar_arquivo_geografico(file_geo)
                file_geojson.seek(0); st.session_state['geojson_data'] = json.load(file_geojson)

                if not df_lab.empty and not df_geo_points.empty:
                    col_id = next((c for c in df_lab.columns if str(c).lower().strip() in ['id', 'ponto', 'amostra', 'codigo']), df_lab.columns[0])
                    df_lab['id_clean'] = df_lab[col_id].apply(lambda x: str(x).split('.')[0].strip())
                    df_geo_points['id_clean'] = df_geo_points['ID_PONTO'].apply(lambda x: str(x).split('.')[0].strip())
                    
                    df_merged = pd.merge(df_lab, df_geo_points, on='id_clean', how='inner')
                    
                    if not df_merged.empty:
                        df_krig, shape = processar_matrizes_interpolacao(df_merged, st.session_state['geojson_data'], 100)
                        st.session_state['dados_processados'] = df_krig
                        st.session_state['grid_shape'] = shape
                        st.success(f"Dados processados: {len(df_merged)} pontos.")
                    else: st.error("Erro no cruzamento de IDs.")
            except Exception as e: st.error(f"Erro: {e}")

    if st.session_state['dados_processados'] is not None:
        st.divider()
        cols = [c for c in st.session_state['dados_processados'].columns if c not in ['latitude', 'longitude']]
        if cols:
            attr = st.selectbox("Nutriente:", cols)
            img, bounds, mm = gerar_imagem_overlay(st.session_state['dados_processados'], attr, st.session_state['geojson_data'], st.session_state['grid_shape'])
            if img:
                m = folium.Map(location=[bounds[0][0], bounds[0][1]], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{base64.b64encode(img.getvalue()).decode()}", bounds=bounds, opacity=0.8).add_to(m)
                folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x: {'color':'black','fillOpacity':0}).add_to(m)
                st_folium(m, height=500, use_container_width=True, key=f"mapa_{attr}")
        else:
            st.warning("Nenhum mapa gerado. Verifique se a planilha contém dados numéricos válidos.")

with aba2:
    st.header("Mapas de Recomendação VRT")
    if st.session_state['dados_processados'] is None:
        st.warning("Gere o diagnóstico primeiro.")
    else:
        if st.button("🔄 Calcular/Atualizar Recomendações"):
            df_calc = calcular_recomendacoes(st.session_state['dados_processados'])
            st.session_state['dados_rec'] = df_calc
            st.success("Recomendações Calculadas!")

        if 'dados_rec' in st.session_state:
            cols_rec = [c for c in st.session_state['dados_rec'].columns if any(x in c for x in ['Ton', 'Kg', 'ha'])]
            if cols_rec:
                escolha = st.selectbox("Mapa de Aplicação:", cols_rec)
                
                media_dose = st.session_state['dados_rec'][escolha].mean()
                
                c1, c2 = st.columns(2)
                c1.metric("Dose Média", f"{media_dose:.1f}")
                c2.info(f"Produtividade Alvo: {meta_prod} sc/ha")

                img_rec, bounds_rec, mm_rec = gerar_imagem_overlay(
                    st.session_state['dados_rec'], escolha, 
                    st.session_state['geojson_data'], st.session_state['grid_shape']
                )
                if img_rec:
                    m2 = folium.Map(location=[bounds_rec[0][0], bounds_rec[0][1]], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                    folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{base64.b64encode(img_rec.getvalue()).decode()}", bounds=bounds_rec, opacity=0.8).add_to(m2)
                    folium.GeoJson(st.session_state['geojson_data'], style_function=lambda x: {'color':'black','fillOpacity':0}).add_to(m2)
                    
                    legend_html = f"""<div style="position:fixed;bottom:30px;right:30px;z-index:9999;background:white;padding:10px;border:1px solid black;"><b>{escolha}</b><br>
                    <div style="display:flex;width:150px;height:10px;"><div style="flex:1;background:#d73027;"></div><div style="flex:1;background:#fc8d59;"></div><div style="flex:1;background:#fee08b;"></div><div style="flex:1;background:#d9ef8b;"></div><div style="flex:1;background:#91cf60;"></div><div style="flex:1;background:#4575b4;"></div></div>
                    <div style="display:flex;justify-content:space-between;font-size:10px;"><span>{mm_rec[0]:.1f}</span><span>{mm_rec[1]:.1f}</span></div></div>"""
                    m2.get_root().html.add_child(folium.Element(legend_html))
                    
                    st_folium(m2, height=500, use_container_width=True, key=f"mapa_rec_{escolha}")
