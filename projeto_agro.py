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

# --- 1. CONFIGURAÇÕES E ESTILO ---
st.set_page_config(layout="wide", page_title="Tríade Agro | Estratégica 1.0", page_icon="🌱")

# Paleta AP: Vermelho (Baixo), Amarelo (Médio), Verde (Alto)
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

# --- 3. NAVEGAÇÃO ---

if st.session_state.pagina == "Entrada":
    st.markdown("<h1 style='text-align:center;'>🛰️ Tríade Agro | Estratégica 1.0</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        senha = st.text_input("Senha de Acesso Técnico", type="password")
        if st.button("ACESSAR PLATAFORMA", use_container_width=True):
            if senha == "triade2026":
                st.session_state.pagina = "Upload"; st.rerun()

elif st.session_state.pagina == "Upload":
    st.header("📂 Cadastro e Importação de Dados")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.produtor = st.text_input("Produtor", "Danilo")
        st.session_state.fazenda = st.text_input("Fazenda", "Berneck")
        st.session_state.municipio = st.text_input("Município")
    with c2:
        f_contorno = st.file_uploader("Contorno (.json)", type=['json', 'geojson'])
        f_dados = st.file_uploader("Planilha Solo (A a Y)", type=['xlsx'])

    if f_contorno and f_dados:
        st.session_state.contorno = json.load(f_contorno)
        df = pd.read_excel(f_dados)
        # Sequência Estrita A-Y
        df.columns = ['LAT', 'LON', 'CAMPO', 'PONTO', 'ARGILA', 'PREM', 'P', 'CA', 'MG', 'K', 
                      'AL', 'HAL', 'S', 'B', 'MN', 'ZN', 'CU', 'FE', 'MO', 'PH', 'CTC', 
                      'CA_PERC', 'MG_PERC', 'K_PERC', 'CAMG'][:len(df.columns)]
        st.session_state.dados = df
        if st.button("🚀 ABRIR DASHBOARD TÉCNICO"):
            st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Dashboard":
    tabs = st.tabs(["⚙️ Atributos", "🔍 Fertilidade", "🏠 Recomendações", "📄 Relatório & Exportação"])
    
    df = st.session_state.dados
    contorno = st.session_state.contorno
    geom = shape(contorno['features'][0]['geometry'])
    minx, miny, maxx, maxy = geom.bounds

    # --- ABA ATRIBUTOS ---
    with tabs[0]:
        st.subheader("Configuração Global de Parâmetros")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🪨 Calcário")
            p_cao = st.number_input("CaO %", 36.0); p_mgo = st.number_input("MgO %", 9.0)
            p_prnt = st.number_input("PRNT %", 80.0); p_ca_des = st.number_input("Ca% desejado CTC", 60.0)
            p_mg_des = st.number_input("Mg% desejado CTC", 18.0); p_preco_calc = st.number_input("Preço Calcário (t)", 190.0)
            p_adicional = st.number_input("Adicional Calcário (t/ha)", 0.0)
        with c2:
            st.markdown("### 🧪 Fósforo ($P_{rem}$)")
            nc1 = st.number_input("NC Prem 0-4", 8.0); nc2 = st.number_input("NC Prem 4-10", 10.0)
            nc3 = st.number_input("NC Prem 10-19", 12.0); nc4 = st.number_input("NC Prem 19-30", 15.0)
            nc5 = st.number_input("NC Prem 30-45", 20.0); nc6 = st.number_input("NC Prem >45", 25.0)
            st.divider()
            f_marg = st.number_input("Fator M. Argiloso (kg/mg)", 10.0); f_arg = st.number_input("Fator Argiloso (kg/mg)", 8.0)
            f_med = st.number_input("Fator Médio (kg/mg)", 4.0); f_are = st.number_input("Fator Arenoso (kg/mg)", 2.0)
            p_adubo_p = st.number_input("% $P_2O_5$ Adubo", 21.0); p_preco_p = st.number_input("Preço Adubo P", 2800.0)
        with c3:
            st.markdown("### 🍌 Potássio & 🧪 Gesso")
            p_prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)
            p_exp_p = st.number_input("Fator Exp P (kg/sc)", 0.8); p_exp_k = st.number_input("Fator Exp K (kg/sc)", 1.2)
            p_k_ctc = st.number_input("K% desejado CTC", 3.2); p_adubo_k = st.number_input("% $K_2O$ Adubo K", 60.0)
            g_fator = st.number_input("Fator Gesso (Arg * F)", 15); g_max = st.number_input("Dose Máx Gesso", 900.0)
            g_min = st.number_input("Dose Mín Gesso", 4
