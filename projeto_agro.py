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

# --- 1. CONFIGURAÇÕES VISUAIS E ESTADOS ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.0", page_icon="🛰️")

# Paleta de 3 Zonas (Vermelho, Amarelo, Verde)
ap_colors = ['#d7191c', '#ffffbf', '#1a9641']
cmap_ap = ListedColormap(ap_colors)
norm_ap = BoundaryNorm([0, 0.33, 0.66, 1.0], cmap_ap.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "mapas_sessao" not in st.session_state: st.session_state.mapas_sessao = {}

# --- 2. MOTOR DE RELATÓRIO PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 30)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'RELATÓRIO ESTRATÉGICO DE AGRICULTURA DE PRECISÃO', 0, 1, 'C')
        self.ln(10)

    def secao_mapa(self, titulo, img_buf, stats, justificativa):
        self.add_page()
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, titulo, 0, 1, 'L')
        img_path = f"temp_{titulo.replace(' ', '_')}.png"
        with open(img_path, "wb") as f: f.write(img_buf.getbuffer())
        self.image(img_path, x=45, w=120)
        self.ln(5)
        self.set_font('Arial', 'B', 10)
        self.cell(0, 10, stats, 0, 1, 'C')
        self.ln(5)
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, justificativa)
        if os.path.exists(img_path): os.remove(img_path)

# --- 3. FLUXO DE NAVEGAÇÃO ---

# PÁGINA 1: LOGIN
if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Senha de Acesso Técnico", type="password")
        if st.button("ACESSAR PLATAFORMA", use_container_width=True):
            if senha == "triade2026":
                st.session_state.pagina = "Upload"
                st.rerun()
            else: st.error("Acesso Negado")

# PÁGINA 2: CONFIGURAÇÃO DE PROJETO
elif st.session_state.pagina == "Upload":
    st.header("📂 Configuração do Projeto e Importação")
    col1, col2 = st.columns(2)
    with col1:
        produtor = st.text_input("Nome do Produtor")
        fazenda = st.text_input("Nome da Fazenda")
        municipio = st.text_input("Município")
    with col2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha de Solo (A-Y)", type=['xlsx'])

    if f_contorno and f_dados:
        try:
            st.session_state.contorno = json.load(f_contorno)
            df = pd.read_excel(f_dados)
            # Colunas A a Y (25 Colunas)
            df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                          'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
                          'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
            st.session_state.dados = df
            st.session_state.info = {"produtor": produtor, "fazenda": fazenda, "municipio": municipio}
            if st.button("🚀 INICIAR DASHBOARD ESTRATÉGICO", use_container_width=True):
                st.session_state.pagina = "Dashboard"; st.rerun()
        except Exception as e: st.error(f"Erro nos arquivos: {e}")

