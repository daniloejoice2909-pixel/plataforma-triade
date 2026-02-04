import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
from io import BytesIO
from pykrige.ok import OrdinaryKriging
from matplotlib.path import Path as MplPath

# Importando nossa caixa de ferramentas v43
from utils_v43 import (
    configurar_pagina, 
    renderizar_cabecalho_sidebar, 
    carregar_dados_blindado, 
    validar_colunas, 
    aplicar_layout_v43, 
    adicionar_contorno_preto
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
# 2. DEFINIÇÃO DA FUNÇÃO DE KRIGAGEM (REVISADA)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Processando Geoestatística (Protocolo v43)...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    # --- ETAPA 1: LIMPEZA NUMÉRICA ---
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
    
    buffer = 0.001 
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

    # --- ETAPA 3: INTERPOLAÇÃO (BLOCO CRÍTICO) ---
    for col in cols_validas:
        # AQUI COMEÇA O BLOCO TRY QUE ESTAVA DANDO ERRO
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
            # O EXCEPT AGORA ESTÁ ALINHADO PERFEITAMENTE COM O TRY
            print(f"Aviso: Falha ao interpolar {col}: {e}")

    df_final = df_result.dropna(subset=cols_validas, how='all')
    return df_final

# ==============================================================================
# 3. INPUT DE DADOS
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")

file_csv = st.sidebar.file_uploader("📂 Tabela de Solo (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno do Talhão (.geojson)", type=["geojson", "json"])

# ==============================================================================
# 4. LÓGICA DE CARREGAMENTO
# ==============================================================================
if file_csv and file_geojson:
    df_raw = carregar_dados_blindado(file_csv)
    # Remove espaços em branco dos nomes das colunas
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
        st.success(f"✅ Arquivos Prontos: {len(df_raw)} pontos.")
        
        col_btn, _ = st.columns([1, 2])
        if col_btn.button("🚀 Processar Matrizes de Solo", type="primary"):
            try:
                df_krig = processar_matrizes_interpolacao(df_raw, geojson_data)
                st.session_state['dados_processados'] = df_krig
                st.toast("Krigagem concluída!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Erro fatal na Krigagem: {e}")
    else:
        st.error(f"Faltam colunas: {faltantes}")

# ==============================================================================
# 5. EXPORTAÇÃO E VISUALIZAÇÃO (COM DIAGNÓSTICO DE MAPA VAZIO)
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
        st.download_button(
            label="💾 BAIXAR ARQUIVO PONTE",
            data=csv_ponte,
            file_name="ponte_triade_solo.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )

    st.divider()

    # --- VISUALIZAÇÃO ---
    st.subheader("📊 2. Validação Visual")
    
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver)
        
        # Limpeza e Conversão
        df_final[atributo] = pd.to_numeric(df_final[atributo], errors='coerce')
        df_plot = df_final.dropna(subset=[atributo, 'latitude', 'longitude'])
        
        if not df_plot.empty:
            # --- ÁREA DE DIAGNÓSTICO (PARA VOCÊ VER O ERRO) ---
            with st.expander("🕵️‍♂️ Clique aqui se o mapa estiver vazio (Raio-X dos Dados)", expanded=False):
                st.write("**O que o Python está tentando plotar:**")
                st.dataframe(df_plot[['latitude', 'longitude', atributo]].head())
                
                lat_min = df_plot['latitude'].min()
                lon_min = df_plot['longitude'].min()
                st.write(f"📍 Latitude Média: {lat_min:.5f} | Longitude Média: {lon_min:.5f}")
                
                if lat_min > 0:
                    st.warning("⚠️ ALERTA: Latitude Positiva detectada! Se for no Brasil, deveria ser NEGATIVA (ex: -18.0).")
                if abs(lat_min) > 90 or abs(lon_min) > 180:
                    st.error("❌ ERRO CRÍTICO: Coordenadas parecem estar em UTM (milhares/milhões). O mapa só aceita Graus Decimais (Lat/Lon).")

            try:
                # Centro dinâmico baseado nos PONTOS (não no GeoJSON)
                centro_lat = df_plot['latitude'].mean()
                centro_lon = df_plot['longitude'].mean()

                fig = go.Figure(go.Scattermapbox(
                    lat=df_plot['latitude'], 
                    lon=df_plot['longitude'], 
                    mode='markers',
                    marker=dict(
                        size=8, # Aumentei o tamanho para garantir visibilidade
                        color=df_plot[atributo],
                        colorscale='Jet',
                        opacity=0.9,
                        showscale=True,
                        colorbar=dict(title=atributo)
                    ),
                    text=df_plot[atributo].apply(lambda x: f"{x:.2f}"),
                    hoverinfo='lat+lon+text'
                ))
                
                # Layout forçando o foco nos pontos
                fig.update_layout(
                    mapbox=dict(
                        style="carto-positron", # Fundo leve para destacar os pontos (pode mudar para satélite depois)
                        center=dict(lat=centro_lat, lon=centro_lon),
                        zoom=12
                    ),
                    margin={"r":0,"t":30,"l":0,"b":0},
                    height=500
                )
                
                # Adiciona GeoJSON apenas como referência (linha preta)
                if st.session_state['geojson_data']:
                    fig = adicionar_contorno_preto(fig, st.session_state['geojson_data'])
                
                st.plotly_chart(fig, use_container_width=True, key=f"mapa_{atributo}")
            
            except Exception as e:
                st.error(f"Erro visual: {e}")
        else:
            st.warning(f"O atributo '{atributo}' está vazio.")
    else:
        st.warning("Sem dados numéricos para exibir.")

    # --- MAPA (VALIDAÇÃO) ---
    st.subheader("📊 2. Validação Visual")
    
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver)
        
        df_final[atributo] = pd.to_numeric(df_final[atributo], errors='coerce')
        df_plot = df_final.dropna(subset=[atributo, 'latitude', 'longitude'])
        
        if not df_plot.empty:
            try:
                fig = go.Figure(go.Scattermapbox(
                    lat=df_plot['latitude'], 
                    lon=df_plot['longitude'], 
                    mode='markers',
                    marker=dict(
                        size=6, 
                        color=df_plot[atributo],
                        colorscale='Jet',
                        opacity=0.8,
                        showscale=True,
                        colorbar=dict(title=atributo)
                    ),
                    text=df_plot[atributo].apply(lambda x: f"{x:.2f}"),
                    hoverinfo='lat+lon+text'
                ))
                
                fig = aplicar_layout_v43(fig, f"Diagnóstico: {atributo}")
                
                if st.session_state['geojson_data']:
                    fig = adicionar_contorno_preto(fig, st.session_state['geojson_data'])
                
                st.plotly_chart(fig, use_container_width=True, key=f"mapa_{atributo}")
            
            except Exception as e:
                st.error(f"Erro visual: {e}")
        else:
            st.warning(f"O atributo '{atributo}' está vazio.")
    else:
        st.warning("Sem dados numéricos para exibir.")

elif file_csv:
    st.info("👆 Clique no botão 'Processar Matrizes' para iniciar.")
