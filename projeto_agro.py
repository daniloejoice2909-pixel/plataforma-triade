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
st.set_page_config(layout="wide", page_title="Tríade Agro - Estratégica 1.3")

# Vermelho (Baixa), Amarelo (Média), Verde (Alta)
ap_colors = ['#d7191c', '#ffffbf', '#1a9641']
cmap_ap = ListedColormap(ap_colors)
norm_ap = BoundaryNorm([0, 0.33, 0.66, 1.0], cmap_ap.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"

# --- 2. LOGIN ---
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        if st.button("ACESSAR SISTEMA (Senha: triade2026)"):
            st.session_state.pagina = "Upload"
            st.rerun()

# --- 3. UPLOAD E SEQUÊNCIA A-Y ---
elif st.session_state.pagina == "Upload":
    st.header("📂 Importação de Dados e Contorno")
    f_contorno = st.file_uploader("Upload Contorno Berneck (.json)", type=['json', 'geojson'])
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
    tab_attr, tab_fert, tab_recom, tab_relat = st.tabs([
        "⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações VRA", "📄 Relatório Final"
    ])

    df = st.session_state.dados
    contorno = st.session_state.contorno

    # --- ABA 1: ATRIBUTOS (VALORES PADRÃO RESTAURADOS) ---
    with tab_attr:
        st.subheader("⚙️ Parâmetros Editáveis de Insumos")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Calcário**")
            cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0)
            prnt = st.number_input("PRNT %", 80.0); ca_ctc = st.number_input("Ca% desejado CTC", 60.0)
            mg_ctc = st.number_input("Mg% desejado CTC", 18.0); preco_calc = st.number_input("Preço Calcário (t)", 190.0)
        with c2:
            st.markdown("**Fósforo (P-Rem)**")
            prod_esp = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp = st.number_input("Fator Exp. P (kg/sc)", 0.8)
            p_adubo_perc = st.number_input("% P2O5 no Adubo", 21.0)
            p_preco = st.number_input("Preço Adubo P (t)", 2800.0)
            st.write("Fatores Argila (P): M.Arg(10), Arg(8), Med(4), Aren(2)")
        with c3:
            st.markdown("**Potássio e Gesso**")
            k_ctc = st.number_input("K% desejado CTC", 3.2); k_exp = st.number_input("Fator Exp. K (kg/sc)", 1.2)
            k_adubo_perc = st.number_input("% K2O no Adubo", 60.0); k_preco = st.number_input("Preço Adubo K (t)", 2800.0)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15); g_max = st.number_input("Dose Máx Gesso", 900.0)

    # --- ABA 3: RECOMENDAÇÕES (FÓRMULAS TÉCNICAS) ---
    with tab_recom:
        st.subheader("🏠 Cálculo de Recomendação Técnica")
        
        # 1. Lógica Fósforo (P-Remanescente)
        def nc_p_danilo(prem):
            if prem <= 4: return 8
            elif prem <= 10: return 10
            elif prem <= 19: return 12
            elif prem <= 30: return 15
            elif prem <= 45: return 20
            else: return 25
        
        df['NC_P'] = df['PREM'].apply(nc_p_danilo)
        # Saldo de P (Economia se acima do NC)
        df['SALDO_P'] = (df['P'] - df['NC_P']).clip(lower=0)
        df['NEC_P'] = (df['NC_P'] - df['P']).clip(lower=0)
        
        # Fator de Solo baseado na Argila (Simulação de classe)
        df['FATOR_SOLO'] = df['ARGILA'].apply(lambda x: 10 if x > 600 else (8 if x > 350 else 4))
        
        # Recomendação Final P: (Necessidade * Fator) + Exportação - Saldo
        df['REC_P2O5'] = (df['NEC_P'] * df['FATOR_SOLO']) + (prod_esp * p_exp) - df['SALDO_P']
        df['REC_ADUBO_P'] = (df['REC_P2O5'] * 100 / p_adubo_perc).clip(lower=0)

        # 2. Gesso (Argila g/kg * Fator)
        df['REC_GESSO'] = (df['ARGILA'] * g_fator / 10).clip(lower=400, upper=g_max)

        st.write("### Planilha de Prescrição Gerada")
        st.dataframe(df[['PONTO', 'REC_ADUBO_P', 'REC_GESSO']])

    # --- ABA 2: MAPAS (KRIGAGEM + RECORTE) ---
    with tab_fert:
        st.subheader("🔍 Mapa de Fertilidade (Krigagem Ordinária)")
        attr_map = st.selectbox("Escolha o Atributo:", ['P', 'K', 'PH', 'ARGILA', 'REC_ADUBO_P', 'REC_GESSO'])
        
        if st.button("GERAR MAPA RECORTE"):
            geom = shape(contorno['features'][0]['geometry'])
            minx, miny, maxx, maxy = geom.bounds
            
            # Krigagem
            OK = OrdinaryKriging(df['LON'], df['LAT'], df[attr_map], variogram_model='spherical')
            grid_x = np.linspace(minx, maxx, 150)
            grid_y = np.linspace(miny, maxy, 150)
            z, ss = OK.execute('grid', grid_x, grid_y)

            # Recorte por Máscara
            z_final = np.full(z.shape, np.nan)
            for i in range(len(grid_y)):
                for j in range(len(grid_x)):
                    if geom.contains(Point(grid_x[j], grid_y[i])):
                        z_final[i, j] = z[i, j]

            # Renderização
            m = folium.Map(location=[geom.centroid.y, geom.centroid.x], zoom_start=15, tiles=None)
            folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri').add_to(m)

            v_min, v_max = np.nanpercentile(z_final, [2, 98])
            z_norm = (z_final - v_min) / (v_max - v_min)
            
            fig, ax = plt.subplots(figsize=(6,6)); ax.axis('off')
            ax.imshow(z_norm, cmap=cmap_ap, norm=norm_ap, origin='lower', extent=[minx, maxx, miny, maxy])
            buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
            
            folium.raster_layers.ImageOverlay(image=np.array(Image.open(buf)), bounds=[[miny, minx], [maxy, maxx]], opacity=0.8).add_to(m)
            folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'yellow', 'weight': 2}).add_to(m)
            folium_static(m, width=1100, height=700)
