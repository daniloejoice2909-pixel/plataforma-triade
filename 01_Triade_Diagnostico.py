import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64

# --- 1. CONFIGURAÇÃO DE BACKEND (A VACINA ANTI-TRAVAMENTO) ---
import matplotlib
matplotlib.use('Agg') # Força modo não-interativo (Essencial para Web)
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

from pykrige.ok import OrdinaryKriging
import folium
from streamlit_folium import st_folium

# Importando utils
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

# ==============================================================================
# 3. KRIGAGEM OTIMIZADA (V58 - LEVE)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Calculando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    df = df_input.copy() 
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao']
    cols_validas = []
    
    # Limpeza Rápida
    for col in df.columns:
        if col.lower() in cols_proibidas: continue
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].notna().sum() > 5: cols_validas.append(col)
        except: pass 

    # Grid Inteligente (Buffer reduzido para 0.003 para não pesar)
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    buffer = 0.003 
    
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    # Prepara DataFrame de Resultado
    xx, yy = np.meshgrid(grid_x, grid_y)
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    # Interpolação
    for col in cols_validas:
        try:
            dados = df[['longitude', 'latitude', col]].dropna()
            if len(dados) < 5: continue

            # Variograma Linear é mais rápido e estável
            OK = OrdinaryKriging(
                dados['longitude'], dados['latitude'], dados[col], 
                variogram_model='linear', verbose=False, enable_plotting=False
            )
            z, _ = OK.execute('grid', grid_x, grid_y)
            df_result[col] = z.flatten()
        except: pass

    return df_result.dropna(subset=cols_validas, how='all')

# ==============================================================================
# 4. GERAÇÃO DE IMAGEM BLINDADA (V63 - CORREÇÃO DE RECORTE GEOGRÁFICO)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data):
    # 1. Prepara Dados e Limites Exatos
    pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values    
    
    x_min, x_max = X.min(), X.max()
    y_min, y_max = Y.min(), Y.max()

    # 2. Configura Cores (Escala Jet - Padrão Agronômico)
    cmap = plt.get_cmap('jet', 8) 
    
    # Vacina contra mapa plano (valores constantes)
    z_min, z_max = np.nanmin(Z), np.nanmax(Z)
    if z_min == z_max:
        z_min -= 0.1
        z_max += 0.1
    elif (z_max - z_min) < 0.0001:
        z_max += 0.0001
        
    bounds = np.linspace(z_min, z_max, 9)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # 3. Gera Figura com Proporção Exata (CORREÇÃO DO DESALINHAMENTO)
    plt.close('all') 
    
    # Calcula a razão de aspecto para que 1 grau de lat seja igual a 1 grau de lon (aproximado)
    # ou simplesmente mantém a proporção dos dados para não distorcer
    aspect_ratio = (x_max - x_min) / (y_max - y_min)
    fig_height = 6
    fig_width = fig_height * aspect_ratio
    
    # Cria a figura com tamanho proporcional
    fig = plt.figure(figsize=(fig_width, fig_height))
    
    # [IMPORTANTE] Define o eixo para ocupar 100% da figura (0,0,1,1)
    # Isso elimina bordas brancas sem usar bbox_inches='tight'
    ax = plt.axes([0, 0, 1, 1])
    ax.set_axis_off()
    
    # 4. Desenha (Contourf)
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both', alpha=1.0)
    
    # 5. Aplica Recorte (Clipping) pelo GeoJSON
    try:
        # Tenta pegar coordenadas (suporte simples para Polygon)
        # Se for MultiPolygon, precisaria de uma lógica mais complexa, 
        # mas mantendo sua estrutura original:
        if geojson_data['features'][0]['geometry']['type'] == 'Polygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
        elif geojson_data['features'][0]['geometry']['type'] == 'MultiPolygon':
            # Pega o maior polígono ou o primeiro (blindagem básica)
            coords = geojson_data['features'][0]['geometry']['coordinates'][0][0]
        else:
            coords = [] # Falha segura

        if len(coords) > 0:
            poly_path = MplPath(coords)
            patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', edgecolor='black', linewidth=2)
            ax.add_patch(patch)
            
            # Aplica o recorte na coleção de contornos
            if hasattr(cf, 'collections'):
                for col in cf.collections: 
                    col.set_clip_path(patch)
    except Exception as e:
        print(f"Erro no recorte (Clipping): {e}")

    # 6. Finaliza com Travamento de Eixos
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    
    img_data = BytesIO()
    
    # [CRÍTICO] Removemos bbox_inches='tight' e pad_inches=0
    # Como definimos o eixo em [0,0,1,1], a imagem sairá exata.
    plt.savefig(img_data, format='png', transparent=True, dpi=100)
    
    plt.close(fig)
    img_data.seek(0)
    
    return img_data, [[y_min, x_min], [y_max, x_max]], bounds

# ==============================================================================
# 5. INTERFACE E LÓGICA
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")
file_csv = st.sidebar.file_uploader("📂 Tabela (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno (.geojson)", type=["geojson", "json"])

if file_csv and file_geojson:
    # Carregamento
    df_raw = carregar_dados_blindado(file_csv)
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    
    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
        st.session_state['geojson_data'] = geojson_data
    except:
        st.error("GeoJSON inválido.")
        st.stop()

    # Validação Colunas
    c1, c2 = st.columns(2)
    cols = list(df_raw.columns)
    idx_lat = cols.index('latitude') if 'latitude' in cols else 0
    idx_lon = cols.index('longitude') if 'longitude' in cols else 1
    
    with c1: lat_col = st.selectbox("Latitude:", cols, index=idx_lat)
    with c2: lon_col = st.selectbox("Longitude:", cols, index=idx_lon)
    
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    if st.button("🚀 Processar Mapas", type="primary"):
        with st.status("Processando...", expanded=True) as status:
            st.write("Calculando Geoestatística...")
            df_krig = processar_matrizes_interpolacao(df_raw, geojson_data)
            st.session_state['dados_processados'] = df_krig
            status.update(label="Concluído!", state="complete", expanded=False)
        st.rerun()

# ==============================================================================
# 6. VISUALIZAÇÃO
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    
    st.divider()
    
    # Download
    csv_ponte = df_final.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Baixar Arquivo Ponte", csv_ponte, "ponte.csv", "text/csv", type="primary")
    
    st.divider()
    
    # Seletor de Mapa
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver)
        df_plot = df_final.dropna(subset=[atributo])
        
        if not df_plot.empty:
            try:
                # Gera Imagem
                img_buffer, bounds, intervals = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'])
                
                # Mapa Folium
                centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                
                # Overlay da Imagem
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=bounds, opacity=0.85
                ).add_to(m)
                
                # Contorno Preto
                folium.GeoJson(
                    st.session_state['geojson_data'],
                    style_function=lambda x: {'color': 'black', 'weight': 3, 'fillOpacity': 0}
                ).add_to(m)
                
                # Legenda Simples
                legend_html = f"""
                <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; background: white; padding: 10px; border: 2px solid black; border-radius: 5px;">
                <b>{atributo}</b><br>
                <span style="color:#d73027">■</span> Baixo ({intervals[0]:.1f} - {intervals[1]:.1f})<br>
                <span style="color:#fee08b">■</span> Médio ({intervals[2]:.1f})<br>
                <span style="color:#1a9850">■</span> Alto ({intervals[4]:.1f} - {intervals[5]:.1f})
                </div>
                """
                m.get_root().html.add_child(folium.Element(legend_html))
                
                st_folium(m, height=500, use_container_width=True)
                
            except Exception as e:
                st.error(f"Erro visual: {e}")
