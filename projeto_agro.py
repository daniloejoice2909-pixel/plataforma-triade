import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf

# --- 1. MOTOR GEOESTATÍSTICO (PROIBIDO PROCESSAR SEM GATILHO) ---
@st.cache_data(show_spinner="Executando Krigagem de Alta Precisão...")
def motor_krigagem_v43(df, coluna):
    """Interpolação Rbf Linear com Grid de 150x150."""
    x, y, z = df['longitude'].values, df['latitude'].values, df[coluna].values
    xi = np.linspace(x.min(), x.max(), 150)
    yi = np.linspace(y.min(), y.max(), 150)
    xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear')
    zi = rbf(xi, yi)
    return xi, yi, zi

# --- 2. COMPONENTE DE RENDERIZAÇÃO (V43 - OPACIDADE 1.0) ---
def renderizar_mapa_triade(df, coluna, geojson_data):
    """Aplica Opacidade 1.0, Contorno Preto e Escala Jet Saturada."""
    if coluna not in df.columns:
        st.warning(f"⚠️ Atributo '{coluna}' ausente na planilha.")
        return

    # Cálculo pesado isolado pelo cache
    xi, yi, zi = motor_krigagem_v43(df, coluna)
    fig = go.Figure()

    # Camada Heatmap: Opacidade Total (Alpha=1.0)
    fig.add_trace(go.Heatmap(
        z=zi, x=xi[0, :], y=yi[:, 0],
        colorscale='Jet',
        opacity=1.0, 
        zsmooth=False,
        colorbar=dict(title=dict(text=f"<b>{coluna}</b>", font={"size":14}), thickness=20)
    ))

    # Camada de Contorno: Leitura Resiliente (Polygon/MultiPolygon)
    if geojson_data:
        try:
            feature = geojson_data['features'][0]
            geom = feature['geometry']
            # Extração dinâmica baseada no tipo de geometria
            if geom['type'] == 'Polygon':
                coords = geom['coordinates'][0]
            elif geom['type'] == 'MultiPolygon':
                coords = geom['coordinates'][0][0]
            else:
                coords = []
            
            if coords:
                lons, lats = zip(*coords)
                fig.add_trace(go.Scattermapbox(
                    lon=lons, lat=lats, mode='lines',
                    line=dict(width=3, color='black'),
                    name='Limite do Talhão'
                ))
        except Exception as e:
            st.warning(f"⚠️ Geometria do GeoJSON simplificada ou com erro: {e}")
        # O bloco try deve sempre terminar com except para não travar

    # Layout Travado: Rigor Geométrico e Satélite
    fig.update_layout(
        mapbox={
            "style": "satellite",
            "center": {"lat": df['latitude'].mean(), "lon": df['longitude'].mean()},
            "zoom": 15
        },
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        height=600,
        yaxis={"scaleanchor": "x", "scaleratio": 1}
    )
    
    st.plotly_chart(fig, use_container_width=True, key=f"v43_map_{coluna}")
    st.info(f"📊 **{coluna}** | Mín: {df[coluna].min():.2f} | Média: {df[coluna].mean():.2f} | Máx: {df[coluna].max():.2f}")
