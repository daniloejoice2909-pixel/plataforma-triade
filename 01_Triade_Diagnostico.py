import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
from io import BytesIO

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
# 1. CONFIGURAÇÃO INICIAL (Protocolo v43.1)
# ==============================================================================
configurar_pagina("Diagnóstico de Solo")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Diagnóstico de Fertilidade (App 1)")
st.markdown("""
> **Protocolo v43.1:** Este ambiente é dedicado ao **Processamento Pesado**. 
> Aqui realizamos a validação dos dados de laboratório e a geração das matrizes interpoladas.
""")

# ==============================================================================
# 2. INPUT DE DADOS (SIDEBAR)
# ==============================================================================
st.sidebar.header("1. Arquivos de Entrada")

if file_csv and file_geojson:
    # Carregamento Blindado
    df_raw = carregar_dados_blindado(file_csv)
    
    # --- CORREÇÃO DE NOMES (NOVO) ---
    # Isso padroniza qualquer jeito que a lat/lon esteja escrita para o padrão do sistema
    df_raw = df_raw.rename(columns={
        'Lat': 'latitude', 'LAT': 'latitude', 'lat': 'latitude', 'LATITUDE': 'latitude',
        'Lon': 'longitude', 'LON': 'longitude', 'lon': 'longitude', 'LONGITUDE': 'longitude', 'long': 'longitude'
    })
    # -------------------------------

    geojson_data = json.load(file_geojson)
    st.session_state['geojson_data'] = geojson_data
    
    # Validação Básica de Colunas
    cols_geo = ['latitude', 'longitude']
    # ... resto do código continua igual
# Upload do GeoJSON
file_geojson = st.sidebar.file_uploader("🌍 Contorno do Talhão (.geojson)", type=["geojson", "json"])

# Inicialização de Session State para persistência
if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None

# ==============================================================================
# 3. MOTOR GEOESTATÍSTICO (Núcleo Pesado)
# ==============================================================================
from pykrige.ok import OrdinaryKriging
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd

@st.cache_data(show_spinner="⚙️ Processando Geoestatística (Protocolo v43)...")
def processar_matrizes_interpolacao(df, geojson_data, resolucao_grid=150):
    """
    Executa Krigagem Ordinária para todas as colunas numéricas e
    aplica o recorte (mask) do talhão para não gerar mapas quadrados.
    """
    # 1. Preparação do Grid (Grade de Pontos)
    # Define os limites baseados nos dados ou no contorno (preferência pelos dados para margem)
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    
    # Adiciona uma pequena margem (buffer) para garantir que cobre as bordas
    buffer = 0.001 
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    # 2. Criação da Máscara do Polígono (O "Cortador de Biscoito")
    # Transforma o GeoJSON em um objeto Path do Matplotlib para verificação rápida
    try:
        coords_poligono = geojson_data['features'][0]['geometry']['coordinates'][0]
        poligono_path = MplPath(coords_poligono)
        
        # Gera a malha 2D para verificar ponto a ponto
        xx, yy = np.meshgrid(grid_x, grid_y)
        points_flat = np.vstack((xx.flatten(), yy.flatten())).T
        
        # Cria a máscara booleana (True = Dentro do talhão, False = Fora)
        mask = poligono_path.contains_points(points_flat)
        # Remodela para o formato do grid (matriz)
        mask_matrix = mask.reshape(xx.shape)
        
    except Exception as e:
        st.error(f"Erro ao processar contorno do GeoJSON: {e}")
        return None

    # DataFrame final que vai guardar tudo
    df_result = pd.DataFrame({
        'latitude': yy.flatten(),
        'longitude': xx.flatten()
    })

    # 3. Loop de Krigagem (Blindado)
    # Lista de colunas para ignorar (não são nutrientes)
    cols_ignorar = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y']
    cols_para_interpolar = [c for c in df.columns if c.lower() not in cols_ignorar]

    for col in cols_para_interpolar:
        try:
            # Pega os dados limpos (remove NaNs dessa coluna específica se houver)
            dados_coluna = df[['longitude', 'latitude', col]].dropna()
            
            if len(dados_coluna) < 5: # Proteção: Krigagem precisa de mínimo de pontos
                continue

            # Configura o Modelo de Krigagem Ordinária
            OK = OrdinaryKriging(
                dados_coluna['longitude'], 
                dados_coluna['latitude'], 
                dados_coluna[col], 
                variogram_model='linear', # Ou 'spherical', ajustável se quiser evoluir
                verbose=False, 
                enable_plotting=False
            )
            
            # Executa a interpolação no Grid
            z, ss = OK.execute('grid', grid_x, grid_y)
            
            # Aplica a MÁSCARA (Zera o que está fora do talhão)
            # O PyKrige devolve um MaskedArray, mas forçamos nossa máscara geométrica
            z_data = z.data # Pega os dados brutos
            z_data[~mask_matrix] = np.nan # Aplica NaN onde está fora do polígono
            
            # Salva no DataFrame (achatando a matriz 2D para coluna 1D)
            df_result[col] = z_data.flatten()
            
        except Exception as e:
            # Não trava o app se um atributo falhar (ex: coluna vazia)
            print(f"Aviso: Não foi possível interpolar {col}. Erro: {e}")

    # 4. Limpeza Final (Remove linhas que são puramente NaN fora do mapa)
    # Isso deixa o arquivo muito mais leve para o App 2
    df_final = df_result.dropna(subset=cols_para_interpolar, how='all')
    
    return df_final

