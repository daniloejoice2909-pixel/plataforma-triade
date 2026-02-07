import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64

# --- 1. CONFIGURAÇÃO DE BACKEND (MATPLOTLIB SEGURO) ---
import matplotlib
matplotlib.use('Agg') # Essencial para não travar o servidor
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.path import Path as MplPath

from pykrige.ok import OrdinaryKriging
import folium
from streamlit_folium import st_folium

# Importando utils originais
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

# Inicialização de Estado (Memória)
if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None

# ==============================================================================
# 3. MOTOR DE CÁLCULO REVISADO (V70 - LEITURA COMPLETA)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Calculando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    # 1. Cópia e Normalização
    df = df_input.copy()
    
    # Metadados
    cols_proibidas = [
        'id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 
        'x', 'y', 'data', 'hora', 'campo', 'fazenda', 
        'profundidade', 'zona', 'talhao', 'geometry'
    ]
    
    # Identificação de Colunas
    cols_validas = []
    for col in df.columns:
        if col.lower() in cols_proibidas: continue
        
        # Tratamento de Vírgula para Ponto
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            # Se tiver pelo menos 3 números válidos, tentamos processar
            if df[col].notna().sum() >= 3: 
                cols_validas.append(col)
        except: pass 

    # 2. Arredondamento de Coordenadas (Resolve duplicação de pontos)
    # Importante: Agrupa pontos duplicados pela média para não travar a Krigagem
    df['longitude'] = df['longitude'].round(5)
    df['latitude'] = df['latitude'].round(5)
    
    df_grouped = df.groupby(['latitude', 'longitude'], as_index=False)[cols_validas].mean()

    # 3. Definição do Grid
    x_min, x_max = df_grouped['longitude'].min(), df_grouped['longitude'].max()
    y_min, y_max = df_grouped['latitude'].min(), df_grouped['latitude'].max()
    buffer = 0.005 
    
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    xx, yy = np.meshgrid(grid_x, grid_y)
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    # 4. Loop INDEPENDENTE
    for col in cols_validas:
        try:
            dados_col = df_grouped[['longitude', 'latitude', col]].dropna()
            
            if len(dados_col) < 5:
                df_result[col] = 0.0
                continue
                
            if dados_col[col].nunique() <= 1:
                df_result[col] = dados_col[col].iloc[0]
                continue

            # Geoestatística (Krigagem)
            OK = OrdinaryKriging(
                dados_col['longitude'], dados_col['latitude'], dados_col[col], 
                variogram_model='linear', verbose=False, enable_plotting=False
            )
            z, _ = OK.execute('grid', grid_x, grid_y)
            df_result[col] = z.flatten()
            
        except Exception as e:
            print(f"⚠️ Erro ao interpolar {col}: {e}")
            continue

    return df_result

# ==============================================================================
# 4. GERAÇÃO DE IMAGEM (V70 - VISUALIZAÇÃO SEGURA)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data):
    # 1. Pivotagem
    pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
    Z = pivot.values
    X_unique = pivot.columns.values 
    Y_unique = pivot.index.values    
    
    x_min, x_max = X_unique.min(), X_unique.max()
    y_min, y_max = Y_unique.min(), Y_unique.max()

    # 2. Máscara de Recorte
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
            
            Z[~mask_grid] = np.nan
            
    except Exception as e:
        print(f"Erro no recorte: {e}")

    # 3. Cálculo de Escala
    z_min = np.nanmin(Z)
    z_max = np.nanmax(Z)
    
    if np.isnan(z_min): z_min = 0
    if np.isnan(z_max): z_max = 1
    
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
    
    ax.contourf(X_unique, Y_unique, Z, levels=50, cmap=cmap, norm=norm, extend='both', alpha=1.0)
    
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    
    img_data = BytesIO()
    plt.savefig(img_data, format='png', transparent=True, dpi=100)
    plt.close(fig)
    img_data.seek(0)
    
    return img_data, [[y_min, x_min], [y_max, x_max]], [z_min, z_max]

# ==============================================================================
# 5. INTERFACE
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")
file_csv = st.sidebar.file_uploader("📂 Tabela (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno (.geojson)", type=["geojson", "json"])

# RESET DE MEMÓRIA AUTOMÁTICO
if not file_csv or not file_geojson:
    if st.session_state.get('dados_processados') is not None:
        st.session_state['dados_processados'] = None
        st.session_state['geojson_data'] = None
        st.cache_data.clear()
        st.rerun()

