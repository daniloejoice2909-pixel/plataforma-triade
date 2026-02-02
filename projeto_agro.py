import plotly.graph_objects as go
import numpy as np
from scipy.interpolate import Rbf

def gerar_mapa_triade_v43(df, coluna, geojson_data, titulo="Mapa de Fertilidade"):
    """
    Motor de Renderização V43: Opacidade 100%, Krigagem Rbf e Rigor Geométrico.
    """
    # 1. Validação de Integridade (Protocolo de Segurança)
    if coluna not in df.columns:
        return f"Erro: Coluna {coluna} não encontrada na planilha."

    # 2. Preparação do Grid de Krigagem (150x150)
    lat, lon = df['latitude'].values, df['longitude'].values
    z = df[coluna].values
    
    grid_lon = np.linspace(lon.min(), lon.max(), 150)
    grid_lat = np.linspace(lat.min(), lat.max(), 150)
    grid_lon, grid_lat = np.meshgrid(grid_lon, grid_lat)
    
    # Interpolação Rbf (Mancha Suave, mas com cores sólidas)
    rbf = Rbf(lon, lat, z, function='linear')
    z_grid = rbf(grid_lon, grid_lat)

    # 3. Construção do Mapa
    fig = go.Figure()

    # Camada de Dados: Opacidade 100% (Alpha = 1.0)
    fig.add_trace(go.Heatmap(
        z=z_grid,
        x=np.linspace(lon.min(), lon.max(), 150),
        y=np.linspace(lat.min(), lat.max(), 150),
        colorscale='Jet',
        opacity=1.0,  # Rigor V43: Sem transparência
        zsmooth=False, # Mantém as divisas de cores mais nítidas
        colorbar=dict(
            title=dict(text=f"<b>{coluna}</b>", font=dict(size=14)),
            thickness=20,
            x=1.02
        )
    ))

    # 4. Camada de Contorno: Preto Sólido (Separação Física)
    if geojson_data:
        # Extrair coordenadas do GeoJSON para a linha de contorno
        # (Lógica simplificada para exemplo)
        lons_contorno = geojson_data['features'][0]['geometry']['coordinates'][0][:,0]
        lats_contorno = geojson_data['features'][0]['geometry']['coordinates'][0][:,1]
        
        fig.add_trace(go.Scattermapbox(
            lon=lons_contorno,
            lat=lats_contorno,
            mode='lines',
            line=dict(width=3, color='black'),
            name='Contorno Talhão'
        ))

    # 5. Configurações de Layout (Aspect Ratio 1:1 e Satélite)
    fig.update_layout(
        title=f"<b>{titulo} - Tríade Agro Estratégica</b>",
        margin={"r":0,"t":40,"l":0,"b":0},
        height=600,
        mapbox=dict(
            style="satellite",
            center={"lat": lat.mean(), "lon": lon.mean()},
            zoom=15
        ),
        yaxis=dict(scaleanchor="x", scaleratio=1) # Impede deformação do talhão
    )

    return fig

# Auditoria de Saída (Box Informativo st.info)
# Mín: {z.min()} | Máx: {z.max()} | Média: {z.mean()}
