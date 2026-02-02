import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf

# --- 1. MOTOR DE CÁLCULO (Blindagem de Processamento) ---
@st.cache_data(show_spinner="Calculando Interpolação Geoestatística...")
def motor_krigagem_v43(df, coluna):
    """Executa Krigagem Rbf Linear com Grid 150x150."""
    x, y, z = df['longitude'].values, df['latitude'].values, df[coluna].values
    xi = np.linspace(x.min(), x.max(), 150)
    yi = np.linspace(y.min(), y.max(), 150)
    xi, yi = np.meshgrid(xi, yi)
    
    rbf = Rbf(x, y, z, function='linear')
    zi = rbf(xi, yi)
    return xi, yi, zi

# --- 2. COMPONENTE DE RENDERIZAÇÃO (Padrão InCeres/Tríade) ---
def renderizar_mapa_triade(df, coluna, geojson_data):
    """Renderiza mapa opaco com contorno preto sólido e imagem de satélite."""
    # Validação de Coluna (Protocolo de Segurança)
    if coluna not in df.columns:
        st.warning(f"⚠️ Atributo '{coluna}' não encontrado na planilha.")
        return

    xi, yi, zi = motor_krigagem_v43(df, coluna)
    fig = go.Figure()

    # Camada de Dados (Saturada e Opaca)
    fig.add_trace(go.Heatmap(
        z=zi, x=xi[0, :], y=yi[:, 0],
        colorscale='Jet',
        opacity=1.0, 
        zsmooth=False, # Garante divisas nítidas
        colorbar=dict(title=dict(text=f"<b>{coluna}</b>", font={"size":12}), thickness=15)
    ))

    # Camada de Contorno (Rigor Geoespacial)
    if geojson_data:
        try:
            feature = geojson_data['features'][0]
            geom = feature['geometry']
            # Suporte a Polygon e MultiPolygon
            coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
            lons, lats = zip(*coords)
            
            fig.add_trace(go.Scattermapbox(
                lon=lons, lat=lats, mode='lines',
                line=dict(width=3, color='black'),
                name='Contorno'
            ))
        except Exception as e:
            st.error(f"Erro na geometria do GeoJSON: {e}")

    # Layout Travado (Razão de Aspecto 1:1)
    fig.update_layout(
        mapbox={
            "style": "satellite",
            "center": {"lat": df['latitude'].mean(), "lon": df['longitude'].mean()},
            "zoom": 15
        },
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        height=450,
        yaxis={"scaleanchor": "x", "scaleratio": 1}
    )
    
    # Renderização com Chave Única (Evita travamento de ID)
    st.plotly_chart(fig, use_container_width=True, key=f"v43_grid_{coluna}")
    
    # Box Informativo Mandatório
    st.info(f"📊 **{coluna}**
