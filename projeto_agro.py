import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
from fpdf import FPDF
import os
from PIL import Image

# --- CONFIGURAÇÃO DE TELA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica", page_icon="🌱")

# --- LOGIN ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "triade2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.image("LogoTriadeInceres.png", width=300)
        st.text_input("Senha de Acesso:", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if check_password():
    with st.sidebar:
        st.image("LogoTriadeInceres.png", width=180)
        st.markdown("---")
        st.subheader("Configurações do Relatório")
        produtor = st.text_input("Nome do Produtor", "Danilo")
        fazenda = st.text_input("Nome da Fazenda", "Fazenda Exemplo")
        municipio = st.text_input("Município", "Uberlândia - MG")
        logo_fazenda_file = st.file_uploader("Logo da Fazenda", type=["png", "jpg", "jpeg"])
        st.markdown("---")
        if st.button("Sair"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("Plataforma de Gestão Estratégica")
    tab_inicio, tab_visualizacao, tab_pdf = st.tabs(["🏠 Dados", "🔍 Mapas", "📄 Relatório Final"])

    area_ha = 0.0

    with tab_inicio:
        u1, u2 = st.columns(2)
        up_geo = u1.file_uploader("1. Contorno (GeoJSON)", type=["json", "geojson"])
        up_ex = u2.file_uploader("2. Planilha de Solo (Excel)", type=["xlsx"])
        
        if up_geo:
            data_geo = json.load(up_geo)
            poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
            bounds = poligono.bounds
            largura = (bounds[2] - bounds[0]) * 111320
            altura = (bounds[3] - bounds[1]) * 110540
            area_ha = (poligono.area / ((bounds[2]-bounds[0])*(bounds[3]-bounds[1]))) * (largura * altura) / 10000
            st.metric("Área Calculada", f"{area_ha:.2f} ha")

    if up_geo and up_ex:
        # LIMPEZA PESADA DE DADOS PARA EVITAR O ERRO
        df_raw = pd.read_excel(up_ex)
        df = df_raw.copy()
        # Converte lat/lon e remove nulos
        df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors='coerce')
        df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors='coerce')
        df = df.dropna(subset=[df.columns[0], df.columns[1]])
        
        # Identifica colunas numéricas de dados
        colunas_dados = []
        for c in df.columns[2:]:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            if not df[c].isnull().all():
                df[c] = df[c].fillna(df[c].mean()) # Preenche buracos com a média
                colunas_dados.append(c)

        def plot_fidedigno(data_series):
            # Filtro final antes do Rbf para garantir que não existam NaNs
            lon_clean = df.iloc[:, 1].values
            lat_clean = df.iloc[:, 0].values
            val_clean = data_series.values
            
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon_clean, lat_clean, val_clean, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            
            fig, ax = plt.subplots(figsize=(6, 6))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=1.2)
            ax.set_aspect('equal')
            cbar = plt.colorbar(cp, fraction=0.03, pad=0.04)
            cbar.ax.tick_params(labelsize=6)
            ax.axis('off')
            return fig, val_clean.min(), val_clean.mean(), val_clean.max()

        with tab_visualizacao:
            c1, c2 = st.columns(2)
            for i, col in enumerate(colunas_dados):
                fig, v_min, v_med, v_max = plot_fidedigno(df[col])
                with (c1 if i % 2 == 0 else c2):
                    st.pyplot(fig)
                    st.caption(f"{col} | Méd: {v_med:.2f}")

        with tab_pdf:
            if st.button("🚀 Gerar Dossiê Estratégico"):
                logo_faz_path = None
                if logo_fazenda_file:
                    logo_faz_path = "/tmp/fazenda_logo.png"
                    Image.open(logo_fazenda_file).save(logo_faz_path)

                pdf = FPDF()
                pdf.set_margins(30, 30, 30)
                
                # --- PÁGINA 1: CAPA E TABELA DE INSUMOS ---
                pdf.add_page()
                try: pdf.image("LogoTriadeInceres.png", x=90, y=10, w=30)
                except: pass
                
                pdf.set_y(45)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, u"RELATÓRIO TÉCNICO ESTRATÉGICO".encode('latin-1','replace').decode('latin-1'), ln=True, align='C')
                
                pdf.set_font("Arial", '', 11)
                pdf.set_text_color(150, 150, 150) # Tom apagado
                pdf.cell(0, 7, f"Produtor: {produtor} | Fazenda: {fazenda} | Municipio: {municipio}", ln=True, align='C')
                pdf.cell(0, 7, f"Area Total: {area_ha:.2f} ha", ln=True, align='C')
                
                pdf.ln(10)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, u"Insumo / Concentração / Volume Total".encode('latin-1','replace').decode('latin-1'), ln=True)
                
                # TABELA DE INSUMOS
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(75, 10, "Insumo", 1, 0, 'C')
                pdf.cell(75, 10, u"Concentração".encode('latin-1','replace').decode('latin-1'), 1, 0, 'C')
                pdf.cell(30, 10, "Volume", 1, 1, 'C')
                
                pdf.set_font("Arial", '', 12)
                insumos = [
                    ["Calcario", "(36% CaO 9% MgO 80% PRNT)", "ton"],
                    ["Gesso Agricola", "(15% S 18% Ca)", "ton"],
                    ["Super Simples", "(21% de P2O5)", "ton"],
                    ["Cloreto Potassio", "(60% K2O)", "ton"]
                ]
                for item in insumos:
                    # Cálculo fictício baseado na média da primeira coluna de dados disponível
                    media = df[colunas_dados[0]].mean()
                    total = (media * area_ha) / 10 if "ton" in item[2] else (media * area_ha)
                    pdf.cell(75, 10, item[0], 1)
                    pdf.cell(75, 10, item[1], 1)
                    pdf.cell(30, 10, f"{total:.1f}", 1, 1, 'C')

                # --- PÁGINAS DE MAPAS ---
                metodologias = {
                    "Calcario": "Metodologia: Saturacao por Bases (V%). Vantagem: Corrige a acidez e fornece Ca e Mg.",
                    "Fosforo": "Metodologia: Disponibilidade por Argila. Vantagem: Melhora o enraizamento e arranque.",
                    "Potassio": "Metodologia: Reposicao na CTC. Vantagem: Melhora o enchimento de graos e resistencia.",
                    "Gesso": "Metodologia: Saturacao de Al em profundidade. Vantagem: Maior resistencia a seca."
                }

                for i, col in enumerate(colunas_dados):
                    pdf.add_page()
                    # TIMBRE
                    try: pdf.image("LogoTriadeInceres.png", x=30, y=10, w=10)
                    except: pass
                    pdf.set_xy(42, 12); pdf.set_font("Arial", '', 8)
                    pdf.cell(0, 5, "Tríade Agro Estratégica | (WA) 34 998670919")
                    try: pdf.image("LogoTriadeInceres.png", x=170, y=10, w=10)
                    except: pass
                    if logo_faz_path: pdf.image(logo_faz_path, x=170, y=25, w=20)

                    pdf.set_y(35); pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, f"Mapa de {col}", ln=True)
                    
                    fig, v_min, v_med, v_max = plot_fidedigno(df[col])
                    img_p = f"/tmp/mapa_{i}.png"
                    fig.savefig(img_p, bbox_inches='tight', dpi=120)
                    plt.close(fig)
                    
                    pdf.image(img_p, x=45, y=55, w=120)
                    pdf.set_y(175); pdf.set_font("Arial", '', 9)
                    pdf.cell(0, 10, f"Min: {v_min:.2f} | Med: {v_med:.2f} | Max: {v_max:.2f}", ln=True, align='C')
                    
                    # Metodologia
                    pdf.set_font("Arial", '', 12)
                    m_text = metodologias.get(col, "Metodologia: Variabilidade Espacial. Vantagem: Otimizacao de custos e precisao.")
                    pdf.multi_cell(0, 8, m_text.encode('latin-1','replace').decode('latin-1'))
                    if os.path.exists(img_p): os.remove(img_p)

                pdf_res = pdf.output(dest='
