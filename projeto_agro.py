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
        st.subheader("Informações do Projeto")
        produtor = st.text_input("Produtor", "Danilo")
        fazenda = st.text_input("Fazenda", "Nome da Fazenda")
        municipio = st.text_input("Município", "Uberlândia - MG")
        logo_fazenda_file = st.file_uploader("Logo da Fazenda", type=["png", "jpg"])
        st.markdown("---")

    st.title("Plataforma de Gestão Estratégica")
    tab_inicio, tab_visualizacao, tab_pdf = st.tabs(["🏠 Dados", "🔍 Mapas", "📄 Relatório Final"])

    area_ha = 0.0
    if "area_ha" not in st.session_state: st.session_state.area_ha = 0.0

    with tab_inicio:
        u1, u2 = st.columns(2)
        up_geo = u1.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        up_ex = u2.file_uploader("Planilha de Solo (Excel)", type=["xlsx"])
        if up_geo:
            data_geo = json.load(up_geo)
            poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
            bounds = poligono.bounds
            largura = (bounds[2] - bounds[0]) * 111320
            altura = (bounds[3] - bounds[1]) * 110540
            st.session_state.area_ha = (poligono.area / ((bounds[2]-bounds[0])*(bounds[3]-bounds[1]))) * (largura * altura) / 10000
            st.metric("Área do Talhão", f"{st.session_state.area_ha:.2f} ha")

    if up_geo and up_ex:
        df_raw = pd.read_excel(up_ex)
        df = df_raw.dropna(subset=[df_raw.columns[0], df_raw.columns[1]]).copy()
        lat, lon = df.iloc[:, 0].values, df.iloc[:, 1].values
        colunas_dados = [c for c in df.columns[2:] if pd.api.types.is_numeric_dtype(df[c])]

        def plot_fidedigno(data_series):
            data_clean = data_series.fillna(data_series.mean()).values
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon, lat, data_clean, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            fig, ax = plt.subplots(figsize=(5, 5))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=1)
            ax.set_aspect('equal')
            cbar = plt.colorbar(cp, fraction=0.03, pad=0.04)
            cbar.ax.tick_params(labelsize=5)
            ax.axis('off')
            return fig, data_clean.min(), data_clean.mean(), data_clean.max()

        with tab_pdf:
            if st.button("🚀 Gerar Dossiê Tríade"):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_margins(20, 20, 20)
                
                # METODOLOGIAS FIXAS
                metodos = {
                    "Calcário": "Metodologia: Equilíbrio de Bases (V%). Vantagem: Neutraliza Alumínio tóxico e otimiza a eficiência de fertilizantes NPK.",
                    "Fósforo": "Metodologia: Disponibilidade Crítica via Argila. Vantagem: Garante arranque vigoroso e expansão radicular.",
                    "Gesso": "Metodologia: Saturação por Alumínio em profundidade. Vantagem: Melhora a resiliência à seca no subsolo.",
                    "Potássio": "Metodologia: Reposição via CTC. Vantagem: Evita lixiviação e melhora o enchimento de grãos."
                }

                # CAPA E TABELA DE INSUMOS
                pdf.add_page()
                try: pdf.image("LogoTriadeInceres.png", x=85, y=10, w=40)
                except: pass
                
                pdf.set_y(50)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "RELATÓRIO TÉCNICO ESTRATÉGICO", ln=True, align='C')
                
                pdf.set_font("Arial", '', 11)
                pdf.set_text_color(100, 100, 100) # Cabeçalho apagado
                pdf.cell(0, 7, f"Produtor: {produtor} | Fazenda: {fazenda} | Município: {municipio}", ln=True, align='C')
                pdf.cell(0, 7, f"Área Processada: {st.session_state.area_ha:.2f} ha", ln=True, align='C')
                
                pdf.ln(10)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, "Resumo de Recomendações e Insumos", ln=True)
                
                # TABELA DE INSUMOS ESTILIZADA
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(60, 10, "Insumo", 1, 0, 'C')
                pdf.cell(70, 10, "Concentração", 1, 0, 'C')
                pdf.cell(40, 10, "Volume Total", 1, 1, 'C')
                
                pdf.set_font("Arial", '', 12)
                insumos_ficticios = [
                    ["Calcário", "(36% CaO 9% MgO 80% PRNT)", "ton"],
                    ["Gesso Agrícola", "(15% S 18% Ca)", "ton"],
                    ["Super Simples", "(21% de P2O5)", "ton"],
                    ["Cloreto Potássio", "(60% K2O)", "ton"]
                ]
                
                for ins in insumos_ficticios:
                    nome_col = [c for c in colunas_dados if ins[0][:4].lower() in c.lower()]
                    media = df[nome_col[0]].mean() if nome_col else 0
                    total = (media * st.session_state.area_ha) / 1000 if "P2O5" not in ins[1] else (media * st.session_state.area_ha)
                    pdf.cell(60, 10, ins[0], 1)
                    pdf.cell(70, 10, ins[1], 1)
                    pdf.cell(40, 10, f"{total:.2f} {ins[2]}", 1, 1, 'C')

                # MAPAS E TIMBRE
                for i, col in enumerate(colunas_dados):
                    pdf.add_page()
                    # Timbre minimalista no topo
                    try: pdf.image("LogoTriadeInceres.png", x=20, y=8, w=10)
                    except: pass
                    pdf.set_font("Arial", '', 7)
                    pdf.set_xy(32, 10)
                    pdf.cell(0, 5, f"Tríade Agro Estratégica | Whatsapp: 34 998670919", 0, 0, 'L')
                    try: pdf.image("LogoTriadeInceres.png", x=180, y=8, w=10)
                    except: pass
                    
                    pdf.set_y(25)
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, f"Mapa de {col}", ln=True, align='L')
                    
                    fig, v_min, v_med, v_max = plot_fidedigno(df[col])
                    img_path = f"/tmp/m_{i}.png"
                    fig.savefig(img_path, bbox_inches='tight', dpi=150)
                    plt.close(fig)
                    
                    pdf.image(img_path, x=45, y=40, w=120)
                    
                    # Estatísticas abaixo do mapa
                    pdf.set_y(165)
                    pdf.set_font("Arial", '', 8)
                    pdf.cell(0, 5, f"Valores do Talhão - Mín: {v_min:.2f} | Méd: {v_med:.2f} | Máx: {v_max:.2f}", ln=True, align='C')
                    
                    # Metodologia
                    pdf.ln(5)
                    pdf.set_font("Arial", '', 12)
                    chave = [k for k in metodos.keys() if k.lower() in col.lower()]
                    txt = metodos[chave[0]] if chave else "Metodologia: Análise de variabilidade espacial via Interpolação Rbf. Vantagem: Maior precisão na aplicação em taxa variável."
                    pdf.multi_cell(0, 8, txt)

                pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
                st.download_button("📥 Baixar Dossiê Final", data=pdf_out, file_name=f"Triade_{fazenda}.pdf")
