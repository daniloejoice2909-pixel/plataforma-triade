import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import base64

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- MOTOR DE INTERPOLAÇÃO IDW ---
def calcular_idw(x, y, z, xi, yi, p=2):
    dist = np.sqrt((x[:, None] - xi[None, :])**2 + (y[:, None] - yi[None, :])**2)
    dist = np.where(dist == 0, 1e-12, dist)
    weights = 1.0 / (dist**p)
    return np.dot(weights.T, z) / weights.sum(axis=0)

# --- FUNÇÃO DE MAPA PROFISSIONAL ---
def renderizar_mapa_idw(df, coluna, geojson_data):
    try:
        df_c = df.dropna(subset=['LATITUDE', 'LONGITUDE', coluna]).copy()
        df_c[coluna] = pd.to_numeric(df_c[coluna], errors='coerce')
        df_c = df_c.dropna(subset=[coluna])
        
        if df_c.empty: return

        x, y, z = df_c['LONGITUDE'].values, df_c['LATITUDE'].values, df_c[coluna].values
        
        # Grid para interpolação
        nx, ny = 100, 100
        xi = np.linspace(x.min(), x.max(), nx)
        yi = np.linspace(y.min(), y.max(), ny)
        xi_grid, yi_grid = np.meshgrid(xi, yi)
        
        zi = calcular_idw(x, y, z, xi_grid.flatten(), yi_grid.flatten()).reshape(nx, ny)

        fig = go.Figure()

        # Camada IDW (Zonas de Manejo)
        fig.add_trace(go.Contour(
            z=zi, x=xi, y=yi,
            colorscale='RdBu_r', ncontours=6,
            line_smoothing=0.8,
            contours=dict(coloring='heatmap', showlines=True),
            colorbar=dict(title=coluna),
            hoverinfo='z'
        ))

        # Pontos de Amostragem
        fig.add_trace(go.Scatter(
            x=x, y=y, mode='markers',
            marker=dict(size=6, color='black', symbol='x'),
            name='Amostras'
        ))

        # Contorno GeoJSON
        if geojson_data:
            for feature in geojson_data['features']:
                geom = feature['geometry']
                all_coords = geom['coordinates'] if geom['type'] == 'Polygon' else geom['coordinates'][0]
                for coords in all_coords:
                    if len(coords) < 3: continue 
                    lons_c, lats_c = zip(*coords)
                    fig.add_trace(go.Scatter(
                        x=lons_c, y=lats_c, mode='lines',
                        line=dict(color='black', width=3),
                        fill='toself', fillcolor='rgba(0,0,0,0)',
                        showlegend=False
                    ))
            fig.update_xaxes(range=[min(lons_c)-0.0003, max(lons_c)+0.0003])
            fig.update_yaxes(range=[min(lats_c)-0.0003, max(lats_c)+0.0003])

        fig.update_layout(
            title=f"Mapa IDW: {coluna}", height=700,
            xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, key=f"idw_{coluna}")
    except Exception as e:
        st.error(f"Erro no mapa {coluna}: {e}")

# --- INTERFACE E LOGICA ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🔒 Acesso Tríade Agro")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.rerun()
else:
    if "dados" not in st.session_state:
        st.subheader("📂 Carregar Dados do Talhão")
        f_geo = st.file_uploader("GeoJSON", type=['geojson', 'json'])
        f_xls = st.file_uploader("Excel", type=['xlsx'])
        if f_geo and f_xls:
            if st.button("Processar"):
                st.session_state.dados = pd.read_excel(f_xls)
                st.session_state.geo = json.load(f_geo)
                st.rerun()
    else:
        tab1, tab2 = st.tabs(["⚙️ ATRIBUTOS", "🔍 MAPAS"])
        with tab1:
            st.write("Configurações V43 ativas.")
        with tab2:
            cols_mapa = ['ARGILA', 'P-REM', 'P', 'K', 'V%']
            for c in cols_mapa:
                if c in st.session_state.dados.columns:
                    renderizar_mapa_idw(st.session_state.dados, c, st.session_state.geo)
