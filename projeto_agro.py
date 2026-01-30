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
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.19", page_icon="🌱")

# Paleta de 6 Camadas: Do Vermelho (Crítico) ao Azul (Alto/Suficiente)
# Sequência: Vermelho, Laranja, Amarelo, Verde Claro, Verde Escuro, Azul
colors_6 = ['#d73027', '#fc8d59', '#fee090', '#d9ef8b', '#91bfdb', '#4575b4']
cmap_6 = ListedColormap(colors_6)
# Definindo 6 classes (7 limites)
norm_6 = BoundaryNorm(np.linspace(0, 1, 7), cmap_6.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "mapas_sessao" not in st.session_state: st.session_state.mapas_sessao = {}
if "info" not in st.session_state: st.session_state.info = {"produtor": "", "fazenda": "", "municipio": ""}

# --- 2. MOTOR DE RELATÓRIO PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 30)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'RELATORIO ESTRATEGICO - TRIADE AGRO', 0, 1, 'C')
        self.ln(10)

    def adicionar_mapa_pdf(self, titulo, img_buf, stats, desc):
        self.add_page()
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, titulo, 0, 1, 'L')
        path = f"temp_{titulo.replace(' ', '_').replace('/', '_')}.png"
        with open(path, "wb") as f: f.write(img_buf.getbuffer())
        self.image(path, x=45, w=120)
        self.ln(5)
        self.set_font('Arial', 'B', 10); self.cell(0, 10, stats, 0, 1, 'C')
        self.ln(5); self.set_font('Arial', '', 10); self.multi_cell(0, 5, desc)
        if os.path.exists(path): os.remove(path)

# --- 3. FLUXO DE NAVEGAÇÃO ---

