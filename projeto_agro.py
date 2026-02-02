import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf

# --- 1. MOTOR GEOESTATÍSTICO COM CACHE (Blindagem de Cálculo) ---
@st.cache_data(show_spinner="Calculando Manchas de Fertilidade...")
def motor_krigagem_v43(df, coluna):
    x, y, z = df['longitude'].values, df['latitude'].values, df[coluna].values
    # Mantemos 150x150 para o cálculo ser preciso, mas renderizamos um por vez
    xi = np.linspace(x.min(), x.max(), 150)
    yi = np.linspace(y.min(), y.max(), 150)
    xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear')
    zi = rbf(xi, yi)
    return xi, yi, zi

# --- 2. COMPONENTE DE MAPA (V43 - FOCO E CONTRASTE) ---
def renderizar_mapa_triade(df, coluna, geojson_data):
    if coluna not in df.columns:
        st.warning(f"⚠️ Atributo '{coluna}' não encontrado.")
        return

    xi, yi, zi = motor_krigagem_v43(df, coluna)
    fig = go.Figure()

    # Camada Heatmap: Opacidade Total (Alpha=1.0)
    fig.add_trace(go.Heatmap(
        z=zi, x=xi[0, :], y=yi[:, 0],
        colorscale='Jet',
        opacity=1.0, 
        zsmooth=False, # Essencial para manter as divisas nítidas e leves
        colorbar=dict(title=f"<b>{coluna}</b>", thickness=20)
    ))

    # Camada de Contorno: Leitura Resiliente
    if geojson_data:
        try:
            # Lógica para Polygon ou MultiPolygon
            feature = geojson_data['features'][0]
            geom = feature['geometry']
            coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
            lons, lats = zip(*coords)
            fig.add_trace(go.Scattermapbox(
                lon=lons, lat=lats, mode='lines',
                line=dict(width=3, color='black'),
                name='Contorno'
            ))
        except Exception:
            pass # Silencioso conforme protocolo de isolamento térmico

    fig.update_layout(
        mapbox={"style": "satellite", "center": {"lat": df['latitude'].mean(), "lon": df['longitude'].mean()}, "zoom": 15},
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        height=600,
        yaxis={"scaleanchor": "x", "scaleratio": 1}
    )
    st.plotly_chart(fig, use_container_width=True, key=f"v43_{coluna}")

# --- 3. INTERFACE DE USUÁRIO (Otimizada) ---
st.sidebar.title("🛠️ Tríade Agro")
if st.sidebar.button("🚀 Processar Talhão"):
    st.session_state.processado = True

if st.session_state.get('processado'):
    tab_fert, tab_vrt = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT"])
    
    with tab_fert:
        # SELETOR: O segredo para a plataforma não travar
        mapa_selecionado = st.selectbox(
            "Selecione a Camada de Fertilidade:",
            ['pH', 'Argila', 'Ca', 'Mg', 'K', 'V%', 'P_Mehl', 'P_rem'],
            index=1 # Começa na Argila por padrão
        )
        renderizar_mapa_triade(df_solo, mapa_selecionado, geojson_file)
        
    with tab_vrt:
        st.info("Utilize o seletor na aba ao lado para analisar os teores antes da recomendação.")
