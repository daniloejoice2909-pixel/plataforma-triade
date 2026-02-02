import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf

# --- 1. CONFIGURAÇÕES DE PÁGINA E ESTADO ---
st.set_page_config(layout="wide", page_title="Tríade Agro - VRT")

if 'gerar_fertilidade' not in st.session_state:
    st.session_state.gerar_fertilidade = False

# --- 2. MOTOR GEOESTATÍSTICO (PROCESSAMENTO PESADO) ---
@st.cache_data(show_spinner="Processando Krigagem (150x150)...")
def motor_interpolacao_v43(df, coluna, pontos=150):
    """Gera a malha de interpolação com rigor de 150x150 pontos."""
    x = df['longitude'].values
    y = df['latitude'].values
    z = df[coluna].values
    
    # Criar grid cobrindo a área total
    xi = np.linspace(x.min(), x.max(), pontos)
    yi = np.linspace(y.min(), y.max(), pontos)
    xi, yi = np.meshgrid(xi, yi)
    
    # RBF Linear para 'Manchas Suaves'
    rbf = Rbf(x, y, z, function='linear')
    zi = rbf(xi, yi)
    return xi, yi, zi

# --- 3. COMPONENTE DE MAPA DE ALTA DEFINIÇÃO ---
def plotar_mapa_triade(df, coluna, geojson_contorno):
    """Renderiza o mapa com opacidade 1.0 e contorno preto sólido."""
    if coluna not in df.columns:
        st.warning(f"⚠️ Atributo '{coluna}' não encontrado na planilha.")
        return

    xi, yi, zi = motor_interpolacao_v43(df, coluna)

    fig = go.Figure()

    # Camada Heatmap: Opacidade Total
    fig.add_trace(go.Heatmap(
        z=zi, x=xi[0, :], y=yi[:, 0],
        colorscale='Jet',
        opacity=1.0, # Rigor V43
        zsmooth=False, # Divisas visíveis
        colorbar=dict(title=f"<b>{coluna}</b>", thickness=15)
    ))

    # Camada de Contorno GeoJSON: Preto Sólido
    if geojson_contorno:
        # Assumindo estrutura padrão de GeoJSON Features
        coords = geojson_contorno['features'][0]['geometry']['coordinates'][0]
        lons, lats = zip(*coords)
        fig.add_trace(go.Scattermapbox(
            lon=lons, lat=lats, mode='lines',
            line=dict(width=3, color='black'),
            name='Contorno'
        ))

    # Layout com Razão de Aspecto Fixa (Rigor Geométrico)
    fig.update_layout(
        mapbox=dict(
            style="satellite",
            center={"lat": df['latitude'].mean(), "lon": df['longitude'].mean()},
            zoom=15
        ),
        margin={"r":0,"t":30,"l":