if file_csv and file_geojson:
    # Leitura Blindada
    try:
        # Tenta ler com pandas padrão
        df_raw = pd.read_csv(file_csv)
        
        # Se só tiver 1 coluna, provavelmente o separador é ponto e vírgula
        if len(df_raw.columns) < 2:
            file_csv.seek(0)
            df_raw = pd.read_csv(file_csv, sep=';')
            
        df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")
        st.stop()
    
    # --- PAINEL DE DIAGNÓSTICO (CORRIGIDO: MOSTRA TUDO) ---
    with st.expander("🕵️ Diagnóstico de Leitura (Verifique seus dados)", expanded=True):
        st.info(f"O sistema leu **{len(df_raw)} linhas** e **{len(df_raw.columns)} colunas**.")
        st.write("Abaixo está a planilha completa carregada na memória:")
        # AQUI ESTAVA O ERRO: ANTES TINHA .head(3). AGORA MOSTRA TUDO.
        st.dataframe(df_raw, use_container_width=True) 
    # -------------------------------------

    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
        st.session_state['geojson_data'] = geojson_data
    except:
        st.error("GeoJSON inválido.")
        st.stop()

    # Seleção de Coordenadas
    c1, c2 = st.columns(2)
    cols = list(df_raw.columns)
    idx_lat = next((i for i, c in enumerate(cols) if 'lat' in c), 0)
    idx_lon = next((i for i, c in enumerate(cols) if 'lon' in c or 'lng' in c), 1)
    
    with c1: lat_col = st.selectbox("Latitude:", cols, index=idx_lat)
    with c2: lon_col = st.selectbox("Longitude:", cols, index=idx_lon)
    
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    # Botão de Processar
    if st.button("🚀 Processar Mapas", type="primary"):
        with st.status("Processando...", expanded=True) as status:
            st.cache_data.clear() 
            
            st.write("Verificando dados...")
            try:
                # Tratamento de erro comum: vírgula no lugar de ponto nas coordenadas
                df_raw['latitude'] = pd.to_numeric(df_raw['latitude'].astype(str).str.replace(',', '.'), errors='coerce')
                df_raw['longitude'] = pd.to_numeric(df_raw['longitude'].astype(str).str.replace(',', '.'), errors='coerce')
                
                # Remove linhas sem coordenadas
                df_raw = df_raw.dropna(subset=['latitude', 'longitude'])
                
                if df_raw.empty:
                    st.error("Erro: Nenhuma linha com Latitude/Longitude válidas encontrada.")
                    st.stop()
                    
            except Exception as e:
                st.error(f"Erro nas coordenadas: {e}")
                st.stop()

            st.write(f"Interpolando {len(df_raw)} pontos...")
            df_krig = processar_matrizes_interpolacao(df_raw, geojson_data)
            
            if df_krig.empty:
                st.error("O processamento retornou uma tabela vazia.")
                st.stop()
                
            st.session_state['dados_processados'] = df_krig
            status.update(label="Concluído!", state="complete", expanded=False)
        st.rerun()

# ==============================================================================
# 6. VISUALIZAÇÃO
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    
    st.divider()
    
    csv_ponte = df_final.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Baixar Arquivo Ponte", csv_ponte, "ponte.csv", "text/csv", type="primary")
    
    st.divider()
    
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        st.subheader("🗺️ Visualização de Diagnóstico")
        atributo = st.selectbox("Selecione o mapa:", cols_ver)
        
        df_plot = df_final[['latitude', 'longitude', atributo]].copy()

        if not df_plot.empty:
            try:
                img_buffer, bounds, min_max = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'])
                z_min, z_max = min_max
                
                centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satellite')
                
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=bounds, opacity=0.9, interactive=True, cross_origin=False, zindex=1
                ).add_to(m)
                
                folium.GeoJson(
                    st.session_state['geojson_data'],
                    style_function=lambda x: {'color': 'black', 'weight': 2, 'fillOpacity': 0}
                ).add_to(m)
                
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
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Mínimo", f"{z_min:.2f}")
                c2.metric("Média Estimada", f"{df_plot[atributo].mean():.2f}")
                c3.metric("Máximo", f"{z_max:.2f}")
                
            except Exception as e:
                st.error(f"Erro visual: {e}")
        else:
            st.warning("Dados insuficientes para este atributo.")
