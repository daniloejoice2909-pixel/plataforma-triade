import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf

# --- 1. MOTOR COM CACHE DE RESULTADO FINAL ---
@st.cache_data(show_spinner="Renderizando matrizes...")
def gerar_figura_v43(df_data, coluna, geojson_contorno, lat_mean, lon_mean):
    """
    Esta função encapsula a criação da figura. 
    O cache aqui evita que o Plotly seja recarregado desnecessariamente.
    """
    x, y, z = df_data['longitude'].values, df_data['latitude'].values, df_data[coluna].values
    
    # Grid de 120x120 (Equilíbrio perfeito entre precisão InCeres e leveza)
    xi = np.linspace(x.min(), x.max(), 120)
    yi = np.linspace(y.min(), y.max(), 120)
    xi, yi = np.meshgrid(xi, yi)
    
    rbf = Rbf(x, y, z, function='linear')
    zi = rbf(xi, yi)

    fig = go.Figure()

    # Heatmap Sólido
    fig.add_trace(go.Heatmap(
        z=zi, x=xi[0, :], y=yi[:, 0],
        colorscale='Jet', opacity=1.0, zsmooth=False,
        colorbar={"title": f"<b>{coluna}</b>", "thickness": 15}
    ))

    # Contorno Preto Sólido
    if geojson_contorno:
        try:
            feat = geojson_contorno['features'][0]
            coords = feat['geometry']['coordinates'][0]
            if feat['geometry']['type'] == 'MultiPolygon': coords = coords[0]
            lons, lats = zip(*coords)
            fig.add_trace(go.Scattermapbox(
                lon=lons, lat=lats, mode='lines',
                line={"width": 3, "color": "black"}
            ))
        except: pass

    fig.update_layout(
        mapbox={"style": "satellite", "center": {"lat": lat_mean, "lon": lon_mean}, "zoom": 15},
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        height=450,
        yaxis={"scaleanchor": "x", "scaleratio": 1}
    )
    return fig

# --- 2. INTERFACE DE EXIBIÇÃO ---
if st.sidebar.button("🚀 Gerar Mapas de Fertilidade"):
    st.session_state.gerar_fertilidade = True

if st.session_state.get('gerar_fertilidade'):
    tab_fert, tab_vrt = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT"])
    
    with tab_fert:
        atributos = ['pH', 'Argila', 'Ca', 'Mg', 'K', 'V%', 'P_Mehl', 'P_rem']
        # Criamos containers para organizar a memória de vídeo
        for i in range(0, len(atributos), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(atributos):
                    attr = atributos[i + j]
                    with cols[j]:
                        # Chamada da função com cache
                        figura = gerar_figura_v43(
                            df_solo, attr, geojson_file, 
                            df_solo['latitude'].mean(), df_solo['longitude'].mean()
                        )
                        st.plotly_chart(figura, use_container_width=True, key=f"mapa_v43_{attr}")
                        st.info(f"**{attr}** | Mín: {df_solo[attr].min():.2f} | Máx: {df_solo[attr].max():.2f}")