# PÁGINA 3: DASHBOARD COMPLETO
elif st.session_state.pagina == "Dashboard":
    tab_at, tab_fe, tab_vr, tab_rel = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 Relatório & Exportação"])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA ATRIBUTOS (100% EDITÁVEL) ---
    with tab_at:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### Calcário")
            p_cao = st.number_input("CaO %", 36.0); p_mgo = st.number_input("MgO %", 9.0)
            p_prnt = st.number_input("PRNT %", 80.0); p_ca_ctc = st.number_input("Ca% desejado CTC", 60.0)
            p_mg_ctc = st.number_input("Mg% desejado CTC", 18.0); p_preco_c = st.number_input("Preço Calcário (t)", 190.0)
        with c2:
            st.markdown("### Fósforo (P-Rem)")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp_f = st.number_input("Fator Exp. P (kg/sc)", 0.8)
            p_adubo_p = st.number_input("% P2O5 no Adubo", 21.0); p_preco_p = st.number_input("Preço Adubo P", 2800.0)
            st.write("Fatores de Textura (kg P p/ 1mg):")
            f_m_arg = st.number_input("M. Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0)
            f_med = st.number_input("Médio", 4.0); f_are = st.number_input("Arenoso", 2.0)
        with c3:
            st.markdown("### Potássio & Gesso")
            p_k_ctc = st.number_input("K% desejado CTC", 3.2); p_exp_k = st.number_input("Fator Exp. K (kg/sc)", 1.2)
            p_ad_k = st.number_input("% K2O Adubo K", 60.0); g_fator = st.number_input("Fator Gesso (Arg * F)", 15)
            g_max = st.number_input("Dose Máx Gesso", 900.0); g_min = st.number_input("Dose Mín Gesso", 400.0)

    # --- MOTOR DE KRIGAGEM COM RECORTE ---
    def render_mapa(col_id, titulo, desc):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[col_id], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 180), np.linspace(miny, maxy, 180)
        z, ss = OK.execute('grid', gx, gy)
        z_mask = np.full(z.shape, np.nan)
        for i in range(len(gy)):
            for j in range(len(gx)):
                if geom.contains(Point(gx[j], gy[i])): z_mask[i, j] = z[i, j]
        
        v_max, v_med, v_min = np.nanmax(z_mask), np.nanmean(z_mask), np.nanmin(z_mask)
        fig, ax = plt.subplots(figsize=(7, 6)); ax.axis('off')
        ax.imshow(z_mask, cmap=cmap_ap, norm=norm_ap, origin='lower', extent=[minx, maxx, miny, maxy])
        buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0); plt.close(fig)
        
        st.session_state.mapas_sessao[col_id] = {
            "img": buf, "stats": f"Máx: {v_max:.2f} | Méd: {v_med:.2f} | Mín: {v_min:.2f}",
            "titulo": titulo, "desc": desc
        }
        return buf, v_max, v_med, v_min

    # --- ABA FERTILIDADE ---
    with tab_fe:
        attr = st.selectbox("Selecione o Atributo de Solo:", ['P', 'K', 'PH', 'ARGILA', 'CTC', 'PREM'])
        if st.button(f"Gerar Mapa de {attr}"):
            b, vmax, vmed, vmin = render_mapa(attr, f"Mapa de {attr}", "Análise da variabilidade espacial dos teores no solo.")
            st.image(b)
            st.write(f"📊 **Máx:** {vmax:.2f} | **Méd:** {vmed:.2f} | **Mín:** {vmin:.2f}")

    # --- ABA RECOMENDAÇÕES VRA ---
    with tab_vr:
        st.subheader("Mapas de Recomendação em Taxa Variável")
        # Cálculos de Prescrição
        df['REC_P_ADUBO'] = (((12 - df['P']).clip(lower=0) * f_arg) + (p_prod * p_exp_f)).clip(lower=0)
        df['REC_K_ADUBO'] = (((p_k_ctc - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) + (p_prod * p_exp_k)).clip(lower=0)
        df['REC_GESSO'] = (df['ARGILA'] * g_fator / 10).clip(lower=g_min, upper=g_max)
        
        sel_vra = st.selectbox("Insumo VRA:", ['REC_P_ADUBO', 'REC_K_ADUBO', 'REC_GESSO'])
        if st.button(f"Gerar Prescrição: {sel_vra}"):
            j_p = "Metodologia: Fósforo Remanescente. Vantagem: Otimiza a dose conforme a capacidade de fixação do solo."
            j_k = "Metodologia: Equilíbrio de Potássio na CTC. Vantagem: Garante a reposição da exportação e a manutenção do nível crítico."
            j_g = "Metodologia: Fator de Argila. Vantagem: Melhora o ambiente radicular em profundidade."
            just = j_p if 'P' in sel_vra else (j_k if 'K' in sel_vra else j_g)
            
            b, vmax, vmed, vmin = render_mapa(sel_vra, f"Recomendação VRA: {sel_vra}", just)
            st.image(b); st.write(f"📊 **Dose Máx:** {vmax:.2f} | **Dose Méd:** {vmed:.2f} | **Dose Mín:** {vmin:.2f}")

    # --- ABA RELATÓRIO PDF ---
    with tab_rel:
        st.subheader("Gerador de Relatórios e Exportação")
        if st.button("📥 GERAR RELATÓRIO PDF OFICIAL"):
            pdf = PDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f"Produtor: {st.session_state.info['produtor']} | Fazenda: {st.session_state.info['fazenda']}", 0, 1)
            pdf.cell(0, 10, f"Município: {st.session_state.info['municipio']}", 0, 1)
            pdf.ln(10)
            
            for k, m in st.session_state.mapas_sessao.items():
                pdf.secao_mapa(m['titulo'], m['img'], m['stats'], m['desc'])
            
            pdf_data = pdf.output()
            st.download_button("Clique para Baixar o Relatório", pdf_data, "Relatorio_Triade_Agro.pdf")
