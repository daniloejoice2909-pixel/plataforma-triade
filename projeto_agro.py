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

# --- 1. CONFIGURAÇÃO E PALETA ---
st.set_page_config(layout="wide", page_title="Tríade Agro - Estratégica 1.5")

# Paleta 3 Zonas Sólidas
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

# --- 3. UPLOAD (Sequência A a Y) ---
elif st.session_state.pagina == "Upload":
    st.header("📂 Importação de Dados da Fazenda")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.info = {
            "produtor": st.text_input("Produtor", "Danilo"),
            "fazenda": st.text_input("Fazenda", "Berneck"),
            "municipio": st.text_input("Município", "Tubarão")
        }
    with col2:
        f_contorno = st.file_uploader("Upload Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Upload Planilha Solo (A-Y)", type=['xlsx'])

    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        # 25 Colunas Exatas
        df.columns = [
            'LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
            'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
            'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'
        ][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 INICIAR PLATAFORMA"):
            st.session_state.pagina = "Dashboard"
            st.rerun()

# --- 4. DASHBOARD COMPLETO ---
elif st.session_state.pagina == "Dashboard":
    # RESTAURAÇÃO DAS PÁGINAS (ABAS)
    aba_attr, aba_fert, aba_recom, aba_zonas, aba_relat = st.tabs([
        "⚙️ Atributos", "🔍 Mapas de Fertilidade", "🏠 Recomendações VRA", "🗺️ Zonas de Manejo", "📄 Relatório & Exportação"
    ])

    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA 1: ATRIBUTOS ---
    with aba_attr:
        st.subheader("⚙️ Parâmetros para Recomendação")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Calcário**")
            cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0)
            prnt = st.number_input("PRNT %", 80.0); ca_ctc = st.number_input("Ca% desejado CTC", 60.0)
            mg_ctc = st.number_input("Mg% desejado CTC", 18.0)
        with c2:
            st.markdown("**Fósforo (P-Rem)**")
            prod_esp = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp = st.number_input("Fator Exp. P (kg/sc)", 0.8)
            p_adubo_perc = st.number_input("% P2O5 no Adubo", 21.0)
        with c3:
            st.markdown("**Potássio & Gesso**")
            k_ctc = st.number_input("K% desejado CTC", 3.2); g_fator = st.number_input("Fator Gesso (Arg * 15)", 15)
            g_max = st.number_input("Dese Máxima Gesso", 900.0)

    # --- ABA 2: MAPAS (AJUSTE DE TAMANHO/RECORTE) ---
    with aba_fert:
        st.subheader("🔍 Visualização Espacial HD")
        attr_map = st.selectbox("Selecione o Atributo:", ['P', 'K', 'ARGILA', 'PH', 'CTC', 'PREM'])
        
        if st.button("GERAR MAPA RECORTE"):
            with st.spinner("Interpolando e ajustando escala..."):
                OK = OrdinaryKriging(df['LON'], df['LAT'], df[attr_map], variogram_model='spherical')
                grid_x = np.linspace(minx, maxx, 250)
                grid_y = np.linspace(miny, maxy, 250)
                z, ss = OK.execute('grid', grid_x, grid_y)

                z_final = np.full(z.shape, np.nan)
                for i in range(len(grid_y)):
                    for j in range(len(grid_x)):
                        if geom.contains(Point(grid_x[j], grid_y[i])):
                            z_final[i, j] = z[i, j]

                # Correção do tamanho: figsize dinâmico + bbox_inches tight
                aspect_ratio = (maxy - miny) / (maxx - minx)
                fig, ax = plt.subplots(figsize=(10, 10 * aspect_ratio))
                ax.axis('off')
                
                v_min, v_max = np.nanpercentile(z_final, [2, 98])
                z_norm = (z_final - v_min) / (v_max - v_min)
                
                ax.imshow(z_norm, cmap=cmap_ap, norm=norm_ap, origin='lower', extent=[minx, maxx, miny, maxy])
                
                buf = io.BytesIO()
                # O segredo do tamanho correto: bbox_inches='tight' e pad_inches=0
                plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
                buf.seek(0); plt.close(fig)

                m = folium.Map(location=[geom.centroid.y, geom.centroid.x], zoom_start=15, tiles=None)
                folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri').add_to(m)
                
                folium.raster_layers.ImageOverlay(
                    image=np.array(Image.open(buf)),
                    bounds=[[miny, minx], [maxy, maxx]],
                    opacity=0.85
                ).add_to(m)

                folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'yellow', 'weight': 2.5}).add_to(m)
                folium_static(m, width=1100, height=750)

    # --- ABA 3: RECOMENDAÇÕES (FÓRMULAS TRÍADE) ---
    with aba_recom:
        st.subheader("🏠 Memória de Cálculo e Prescrição")
        # Implementação da lógica P-Rem
        df['NC_P'] = df['PREM'].apply(lambda x: 8 if x <= 4 else (10 if x <= 10 else (12 if x <= 19 else (15 if x <= 30 else (20 if x <= 45 else 25)))))
        df['SALDO_P'] = (df['P'] - df['NC_P']).clip(lower=0)
        df['DESS_P'] = (df['NC_P'] - df['P']).clip(lower=0)
        df['F_SOLO'] = df['ARGILA'].apply(lambda x: 10 if x > 600 else (8 if x > 350 else 4))
        df['REC_P'] = (((df['DESS_P'] * df['F_SOLO']) + (prod_esp * p_exp) - df['SALDO_P']) * 100 / p_adubo_perc).clip(lower=0)
        
        st.dataframe(df[['PONTO', 'ARGILA', 'PREM', 'P', 'REC_P']])

    # --- ABA 5: RELATÓRIO & EXPORTAÇÃO ---
    with aba_relat:
        st.subheader("📄 Exportação VRA e Relatório PDF")
        st.info("Utilize esta aba para gerar os arquivos compatíveis com os monitores John Deere e Case IH.")
        if st.button("Gerar Planilha de Exportação (.CSV)"):
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar Dados Prescrição", csv, "prescricao_triade.csv", "text/csv")
