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

# Upload do CSV
file_csv = st.sidebar.file_uploader("📂 Tabela de Solo (.csv)", type=["csv"])
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
@st.cache_data(show_spinner="Rodando Krigagem (Protocolo v43)...")
def processar_matrizes_interpolacao(df, resolucao_grid=150):
    """
    Simula/Executa a Krigagem para TODAS as colunas numéricas relevantes.
    RETORNA: Um DataFrame denso com Lat/Lon e valores interpolados.
    """
    # 1. Identificar colunas interpoláveis (Numéricas)
    cols_para_interpolar = [c for c in df.columns if c not in ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude']]
    
    # [SIMULAÇÃO DA KRIGAGEM PARA EXEMPLO] 
    # No seu código real, aqui entram suas funções do PyKrige ou SciKit-Learn.
    # Vou criar um Grid fictício para o código rodar e você ver a exportação funcionando.
    
    # Criando grid baseado nas coordenadas min/max do input
    # (Adapte isso para usar seu algoritmo real de grid + máscara do polígono)
    lat_min, lat_max = df['latitude'].min(), df['latitude'].max()
    lon_min, lon_max = df['longitude'].min(), df['longitude'].max()
    
    lats = np.linspace(lat_min, lat_max, resolucao_grid)
    lons = np.linspace(lon_min, lon_max, resolucao_grid)
    grid_lat, grid_lon = np.meshgrid(lats, lons)
    
    df_result = pd.DataFrame({
        'latitude': grid_lat.flatten(),
        'longitude': grid_lon.flatten()
    })
    
    # Interpolação (Simulada com Nearest para performance do exemplo)
    from scipy.interpolate import griddata
    points = df[['longitude', 'latitude']].values
    
    for col in cols_para_interpolar:
        values = df[col].values
        # Bloco Try para evitar crash em coluna com NaN
        try:
            grid_z = griddata(points, values, (grid_lon, grid_lat), method='linear')
            df_result[col] = grid_z.flatten()
        except Exception as e:
            pass # Ignora colunas problemáticas
            
    # Remove NaNs gerados fora do convex hull (opcional)
    df_result = df_result.dropna()
    
    return df_result

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
