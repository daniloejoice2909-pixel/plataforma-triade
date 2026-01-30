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

# --- 1. CONFIGURAÇÕES E ESTADOS ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.13", page_icon="🛰️")

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
        self.cell(0, 10, 'RELATORIO ESTRATEGICO - TRIADE AGRO', 0, 1, 'C')
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

if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Senha de Acesso", type="password")
        if st.button("ACESSAR PLATAFORMA", use_container_width=True):
            if senha == "triade2026":
                st.session_state.pagina = "Upload"; st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Importação de Dados (Berneck)")
    col1, col2 = st.columns(2)
    with col1:
        produtor = st.text_input("Produtor", "Danilo")
        fazenda = st.text_input("Fazenda", "Berneck")
        municipio = st.text_input("Município")
    with col2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha Solo (A a Y)", type=['xlsx'])

    if f_contorno and f_dados:
        try:
            st.session_state.contorno = json.load(f_contorno)
            df = pd.read_excel(f_dados)
            df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                          'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
                          'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
            st.session_state.dados = df
            st.session_state.info = {"produtor": produtor, "fazenda": fazenda, "municipio": municipio}
            if st.button("🚀 ABRIR DASHBOARD TÉCNICO"):
                st.session_state.pagina = "Dashboard"; st.rerun()
        except Exception as e: st.error(f"Erro nos arquivos: {e}")

elif st.session_state.pagina == "Dashboard":
    tab_at, tab_fe, tab_vr, tab_rel = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 Relatório PDF"])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA ATRIBUTOS (COM CLASSES DE P-REM EDITÁVEIS) ---
    with tab_at:
        st.subheader("⚙️ Configuração de Recomendação de Solo")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**1. Fósforo ($P_{rem}$) - Níveis Críticos**")
            nc1 = st.number_input("Prem 0 a 4 (NC)", value=8.0)
            nc2 = st.number_input("Prem 4 a 10 (NC)", value=10.0)
            nc3 = st.number_input("Prem 10 a 19 (NC)", value=12.0)
            nc4 = st.number_input("Prem 19 a 30 (NC)", value=15.0)
            nc5 = st.number_input("Prem 30 a 45 (NC)", value=20.0)
            nc6 = st.number_input("Prem > 45 (NC)", value=25.0)
        with c2:
            st.markdown("**2. Fatores de Textura e Exportação**")
            p_prodesp = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp_f = st.number_input("Fator Exportação P (kg/sc)", 0.8)
            f_marg = st.number_input("Fator M. Argiloso (kg P/mg)", 10.0)
            f_arg = st.number_input("Fator Argiloso (kg P/mg)", 8.0)
            f_med = st.number_input("Fator Médio (kg P/mg)", 4.0)
            f_are = st.number_input("Fator Arenoso (kg P/mg)", 2.0)
            p_perc_adubo = st.number_input("% $P_2O_5$ no Adubo", 21.0)
        with c3:
            st.markdown("**3. Calcário, Potássio e Gesso**")
            p_ca_ctc = st.number_input("Ca% desejado CTC", 60.0)
            p_mg_ctc = st.number_input("Mg% desejado CTC", 18.0)
            p_k_ctc = st.number_input("K% desejado CTC", 3.2)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15)
            g_max = st.number_input("Dose Máxima Gesso", 900.0)

    # --- MOTOR DE KRIGAGEM HD ---
    def render_mapa(col_id, titulo, desc):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[col_id], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 150), np.linspace(miny, maxy, 150)
        z, ss = OK.execute('grid', gx, gy)
        z_mask = np.full(z.shape, np.nan)
        for i in range(len(gy)):
            for j in range(len(gx)):
                if geom.contains(Point(gx[j], gy[i])): z_mask[i, j] = z[i, j]
        
        v_max, v_med, v_min = np.nanmax(z_mask), np.nanmean(z_mask), np.nanmin(z_mask)
        fig, ax = plt.subplots(figsize=(8, 7)); ax.axis('off')
        ax.imshow(z_mask, cmap=cmap_ap, norm=norm_ap, origin='lower', extent=[minx, maxx, miny, maxy])
        buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0); plt.close(fig)
        st.session_state.mapas_sessao[col_id] = {"img": buf, "stats": f"Max: {v_max:.2f} | Med: {v_med:.2f} | Min: {v_min:.2f}", "titulo": titulo, "desc": desc}
        return buf, v_max, v_med, v_min

    with tab_fe:
        sel = st.selectbox("Mapa de Fertilidade:", ['P', 'K', 'PH', 'ARGILA', 'PREM', 'CTC'])
        if st.button("Gerar Mapa de Fertilidade"):
            b, vmax, vmed, vmin = render_mapa(sel, f"Mapa de {sel}", "Distribuição geoestatística dos teores no solo.")
            st.image(b); st.write(f"📊 **Max:** {vmax:.2f} | **Med:** {vmed:.2f} | **Min:** {vmin:.2f}")

    with tab_vr:
        st.subheader("Mapas de Recomendação (VRA)")
        
        # --- LÓGICA DE FÓSFORO REMANESCENTE DINÂMICA ---
        def calc_nc(prem):
            if prem <= 4: return nc1
            elif prem <= 10: return nc2
            elif prem <= 19: return nc3
            elif prem <= 30: return nc4
            elif prem <= 45: return nc5
            else: return nc6

        df['NC_P'] = df['PREM'].apply(calc_nc)
        df['F_TEXT'] = df['ARGILA'].apply(lambda x: f_marg if x>600 else (f_arg if x>350 else (f_med if x>150 else f_are)))
        
        # Fórmula: (Necessidade de elevação * Fator) + Exportação - Reserva do solo (Saldo)
        df['REC_P_ADUBO'] = (((df['NC_P'] - df['P']).clip(lower=0) * df['F_TEXT']) + (p_prodesp * p_exp_f) - (df['P'] - df['NC_P']).clip(lower=0)) * 100 / p_perc_adubo
        df['REC_P_ADUBO'] = df['REC_P_ADUBO'].clip(lower=0)

        # Gesso e Potássio
        df['REC_GESSO'] = (df['ARGILA'] * g_fator / 10).clip(lower=400, upper=g_max)
        df['REC_K_ADUBO'] = (((p_k_ctc - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) + (p_prodesp * 1.2)) * 1.66

        sel_vr = st.selectbox("Prescrição de Insumo:", ['REC_P_ADUBO', 'REC_K_ADUBO', 'REC_GESSO'])
        if st.button("Gerar Mapa de Recomendação"):
            desc_p = f"Metodologia: Fósforo Remanescente com NC de {nc1} a {nc6} mg/dm³. Vantagem: Otimiza a dose considerando a capacidade de fixação de cada zona."
            b_v, vma, vme, vmi = render_mapa(sel_vr, f"Recomendação: {sel_vra if 'sel_vra' in locals() else sel_vr}", desc_p)
            st.image(b_v); st.write(f"📊 **Dose Máx:** {vma:.2f} | **Dose Méd:** {vme:.2f} | **Dose Mín:** {vmi:.2f}")

    with tab_rel:
        if st.button("📥 GERAR RELATÓRIO PDF"):
            pdf = PDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f"Cliente: {st.session_state.info['produtor']} | Fazenda: {st.session_state.info['fazenda']}", 0, 1)
            pdf.ln(5)
            for k, m in st.session_state.mapas_sessao.items():
                pdf.secao_mapa(m['titulo'], m['img'], m['stats'], m['desc'])
            st.download_button("Baixar Relatório Oficial", pdf.output(), "Relatorio_Triade_Agro.pdf")
