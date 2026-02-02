import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf

# --- 1. CONFIGURAÇÃO DE ESTADO E PERSISTÊNCIA ---
if 'gerar_fertilidade' not in st.session_state:
    st.session_state.gerar_fertilidade = False

# --- 2. MOTOR GEOESTATÍSTICO (PROIBIDO PROCESSAR SEM GATILHO) ---
@st.cache_data(show_spinner="Executando Krigagem de Alta Precisão...")
def motor_krigagem_v43(df, coluna):
    """
    Interpolação Rbf Linear com Grid de 150x150.
    Garante o preenchimento total e manchas suaves.
    """
    x, y, z = df['longitude'].values, df['latitude'].values, df[coluna].values
    
    # Grid denso para evitar pixelização
    xi = np.linspace(x.min(), x.max(), 150)
    yi = np.linspace(y.min(), y.max(), 150)
    xi, yi = np.meshgrid(xi, yi)
    
    # Algoritmo de Krigagem (Rbf)
    rbf = Rbf(x, y, z, function='linear')
    zi = rbf(xi, yi)
    return xi, yi, zi

# --- 3. COMPONENTE DE RENDERIZAÇÃO (OPACIDADE 1.0 E RIGOR GEOMÉTRICO) ---
def renderizar_mapa_triade(df, coluna, geojson_data):
    """
    Aplica Opacidade 1.0, Contorno Preto e Escala Jet Saturada.
    """
    # Blindagem de Erro: Validação de Coluna
    if coluna not in df.columns:
        st.warning(f"⚠️ Atributo '{coluna}' ausente na planilha original.")
        return

    # Processamento pesado isolado pelo cache
    xi, yi, zi = motor_krigagem_v43(df, coluna)

    fig = go.Figure()

    # Camada de Dados: Opacidade Total (Alpha=1.0)
    fig.add_trace(go.Heatmap(
        z=zi, x=xi[0, :], y=yi[:, 0],
        colorscale='Jet',
        opacity=1.0,
        zsmooth=False, # Mantém as divisas de cores visíveis
        colorbar=dict(title=dict(text=f"<b>{coluna}</b>", font={"size":14}), thickness=20)
    ))

    # Camada de Contorno: Leitura Resiliente (Polygon/MultiPolygon)
    if geojson_data:
        try:
            feature = geojson_data['features'][0]
            geom = feature['geometry']
            # Extração dinâmica de coordenadas
            coords
