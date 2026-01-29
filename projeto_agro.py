def calcular_idw(x, y, z, xi, yi, p=2):
    """ Função matemática para calcular a interpolação IDW """
    dist = np.sqrt((x[:, None] - xi[None, :])**2 + (y[:, None] - yi[None, :])**2)
    # Evita divisão por zero
    dist = np.where(dist == 0, 1e-12, dist)
    weights = 1.0 / (dist**p)
    idw_z = np.dot(weights.T, z) / weights.sum(axis=0)
    return idw_z

def renderizar_mapa_idw(df, coluna, geojson_data):
    try:
        # 1. Preparação dos dados
        df_c = df.dropna(subset=['LATITUDE', 'LONGITUDE', coluna]).copy()
        x = df_c['LONGITUDE'].values
        y = df_c['LATITUDE'].values
        z = df_c[coluna].values

        # 2. Criação da Grade (Grid) para a Interpolação
        # Criamos 100x100 pontos para o mapa ficar bem detalhado
        nx, ny = 100, 100
        xi = np.linspace(x.min(), x.max(), nx)
        yi = np.linspace(y.min(), y.max(), ny)
        xi_grid, yi_grid = np.meshgrid(xi, yi)
        
        # Executa o IDW
        zi = calcular_idw(x, y, z, xi_grid.flatten(), yi_grid.flatten())
        zi = zi.reshape(nx, ny)

        fig = go.Figure()

        # 3. O MAPA TÉCNICO (Contour sobre o grid IDW)
        fig.add_trace(go.Contour(
            z=zi, x=xi, y=yi,
            colorscale='RdBu_r', 
            ncontours=6, # Suas 6 zonas de manejo
            line_smoothing=0.8,
            contours=dict(coloring='heatmap', showlines=True),
            colorbar=dict(title=coluna, titleside='right'),
            hoverinfo='z'
        ))

        # 4. PONTOS DE COLETA (Essencial para conferência técnica)
        fig.add_trace(go.Scatter(
            x=x, y=y, mode='markers',
            marker=dict(size=6, color='black', symbol='x'),
            name='Pontos de Coleta',
            hovertemplate='Valor: %{text}<br>Lat: %{y}<br>Lon: %{x}',
            text=z
        ))

        # 5. MÁSCARA DO CONTORNO (GeoJSON)
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
                        fill='toself', fillcolor='rgba(255,255,255,0)',
                        showlegend=False, hoverinfo='skip'
                    ))
            
            # Zoom no contorno
            fig.update_xaxes(range=[min(lons_c)-0.0003, max(lons_c)+0.0003])
            fig.update_yaxes(range=[min(lats_c)-0.0003, max(lats_c)+0.0003])

        # 6. LOGO E LAYOUT
        logo_b64 = get_base64("LogoTriadeagro.png.png")
        if logo_b64:
            fig.add_layout_image(dict(
                source=f"data:image/png;base64,{logo_b64}",
                xref="paper", yref="paper", x=0.5, y=0.5,
                sizex=0.2, sizey=0.2, xanchor="center", yanchor="middle", opacity=0.1
            ))

        fig.update_layout(
            title=f"Mapa de Precisão (IDW): {coluna}",
            height=700, margin=dict(l=0,r=0,t=40,b=0),
            xaxis=dict(visible=False), 
            yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
            plot_bgcolor='white'
        )
        
        st.plotly_chart(fig, use_container_width=True, key=f"idw_map_{coluna}")

    except Exception as e:
        st.error(f"Erro no cálculo IDW de {coluna}: {e}")
