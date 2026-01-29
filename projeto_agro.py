def render_mapas(df):
    st.markdown("### 🗺️ Análise de Fertilidade com Contorno Geográfico")
    
    cols = ['ARGILA', 'P-REM', 'P', 'CA', 'MG', 'K', 'CTC', 'CA%', 'MG%', 'K%', 'PH_CACL2']
    logo = get_base64("LogoTriadeagro.png.png")
    
    # Recupera o contorno carregado
    geojson_data = st.session_state.get('geo_json', None)
    
    for col in cols:
        try:
            if col not in df.columns: continue
            
            df_safe = df.dropna(subset=['LATITUDE', 'LONGITUDE', col]).copy()
            df_safe[col] = pd.to_numeric(df_safe[col], errors='coerce')
            df_safe = df_safe.dropna(subset=[col])
            
            if df_safe.empty: continue

            fig = go.Figure()

            # 1. ADICIONA O MAPA DE CALOR (CONTORNOS)
            fig.add_trace(go.Histogram2dContour(
                x=df_safe['LONGITUDE'],
                y=df_safe['LATITUDE'],
                z=df_safe[col],
                colorscale='RdBu_r',
                ncontours=10,
                line_width=0,
                hoverinfo='z'
            ))

            # 2. ADICIONA O CONTORNO DO TALHÃO (MÁSCARA)
            if geojson_data:
                for feature in geojson_data['features']:
                    coords = feature['geometry']['coordinates'][0]
                    # Se for MultiPolygon, pode precisar de ajuste, mas para Polygon simples:
                    lons, lats = zip(*coords)
                    
                    fig.add_trace(go.Scatter(
                        x=lons, y=lats,
                        mode='lines',
                        line=dict(color='black', width=2),
                        fill='toself',
                        fillcolor='rgba(255,255,255,0)', # Transparente dentro
                        hoverinfo='skip',
                        showlegend=False
                    ))

            # 3. AJUSTE DE LIMITES (Corta o "vazio" fora do talhão)
            if geojson_data:
                fig.update_xaxes(range=[min(lons)-0.001, max(lons)+0.001])
                fig.update_yaxes(range=[min(lats)-0.001, max(lats)+0.001])

            if logo:
                fig.add_layout_image(dict(
                    source=f"data:image/png;base64,{logo}",
                    xref="x", yref="y", x=df_safe['LONGITUDE'].mean(), y=df_safe['LATITUDE'].mean(),
                    sizex=0.002, sizey=0.002, xanchor="center", yanchor="middle",
                    opacity=0.2, layer="above"
                ))

            fig.update_layout(
                width=900, height=600,
                paper_bgcolor='white',
                plot_bgcolor='rgba(240,240,240,0.5)',
                xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1)
            )
            
            st.plotly_chart(fig, use_container_width=True, key=f"map_geo_{col}")
            
        except Exception as e:
            st.error(f"Erro no mapa de {col}: {e}")