# ==============================================================================
# 4. LÓGICA DE EXECUÇÃO
# ==============================================================================

if file_csv and file_geojson:
    # Carregamento Blindado
    df_raw = carregar_dados_blindado(file_csv)
    geojson_data = json.load(file_geojson)
    st.session_state['geojson_data'] = geojson_data
    
    # Validação Básica de Colunas
    cols_geo = ['latitude', 'longitude']
    valido, faltantes = validar_colunas(df_raw, cols_geo)
    
    if not valido:
        st.error(f"Erro: Seu CSV não tem as colunas de coordenadas: {faltantes}")
    else:
        st.success(f"✅ Arquivos Carregados. {len(df_raw)} pontos de amostragem identificados.")
        
        # --- BOTÃO GATILHO (Protocolo v43) ---
        col_btn, col_info = st.columns([1, 2])
        if col_btn.button("🚀 Processar Matrizes de Solo", type="primary"):
            try:
                # Chama a função pesada (que tem @st.cache_data)
                df_krig = processar_matrizes_interpolacao(df_raw)
                st.session_state['dados_processados'] = df_krig
                st.toast("Processamento Concluído com Sucesso!", icon="✅")
            except Exception as e:
                st.error(f"Erro na Krigagem: {e}")

# ==============================================================================
# 5. VISUALIZAÇÃO E EXPORTAÇÃO (A PONTE)
# ==============================================================================

if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados']
    
    st.divider()
    st.subheader("📊 Validação Visual dos Mapas")
    
    # Seletor de visualização (para não renderizar 10 mapas de uma vez e travar o browser aqui também)
    cols_disponiveis = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    atributo_selecionado = st.selectbox("Selecione o Atributo para Conferência:", cols_disponiveis)
    
    # Plotagem Única de Conferência
    if atributo_selecionado:
        fig = go.Figure(go.Heatmap(
            lon=df_final['longitude'], 
            lat=df_final['latitude'], 
            z=df_final[atributo_selecionado],
            colorscale='Jet',
            opacity=1.0, # Regra v43
            zsmooth='best',
            colorbar=dict(title=atributo_selecionado)
        ))
        
        # Aplica Layout v43 (Aspect Ratio e Mapbox)
        fig = aplicar_layout_v43(fig, f"Mapa de {atributo_selecionado}")
        fig = adicionar_contorno_preto(fig, st.session_state['geojson_data'])
        
        st.plotly_chart(fig, use_container_width=True, key="mapa_diagnostico")
    
    st.divider()
    
    # --- ÁREA DE EXPORTAÇÃO DA PONTE ---
    st.info("🏁 **Próximo Passo:** Exporte os dados processados para usar no App de Prescrição.")
    
    c1, c2 = st.columns(2)
    
    # Conversão para CSV em memória
    csv_buffer = df_final.to_csv(index=False).encode('utf-8')
    
    c1.download_button(
        label="💾 Baixar ARQUIVO PONTE (.csv)",
        data=csv_buffer,
        file_name="ponte_triade_solo.csv",
        mime="text/csv",
        help="Use este arquivo no App 02 - Prescrição",
        type="primary"
    )
    
    c2.markdown("""
    **O que este arquivo contém?**
    * Coordenadas densas (Grid interpolado).
    * Valores de Argila, pH, P, K, etc. já calculados.
    * Pronto para gerar Zonas de Manejo.
    """)

elif file_csv:
    st.info("👆 Clique no botão 'Processar Matrizes' para iniciar a Geoestatística.")
