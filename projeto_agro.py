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

# --- 1. CONFIGURAÇÕES VISUAIS E IDENTIDADE ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.0", page_icon="🌱")

# Paleta Térmica de 6 Camadas: Azul (Alto/Suficiente) ao Vermelho (Crítico/Baixo)
colors_6 = ['#4575b4', '#91bfdb', '#d9ef8b', '#fee090', '#fc8d59', '#d73027']
cmap_6 = ListedColormap(colors_6)
norm_6 = BoundaryNorm(np.linspace(0, 1, 7), cmap_6.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "mapas_sessao" not in st.session_state: st.session_state.mapas_sessao = {}
if "info" not in st.session_state: st.session_state.info = {}

# --- 2. MOTOR DE RELATÓRIO PDF ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logoTriadetransparente.png"):
            self.image("logoTriadetransparente.png", 10, 8, 30)
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'RELATORIO ESTRATEGICO - TRIADE AGRO', 0, 1, 'C')
        self.ln(10)

    def secao_mapa(self, titulo, img_buf, stats, desc):
        self.add_page()
        self.set_font('Arial', 'B', 12); self.cell(0, 10, titulo, 0, 1, 'L')
        img_path = f"temp_{titulo.replace(' ', '_').replace('/', '_')}.png"
        with open(img_path, "wb") as f: f.write(img_buf.getbuffer())
        self.image(img_path, x=45, w=120)
        self.ln(5)
        self.set_font('Arial', 'B', 10); self.cell(0, 10, stats, 0, 1, 'C')
        self.ln(5); self.set_font('Arial', '', 10); self.multi_cell(0, 5, desc)
        if os.path.exists(img_path): os.remove(img_path)

# --- 3. FLUXO DE NAVEGAÇÃO ---

