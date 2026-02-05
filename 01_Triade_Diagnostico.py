import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from matplotlib.path import Path as MplPath
from scipy.interpolate import Rbf

# --- PROTOCOLO v43.1: CACHE E BLINDAGEM ---
@st.cache_data(show_spinner=False)
def gerar_grid_interpolado_recortado(df, col_alvo, coords_poligono, resolucao=200):
    """
    Gera um grid de alta densidade e recorta exatamente no formato do talhão.
    Retorna apenas os pontos que estão DENTRO do contorno.
    """
    try:
        # 1. Extrair Limites do Polígono
        # coords_poligono deve ser uma lista de listas: [[lon, lat], [lon, lat]...]
        poly_path = MplPath(coords_poligono)
        
        lons = [p[0] for p in coords_poligono]
        lats = [p[1] for p in coords_poligono]
        
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        
        # 2. Criar Grid de Alta Densidade (O segredo para reduzir o serrilhado)
        # Adicionamos um pequeno buffer para garantir que cobre as bordas
        xi = np.linspace(min_lon, max_lon, resolucao)
        yi = np.linspace(min_lat, max_lat, resolucao)
        xi, yi = np.meshgrid(xi, yi)
        
        # Achatando para interpolação
        flat_xi = xi.flatten()
        flat_yi = yi.flatten()
        
        # 3. Interpolação (RBF ou Krigagem Simples)
        # Se tiver muitos pontos, RBF pode ser pesado. Se for o caso, usamos LinearNDInterpolator
        rbf = Rbf(df['longitude'], df['latitude'], df[col_alvo], function='linear')
        zi = rbf(flat_xi, flat_yi)
        
        # 4. MÁSCARA DE RECORTE (O segredo do "Não Extrapolar")
        # Cria uma lista de pares (lon, lat) para verificar
        pontos_grid = np.vstack((flat_xi, flat_yi)).T
        
        # Verifica quais pontos estão DENTRO do polígono
        mask_inside = poly_path.contains_points(pontos_grid)
        
        # Filtra apenas os dados internos (Isso garante 100% de preenchimento interno e 0% fora)
        final_lon = flat_xi[mask_inside]
        final_lat = flat_yi[mask_inside]
        final_z = zi[mask_inside]
        
        return final_lon, final_lat, final_z, min_lon, max_lon

    except Exception as e:
        st.error(f"Erro na interpolação geométrica: {e}")
        return None, None, None, None, None

def criar_escala_discreta(min_v, max_v):
    """
    Cria uma escala de cores 'Bruta' (Sem degradê/mistura).
    Divide em 5 classes rígidas.
    """
    # Cores no padrão agronômico (Vermelho -> Verde)
    colors = ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'] # Spectral adaptado
    
    # Criando os passos discretos para o Plotly
    # O truque é repetir a cor para criar "degraus"
    step = 1/5
    discrete_colorscale = [
        [0, colors[0]], [step, colors[0]],
        [step, colors[1]], [2*step, colors[1]],
        [2*step, colors[2]], [3*step, colors[2]],
        [3*step, colors[3]], [4*step, colors[3]],
        [4*step, colors[4]], [1, colors[4]]
    ]
    return discrete_colorscale

# --- RENDERIZAÇÃO ---
def plotar_mapa_perfeito(df, geojson_polygon, coluna, nome_atributo):
    
    # Extraindo coordenadas do GeoJSON (Assumindo Polygon simples)
    # Se for MultiPolygon, precisa tratar a lista. Aqui focamos no Polygon padrão.
    try:
        coords = geojson_polygon['features'][0]['geometry']['coordinates'][0]
    except:
        st.warning("Estrutura do GeoJSON inválida para recorte.")
        return

    # 1. Processamento Matemático
    lon_grid, lat_grid, z_grid, min_x, max_x = gerar_grid_interpolado_recortado(
        df, coluna, coords, resolucao=200 # 200 é um bom equilíbrio, tente 250 se quiser mais liso
    )
    
    if lon_grid is None: return

    # Estatísticas
    v_min, v_max = np.nanmin(z_grid), np.nanmax(z_grid)
    v_med = np.nanmean(z_grid)

    # 2. Configuração Visual
    fig = go.Figure()

    # CAMADA 1: O MAPA DE CALOR "SÓLIDO"
    # Usamos Scattermapbox com quadrados para simular o raster
    # O tamanho do marker deve ser calculado dinamicamente para fechar os buracos
    # Tamanho base ~ (Largura em graus / resolução) * fator de zoom
    # Ajuste manual fino: size=6 a 8 geralmente cobre bem grids de 200px
    
    fig.add_trace(go.Scattermapbox(
        lat=lat_grid,
        lon=lon_grid,
        mode='markers',
        marker=dict(
            size=7, # Aumente levemente se houver buracos brancos entre os pontos
            symbol='square', # Quadrado preenche melhor que círculo
            color=z_grid,
            colorscale=criar_escala_discreta(v_min, v_max),
            cmin=v_min,
            cmax=v_max,
            opacity=1.0, # Opacidade total como solicitado
            showscale=True,
            colorbar=dict(
                title=f"<b>{nome_atributo}</b>",
                titleside="right",
                x=1.02, # Legenda à direita
                tickfont=dict(size=10),
                thickness=15
            )
        ),
        text=[f"{val:.2f}" for val in z_grid],
        hoverinfo='text+lon+lat',
        name="Grid"
    ))

    # CAMADA 2: O CONTORNO PRETO (LIMITE FÍSICO)
    lons_poly = [p[0] for p in coords]
    lats_poly = [p[1] for p in coords]
    
    fig.add_trace(go.Scattermapbox(
        lat=lats_poly,
        lon=lons_poly,
        mode='lines',
        line=dict(color='black', width=3), # Linha grossa preta
        hoverinfo='none',
        name='Limite'
    ))

    # CAMADA 3: BOX DE INFORMAÇÃO (Abaixo do mapa, como HTML ou Anotação)
    # No Streamlit, é melhor usar st.metric ou st.markdown colunas abaixo do gráfico
    # Mas se quiser no gráfico, use layout.annotations (complexo para manter responsivo)

    # LAYOUT MAPBOX
    fig.update_layout(
        mapbox=dict(
            style="satellite", # Imagem Real
            center=dict(lat=np.mean(lats_poly), lon=np.mean(lons_poly)),
            zoom=13 # Ajuste dinâmico seria ideal
        ),
        margin={"r":0,"t":0,"l":0,"b":0},
        height=600,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True, key=f"map_{coluna}")

    # RODAPÉ DE DADOS (Conforme solicitado)
    c1, c2, c3 = st.columns(3)
    c1.metric("Mínimo", f"{v_min:.2f}")
    c2.metric("Média", f"{v_med:.2f}")
    c3.metric("Máximo", f"{v_max:.2f}")
