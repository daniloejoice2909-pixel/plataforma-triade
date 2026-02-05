import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
from pykrige.ok import OrdinaryKriging
from matplotlib.path import Path as MplPath
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
import folium
from folium import plugins
from streamlit_folium import st_folium
import base64

# Importando nossa caixa de ferramentas v43
from utils_v43 import (
    configurar_pagina, 
    renderizar_cabecalho_sidebar, 
    carregar_dados_blindado, 
    validar_colunas
)

# ==============================================================================
# 1. CONFIGURAÇÃO E INICIALIZAÇÃO
# ==============================================================================
configurar_pagina("Diagnóstico de Solo")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Diagnóstico de Fertilidade (App 1)")

if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None

# ==============================================================================
# 2. KRIGAGEM (MATRIZ PURA)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Processando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    # --- ETAPA 1: LIMPEZA ---
    df = df_input.copy() 
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao']
    cols_validas = []
    
    for col in df.columns:
        if col.lower() in cols_proibidas:
            continue
        try:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].notna().sum() > 5:
                cols_validas.append(col)
        except Exception:
            pass 

    # --- ETAPA 2: GRID E MÁSCARA ---
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    
    # Buffer para garantir que a imagem cubra tudo (o recorte vem depois)
    buffer = 0.002 
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    try:
        coords_poligono = geojson_data['features'][0]['geometry']['coordinates'][0]
        poligono_path = MplPath(coords_poligono)
        
        xx, yy = np.meshgrid(grid_x, grid_y)
        points_flat = np.vstack((xx.flatten(), yy.flatten())).T
        
        mask = poligono_path.contains_points(points_flat)
        mask_matrix = mask.reshape(xx.shape)
        
    except Exception as e:
        st.error(f"Erro ao processar contorno do GeoJSON: {e}")
        return None

    df_result = pd.DataFrame({
        'latitude': yy.flatten(),
        'longitude': xx.flatten()
    })

    # --- ETAPA 3: INTERPOLAÇÃO ---
    for col in cols_validas:
        try:
            dados_coluna = df[['longitude', 'latitude', col]].dropna()
            
            if len(dados_coluna) < 5: 
                continue

            OK = OrdinaryKriging(
                dados_coluna['longitude'], 
                dados_coluna['latitude'], 
                dados_coluna[col], 
                variogram_model='linear', 
                verbose=False, 
                enable_plotting=False
            )
            
            z, ss = OK.execute('grid', grid_x, grid_y)
            z_data = z.data 
            z_data[~mask_matrix] = np.nan 
            
            df_result[col] = z_data.flatten()
            
        except Exception as e:
            print(f"Aviso: Falha ao interpolar {col}: {e}")

    df_final = df_result.dropna(subset=cols_validas, how='all')
    return df_final

# ==============================================================================
# 3. FUNÇÃO DE GERAÇÃO DE IMAGEM (CORRIGIDA PARA MATPLOTLIB NOVO)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data):
    """
    Gera uma imagem PNG com curvas de nível suaves e recorte perfeito.
    """
    # 1. Pivotar dados
    pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
    Z = pivot.values
    X = pivot.columns.values # Longitude
    Y = pivot.index.values   # Latitude
    
    # 2. Configurar Cores InCeres
    colors = ['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850'] 
    cmap = mcolors.ListedColormap(colors)
    bounds = np.linspace(np.nanmin(Z), np.nanmax(Z), 6)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # 3. Criar Figura
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_axis_off()
    
    # 4. Desenhar Curvas de Nível
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both')
    
    # 5. MÁGICA DO RECORTE (CLIPPING) - BLINDADO
    coords = geojson_data['features'][0]['geometry']['coordinates'][0]
    poly_path = MplPath(coords)
    patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', edgecolor='black', linewidth=2)
    ax.add_patch(patch)
    
    # --- CORREÇÃO DO ERRO AQUI ---
    # Verifica se é versão antiga (.collections) ou nova (set_clip_path direto)
    if hasattr(cf, 'collections'):
        for collection in cf.collections:
            collection.set_clip_path(patch)
    else:
        try:
            # Tenta aplicar direto no objeto (Matplotlib 3.8+)
            cf.set_clip_path(patch)
        except Exception:
            pass # Se falhar, segue sem clip (mas geralmente funciona)

    # 6. Ajustar limites
    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    
    # 7. Salvar
    img_data = BytesIO()
    plt.savefig(img_data, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=150)
    plt.close(fig)
    img_data.seek(0)
    
    return img_data, [[Y.min(), X.min()], [Y.max(), X.max()]], bounds

# ==============================================================================
# 4. INPUT DE DADOS
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")

file_csv = st.sidebar.file_uploader("📂 Tabela de Solo (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno do Talhão (.geojson)", type=["geojson", "json"])

