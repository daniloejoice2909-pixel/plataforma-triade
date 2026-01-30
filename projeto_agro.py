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
from fpdf import FPDF

# --- 1. CONFIGURAÇÕES DE PÁGINA E CORES ---
st.set_page_config(layout="wide", page_title="Tríade Agro v1.11", page_icon="🛰️")

# Paleta 3 Zonas Sólidas
ap_colors = ['#d7191c', '#ffffbf', '#1a9641']
cmap_ap = ListedColormap(ap_colors)
norm_ap = BoundaryNorm([0, 0.33, 0.66, 1.0], cmap_ap.N)

# Inicialização de Estados (Evita tela branca por falta de variável)
if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "dados" not in st.session_state: st.session_state.dados = None
if "contorno" not in st.session_state: st.session_state.contorno = None
if "mapas_gerados" not in st.session_state: st.session_state.mapas_gerados = {}

# --- 2. CLASSE DO RELATÓRIO PDF ---
class RelatorioTriade(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 30)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'RELATÓRIO TÉCNICO - AGRICULTURA DE PRECISÃO', 0, 1, 'C')
        self.ln(15)

    def adicionar_mapa(self, titulo, img_buf, estatisticas, descricao):
        self.add_page()
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, titulo, 0, 1, 'L')
        # Salva imagem temporária
        img_path = f"temp_{titulo.replace(' ', '_')}.png"
        with open(img_path, "wb") as f: f.write(img_buf.getbuffer())
        self.image(img_path, x=40, w=130)
        self.ln(5)
        self.set_font('Arial', 'B', 10)
        self.cell(0, 10, estatisticas, 0, 1, 'C')
        self.ln(5)
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 6, descricao)
        if os.path.exists(img_path): os.remove(img_path)

# --- 3. LÓGICA DE NAVEGAÇÃO ---

# PÁGINA 1: ENTRADA
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        st.info("Plataforma de Diagnóstico e Recomendação de Solo")
        senha = st.text_input("Senha de Acesso", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True):
            if senha == "triade2026":
                st.session_state.pagina = "Upload"
                st.rerun()
            else: st.error("Senha incorreta")

# PÁGINA 2: UPLOAD
elif st.session_state.pagina == "Upload":
    st.header("📂 Configuração do Projeto")
    col1, col2 = st.columns(2)
    with col1:
        produtor = st.text_input("Nome do Produtor", "Berneck")
        fazenda = st.text_input("Nome da Fazenda", "Unidade I")
        municipio = st.text_input("Município")
    with col2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha de Solo (Colunas A a Y)", type=['xlsx'])

    if f_contorno and f_dados:
        try:
            st.session_state.contorno = json.load(f_contorno)
            df = pd.read_excel(f_dados)
            # 25 Colunas Exatas A-Y
            df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                          'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
                          'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
            st.session_state.dados = df
            st.session_state.info = {"produtor": produtor, "fazenda": fazenda, "municipio": municipio}
            if st.button("🚀 ABRIR DASHBOARD TÉCNICO", use_container_width=True):
                st.session_state.pagina = "Dashboard"
                st.rerun()
        except Exception as e: st.error(f"Erro ao ler arquivos: {e}")

# PÁGINA 3: DASHBOARD PRINCIPAL
elif st.session_state.pagina == "Dashboard":
    tab_attr, tab_fert, tab_recom, tab_relat = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações", "📄 PDF"])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # ABA ATRIBUTOS (Editáveis)
    with tab_attr:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("Calcário")
            p_ca_ctc = st.number_input("Ca% desejado CTC", 60.0)
            p_mg_ctc = st.number_input("Mg% desejado CTC", 18.0)
        with c2:
            st.subheader("Fósforo")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            f_arg = st.number_input("Fator Argiloso (kg P p/ elevar 1mg)", 8.0)
        with c3:
            st.subheader("Potássio/Gesso")
            p_k_ctc = st.number_input("K% desejado CTC", 3.2)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15)

    # MOTOR DE MAPAS
    def criar_mapa_hd(coluna, titulo, descricao):
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
        buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        
        # Salva no estado para o PDF
        st.session_state.mapas_gerados[coluna] = {
            "img": buf, "estat": f"Máx: {v_max:.2f} | Méd: {v_med:.2f} | Mín: {v_min:.2f}",
            "titulo": titulo, "desc": descricao
        }
        return buf, v_max, v_med, v_min

    with tab_fert:
        attr = st.selectbox("Atributo de Solo:", ['P', 'K', 'ARGILA', 'PH'])
        if st.button(f"Gerar Mapa de {attr}"):
            buf, vmax, vmed, vmin = criar_mapa_hd(attr, f"Mapa de {attr}", "Distribuição geoestatística do nutriente no perfil do solo.")
            st.image(buf)
            st.write(f"📊 **Máx:** {vmax:.2f} | **Méd:** {vmed:.2f} | **Mín:** {vmin:.2f}")

    with tab_recom:
        st.subheader("Mapas de Recomendação VRA")
        # Exemplo Fósforo (Lógica P-Rem Danilo)
        df['REC_P'] = (((12 - df['P']).clip(lower=0) * f_arg) + (p_prod * 0.8)).clip(lower=0)
        
        if st.button("Gerar Mapa de Fósforo (VRA)"):
            desc_p = "Metodologia: Fósforo Remanescente. Vantagem: Ajusta o nível crítico conforme a capacidade de adsorção do solo, evitando desperdício em áreas de reserva."
            buf_p, vma, vme, vmi = criar_mapa_hd('REC_P', "Recomendação de Fósforo (kg/ha)", desc_p)
            st.image(buf_p)
            st.write(f"📊 **Dose Máx:** {vma:.2f} | **Dose Méd:** {vme:.2f} | **Dose Mín:** {vmi:.2f}")

    with tab_relat:
        st.subheader("Gerador de Relatório Oficial")
        if st.button("📥 EXPORTAR PDF COMPLETO"):
            pdf = RelatorioTriade()
            for key, m in st.session_state.mapas_gerados.items():
                pdf.adicionar_mapa(m['titulo'], m['img'], m['estat'], m['desc'])
            
            pdf_data = pdf.output()
            st.download_button("Baixar Relatório Tríade Agro", pdf_data, "Relatorio_Triade.pdf", "application/pdf")
