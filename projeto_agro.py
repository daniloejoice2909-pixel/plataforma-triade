import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
from fpdf import FPDF
import os

# --- CONFIGURAÇÃO DE TELA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica", page_icon="🌱")

# --- DICIONÁRIO DE TRADUÇÃO (Para nomes ficarem bonitos no relatório) ---
TRADUCAO_NOMES = {
    'Argila': 'Teor de Argila',
    'pH': 'Acidez do Solo (pH)',
    'P': 'Fósforo',
    'K': 'Potássio',
    'Ca': 'Cálcio',
    'Mg': 'Magnésio',
    'Al': 'Alumínio',
    'H+Al': 'Acidez Potencial',
    'V%': 'Saturação por Bases',
    'S': 'Enxofre',
    'B': 'Boro',
    'Cu': 'Cobre',
    'Fe': 'Ferro',
    'Mn': 'Manganês',
    'Zn': 'Zinco',
    'CTC': 'Capacidade de Troca Catiônica (CTC)'
}

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
        st.markdown(f"### 👤 Usuário: Danilo")
        if st.button("Sair"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("Plataforma de Gestão Estratégica")
    
    tab_inicio, tab_visualizacao, tab_pdf = st.tabs(["🏠 Upload", "🔍 Visualizar Todos os Mapas", "📄 Gerar Relatório Completo"])

    with tab_inicio:
        u1, u2 = st.columns(2)
        up_geo = u1.file_uploader("Contorno do Talhão (GeoJSON)", type=["json", "geojson"])
        up_ex = u2.file_uploader("Dados de Solo (Excel)", type=["xlsx"])

    if up_geo and up_ex:
        data_geo = json.load(up_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        df = pd.read_excel(up_ex)
        
        # Identifica coordenadas (assumindo que são as duas primeiras colunas)
        lat, lon = df.iloc[:,0], df.iloc[:,1]
        
        # Seleciona apenas colunas numéricas que não sejam Lat/Lon
        colunas_dados = df.select_dtypes(include=[np.number]).columns[2:]

        def plot_fidedigno(data, titulo):
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon, lat, data, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            fig, ax = plt.subplots(figsize=(8, 8))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=2)
            ax.set_aspect('equal')
            plt.colorbar(cp, fraction=0.046, pad=0.04)
            ax.axis('off')
            return fig

        # Gerar lista dinâmica de mapas
        mapas_para_gerar = []
        for col in colunas_dados:
            nome_amigavel = TRADUCAO_NOMES.get(col, col)
            mapas_para_gerar.append((df[col], nome_amigavel))

        with tab_visualizacao:
            st.info(f"Foram detectados {len(mapas_para_gerar)} atributos na sua planilha.")
            cols = st.columns(2)
            for idx, (dados, nome) in enumerate(mapas_para_gerar):
                with cols[idx % 2]:
                    st.pyplot(plot_fidedigno(dados, nome))

        with tab_pdf:
            if st.button("🚀 Gerar Relatório Com Todos os Atributos"):
                try:
                    pdf = FPDF(orientation='P', unit='mm', format='A4')
                    pdf.set_auto_page_break(auto=True, margin=15)
                    
                    # Capa
                    pdf.add_page()
                    try: pdf.image("LogoTriadeInceres.png", x=75, y=50, w=60)
                    except: pass
                    pdf.ln(100)
                    pdf.set_font("Arial", 'B', 22)
                    pdf.cell(0, 15, "RELATÓRIO TÉCNICO ESTRATÉGICO", ln=True, align='C')
                    pdf.set_font("Arial", '', 12)
                    pdf.cell(0, 10, f"Total de Atributos Mapeados: {len(mapas_para_gerar)}", ln=True, align='C')
                    
                    for i, (dados, nome) in enumerate(mapas_para_gerar):
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 14)
                        pdf.cell(0, 10, f"Mapa de {nome}", ln=True, align='L')
                        pdf.line(10, 22, 200, 22)
                        
                        img_name = f"/tmp/mapa_dinamico_{i}.png"
                        fig_temp = plot_fidedigno(dados, nome)
                        fig_temp.savefig(img_name, bbox_inches='tight', dpi=150)
                        plt.close(fig_temp)
                        
                        pdf.image(img_name, x=25, y=35, w=160)
                        
                        pdf.set_y(190)
                        pdf.set_font("Arial", 'B', 12)
                        pdf.set_text_color(46, 125, 50)
                        pdf.cell(0, 10, "Observação Técnica:", ln=True)
                        pdf.set_font("Arial", '', 11)
                        pdf.set_text_color(0, 0, 0)
                        pdf.multi_cell(0, 7, f"Análise da variabilidade espacial do atributo {nome} no talhão selecionado, visando o equilíbrio nutricional e a otimização de recursos.")
                        
                        pdf.set_y(-20)
                        pdf.set_font("Arial", 'I', 8)
                        pdf.cell(0, 10, "Tríade Agro Estratégica - Relatório Gerado Automaticamente", align='C')
                        
                        if os.path.exists(img_name): os.remove(img_name)

                    pdf_out = pdf.output(dest='S').encode('latin-1')
                    st.download_button("📥 Baixar Relatório Completo", data=pdf_out, file_name="Relatorio_Completo_Triade.pdf")
                    st.success("Relatório pronto com todos os dados detectados!")
                except Exception as e:
                    st.error(f"Erro ao processar todos os mapas: {e}")