# ==============================================================================
# 5. PROCESSAMENTO
# ==============================================================================
if file_csv and file_geojson:
    df_raw = carregar_dados_blindado(file_csv)
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]

    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
    except Exception:
        try:
            file_geojson.seek(0)
            conteudo = file_geojson.getvalue().decode("utf-8")
            geojson_data = json.loads(conteudo)
        except Exception as e:
            st.error(f"❌ GeoJSON inválido: {e}")
            st.stop()
            
    st.session_state['geojson_data'] = geojson_data

    # Validação
    st.info("📍 Validação de Coordenadas:")
    c1, c2 = st.columns(2)
    idx_lat = list(df_raw.columns).index('latitude') if 'latitude' in df_raw.columns else 0
    idx_lon = list(df_raw.columns).index('longitude') if 'longitude' in df_raw.columns else 1 if len(df_raw.columns) > 1 else 0

    with c1:
        lat_col = st.selectbox("Coluna LATITUDE (Y):", df_raw.columns, index=idx_lat)
    with c2:
        lon_col = st.selectbox("Coluna LONGITUDE (X):", df_raw.columns, index=idx_lon)
        
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    valido, faltantes = validar_colunas(df_raw, ['latitude', 'longitude'])
    
    if valido:
        col_btn, _ = st.columns([1, 2])
        if col_btn.button("🚀 Processar Matrizes de Solo", type="primary"):
            try:
                df_krig = processar_matrizes_interpolacao(df_raw, geojson_data, resolucao_grid=150)
                st.session_state['dados_processados'] = df_krig
                st.toast("Processamento Concluído!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Erro fatal na Krigagem: {e}")

# ==============================================================================
# 6. VISUALIZAÇÃO FOLIUM (V55)
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    
    st.divider()
    
    # --- DOWNLOAD ---
    c_down1, c_down2 = st.columns([2, 1])
    with c_down1:
        st.subheader("🏁 1. Exportação")
        st.info("Baixe o arquivo PONTE para usar no App de Prescrição.")
    with c_down2:
        st.write("") 
        st.write("") 
        csv_ponte = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("💾 BAIXAR ARQUIVO PONTE", csv_ponte, "ponte_triade.csv", "text/csv", type="primary", use_container_width=True)

    st.divider()

    # --- MAPA VISUAL ---
    st.subheader("📊 2. Validação Visual (Padrão Folium)")
    
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver, key='seletor_folium')
        df_final[atributo] = pd.to_numeric(df_final[atributo], errors='coerce')
        df_plot = df_final.dropna(subset=[atributo, 'latitude', 'longitude'])
        
        if not df_plot.empty:
            try:
                # 1. Gerar a Imagem (Overlay) com Recorte Perfeito
                img_buffer, bounds, intervals = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'])
                
                # 2. Configurar Mapa Folium
                centro_lat = df_plot['latitude'].mean()
                centro_lon = df_plot['longitude'].mean()
                
                m = folium.Map(
                    location=[centro_lat, centro_lon],
                    zoom_start=14,
                    # Tiles do Google Satellite (Alta Resolução)
                    tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                    attr='Google',
                    name='Satélite'
                )

                # 3. Adicionar a Imagem Overlay
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                img_url = f"data:image/png;base64,{img_b64}"
                
                folium.raster_layers.ImageOverlay(
                    image=img_url,
                    bounds=bounds,
                    opacity=0.8, 
                    name=f"Mapa de {atributo}"
                ).add_to(m)

                # 4. Adicionar Contorno Preto (GeoJSON)
                folium.GeoJson(
                    st.session_state['geojson_data'],
                    style_function=lambda x: {'color': 'black', 'weight': 3, 'fillOpacity': 0}
                ).add_to(m)

                # 5. Legenda HTML
                colors_hex = ['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850']
                legend_html = f"""
                <div style="position: fixed; bottom: 50px; right: 50px; z-index:9999; font-size:14px; background-color: white; padding: 10px; border-radius: 5px; border: 2px solid grey;">
                <b>{atributo}</b><br>
                <i style="background: {colors_hex[4]}; width: 15px; height: 15px; display: inline-block;"></i> > {intervals[4]:.2f}<br>
                <i style="background: {colors_hex[3]}; width: 15px; height: 15px; display: inline-block;"></i> {intervals[3]:.2f} - {intervals[4]:.2f}<br>
                <i style="background: {colors_hex[2]}; width: 15px; height: 15px; display: inline-block;"></i> {intervals[2]:.2f} - {intervals[3]:.2f}<br>
                <i style="background: {colors_hex[1]}; width: 15px; height: 15px; display: inline-block;"></i> {intervals[1]:.2f} - {intervals[2]:.2f}<br>
                <i style="background: {colors_hex[0]}; width: 15px; height: 15px; display: inline-block;"></i> < {intervals[1]:.2f}
                </div>
                """
                m.get_root().html.add_child(folium.Element(legend_html))
                
                folium.LayerControl().add_to(m)

                # 6. Renderizar
                st_folium(m, width=None, height=550)
                
                # Estatísticas
                st.markdown(
                    f"""
                    <div style="text-align: center; margin-top: 10px; padding: 10px; background-color: #f0f2f6; border-radius: 5px;">
                    <b>Estatísticas do Talhão:</b> 
                    🔴 Min: {df_plot[atributo].min():.2f} | 
                    🟡 Méd: {df_plot[atributo].mean():.2f} | 
                    🟢 Max: {df_plot[atributo].max():.2f}
                    </div>
                    """, unsafe_allow_html=True
                )

            except Exception as e:
                st.error(f"Erro na renderização Folium: {e}")
        else:
            st.warning("Atributo vazio.")

elif file_csv:
    st.info("👆 Clique no botão 'Processar Matrizes' para iniciar.")
