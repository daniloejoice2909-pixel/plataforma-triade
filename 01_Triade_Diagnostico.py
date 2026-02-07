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

# Importando utils (Seu arquivo original)
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
# 3. KRIGAGEM OTIMIZADA (V60 - COM DETECÇÃO DE CONSTANTES)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Calculando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    df = df_input.copy() 
    
    # Metadados que não devem ser interpolados
    cols_proibidas = [
        'id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 
        'x', 'y', 'data', 'hora', 'campo', 'fazenda', 
        'profundidade', 'zona', 'talhao', 'geometry'
    ]
    
    cols_validas = []
    
    # 1. Limpeza e Validação Inicial
    for col in df.columns:
        if col.lower() in cols_proibidas: continue
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].notna().sum() > 5: 
                cols_validas.append(col)
        except: pass 

    # 2. Criação do Grid
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    buffer = 0.003 
    
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    xx, yy = np.meshgrid(grid_x, grid_y)
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    # 3. Loop Inteligente
    for col in cols_validas:
        if col not in df.columns: continue

        try:
            dados = df[['longitude', 'latitude', col]].dropna()
            if len(dados) < 5: continue

            # Correção para Mapas Planos (ex: Alumínio Zero)
            if dados[col].nunique() <= 1:
                valor_constante = dados[col].iloc[0]
                df_result[col] = valor_constante
                continue 
            
            # Geoestatística
            OK = OrdinaryKriging(
                dados['longitude'], dados['latitude'], dados[col], 
                variogram_model='linear', verbose=False, enable_plotting=False
            )
            z, _ = OK.execute('grid', grid_x, grid_y)
            df_result[col] = z.flatten()
            
        except Exception as e:
            print(f"⚠️ Erro ao processar '{col}': {e}")
            continue

    # Filtra apenas colunas que realmente foram geradas
    cols_finais = [c for c in cols_validas if c in df_result.columns]
    if not cols_finais: return df_result # Retorna vazio se falhar tudo
    
    return df_result.dropna(subset=cols_finais, how='all')

# ==============================================================================
# 4. GERAÇÃO DE IMAGEM (V64 - GEOMETRIA PERFEITA E CORES VIVAS)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data):
    # 1. Extração dos Limites Exatos
    pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values    
    
    x_min, x_max = X.min(), X.max()
    y_min, y_max = Y.min(), Y.max()

    # 2. Configuração de Cores (JET)
    cmap = plt.get_cmap('jet', 256) # 256 níveis para gradiente suave ou use 8 para faixas
    
    # Tratamento para mapas planos (sem variação de cor)
    z_min, z_max = np.nanmin(Z), np.nanmax(Z)
    if z_min == z_max:
        z_min -= 0.1
        z_max += 0.1
        
    levels = np.linspace(z_min, z_max, 50) # Aumentei níveis para cor não sumir
    norm = mcolors.Normalize(vmin=z_min, vmax=z_max)

    # 3. CRIAÇÃO DA FIGURA COM PROPORÇÃO MATEMÁTICA (Segredo do Encaixe)
    plt.close('all') 
    
    # Razão de aspecto: (Largura / Altura)
    aspect_ratio = (x_max - x_min) / (y_max - y_min)
    
    # Definimos uma altura fixa alta (ex: 10 polegadas) e calculamos a largura
    h_fig = 10
    w_fig = h_fig * aspect_ratio
    
    fig = plt.figure(figsize=(w_fig, h_fig))
    
    # [IMPORTANTE] Eixo ocupando 100% da figura (0,0,1,1) -> Remove bordas brancas
    ax = plt.axes([0, 0, 1, 1])
    ax.set_axis_off()
    
    # 4. Desenha o Mapa (Contourf)
    # alpha=1.0 Garante cor sólida
    cf = ax.contourf(X, Y, Z, levels=levels, cmap=cmap, norm=norm, extend='both', alpha=1.0)
    
    # 5. Aplica Recorte (Clipping) - O "Cookie Cutter"
    try:
        # Lógica para pegar coordenadas do Polígono
        coords = []
        geom_type = geojson_data['features'][0]['geometry']['type']
        
        if geom_type == 'Polygon':
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
        elif geom_type == 'MultiPolygon':
            # Pega o maior polígono (geralmente o contorno externo)
            coords = geojson_data['features'][0]['geometry']['coordinates'][0][0]
            
        if len(coords) > 0:
            poly_path = MplPath(coords)
            patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', edgecolor='none') # Edgecolor none para não duplicar linha
            ax.add_patch(patch)
            
            # Aplica o recorte na imagem gerada
            for collection in cf.collections:
                collection.set_clip_path(patch)
                
    except Exception as e:
        print(f"Erro Clipping: {e}")

    # 6. Trava os limites do eixo nos limites exatos dos dados
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    
    # 7. Salva a imagem
    img_data = BytesIO()
    # NÃO usar bbox_inches='tight' aqui, pois já configuramos o eixo exato
    plt.savefig(img_data, format='png', transparent=True, dpi=150)
    plt.close(fig)
    img_data.seek(0)
    
    # Retorna imagem e os limites exatos para o Folium
    return img_data, [[y_min, x_min], [y_max, x_max]], [z_min, z_max]

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
                # Gera Imagem Perfeita
                img_buffer, bounds, min_max = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'])
                
                # Mapa Folium
                centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satellite')
                
                # Overlay da Imagem (Agora com encaixe exato)
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=bounds, 
                    opacity=0.8, # Leve transparência para ver o terreno fundo
                    interactive=True,
                    cross_origin=False,
                    zindex=1
                ).add_to(m)
                
                # Contorno Preto por Cima (LineString para não preencher)
                folium.GeoJson(
                    st.session_state['geojson_data'],
                    style_function=lambda x: {'color': 'black', 'weight': 3, 'fillOpacity': 0}
                ).add_to(m)
                
                # Legenda Simples e Dinâmica
                z_min, z_max = min_max
                legend_html = f"""
                <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; 
                            background: white; padding: 10px; border: 2px solid black; border-radius: 5px;">
                <b>{atributo}</b><br>
                <div style="background: linear-gradient(to right, #000080, #0000ff, #00ffff, #ffff00, #ff0000, #800000); height: 10px; width: 100px;"></div>
                <small>Min: {z_min:.2f} | Max: {z_max:.2f}</small>
                </div>
                """
                m.get_root().html.add_child(folium.Element(legend_html))
                
                st_folium(m, height=500, use_container_width=True)
                
            except Exception as e:
                st.error(f"Erro visual: {e}")