if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Consultoria Técnica", type="password")
        if st.button("ACESSAR PLATAFORMA", use_container_width=True):
            if senha == "triade2026":
                st.session_state.pagina = "Upload"
                st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Cadastro de Projeto e Importação A-Y")
    c1, c2 = st.columns(2)
    with c1:
        p_n = st.text_input("Nome do Produtor", "Danilo")
        f_n = st.text_input("Nome da Fazenda", "Berneck")
        m_n = st.text_input("Município")
    with c2:
        f_contorno = st.file_uploader("Contorno Georreferenciado (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha de Solo (Colunas A a Y)", type=['xlsx'])

    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        # Sequência Rigorosa A-Y
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                      'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH_CACL2', 'CTC', 
                      'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        st.session_state.info = {"produtor": p_n, "fazenda": f_n, "municipio": m_n}
        if st.button("🚀 INICIAR DASHBOARD", use_container_width=True):
            st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    tabs = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 PDF & Exportação"])
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA 1: ATRIBUTOS EDITÁVEIS ---
    with tabs[0]:
        st.subheader("Configuração de Metas Agronômicas")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🪨 Calcário")
            p_cao = st.number_input("CaO %", 36.0); p_mgo = st.number_input("MgO %", 9.0); p_prnt = st.number_input("PRNT %", 80.0)
            p_ca_des = st.number_input("Ca% desejado CTC", 60.0); p_mg_des = st.number_input("Mg% desejado CTC", 18.0)
            p_adicional = st.number_input("Adicional Calcário (t/ha)", 0.0); p_preco_c = st.number_input("Preço Calcário", 190.0)
        with c2:
            st.markdown("### 🧪 Fósforo ($P_{rem}$)")
            nc1 = st.number_input("NC Prem 0-4", 8.0); nc2 = st.number_input("NC Prem 4.1-10", 10.0)
            nc3 = st.number_input("NC Prem 10.1-19", 12.0); nc4 = st.number_input("NC Prem 19.1-30", 15.0)
            nc5 = st.number_input("NC Prem 30.1-45", 20.0); nc6 = st.number_input("NC Prem 45-60", 25.0)
            st.divider()
            f_marg = st.number_input("Fator M. Argiloso", 10.0); f_arg = st.number_input("Fator Argiloso", 8.0)
            p_exp_p_f = st.number_input("Exportação P (kg/sc)", 0.8)
            p_perc_p = st.number_input("% P2O5 no Adubo", 21.0); p_preco_p = st.number_input("Preço Adubo P", 2800.0)
        with c3:
            st.markdown("### 🍌 Potássio & 🧪 Gesso")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp_k_f = st.number_input("Exportação K (kg/sc)", 1.2); p_k_des = st.number_input("K% desejado CTC", 3.2)
            p_perc_k = st.number_input("% K2O no Adubo", 60.0); p_preco_k = st.number_input("Preço Adubo K", 2800.0)
            st.divider()
            g_f = st.number_input("Fator Gesso (Arg * F)", 15); g_max = st.number_input("Dose Máx Gesso", 900.0)
            g_min = st.number_input("Dose Mín Gesso", 400.0); g_preco = st.number_input("Preço Gesso", 400.0)

    # --- MOTOR DE MAPAS HD ---
    def render_mapa_triade(col_id, titulo, desc):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[col_id], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 200), np.linspace(miny, maxy, 200)
        z, ss = OK.execute('grid', gx, gy)
        z_mask = np.full(z.shape, np.nan)
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
        folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri Clarity').add_to(m)
        folium.raster_layers.ImageOverlay(image=np.array(Image.open(buf)), bounds=[[miny, minx], [maxy, maxx]], opacity=0.8).add_to(m)
        # CONTORNO AMARELO DESTACADO (Weight 5)
        folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'yellow', 'weight': 5}).add_to(m)
        folium_static(m, width=1000, height=700)
        st.write(f"📊 **Máximo:** {v_max:.2f} | **Médio:** {v_med:.2f} | **Mínimo:** {v_min:.2f}")

    with tabs[1]:
        sel_f = st.selectbox("Escolha o Mapa de Fertilidade:", ['P', 'K', 'PH_CACL2', 'ARGILA', 'PREM', 'CTC', 'CA', 'MG', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO'])
        if st.button("Gerar Visualização"):
            render_mapa_triade(sel_f, f"Fertilidade: {sel_f}", "Distribuição geoestatística dos teores no solo.")

    with tabs[2]:
        st.subheader("Mapas de Prescrição em Taxa Variável")
        # --- CÁLCULOS TÉCNICOS ---
        # 1. Calcário (Maior dose entre Ca e Mg)
        df['REC_CALC'] = (np.maximum(((p_ca_des - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt) * 2,
                                     ((p_mg_des - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt) * 5) + p_adicional).round(2)
        
        # 2. Fósforo (Gordura do solo além do NC subtraída da Exportação)
        df['NC_P_D'] = df['PREM'].apply(lambda x: nc1 if x<=4 else (nc2 if x<=10 else (nc3 if x<=19 else (nc4 if x<=30 else (nc5 if x<=45 else nc6)))))
        df['F_TEXT_D'] = df['ARGILA'].apply(lambda x: f_marg if x>600 else f_arg)
        # Dose = (Necessidade elevação * Fator) + Exportação - Gordura (P_atual - NC)
        df['REC_P_ADUBO'] = ((((df['NC_P_D'] - df['P']).clip(lower=0) * df['F_TEXT_D']) + (p_prod * p_exp_p_f)) - (df['P'] - df['NC_P_D']).clip(lower=0))
        df['REC_P_ADUBO'] = (df['REC_P_ADUBO'] * 100 / p_perc_p).clip(lower=0).round(2)

        # 3. Potássio (Elevação para meta % + Exportação Incondicional)
        df['REC_K_ADUBO'] = (((((p_k_des - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) * 240) + (p_prod * p_exp_k_f * 1.2)) * 100 / p_perc_k).round(2)

        # 4. Gesso (Argila g/kg * Fator)
        df['REC_GESSO'] = (df['ARGILA'] * g_f / 10).clip(lower=g_min, upper=g_max).round(2)

        sel_vr = st.selectbox("Selecione o Insumo VRA:", ['REC_CALC', 'REC_P_ADUBO', 'REC_K_ADUBO', 'REC_GESSO'])
        if st.button("Gerar Mapa de Recomendação"):
            just_p = f"Metodologia: Fósforo Remanescente. Vantagem: Utiliza a reserva de solo excedente (gordura) para abater a dose de exportação de {p_prod} sc/ha."
            just_k = f"Metodologia: Elevação CTC para {p_k_des}% + Reposição de Exportação. Vantagem: Garante o balanço de massa independente da fertilidade atual."
            j_f = just_p if 'P_ADUBO' in sel_vr else (just_k if 'K_ADUBO' in sel_vr else "Equilíbrio de bases na CTC.")
            render_mapa_triade(sel_vr, sel_vr, j_f)

    with tabs[3]:
        st.subheader("Finalização do Projeto")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📥 EXPORTAR RELATÓRIO PDF"):
                pdf = PDF()
                pdf.add_page()
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f"Fazenda: {st.session_state.info.get('fazenda','')} | Produtor: {st.session_state.info.get('produtor','')}",
