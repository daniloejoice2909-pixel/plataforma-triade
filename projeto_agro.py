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
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.14", page_icon="🛰️")

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
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                      'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
                      'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        st.session_state.info = {"produtor": produtor, "fazenda": fazenda, "municipio": municipio}
        if st.button("🚀 ABRIR DASHBOARD TÉCNICO"):
            st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    tab_at, tab_fe, tab_vr, tab_rel = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 Relatório PDF"])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA ATRIBUTOS (TODOS OS ATRIBUTOS RESTAURADOS) ---
    with tab_at:
        st.subheader("⚙️ Configuração de Recomendação de Solo")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**1. Atributos do Calcário (Editáveis)**")
            p_cao = st.number_input("CaO %", value=36.0)
            p_mgo = st.number_input("MgO %", value=9.0)
            p_prnt = st.number_input("PRNT %", value=80.0)
            p_ca_des = st.number_input("Ca% desejado na CTC", value=60.0)
            p_mg_des = st.number_input("Mg% desejado na CTC", value=18.0)
            p_preco_calc = st.number_input("Preço Calcário (t)", value=190.0)
            p_adicional_calc = st.number_input("Adicional de Calcário (t/ha)", value=0.0)
        with c2:
            st.markdown("**2. Fósforo ($P_{rem}$) - NC Classes**")
            nc1 = st.number_input("Prem 0-4 (NC)", 8.0); nc2 = st.number_input("Prem 4-10 (NC)", 10.0)
            nc3 = st.number_input("Prem 10-19 (NC)", 12.0); nc4 = st.number_input("Prem 19-30 (NC)", 15.0)
            nc5 = st.number_input("Prem 30-45 (NC)", 20.0); nc6 = st.number_input("Prem >45 (NC)", 25.0)
            st.divider()
            f_arg_m = st.number_input("Fator M. Argiloso (P)", 10.0); f_arg = st.number_input("Fator Argiloso (P)", 8.0)
        with c3:
            st.markdown("**3. Potássio, Gesso e Exportação**")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp_p = st.number_input("Exp. P (kg/sc)", 0.8); p_exp_k = st.number_input("Exp. K (kg/sc)", 1.2)
            p_k_ctc = st.number_input("K% desejado CTC", 3.2)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15); g_max = st.number_input("Dose Máxima Gesso", 900.0)

    # --- MOTOR DE CÁLCULOS TÉCNICOS ---
    # Calcário (Maior dose entre elevar Ca ou Mg)
    # NC (t/ha) = (Cation_desejado - Cation_atual) * CTC / 100 * (Fator de Conversão baseado no PRNT)
    # Simplificando a estequiometria para elevar 1 cmolc de Ca/Mg com PRNT 100%
    df['NC_CALC_CA'] = ((p_ca_des - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100) * (100 / p_prnt) * 2 # Exemplo fator 2 para CaCO3
    df['NC_CALC_MG'] = ((p_mg_des - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100) * (100 / p_prnt) * 2
    df['REC_CALCARIO'] = (df[['NC_CALC_CA', 'NC_CALC_MG']].max(axis=1) + p_adicional_calc).round(2)

    # Fósforo (P-Rem + Exportação - Saldo)
    df['NC_P_DYN'] = df['PREM'].apply(lambda x: nc1 if x<=4 else (nc2 if x<=10 else (nc3 if x<=19 else (nc4 if x<=30 else (nc5 if x<=45 else nc6)))))
    df['F_TEXT_DYN'] = df['ARGILA'].apply(lambda x: f_arg_m if x>600 else (f_arg if x>350 else 4.0))
    df['REC_P_ADUBO'] = (((df['NC_P_DYN'] - df['P']).clip(lower=0) * df['F_TEXT_DYN']) + (p_prod * p_exp_p) - (df['P'] - df['NC_P_DYN']).clip(lower=0)).clip(lower=0)

    # Gesso
    df['REC_GESSO'] = (df['ARGILA'] * g_fator / 10).clip(lower=400, upper=g_max)

    # --- ABA MAPAS ---
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
        sel = st.selectbox("Atributo de Solo:", ['P', 'K', 'PH', 'ARGILA', 'CTC', 'CA_PERC', 'MG_PERC'])
        if st.button("Gerar Mapa de Fertilidade"):
            b, vmax, vmed, vmin = render_mapa(sel, f"Mapa de {sel}", "Distribuição espacial teórica baseada em Krigagem Ordinária.")
            st.image(b); st.write(f"📊 **Max:** {vmax:.2f} | **Méd:** {vmed:.2f} | **Mín:** {vmin:.2f}")

    with tab_vr:
        st.subheader("Mapas de Prescrição VRA")
        sel_vr = st.selectbox("Insumo VRA:", ['REC_CALCARIO', 'REC_P_ADUBO', 'REC_GESSO'])
        if st.button("Gerar Mapa de Recomendação"):
            desc_calc = f"Metodologia: Elevação de Ca para {p_ca_des}% e Mg para {p_mg_des}% na CTC. Vantagem: Garante o equilíbrio de bases e neutralização de Alumínio, priorizando o cátion mais deficitário."
            desc_p = "Metodologia: Fósforo Remanescente. Vantagem: Ajusta o nível crítico conforme a textura, economizando insumo onde há reserva no solo."
            just = desc_calc if 'CALCARIO' in sel_vr else desc_p
            b_v, vma, vme, vmi = render_mapa(sel_vr, titulo=sel_vr, desc=just)
            st.image(b_v); st.write(f"📊 **Dose Máx:** {vma:.2f} | **Dose Méd:** {vme:.2f} | **Dose Mín:** {vmi:.2f}")

    with tab_rel:
        if st.button("📥 GERAR PDF COMPLETO"):
            pdf = PDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 10, f"Produtor: {st.session_state.info['produtor']} | Fazenda: {st.session_state.info['fazenda']}", 0, 1)
            pdf.ln(5)
            for k, m in st.session_state.mapas_sessao.items():
                pdf.secao_mapa(m['titulo'], m['img'], m['stats'], m['desc'])
            st.download_button("Baixar Relatório Oficinal", pdf.output(), "Relatorio_Triade_Solo.pdf")
