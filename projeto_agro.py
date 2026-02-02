def renderizar_mapa_triade(df, coluna, geojson_data):
    """Renderiza mapa opaco com contorno preto sólido e auditoria de dados."""
    if coluna not in df.columns:
        st.warning(f"⚠️ Atributo '{coluna}' não encontrado.")
        return

    # 1. Cálculo Pesado (Cache)
    xi, yi, zi = motor_krigagem_v43(df, coluna)
    fig = go.Figure()

    # 2. Camada Heatmap (Opacidade 1.0)
    fig.add_trace(go.Heatmap(
        z=zi, x=xi[0, :], y=yi[:, 0],
        colorscale='Jet',
        opacity=1.0, 
        zsmooth=False,
        colorbar={"title": {"text": f"<b>{coluna}</b>", "font": {"size": 12}}, "thickness": 15}
    ))

    # 3. Camada de Contorno (Rigor Geoespacial)
    if geojson_data:
        try:
            feature = geojson_data['features'][0]
            geom = feature['geometry']
            coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
            lons, lats = zip(*coords)
            
            fig.add_trace(go.Scattermapbox(
                lon=lons, lat=lats, mode='lines',
                line={"width": 3, "color": "black"},
                name='Contorno'
            ))
        except Exception:
            pass

    # 4. Layout Travado (Aspect Ratio 1:1)
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
    
    # 5. Renderização e Box de Informação (Correção da f-string)
    st.plotly_chart(fig, use_container_width=True, key=f"v43_grid_{coluna}")
    
    # Box informativo escrito em linha única para evitar erro de sintaxe
    min_val, max_val = df[coluna].min(), df[coluna].max()
    st.info(f"📊 **{coluna}** | Mínimo: {min_val:.2f} | Máximo: {max_val:.2f}")
