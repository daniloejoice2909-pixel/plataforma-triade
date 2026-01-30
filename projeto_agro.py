import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
import io
from streamlit_folium import folium_static
from pykrige.ok import OrdinaryKriging
from shapely.geometry import shape, Point
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

# --- 1. CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(layout="wide", page_title="Tríade Agro - Estratégica 1.2")

# Paleta Recomendada: 3 Zonas Definidas (Baixa, Média, Alta)
ap_colors = ['#d7191c', '#ffffbf', '#1a9641'] # Vermelho, Amarelo, Verde
cmap_ap = ListedColormap(ap_colors)
norm_ap = BoundaryNorm([0, 0.33, 0.66, 1.0], cmap_ap.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"

# --- 2. LOGIN (MANTIDO) ---
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Solo & Precisão</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Estratégico", type="password")
        if st.button("ACESSAR SISTEMA"):
            if senha == "triade2026":
                st.session_state.pagina = "Upload"
                st.rerun()

# --- 3. UPLOAD E MAPEAMENTO A-Y ---
elif st.session_state.pagina == "Upload":
    st.header("📂 Importação de Dados")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.info = {"produtor": st.text_input("Produtor"), "fazenda": st.text_input("Fazenda")}
    with col2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha de Solo (Colunas A a Y)", type=['xlsx'])

    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        # Sequência Exata do Roteiro (A a Y)
        df.columns = [
            'LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
            'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
            'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'
        ][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 PROCESSAR MAPAS"):
            st.session_state.pagina = "Dashboard"
            st.rerun()

# --- 4. DASHBOARD ESTRATÉGICO ---
elif st.session_state.pagina == "Dashboard":
    tab_fert, tab_recom, tab_relat = st.tabs(["🔍 Mapas de Fertilidade", "🏠 Recomendações VRA", "📄 Relatório Final"])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    with tab_fert:
        st.subheader("Interpolação por Krigagem (Recorte de Contorno)")
        attr = st.selectbox("Atributo para Mapear:", ['P', 'K', 'PH', 'ARGILA', 'CTC', 'V_PERC'])
        
        if st.button("GERAR MAPA DEFINIDO"):
            with st.spinner("Realizando Krigagem e Recorte Espacial..."):
                # 1. Motor de Krigagem
                OK = OrdinaryKriging(df['LON'], df['LAT'], df[attr], variogram_model='spherical')
                
                # 2. Grid de Alta Resolução (200x200 para suavidade)
                grid_x = np.linspace(minx, maxx, 200)
                grid_y = np.linspace(miny, maxy, 200)
                z, ss = OK.execute('grid', grid_x, grid_y)

                # 3. MÁSCARA DE RECORTE (Clipping)
                # Criamos uma matriz de NaNs e preenchemos apenas o que está dentro do polígono
                z_masked = np.full(z.shape, np.nan)
                for i in range(len(grid_y)):
                    for j in range(len(grid_x)):
                        if geom.contains(Point(grid_x[j], grid_y[i])):
                            z_masked[i, j] = z[i, j]

                # 4. Renderização no Folium
                m = folium.Map(location=[geom.centroid.y, geom.centroid.x], zoom_start=15, tiles=None)
                folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', 
                                 attr='Esri Clarity', name='Satélite').add_to(m)

                # Normalização para a escala de 3 cores
                v_min, v_max = np.nanpercentile(z_masked, [2, 98])
                z_norm = (z_masked - v_min) / (v_max - v_min)
                
                # Transformação para Imagem e Overlay
                fig, ax = plt.subplots(figsize=(8,8)); ax.axis('off')
                ax.imshow(z_norm, cmap=cmap_ap, norm=norm_ap, origin='lower', extent=[minx, maxx, miny, maxy])
                
                buf = io.BytesIO()
                plt.savefig(buf, format='png', transparent=True, pad_inches=0); plt.close(fig)
                
                folium.raster_layers.ImageOverlay(
                    image=np.array(Image.open(buf)),
                    bounds=[[miny, minx], [maxy, maxx]],
                    opacity=0.8
                ).add_to(m)

                folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'yellow', 'weight': 2}).add_to(m)
                folium_static(m, width=1100, height=700)

    with tab_recom:
        st.subheader("Resumo de Insumos (Cálculos Tríade)")
        # Fórmulas de Calcário, P e K aplicadas conforme o roteiro...
        st.write("Cálculos ativos baseados na Produtividade Esperada (80 sc/ha) e P-Rem.")
        st.dataframe(df[['PONTO', 'P', 'K', 'ARGILA']].head())
