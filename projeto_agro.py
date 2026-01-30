import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
import io
import os
import zipfile
from streamlit_folium import folium_static
from pykrige.ok import OrdinaryKriging
from shapely.geometry import shape, Point
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from PIL import Image
from fpdf import FPDF

# --- 1. CONFIGURAÇÕES VISUAIS (6 CAMADAS AZUL-VERMELHO) ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.31", page_icon="🌱")

# Paleta: Azul (Alto) -> Verde -> Amarelo -> Vermelho (Baixo)
# Invertendo para que o Azul seja o topo da fertilidade
colors_6 = ['#d73027', '#fc8d59', '#fee090', '#d9ef8b', '#91bfdb', '#4575b4'] 
cmap_6 = ListedColormap(colors_6)
norm_6 = BoundaryNorm(np.linspace(0, 1, 7), cmap_6.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "mapas_sessao" not in st.session_state: st.session_state.mapas_sessao = {}

# --- 2. CLASSE PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 30)
        self.set_font('Arial', 'B', 14); self.cell(0, 10, 'RELATORIO ESTRATEGICO - TRIADE AGRO', 0, 1, 'C'); self.ln(10)

    def secao_mapa(self, titulo, img_buf, stats, desc):
        self.add_page(); self.set_font('Arial', 'B', 12); self.cell(0, 10, titulo, 0, 1, 'L')
        img_path = f"temp_{titulo.replace(' ', '_').replace('/', '_')}.png"
        with open(img_path, "wb") as f: f.write(img_buf.getbuffer())
        self.image(img_path, x=45, w=120); self.ln(5)
        self.set_font('Arial', 'B', 10); self.cell(0, 10, stats, 0, 1, 'C'); self.ln(5)
        self.set_font('Arial', '', 10); self.multi_cell(0, 5, desc)
        if os.path.exists(img_path): os.remove(img_path)

# --- 3. NAVEGAÇÃO ---
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Consultoria Técnica", type="password")
        if st.button("ACESSAR PLATAFORMA", use_container_width=True):
            if senha == "triade2026": st.session_state.pagina = "Upload"; st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Importação A-Y e Contorno")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.produtor = st.text_input("Produtor", "Danilo")
        st.session_state.fazenda = st.text_input("Fazenda", "Berneck")
        st.session_state.municipio = st.text_input("Município")
    with c2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha Solo (.xlsx)", type=['xlsx'])
    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 INICIAR DASHBOARD"): st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    tabs = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações", "📄 PDF & Exportação"])
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry']); minx, miny, maxx, maxy = geom.bounds

    # --- ABA 1: ATRIBUTOS (Fórmulas Corrigidas) ---
    with tabs[0]:
        st.subheader("Painel de Controle de Insumos")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🪨 Calcário")
            p_ca_des = st.number_input("Ca% desejado CTC", 60.0); p_mg_des = st.number_input("Mg% desejado CTC", 18.0)
            p_prnt = st.number_input("PRNT %", 80.0); p_adicional = st.number_input("Adicional Calcário (t/ha)", 0.0)
        with c2:
            st.markdown("### 🧪 Fósforo ($P_{rem}$)")
            nc_list = [st.number_input(f"NC Classe {i}", v) for i, v in enumerate([8.0, 10.0, 12.0, 15.0, 20.0, 25.0])]
            f_arg = st.number_input("Fator Argiloso (P)", 8.0); p_exp_p = st.number_input("Exp. P (kg/sc)", 0.8)
        with c3:
            st.markdown("### 🍌 Potássio & 🧪 Gesso")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_k_des = st.number_input("K% desejado CTC", 3.2); p_exp_k = st.number_input("Exp. K (kg/sc)", 1.2)
            k_fator = st.number_input("Fator Atômico K", 391.0) # <--- SEU PEDIDO

    # --- MOTOR DE MAPAS HD ---
    def render_mapa(col_id, titulo, desc):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[col_id], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 200), np.linspace(miny, maxy, 200)
        z, ss = OK.execute('grid', gx, gy); z_mask = np.full(z.shape, np.nan)
        for i in range(len(gy)):
            for j in range(len(gx)):
                if geom.contains(Point(gx[j], gy[i])): z_mask[i, j] = z[i, j]
        v_max, v_med, v_min = np.nanmax(z_mask), np.nanmean(z_mask), np.nanmin(z_mask)
        z_norm = (z_mask - v_min) / (v_max - v_min) if v_max > v_min else z_mask * 0
        fig, ax = plt.subplots(figsize=(8, 7)); ax.axis('off')
        ax.imshow(z_norm, cmap=cmap_6, norm=norm_6, origin='lower', extent=[minx, maxx, miny, maxy])
        buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0); plt.close(fig)
        st.session_state.mapas_sessao[col_id] = {"img": buf, "stats": f"Max: {v_max:.2f} | Med: {v_med:.2f} | Min: {v_min:.2f}", "titulo": titulo, "desc": desc}
        
        m = folium.Map(location=[geom.centroid.y, geom.centroid.x], zoom_start=15, tiles=None)
        folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri').add_to(m)
        folium.raster_layers.ImageOverlay(image=np.array(Image.open(buf)), bounds=[[miny, minx], [maxy, maxx]], opacity=0.8).add_to(m)
        # CONTORNO AMARELO GROSSO
        folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'yellow', 'weight': 5}).add_to(m)
        folium_static(m, width=1000, height=700)
        st.write(f"📊 **Max:** {v_max:.2f} | **Méd:** {v_med:.2f} | **Mín:** {v_min:.2f}")

    # --- MOTOR DE RECOMENDAÇÕES ---
    with tabs[2]:
        # 1. CALCÁRIO CORRIGIDO (Relação 1:1 cmolc para t/ha)
        nc_ca = ((p_ca_des - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100) * (100 / p_prnt)
        nc_mg = ((p_mg_des - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100) * (100 / p_prnt)
        df['REC_CALC'] = (np.maximum(nc_ca, nc_mg) + p_adicional).round(2)

        # 2. POTÁSSIO (Fator 391)
        df['REC_K_ADUBO'] = ((((p_k_des - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) * k_fator * 2 * 1.2) + (p_prod * p_exp_k * 1.2)).round(2)

        # 3. FÓSFORO (Economia de Gordura)
        df['NC_P'] = df['PREM'].apply(lambda x: nc_list[0] if x<=4 else (nc_list[1] if x<=10 else (nc_list[2] if x<=19 else (nc_list[3] if x<=30 else (nc_list[4] if x<=45 else nc_list[5])))))
        df['REC_P_ADUBO'] = ((((df['NC_P'] - df['P']).clip(lower=0) * f_arg) + (p_prod * p_exp_p)) - (df['P'] - df['NC_P']).clip(lower=0)).clip(lower=0)

        sel_vr = st.selectbox("Selecione Recomendação:", ['REC_CALC', 'REC_P_ADUBO', 'REC_K_ADUBO'])
        if st.button("Gerar Prescrição"): render_mapa(sel_vr, sel_vr, "Motor Tríade Agro v1.31")

    with tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📥 EXPORTAR PDF"):
                pdf = PDF()
                for k, m in st.session_state.mapas_sessao.items(): pdf.secao_mapa(m['titulo'], m['img'], m['stats'], m['desc'])
                st.download_button("Baixar PDF", bytes(pdf.output()), "Relatorio_Triade.pdf")
        with c2:
            if st.button("🚜 GERAR EXPORTAÇÃO MÁQUINAS"):
                zip_b = io.BytesIO()
                with zipfile.ZipFile(zip_b, "w") as z:
                    z.writestr("John_Deere/Rx/prescricao.shp", "SHP JD")
                    z.writestr("Case_IH/TaskData/prescricao.xml", "ISOXML CASE")
                st.download_button("Baixar ZIP", zip_b.getvalue(), "Exportacao_Triade.zip")
