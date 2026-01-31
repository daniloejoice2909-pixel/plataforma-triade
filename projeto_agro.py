import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import Draw
import json
import io
import os
import zipfile
from streamlit_folium import folium_static, st_folium
from pykrige.ok import OrdinaryKriging
from shapely.geometry import shape, Point, Polygon
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from PIL import Image
from fpdf import FPDF

# --- 1. CONFIGURAÇÕES VISUAIS PREMIUM ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.0", page_icon="🌱")

# Paleta Profissional 6 Camadas: Azul (Alto) ao Vermelho (Crítico)
colors_6 = ['#08306b', '#2171b5', '#6baed6', '#fee090', '#f46d43', '#a50026']
cmap_6 = ListedColormap(colors_6)
norm_6 = BoundaryNorm(np.linspace(0, 1, 7), cmap_6.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "info" not in st.session_state: st.session_state.info = {}
if "mapas_finalizados" not in st.session_state: st.session_state.mapas_finalizados = {}

# --- 2. MOTOR DE RELATÓRIO PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 30)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'RELATÓRIO DE PRESCRIÇÃO ESTRATÉGICA - TRÍADE AGRO', 0, 1, 'C')
        self.ln(10)

    def secao_mapa(self, titulo, img_buf, stats, desc):
        self.add_page()
        self.set_font('Arial', 'B', 12); self.cell(0, 10, titulo.upper(), 0, 1, 'L')
        img_path = f"temp_{titulo.replace(' ', '_')}.png"
        with open(img_path, "wb") as f: f.write(img_buf.getbuffer())
        self.image(img_path, x=35, w=140); self.ln(5)
        self.set_font('Arial', 'B', 9); self.cell(0, 8, stats, 0, 1, 'C')
        self.set_font('Arial', '', 10); self.multi_cell(0, 5, desc)
        if os.path.exists(img_path): os.remove(img_path)

# --- 3. FLUXO DE NAVEGAÇÃO ---

if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Consultoria Técnica", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True):
            if senha == "triade2026": st.session_state.pagina = "Upload"; st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Cadastro do Projeto e Área")
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.session_state.info['produtor'] = st.text_input("Produtor", "Danilo")
        st.session_state.info['fazenda'] = st.text_input("Fazenda", "Berneck")
        st.session_state.info['municipio'] = st.text_input("Município")
        f_dados = st.file_uploader("Upload Planilha Solo (A a Y)", type=['xlsx'])
        f_json = st.file_uploader("Upload Contorno JSON", type=['json', 'geojson'])
    with c2:
        st.write("🌍 **Globo Terrestre: Localize e Desenhe sua Área**")
        m = folium.Map(location=[-15.78, -47.92], zoom_start=4)
        folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri').add_to(m)
        Draw(export=True).add_to(m)
        output = st_folium(m, width=700, height=450)
        if f_json: st.session_state.contorno = json.load(f_json)
        elif output.get("all_drawings"): st.session_state.contorno = {"type": "FeatureCollection", "features": [output["all_drawings"][-1]]}

    if 'contorno' in st.session_state and f_dados:
        df = pd.read_excel(f_dados)
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 ABRIR DASHBOARD TÉCNICO", use_container_width=True): st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    # --- SIDEBAR: ATRIBUTOS EDITÁVEIS (PREVENÇÃO DE NAMEERROR) ---
    st.sidebar.header("⚙️ Parâmetros Técnicos")
    with st.sidebar.expander("Calcário (Elevação Ca/Mg)", expanded=True):
        p_cao = st.number_input("Teor CaO %", 36.0); p_mgo = st.number_input("Teor MgO %", 9.0)
        p_prnt = st.number_input("PRNT %", 80.0); p_ca_des = st.number_input("Ca% desejado CTC", 60.0)
        p_mg_des = st.number_input("Mg% desejado CTC", 18.0); p_adicional = st.number_input("Adicional (t/ha)", 0.0)
    with st.sidebar.expander("Fósforo (P-Rem + Gordura)", expanded=False):
        nc_list = [st.number_input(f"NC Classe {i+1}", v) for i, v in enumerate([8.0, 10.0, 12.0, 15.0, 20.0, 25.0])]
        f_marg = st.number_input("Fator M.Argiloso", 10.0); f_arg = st.number_input("Fator Argiloso", 8.0)
        f_med = st.number_input("Fator Médio", 4.0); f_are = st.number_input("Fator Arenoso", 2.0)
        p_prod = st.number_input("Produtividade (sc/ha)", 80.0); p_exp_p = st.number_input("Exp. P (kg/sc)", 0.8)
    with st.sidebar.expander("Potássio e Gesso", expanded=False):
        p_k_des = st.number_input("K% desejado CTC", 3.2); k_f_391 = st.number_input("Fator Atômico K", 391.0)
        p_exp_k = st.number_input("Exp. K (kg/sc)", 1.2); p_perc_k = st.number_input("% K2O Adubo", 60.0)
        g_fator = st.number_input("Fator Gesso (Arg * F)", 15); g_max = st.number_input("Dose Máxima Gesso", 900.0)

    tabs = st.tabs(["🔍 Fertilidade", "🏠 Recomendações VRA", "📄 Relatório & Exportação"])
    df = st.session_state.dados; contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry']); minx, miny, maxx, maxy = geom.bounds

    # --- MOTOR DE MAPEAMENTO HD ---
    def render_mapa_grid(colunas, desc_base, is_recom=False):
        cols_st = st.columns(3)
        for i, col_id in enumerate(colunas):
            with cols_st[i % 3]:
                df_l = df[['LON', 'LAT', col_id]].dropna().drop_duplicates(subset=['LON', 'LAT'])
                OK = OrdinaryKriging(df_l['LON'], df_l['LAT'], df_l[col_id], variogram_model='spherical')
                gx, gy = np.linspace(minx, maxx, 250), np.linspace(miny, maxy, 250)
                z, ss = OK.execute('grid', gx, gy); z_mask = np.full(z.shape, np.nan)
                for r in range(len(gy)):
                    for c in range(len(gx)):
                        if geom.contains(Point(gx[c], gy[r])): z_mask[r, c] = z[r, c]
                
                v_max, v_med, v_min = np.nanmax(z_mask), np.nanmean(z_mask), np.nanmin(z_mask)
                z_norm = (z_mask - v_min) / (v_max - v_min) if v_max > v_min else z_mask * 0
                
                fig, ax = plt.subplots(figsize=(5, 4)); ax.axis('off')
                ax.imshow(z_norm, cmap=cmap_6, norm=norm_6, origin='lower', extent=[minx, maxx, miny, maxy])
                poly = shape(contorno['features'][0]['geometry']); x_p, y_p = poly.exterior.xy
                ax.plot(x_p, y_p, color='black', linewidth=4) # CONTORNO PRETO PREMIUM
                
                buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0); plt.close(fig)
                st.image(buf, use_container_width=True)
                st.markdown(f"<p style='text-align:center; font-size:12px;'><b>{col_id}</b><br>Mín: {v_min:.2f} | Méd: {v_med:.2f} | Máx: {v_max:.2f}</p>", unsafe_allow_html=True)
                st.session_state.mapas_finalizados[col_id] = {"img": buf, "stats": f"Máx: {v_max:.2f} | Méd: {v_med:.2f} | Mín: {v_min:.2f}", "titulo": col_id,