if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Consultoria Técnica", type="password")
        if st.button("ACESSAR PLATAFORMA", use_container_width=True):
            if senha == "triade2026": st.session_state.pagina = "Upload"; st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Cadastro e Importação (Sequência A a Y)")
    c1, c2 = st.columns(2)
    with c1:
        p_n = st.text_input("Produtor", "Danilo"); f_n = st.text_input("Fazenda", "Berneck"); m_n = st.text_input("Município")
    with c2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha Solo (.xlsx)", type=['xlsx'])

    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        # 25 colunas rigorosas
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                      'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
                      'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        st.session_state.info = {"produtor": p_n, "fazenda": f_n, "municipio": m_n}
        if st.button("🚀 INICIAR DASHBOARD", use_container_width=True):
            st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    tab_at, tab_fe, tab_vr, tab_rel = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 PDF"])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA ATRIBUTOS (Fórmulas Danillo) ---
    with tab_at:
        st.subheader("Configuração de Metas Agronômicas")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🪨 Calcário")
            p_ca_des = st.number_input("Ca% desejado CTC", 60.0); p_mg_des = st.number_input("Mg% desejado CTC", 18.0)
            p_prnt = st.number_input("PRNT %", 80.0); p_adicional = st.number_input("Adicional Calcário (t/ha)", 0.0)
        with c2:
            st.markdown("### 🧪 Fósforo ($P_{rem}$)")
            nc1 = st.number_input("NC Prem 0-4", 8.0); nc2 = st.number_input("NC Prem 4-10", 10.0)
            nc3 = st.number_input("NC Prem 10-19", 12.0); nc4 = st.number_input("NC Prem 19-30", 15.0)
            nc5 = st.number_input("NC Prem 30-45", 20.0); nc6 = st.number_input("NC Prem >45", 25.0)
            f_arg = st.number_input("Fator Argiloso (kg/mg)", 8.0); p_perc_p = st.number_input("% $P_2O_5$ no Adubo", 21.0)
        with c3:
            st.markdown("### 🍌 Potássio & Gesso")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp_p = st.number_input("Exp. P (kg/sc)", 0.8); p_exp_k = st.number_input("Exp. K (kg/sc)", 1.2)
            p_k_ctc = st.number_input("K% desejado CTC", 3.2); p_perc_k = st.number_input("% $K_2O$ no Adubo", 60.0)
            g_fator = st.number_input("Fator Gesso (Arg * 15)", 15); g_max = st.number_input("Dose Máxima Gesso", 900.0)

    # --- MOTOR DE MAPEAMENTO 6 CAMADAS ---
    def render_mapa_6c(col_id, titulo, desc):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[col_id], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 200), np.linspace(miny, maxy, 200)
        z, ss = OK.execute('grid', gx, gy)
        z_mask = np.full(z.shape, np.nan)
        for i in range(len(gy)):
            for j in range(len(gx)):
                if geom.contains(Point(gx[j], gy[i])): z_mask[i, j] = z[i, j]
        
        v_max, v_med, v_min = np.nanmax(z_mask), np.nanmean(z_mask), np.nanmin(z_mask)
        # Normalização dinâmica para ocupar as 6 classes
        z_norm = (z_mask - v_min) / (v_max - v_min) if v_max > v_min else z_mask * 0
        
        fig, ax = plt.subplots(figsize=(8, 7)); ax.axis('off')
        ax.imshow(z_norm, cmap=cmap_6, norm=norm_6, origin='lower', extent=[minx, maxx, miny, maxy])
        buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0); plt.close(fig)
        st.session_state.mapas_sessao[col_id] = {"img": buf, "stats": f"Max: {v_max:.2f} | Med: {v_med:.2f} | Min: {v_min:.2f}", "titulo": titulo, "desc": desc}
        return buf, v_max, v_med, v_min

    # --- ABA FERTILIDADE ---
    with tab_fe:
        attr = st.selectbox("Escolha o Atributo de Solo:", ['P', 'K', 'PH_CACL2', 'ARGILA', 'CTC', 'PREM'])
        if st.button("Gerar Mapa de Fertilidade"):
            b, vmax, vmed, vmin = render_mapa_6c(attr, f"Mapa de {attr}", "Variabilidade nutricional em 6 camadas.")
            st.image(b); st.write(f"📊 **Max:** {vmax:.2f} | **Méd:** {vmed:.2f} | **Mín:** {vmin:.2f}")

    # --- ABA RECOMENDAÇÕES (Fórmulas Danillo v1.19) ---
    with tab_vr:
        # 1. Calcário (Maior Dose)
        df['REC_CALC'] = (np.maximum(((p_ca_des - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt) * 2,
                                     ((p_mg_des - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt) * 5) + p_adicional).round(2)
        
        # 2. Fósforo (P-Rem + Economia)
        df['NC_P'] = df['PREM'].apply(lambda x: nc1 if x<=4 else (nc2 if x<=10 else (nc3 if x<=19 else (nc4 if x<=30 else (nc5 if x<=45 else nc6)))))
        df['REC_P_ADUBO'] = ((((df['NC_P'] - df['P']).clip(lower=0) * f_arg) + (p_prod * p_exp_p) - (df['P'] - df['NC_P']).clip(lower=0)) * 100 / p_perc_p).clip(lower=0).round(2)

        # 3. Potássio (Soma Incondicional: Elevação + Exportação)
        k_elev = ((p_k_ctc - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) * 240 # Fator simplificado para K2O
        k_expo = (p_prod * p_exp_k * 1.2)
        df['REC_K_ADUBO'] = ((k_elev + k_expo) * 100 / p_perc_k).round(2)

        # 4. Gesso
        df['REC_GESSO'] = (df['ARGILA'] * g_fator / 10).clip(lower=400, upper=g_max).round(2)

        sel_vr = st.selectbox("Mapa de Prescrição:", ['REC_CALC', 'REC_P_ADUBO', 'REC_K_ADUBO', 'REC_GESSO'])
        if st.button("Gerar Recomendação VRA"):
            just = f"Recomendação estratégica Tríade Agro. Escala de 6 níveis para gestão de precisão."
            b, vma, vme, vmi = render_mapa_6c(sel_vr, sel_vr, just)
            st.image(b); st.write(f"📊 **Dose Máx:** {vma:.2f} | **Dose Méd:** {vme:.2f} | **Dose Mín:** {vmi:.2f}")

    # --- ABA RELATÓRIO PDF ---
    with tab_rel:
        if st.button("📥 EXPORTAR PDF COMPLETO"):
            pdf = PDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f"Fazenda: {st.session_state.info['fazenda']} | Produtor: {st.session_state.info['produtor']}", 0, 1)
            for k, m in st.session_state.mapas_sessao.items():
                pdf.adicionar_mapa_pdf(m['titulo'], m['img'], m['stats'], m['desc'])
            st.download_button("Clique aqui para Baixar", pdf.output(), "Relatorio_Solo_6C.pdf")
