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
# 2. DEFINIÇÃO DA FUNÇÃO DE KRIGAGEM (V51 - LEVE E RÁPIDA)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Processando Geoestatística Otimizada (150x)...")
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
    
    # Buffer calibrado para 150x150
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

            # Variograma Linear (Mais rápido e robusto para evitar travamentos)
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
                # Processamento Leve (150x)
                df_krig = processar_matrizes_interpolacao(df_raw, geojson_data)
                st.session_state['dados_processados'] = df_krig
                st.toast("Mapas Gerados (Modo Performance)!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Erro fatal na Krigagem: {e}")
    else:
        st.error(f"Faltam colunas: {faltantes}")

# ==============================================================================
# 5. VISUALIZAÇÃO LEVE COM ESTÉTICA INCERES (V51)
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

    # --- MAPA VISUAL ---
    st.subheader("📊 2. Validação Visual")
    
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver, key='seletor_atributo_final')
        
        # Limpeza
        df_final[atributo] = pd.to_numeric(df_final[atributo], errors='coerce')
        df_plot = df_final.dropna(subset=[atributo, 'latitude', 'longitude'])
        
        if not df_plot.empty:
            
            val_min = df_plot[atributo].min()
            val_max = df_plot[atributo].max()
            val_med = df_plot[atributo].mean()

            # --- PALETA "HARD BREAKS" (InCeres) ---
            colorscale_inceres = [
                [0.0, '#d73027'], [0.2, '#d73027'], # Vermelho
                [0.2, '#fc8d59'], [0.4, '#fc8d59'], # Laranja
                [0.4, '#fee08b'], [0.6, '#fee08b'], # Amarelo
                [0.6, '#91cf60'], [0.8, '#91cf60'], # Verde Claro
                [0.8, '#1a9850'], [1.0, '#1a9850']  # Verde Escuro
            ]

            try:
                centro_lat = df_plot['latitude'].mean()
                centro_lon = df_plot['longitude'].mean()

                fig = go.Figure(go.Scattermapbox(
                    lat=df_plot['latitude'], 
                    lon=df_plot['longitude'], 
                    mode='markers', 
                    marker=dict(
                        # --- CALIBRAÇÃO PERFEITA 150x ---
                        # Size=22 garante cobertura sem travar
                        size=22,             
                        color=df_plot[atributo],
                        colorscale=colorscale_inceres,
                        cmin=val_min,
                        cmax=val_max,
                        opacity=1.0,        # Sólido
                        showscale=True,
                        colorbar=dict(
                            title=dict(text=atributo, font=dict(size=12)),
                            tickfont=dict(size=10),
                            len=0.7,
                            thickness=20,
                            x=1.02
                        )
                    ),
                    text=df_plot[atributo].apply(lambda x: f"{x:.2f}"),
                    hoverinfo='text' 
                ))
                
                # Layout V51: 'open-street-map' é o mais leve que existe.
                fig.update_layout(
                    mapbox=dict(
                        style="open-street-map", 
                        center=dict(lat=centro_lat, lon=centro_lon),
                        zoom=13.5
                    ),
                    margin={"r":0,"t":0,"l":0,"b":0},
                    height=550
                )
                
                if st.session_state['geojson_data']:
                    fig = adicionar_contorno_preto(fig, st.session_state['geojson_data'])
                
                st.plotly_chart(fig, use_container_width=True, key=f"mapa_render_{atributo}")
                
                # --- PAINEL ESTATÍSTICO ---
                st.markdown(
                    f"""
                    <div style="
                        background-color: #ffffff; 
                        padding: 15px; 
                        border-radius: 8px; 
                        text-align: center; 
                        font-size: 16px; 
                        color: #333;
                        margin-top: 5px;
                        border-left: 5px solid #1a9850;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        border: 1px solid #e0e0e0;">
                        <b>📏 Estatísticas do Talhão ({atributo}):</b> <br>
                        🔴 Min: <b>{val_min:.2f}</b> &nbsp;|&nbsp; 
                        🟡 Méd: <b>{val_med:.2f}</b> &nbsp;|&nbsp; 
                        🟢 Max: <b>{val_max:.2f}</b>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            except Exception as e:
                st.error(f"Erro visual: {e}")
        else:
            st.warning(f"O atributo '{atributo}' ficou
