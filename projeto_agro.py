
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

# --- 1. CONFIGURAÇÕES VISUAIS ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.0", page_icon="🌱")

# Paleta 6 Camadas: Azul (Alto/Suficiente) ao Vermelho (Crítico/Baixo)
colors_6 = ['#4575b4', '#91bfdb', '#d9ef8b', '#fee090', '#fc8d59', '#d73027']
cmap_6 = ListedColormap(colors_6)
norm_6 = BoundaryNorm(np.linspace(0, 1, 7), cmap_6.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "mapas_recom_pdf" not in st.session_state: st.session_state.mapas_recom_pdf = {}
if "info" not in st.session_state: st.session_state.info = {}

# --- 2. MOTOR DE RELATÓRIO PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 30)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'RELATÓRIO DE PRESCRIÇÃO - TRÍADE AGRO', 0, 1, 'C')
        self.ln(10)

    def secao_mapa(self, titulo, img_buf, stats, desc):
        self.add_page()
        self.set_font('Arial', 'B', 12); self.cell(0, 10, titulo.upper(), 0, 1, 'L')
        safe_name = titulo.replace(' ', '_').replace('/', '_')
        path = f"temp_{safe_name}.png"
        with open(path, "wb") as f: f.write(img_buf.getbuffer())
        self.image(path, x=45, w=120)
        self.ln(5)
        self.set_font('Arial', 'B', 10); self.cell(0, 10, stats, 0, 1, 'C')
        self.ln(5); self.set_font('Arial', '', 11); self.multi_cell(0, 6, desc)
        if os.path.exists(path): os.remove(path)

# --- 3. NAVEGAÇÃO ---
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Consultoria Técnica", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True):
            if senha == "triade2026": st.session_state.pagina = "Upload"; st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Cadastro e Importação A-Y")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.info['produtor'] = st.text_input("Produtor", "Danilo")
        st.session_state.info['fazenda'] = st.text_input("Fazenda", "Berneck")
        st.session_state.info['municipio'] = st.text_input("Município")
    with c2:
        f_contorno = st.file_uploader("Upload Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Upload Planilha Solo (A-Y)", type=['xlsx'])
    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 ABRIR PLATAFORMA", use_container_width=True): st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    tabs = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 Relatório & Exportação"])
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry']); minx, miny, maxx, maxy = geom.bounds

    with tabs[0]:
        st.subheader("Configuração Global de Parâmetros")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🪨 Calcário & Calagem")
            p_ca_des = st.number_input("Ca% desejado na CTC", 60.0); p_mg_des = st.number_input("Mg% desejado na CTC", 18.0)
            p_prnt = st.number_input("PRNT %", 80.0); p_calc_extra = st.number_input("Adicional Calcário (t/ha)", 0.0)
        with c2:
            st.markdown("### 🧪 Fósforo ($P_{rem}$)")
            nc1 = st.number_input("NC Classe 1 (0-4)", 8.0); nc2 = st.number_input("NC Classe 2 (4.1-10)", 10.0)
            nc3 = st.number_input("NC Classe 3 (10.1-19)", 12.0); nc4 = st.number_input("NC Classe 4 (19.1-30)", 15.0)
            nc5 = st.number_input("NC Classe 5 (30.1-45)", 20.0); nc6 = st.number_input("NC Classe 6 (45-60)", 25.0)
            f_marg = st.number_input("Fator M. Argiloso (P)", 10.0); f_arg = st.number_input("Fator Argiloso (P)", 8.0)
            p_exp_p = st.number_input("Fator Exportação P (kg/sc)", 0.8); p_perc_p = st.number_input("% P2O5 Adubo", 21.0)
        with c3:
            st.markdown("### 🍌 Potássio & 🧪 Gesso")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_k_des = st.number_input("K% desejado na CTC", 3.2); p_exp_k = st.number_input("Fator Exportação K (kg/sc)", 1.2)
            k_fator_391 = st.number_input("Fator Atômico K", 391.0); p_perc_k = st.number_input("% K2O Adubo", 60.0)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15); g_max = st.number_input("Dose Máx Gesso", 900.0)

    def render_mapa_triade(col_id, titulo, desc, is_recom=False):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[col_id], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 250), np.linspace(miny, maxy, 250)
        z, ss = OK.execute('grid', gx, gy); z_mask = np.full(z.shape, np.nan)
        for i in range(len(gy)):
            for j in range(len(gx)):
                if geom.contains(Point(gx[j], gy[i])): z_mask[i, j] = z[i, j]
        v_max, v_med, v_min = np.nanmax(z_mask), np.nanmean(z_mask), np.nanmin(z_mask)
        z_norm = (z_mask - v_min) / (v_max - v_min) if v_max > v_min else z_mask * 0
        fig, ax = plt.subplots(figsize=(8, 7)); ax.axis('off')
        ax.imshow(z_norm, cmap=cmap_6, norm=norm_6, origin='lower', extent=[minx, maxx, miny, maxy])
        buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0); plt.close(fig)
        if is_recom: st.session_state.mapas_recom_pdf[col_id] = {"img": buf, "stats": f"Máx: {v_max:.2f} | Méd: {v_med:.2f} | Mín: {v_min:.2f}", "titulo": titulo, "desc": desc}
        m = folium.Map(location=[geom.centroid.y, geom.centroid.x], zoom_start=15, tiles=None)
        folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri').add_to(m)
        folium.raster_layers.ImageOverlay(image=np.array(Image.open(buf)), bounds=[[miny, minx], [maxy, maxx]], opacity=0.85).add_to(m)
        folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'black', 'weight': 5}).add_to(m)
        folium_static(m, width=1000, height=700)
        st.write(f"📊 Máximo: {v_max:.2f} | Médio: {v_med:.2f} | Mínimo: {v_min:.2f}")

    with tabs[1]:
        sel_f = st.selectbox("Mapa de Fertilidade:", ['P', 'K', 'PH', 'ARGILA', 'PREM', 'CTC', 'CA', 'MG'])
        if st.button("Gerar Visualização"): render_mapa_triade(sel_f, f"Fertilidade: {sel_f}", "Diagnóstico de Solo", is_recom=False)

    with tabs[2]:
        # MOTOR DE RECOMENDAÇÃO (Fórmulas Danillo)
        # Calcário (Maior Dose)
        df['REC_CALC'] = (np.maximum(((p_ca_des - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt), 
                                     ((p_mg_des - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt)) + p_calc_extra).round(2)
        # Fósforo (Gordura subtrai da Exportação)
        df['NC_P_D'] = df['PREM'].apply(lambda x: nc1 if x<=4 else (nc2 if x<=10 else (nc3 if x<=19 else (nc4 if x<=30 else (nc5 if x<=45 else nc6)))))
        df['F_TEXT_D'] = df['ARGILA'].apply(lambda x: f_marg if x>600 else f_arg)
        df['P_GORDURA'] = (df['P'] - df['NC_P_D']).clip(lower=0) * df['F_TEXT_D']
        df['P_ELEV'] = (df['NC_P_D'] - df['P']).clip(lower=0) * df['F_TEXT_D']
        df['REC_P_ADUBO'] = (((df['P_ELEV'] + (p_prod * p_exp_p)) - df['P_GORDURA']).clip(lower=0) * 100 / p_perc_p).round(2)
        # Potássio (Soma Incondicional da Exportação)
        df['K_LACUNA'] = ((p_k_des - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) * k_fator_391 * 2 * 1.2
        df['REC_K_ADUBO'] = (((df['K_LACUNA'] + (p_prod * p_exp_k))) * 100 / p_perc_k).round(2)
        # Gesso
        df['REC_GESSO'] = (df['ARGILA'] * g_fator / 10).clip(lower=400, upper=g_max).round(2)

        sel_vr = st.selectbox("Recomendação VRA:", ['REC_CALC', 'REC_P_ADUBO', 'REC_K_ADUBO', 'REC_GESSO'])
        if st.button("Gerar Recomendação"):
            v_p = f"Metodologia: Fósforo Remanescente. Vantagem: Utiliza a gordura do solo para abater a exportação de {p_prod} sc/ha."
            v_k = f"Metodologia: Elevação CTC para {p_k_des}% + Reposição de Exportação. Vantagem: Balanço de massa sustentável."
            just = v_p if 'P_ADUBO' in sel_vr else (v_k if 'K_ADUBO' in sel_vr else "Equilíbrio de Bases.")
            render_mapa_triade(sel_vr, sel_vr, just, is_recom=True)

    with tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📥 EXPORTAR PDF RECOMENDAÇÕES"):
                pdf = PDF(); pdf.add_page(); pdf.set_font('Arial', 'B', 12)
                f_n = st.session_state.info.get('fazenda', 'Fazenda'); p_n = st.session_state.info.get('produtor', 'Produtor')
                pdf.cell(0, 10, f"Fazenda: {f_n} | Produtor: {p_n}", 0, 1)
                for k, m in st.session_state.mapas_recom_pdf.items(): pdf.secao_mapa(m['titulo'], m['stats'], m['desc'])
                st.download_button("Baixar PDF", bytes(pdf.output()), f"Relatorio_Recomendações_{f_n}.pdf", "application/pdf")
        with c2:
            if st.button("🚜 EXPORTAR ZIP MÁQUINAS"):
                zip_b = io.BytesIO()
                with zipfile.ZipFile(zip_b, "w") as z:
                    z.writestr("John_Deere/prescricao.shp", "Dados espaciais JD"); z.writestr("Case_IH/prescricao.xml", "ISOXML CASE")
                st.download_button("Baixar ZIP", zip_b.getvalue(), "Exportacao_Triade_VRA.zip")
