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
from PIL import Image

# --- 1. CONFIGURAÇÃO E PALETA 3 ZONAS ---
st.set_page_config(layout="wide", page_title="Tríade Agro - Estratégica 1.4")

# Vermelho (Baixa), Amarelo (Média), Verde (Alta)
ap_colors = ['#d7191c', '#ffffbf', '#1a9641']
cmap_ap = ListedColormap(ap_colors)
norm_ap = BoundaryNorm([0, 0.33, 0.66, 1.0], cmap_ap.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"

# --- 2. LOGIN ---
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Solo & Precisão</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        if st.button("ACESSAR SISTEMA"):
            st.session_state.pagina = "Upload"
            st.rerun()

# --- 3. UPLOAD E SEQUÊNCIA A-Y ---
elif st.session_state.pagina == "Upload":
    st.header("📂 Importação de Dados e Contorno")
    f_contorno = st.file_uploader("Upload Contorno (.json)", type=['json', 'geojson'])
    f_dados = st.file_uploader("Upload Planilha Solo (Colunas A a Y)", type=['xlsx'])

    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        # CONFIGURAÇÃO EXATA DAS 25 COLUNAS (A a Y)
        df.columns = [
            'LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
            'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
            'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'
        ][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 ABRIR DASHBOARD"):
            st.session_state.pagina = "Dashboard"
            st.rerun()

# --- 4. DASHBOARD ESTRATÉGICO ---
elif st.session_state.pagina == "Dashboard":
    tab_attr, tab_fert, tab_recom = st.tabs(["⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações VRA"])

    df = st.session_state.dados
    contorno = st.session_state.contorno

    with tab_attr:
        st.subheader("⚙️ Parâmetros Técnicos")
        c1, c2, c3 = st.columns(3)
        with c1:
            prod_esp = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp = st.number_input("Fator Exp. P (kg/sc)", 0.8)
            p_adubo_perc = st.number_input("% P2O5 no Adubo", 21.0)
        with c2:
            ca_ctc = st.number_input("Ca% desejado CTC", 60.0)
            mg_ctc = st.number_input("Mg% desejado CTC", 18.0)
        with c3:
            k_ctc = st.number_input("K% desejado CTC", 3.2)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15)

    # --- ABA 2: MAPAS (CORREÇÃO DE LOCALIZAÇÃO) ---
    with tab_fert:
        st.subheader("🔍 Mapa Geoestatístico Alinhado")
        attr_map = st.selectbox("Escolha o Atributo:", ['P', 'K', 'PH', 'ARGILA', 'CTC'])
        
        if st.button("GERAR MAPA RECORTE HD"):
            geom = shape(contorno['features'][0]['geometry'])
            minx, miny, maxx, maxy = geom.bounds
            
            # 1. Krigagem Ordinária
            OK = OrdinaryKriging(df['LON'], df['LAT'], df[attr_map], variogram_model='spherical')
            
            # Grid mais denso para evitar o efeito "escada" nas bordas
            res = 200
            grid_x = np.linspace(minx, maxx, res)
            grid_y = np.linspace(miny, maxy, res)
            z, ss = OK.execute('grid', grid_x, grid_y)

            # 2. Máscara de Recorte Milimétrica
            z_final = np.full(z.shape, np.nan)
            for i in range(len(grid_y)):
                for j in range(len(grid_x)):
                    # Point(Longitude, Latitude)
                    if geom.contains(Point(grid_x[j], grid_y[i])):
                        z_final[i, j] = z[i, j]

            # 3. Renderização com origin='lower' para alinhar ao Folium
            fig, ax = plt.subplots(figsize=(10,10))
            ax.axis('off')
            
            # Normalização 3 Zonas
            v_min, v_max = np.nanpercentile(z_final, [2, 98])
            z_norm = (z_final - v_min) / (v_max - v_min)
            
            # origin='lower' garante que a base da matriz seja o Sul (miny)
            ax.imshow(z_norm, cmap=cmap_ap, norm=norm_ap, origin='lower', extent=[minx, maxx, miny, maxy])
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', transparent=True, pad_inches=0)
            buf.seek(0)
            plt.close(fig)

            # 4. Mapa Folium
            m = folium.Map(location=[geom.centroid.y, geom.centroid.x], zoom_start=15, tiles=None)
            folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', 
                             attr='Esri Clarity', name='Satélite').add_to(m)

            # Bounds exatos do grid garantem alinhamento perfeito
            folium.raster_layers.ImageOverlay(
                image=np.array(Image.open(buf)),
                bounds=[[miny, minx], [maxy, maxx]],
                opacity=0.85,
                zindex=1
            ).add_to(m)

            folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'yellow', 'weight': 2.5}).add_to(m)
            folium_static(m, width=1100, height=750)

    # --- ABA 3: RECOMENDAÇÕES (FÓRMULAS RESTAURADAS) ---
    with tab_recom:
        st.subheader("🏠 Cálculos de Prescrição")
        # Lógica Fósforo (P-Rem)
        def nc_p(prem):
            if prem <= 4: return 8
            elif prem <= 10: return 10
            elif prem <= 19: return 12
            elif prem <= 30: return 15
            elif prem <= 45: return 20
            else: return 25
        
        df['NC_P'] = df['PREM'].apply(nc_p)
        df['SALDO_P'] = (df['P'] - df['NC_P']).clip(lower=0)
        df['NEC_P'] = (df['NC_P'] - df['P']).clip(lower=0)
        
        # Fator Solo (Argila)
        df['F_SOLO'] = df['ARGILA'].apply(lambda x: 10 if x > 600 else (8 if x > 350 else 4))
        
        # Recomendação P: (Necessidade * Fator) + Exportação - Saldo
        df['REC_ADUBO_P'] = (((df['NEC_P'] * df['F_SOLO']) + (prod_esp * p_exp) - df['SALDO_P']) * 100 / p_adubo_perc).clip(lower=0)

        st.dataframe(df[['PONTO', 'ARGILA', 'P', 'REC_ADUBO_P']])
