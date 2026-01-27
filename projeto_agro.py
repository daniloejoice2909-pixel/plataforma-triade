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

# --- DICIONÁRIO DE NOMES (Para o Relatório) ---
TRADUCAO = {
    'Argila': 'Teor de Argila', 'pH': 'Acidez (pH)', 'P': 'Fósforo', 'K': 'Potássio',
    'Ca': 'Cálcio', 'Mg': 'Magnésio', 'Al': 'Alumínio', 'V%': 'Saturação por Bases',
    'S': 'Enxofre', 'CTC': 'Capacidade de Troca Catiônica (CTC)'
}

# --- SISTEMA DE LOGIN ---
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
        st.markdown("### 👤 Usuário: Danilo")
        if st.button("Sair"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("Plataforma de Gestão Estratégica")
    
    tab_inicio, tab_visualizacao, tab_pdf = st.tabs(["🏠 Upload", "🔍 Visualizar Mapas", "📄 Gerar Relatório"])

    with tab_inicio:
        u1, u2 = st.columns(2)
        up_geo = u1.file_uploader("1. Contorno do Talhão (GeoJSON)", type=["json", "geojson"])
        up_ex = u2.file_uploader("2. Planilha de Solo (Excel)", type=["xlsx"])

    if up_geo and up_ex:
        try:
            # Carregar Contorno
            data_geo = json.load(up_geo)
            poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
            
            # Carregar e Limpar Planilha
            df = pd.read_excel(up_ex)
            df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors='coerce')
            df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors='coerce')
            df = df.dropna(subset=[df.columns[0], df.columns[1]])
            
            lat, lon = df.iloc[:, 0], df.iloc[:, 1]
            
            # Identificar colunas de dados (da 3ª em diante)
            colunas_finais = []
            for col in df.columns[2:]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                if not df[col].isnull().all():
                    df[col] = df[col].fillna(df[col].mean())
                    colunas_finais.append(col)

            # Função para desenhar o mapa sem achatar
            def plot_mapa(data, titulo):
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

            with tab_visualizacao:
                st.success(f"Foram detectados {len(colunas_finais)} mapas.")
                c1, c2 = st.columns(2)
                for i, col in enumerate(colunas_finais):
                    nome_mapa = TRADUCAO.get(col, col)
                    with (c1 if i % 2 == 0 else c2):
                        st.pyplot(plot_mapa(df[col], nome_mapa))

            with tab_pdf:
                if st.button("🚀 Gerar e Baixar Relatório PDF"):
                    pdf = FPDF(orientation='P', unit='mm', format='A4')
                    
                    # Capa
                    pdf.add_page()
                    try: pdf.image("LogoTriadeInceres.png", x=75, y=50, w=60)
                    except: pass
                    pdf.ln(100)
                    pdf.set_font("Arial", 'B', 22)
                    pdf.cell(0, 15, "RELATORIO TECNICO ESTRATEGICO", ln=True, align='C')
                    pdf.set_font("Arial", '', 12)
                    pdf.cell(0, 10, "Tríade Agro Estratégica", ln=True, align='C')

                    # Páginas de Mapas
                    for i, col in enumerate(colunas_finais):
                        pdf.add_page()
                        nome_mapa = TRADUCAO.get(col, col)
                        pdf.set_font("Arial", 'B', 14)
                        pdf.cell(0, 10, f"Mapa: {nome_mapa}", ln=True)
                        pdf.line(10, 22, 200, 22)
                        
                        img_path = f"/tmp/mapa_{i}.png"
                        fig_tmp = plot_mapa(df[col], nome_mapa)
                        fig_tmp.savefig(img_path, bbox_inches='tight', dpi=120)
                        plt.close(fig_tmp)
                        
                        pdf.image(img_path, x=25, y=30, w=160)
                        
                        pdf.set_y(185)
                        pdf.set_font("Arial", 'B', 12)
                        pdf.set_text_color(46, 125, 50)
                        pdf.cell(0, 10, "Analise Tecnica:", ln=True)
                        pdf.set_font("Arial", '', 11)
                        pdf.set_text_color(0, 0, 0)
                        pdf.multi_cell(0, 7, f"Analise de variabilidade do atributo {nome_mapa} para tomada de decisao estrategica no manejo do solo.")
                        
                        if os.path.exists(img_path): os.remove(img_path)

                    pdf_out = pdf.output(dest='S').encode('latin-1')
                    st.download_button("📥 Clique aqui para Baixar PDF", data=pdf_out, file_name="Relatorio_Triade.pdf")
                    
        except Exception as e:
            st.error(f"Erro no processamento: {e}. Verifique se a planilha segue o padrão (Lat, Lon, Dados).")
