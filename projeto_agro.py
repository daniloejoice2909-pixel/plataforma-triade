import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
import io
import os
from streamlit_folium import folium_static
from pykrige.ok import OrdinaryKriging
from shapely.geometry import shape, Point
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from PIL import Image
from fpdf import FPDF # Requer fpdf2

# --- 1. CONFIGURAÇÕES TÉCNICAS E CORES ---
st.set_page_config(layout="wide", page_title="Tríade Agro - Estratégica 1.10")

ap_colors = ['#d7191c', '#ffffbf', '#1a9641'] # Vermelho, Amarelo, Verde
cmap_ap = ListedColormap(ap_colors)
norm_ap = BoundaryNorm([0, 0.33, 0.66, 1.0], cmap_ap.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "mapas_gerados" not in st.session_state: st.session_state.mapas_gerados = {}

# --- 2. MOTOR DE GERAÇÃO DE PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 33)
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, 'Relatorio Tecnico de Agricultura de Precisao', 0, 0, 'C')
        self.ln(20)

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, label, 0, 1, 'L', fill=True)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

# --- 3. PÁGINA DE ENTRADA ---
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Estrategico", type="password")
        if st.button("ACESSAR PLATAFORMA"):
            if senha == "triade2026": st.session_state.pagina = "Upload"; st.rerun()

# --- 4. DASHBOARD ESTRATÉGICO ---
elif st.session_state.pagina == "Dashboard":
    tab_attr, tab_fert, tab_recom, tab_relat = st.tabs([
        "⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 Relatorio Final PDF"
    ])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    with tab_attr:
        st.subheader("Configuracoes de Insumos")
        c1, c2, c3 = st.columns(3)
        with c1:
            p_cao = st.number_input("CaO %", 36.0); p_mgo = st.number_input("MgO %", 9.0)
            p_ca_ctc = st.number_input("Ca% desejado CTC", 60.0); p_mg_ctc = st.number_input("Mg% desejado CTC", 18.0)
        with c2:
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp_p = st.number_input("Fator Exp. P (kg/sc)", 0.8)
            f_arg = st.number_input("Fator Argiloso (kg P p/ 1mg)", 8.0)
        with c3:
            p_k_ctc = st.number_input("K% desejado CTC", 3.2)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15)

    # --- FUNÇÃO DE MAPEAMENTO ---
    def processar_mapa(coluna, titulo, subtitulo):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[coluna], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 150), np.linspace(miny, maxy, 150)
        z, ss = OK.execute('grid', gx, gy)
        z_f = np.full(z.shape, np.nan)
        for i in range(len(gy)):
            for j in range(len(gx)):
                if geom.contains(Point(gx[j], gy[i])): z_f[i, j] = z[i, j]
        
        v_max, v_med, v_min = np.nanmax(z_f), np.nanmean(z_f), np.nanmin(z_f)
        fig, ax = plt.subplots(figsize=(6, 5)); ax.axis('off')
        ax.imshow(z_f, cmap=cmap_ap, norm=norm_ap, origin='lower', extent=[minx, maxx, miny, maxy])
        buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        
        st.session_state.mapas_gerados[coluna] = {
            "img": buf, "max": v_max, "med": v_med, "min": v_min, "titulo": titulo, "desc": subtitulo
        }
        return buf

    with tab_fert:
        sel = st.selectbox("Atributo:", ['P', 'K', 'PH', 'ARGILA'])
        if st.button(f"Mapear {sel}"):
            img_buf = processar_mapa(sel, f"Mapa de {sel}", "Analise geoestatistica da variabilidade nutricional.")
            st.image(img_buf)

    with tab_recom:
        st.subheader("Mapas de Prescricao")
        # Calculo Potassio (Exemplo)
        df['REC_POTASSIO'] = (((p_k_ctc - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) + (p_prod * 1.2)) * 1.66
        
        if st.button("Gerar Recomendacao Potassio"):
            desc_k = "Metodologia: Elevacao da saturacao de potassio na CTC para 3.2% somada a reposicao de exportacao. Vantagem: Mantem o equilibrio cationico e evita o esgotamento das reservas pelo alto teto produtivo."
            img_k = processar_mapa('REC_POTASSIO', 'Recomendacao de Potassio (K2O)', desc_k)
            st.image(img_k)

    with tab_relat:
        if st.button("📥 GERAR RELATÓRIO PDF COMPLETO"):
            pdf = PDF()
            pdf.add_page()
            pdf.chapter_title(f"Cliente: {st.session_state.produtor} | Fazenda: {st.session_state.fazenda}")
            
            for m_id, m_data in st.session_state.mapas_gerados.items():
                pdf.chapter_title(m_data['titulo'])
                # Salva imagem temporária para o PDF
                with open(f"temp_{m_id}.png", "wb") as f: f.write(m_data['img'].getbuffer())
                pdf.image(f"temp_{m_id}.png", x=50, w=110)
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 10, f"Max: {m_data['max']:.2f} | Med: {m_data['med']:.2f} | Min: {m_data['min']:.2f}", 0, 1, 'C')
                pdf.chapter_body(m_data['desc'])
                pdf.ln(10)
            
            pdf_output = pdf.output()
            st.download_button("Clique para Baixar o Relatorio", pdf_output, "Relatorio_Triade_Agro.pdf")
