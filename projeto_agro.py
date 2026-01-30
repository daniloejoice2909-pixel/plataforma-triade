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

# --- 1. CONFIGURAÇÕES VISUAIS E ESTADOS ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.0", page_icon="🌱")

# Paleta Térmica 6 Camadas: Azul (Topo) ao Vermelho (Crítico)
# Ordem: Azul, Azul Claro, Verde, Amarelo, Laranja, Vermelho
colors_6 = ['#4575b4', '#91bfdb', '#d9ef8b', '#fee090', '#fc8d59', '#d73027']
cmap_6 = ListedColormap(colors_6)
norm_6 = BoundaryNorm(np.linspace(0, 1, 7), cmap_6.N)

if "pagina" not in st.session_state: st.session_state.pagina = "Entrada"
if "mapas_recom_pdf" not in st.session_state: st.session_state.mapas_recom_pdf = {}
if "info" not in st.session_state: st.session_state.info = {}

# --- 2. MOTOR DE RELATÓRIO PDF (EXCLUSIVO RECOMENDAÇÕES) ---
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

# --- 3. FLUXO DE NAVEGAÇÃO ---

if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Acesso Consultoria Técnica", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True):
            if senha == "triade2026": st.session_state.pagina = "Upload"; st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Importação e Cadastro do Projeto")
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
        # 25 Colunas Mapeadas A-Y
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                      'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
                      'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 ABRIR PLATAFORMA", use_container_width=True):
            st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    tabs = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações VRA", "📄 Relatório & Exportação"])
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA 1: ATRIBUTOS (NÃO FICOU NENHUM DE FORA) ---
    with tabs[0]:
        st.subheader("Configuração Global de Parâmetros")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🪨 Calcário & Calagem")
            p_cao = st.number_input("CaO %", 36.0); p_mgo = st.number_input("MgO %", 9.0); p_prnt = st.number_input("PRNT %", 80.0)
            p_ca_des = st.number_input("Ca% desejado na CTC", 60.0); p_mg_des = st.number_input("Mg% desejado na CTC", 18.0)
            p_calc_extra = st.number_input("Adicional de Calcário (t/ha)", 0.0); p_preco_c = st.number_input("Preço Calcário", 190.0)
        with c2:
            st.markdown("### 🧪 Fósforo ($P_{rem}$)")
            nc_list = [st.number_input(f"NC Classe {i+1}", v) for i, v in enumerate([8.0, 10.0, 12.0, 15.0, 20.0, 25.0])]
            f_arg_m = st.number_input("Fator M. Argiloso (P)", 10.0); f_arg = st.number_input("Fator Argiloso (P)", 8.0)
            f_med = st.number_input("Fator Médio (P)", 4.0); f_are = st.number_input("Fator Arenoso (P)", 2.0)
            p_exp_p = st.number_input("Fator Exportação P (kg/sc)", 0.8)
            p_perc_p = st.number_input("% P2O5 no Adubo", 21.0); p_preco_p = st.number_input("Preço Adubo P", 2800.0)
        with c3:
            st.markdown("### 🍌 Potássio & 🧪 Gesso")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_k_des = st.number_input("K% desejado na CTC", 3.2); p_exp_k = st.number_input("Fator Exportação K (kg/sc)", 1.2)
            k_fator_391 = st.number_input("Fator Atômico K (Conversão)", 391.0)
            p_perc_k = st.number_input("% K2O no Adubo", 60.0); p_preco_k = st.number_input("Preço Adubo K", 2800.0)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15); g_max = st.number_input("Dose Máx Gesso", 900.0)
            g_min = st.number_input("Dose Mín Gesso", 400.0); g_preco = st.number_input("Preço Gesso", 400.0)

    # --- MOTOR DE MAPEAMENTO HD (CONTORNO PRETO) ---
    def render_mapa_triade(col_id, titulo, desc, is_recom=False):
        OK = OrdinaryKriging(df['LON'], df['LAT'], df[col_id], variogram_model='spherical')
        gx, gy = np.linspace(minx, maxx, 250), np.linspace(miny, maxy, 250)
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
        
        if is_recom:
            st.session_state.mapas_recom_pdf[col_id] = {"img": buf, "stats": f"Máx: {v_max:.2f} | Méd: {v_med:.2f} | Mín: {v_min:.2f}", "titulo": titulo, "desc": desc}
        
        m = folium.Map(location=[geom.centroid.y, geom.centroid.x], zoom_start=15, tiles=None)
        folium.TileLayer('https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri Clarity').add_to(m)
        folium.raster_layers.ImageOverlay(image=np.array(Image.open(buf)), bounds=[[miny, minx], [maxy, maxx]], opacity=0.85).add_to(m)
        # CONTORNO PRETO BEM VISÍVEL (Weight 5)
        folium.GeoJson(contorno, style_function=lambda x: {'fillColor': 'none', 'color': 'black', 'weight': 5}).add_to(m)
        folium_static(m, width=1000, height=700)
        st.write(f"📊 **Resultados Geostatísticos:** Máximo: {v_max:.2f} | Médio: {v_med:.2f} | Mínimo: {v_min:.2f}")

    # --- ABA 2: FERTILIDADE ---
    with tabs[1]:
        sel_f = st.selectbox("Escolha o Mapa de Fertilidade:", ['P', 'K', 'PH', 'ARGILA', 'PREM', 'CTC', 'CA', 'MG', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO'])
        if st.button("Gerar Visualização de Fertilidade"):
            render_mapa_triade(sel_f, f"Mapa de {sel_f}", "Diagnóstico de Fertilidade", is_recom=False)

    # --- ABA 3: RECOMENDAÇÕES (O MOTOR DAS FÓRMULAS) ---
    with tabs[2]:
        st.subheader("Motor de Prescrições Tríade Agro")
        
        # 1. Calcário (Dose Ca vs Mg)
        df['REC_CALC'] = (np.maximum(((p_ca_des - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt),
                                     ((p_mg_des - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100) * (100/p_prnt)) + p_calc_extra).round(2)
        
        # 2. Fósforo (Lógica da Gordura + Exportação)
        df['NC_P_D'] = df['PREM'].apply(lambda x: nc_list[0] if x<=4 else (nc_list[1] if x<=10 else (nc_list[2] if x<=19 else (nc_list[3] if x<=30 else (nc_list[4] if x<=45 else nc_list[5])))))
        df['F_TEXT_D'] = df['ARGILA'].apply(lambda x: f_marg if x>600 else (f_arg if x>350 else (f_med if x>150 else f_are)))
        # Dose = (Necessidade de elevação * Fator) + Exportação - Gordura (P_solo - NC)
        df['P_GORDURA'] = (df['P'] - df['NC_P_D']).clip(lower=0) * df['F_TEXT_D']
        df['P_ELEV'] = (df['NC_P_D'] - df['P']).clip(lower=0) * df['F_TEXT_D']
        df['REC_P_ADUBO'] = (((df['P_ELEV'] + (p_prod * p_exp_p)) - df['P_GORDURA']).clip(lower=0) * 100 / p_perc_p).round(2)

        # 3. Potássio (Elevação meta + Exportação Incondicional)
        # (K_lacuna * Fator 391 * 2 [cmol -> kg] * 1.2 [K -> K2O]) + Exportação
        df['K_LACUNA'] = ((p_k_des - df['K_PERC']).clip(lower=0) * df['CTC'] / 100) * k_fator_391 * 2 * 1.2
        df['REC_K_ADUBO'] = (((df['K_LACUNA'] + (p_prod * p_exp_k))) * 100 / p_perc_k).round(2)

        # 4. Gesso (Argila g/kg * Fator)
        df['REC_GESSO'] = (df['ARGILA'] * g_fator / 10).clip(lower=g_min, upper=g_max).round(2)

        sel_vr = st.selectbox("Selecione a Recomendação:", ['REC_CALC', 'REC_P_ADUBO', 'REC_K_ADUBO', 'REC_GESSO'])
        if st.button("Gerar Mapa de Recomendação"):
            v_p = f"Metodologia: Fósforo Remanescente. Vantagem: Otimiza o investimento utilizando a reserva do solo para abater a exportação de {p_prod} sc/ha."
            v_k = f"Metodologia: Elevação para {p_k_des}% da CTC + Exportação Incondicional. Vantagem: Garante a sustentabilidade do estoque de K no solo."
            v_c = "Metodologia: Equilíbrio de Bases na CTC (Ca/Mg). Vantagem: Neutralização do alumínio tóxico e fornecimento de Ca e Mg em profundidade."
            just = v_p if 'P_ADUBO' in sel_vr else (v_k if 'K_ADUBO' in sel_vr else v_c)
            render_mapa_triade(sel_vr, sel_vr, just, is_recom=True)

    with tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Relatórios Estratégicos")
            if st.button("📥 GERAR RELATÓRIO PDF"):
                if not st.session_state.mapas_recom_pdf:
                    st.warning("Gere um Mapa de Recomendação primeiro para incluí-lo no relatório.")
                else:
                    pdf = PDF()
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, f"Fazenda: {st.session_state.info['fazenda']} | Produtor: {st.session_state.info['produtor']}", 0, 1)
                    for k, m in st.session_state.mapas_recom_pdf.items():
                        pdf.secao_mapa(m['titulo'], m['stats'], m['desc'])
                    st.download_button("Clique para Baixar o Relatório", bytes(pdf.output()), "Relatorio_Triade_Agro.pdf", "application/pdf")
        with c2:
            st.subheader("Exportação VRA (Shapefile)")
            if st.button("🚜 GERAR ARQUIVOS DE MÁQUINA"):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as z:
                    z.writestr("John_Deere/GS3_2630/Rx/prescricao.shp", "Dados espaciais para JD")
                    z.writestr("Case_IH/TaskData/prescricao.xml", "Dados ISOXML para Case/NH")
                    z.writestr("Trimble/AgGPS/prescricao.txt", "Dados para monitores Trimble")
                    z.writestr("Stara/StaraData/prescricao.shp", "Dados para monitores Stara")
                st.download_button("Baixar ZIP Multi-Marcas", zip_buffer.getvalue(), "Exportacao_Monitores_Triade.zip")
