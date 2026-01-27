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
        st.markdown("### 👤 Usuário: Danilo")
        if st.button("Sair"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("Gerador de Relatórios v43")
    
    tab_inicio, tab_visualizacao, tab_pdf = st.tabs(["🏠 Upload", "🔍 Ver Mapas", "📄 Gerar Relatório Full"])

    with tab_inicio:
        u1, u2 = st.columns(2)
        up_geo = u1.file_uploader("GeoJSON do Talhão", type=["json", "geojson"])
        up_ex = u2.file_uploader("Planilha de Solo (Excel)", type=["xlsx"])

    if up_geo and up_ex:
        data_geo = json.load(up_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        df = pd.read_excel(up_ex).apply(pd.to_numeric, errors='coerce').fillna(0)
        
        # Mapeamento de Colunas (Padrão v43)
        lat, lon = df.iloc[:,0], df.iloc[:,1]
        arg, p_rem, p_solo = df.iloc[:,4], df.iloc[:,5], df.iloc[:,6]
        ca, mg, k = df.iloc[:,7], df.iloc[:,8], df.iloc[:,9]
        ctc = df.iloc[:,20]

        # Função de Plotagem
        def plot_para_pdf(data, titulo, cmap='Spectral_r'):
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon, lat, data, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            fig, ax = plt.subplots(figsize=(8, 5))
            cp = ax.contourf(gx, gy, z, levels=6, cmap=cmap)
            ax.plot(*poligono.exterior.xy, color='black', linewidth=2)
            plt.colorbar(cp)
            ax.set_title(titulo)
            ax.axis('off')
            return fig

        # Cálculos de Recomendação
        rec_calc = (np.maximum(((60/100*ctc)-ca)*0.56*(100/36), (18/100*ctc-mg)*0.40*(100/9)) * 1000 * (100/80)).clip(lower=0)
        rec_gesso = ((arg / 10) * 15.0).clip(lower=0)
        rec_k = (((3.2/100 * ctc) - k).clip(lower=0) * 1200 + 100) / 0.60

        # Lista de Mapas para o Relatório
        mapas_trabalho = [
            (ctc, "Mapa de CTC (cmolc/dm³)", "Diagnóstico"),
            (arg, "Mapa de Argila (g/kg)", "Diagnóstico"),
            (p_solo, "Fósforo no Solo (mg/dm³)", "Diagnóstico"),
            (ca, "Cálcio (cmolc/dm³)", "Diagnóstico"),
            (mg, "Magnésio (cmolc/dm³)", "Diagnóstico"),
            (k, "Potássio (cmolc/dm³)", "Diagnóstico"),
            (rec_calc, "Recomendação de Calcário (kg/ha)", "Recomendação"),
            (rec_gesso, "Recomendação de Gesso (kg/ha)", "Recomendação"),
            (rec_k, "Recomendação de Potássio (kg/ha)", "Recomendação")
        ]

        with tab_visualizacao:
            st.write("Confira os mapas processados antes de exportar:")
            col1, col2 = st.columns(2)
            for i, (dados, tit, tipo) in enumerate(mapas_trabalho):
                with (col1 if i % 2 == 0 else col2):
                    st.pyplot(plot_para_pdf(dados, tit))

        with tab_pdf:
            if st.button("🚀 Gerar Dossiê Completo (PDF)"):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                
                # Capa
                pdf.add_page()
                try: pdf.image("LogoTriadeInceres.png", x=70, y=50, w=70)
                except: pass
                pdf.set_font("Arial", 'B', 24)
                pdf.ln(100)
                pdf.cell(0, 20, "RELATÓRIO TÉCNICO AGROESTRATÉGICO", ln=True, align='C')
                pdf.set_font("Arial", '', 14)
                pdf.cell(0, 10, "Metodologia de Precisão v43", ln=True, align='C')
                
                # Loop para cada mapa
                for dados, tit, tipo in mapas_trabalho:
                    pdf.add_page()
                    # Cabeçalho pequeno
                    try: pdf.image("LogoTriadeInceres.png", x=10, y=10, w=30)
                    except: pass
                    pdf.set_font("Arial", 'B', 14)
                    pdf.set_y(15)
                    pdf.cell(0, 10, f"{tipo}: {tit}", ln=True, align='R')
                    pdf.line(10, 25, 200, 25)
                    
                    # Gera e salva imagem temporária
                    fig_temp = plot_para_pdf(dados, tit)
                    img_name = f"temp_{tit.replace(' ', '_')}.png"
                    fig_temp.savefig(img_name, bbox_inches='tight', dpi=150)
                    plt.close(fig_temp)
                    
                    pdf.image(img_name, x=20, y=40, w=170)
                    
                    # Argumentação Técnica baseada no tipo
                    pdf.set_y(160)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, "Análise Técnica:", ln=True)
                    pdf.set_font("Arial", '', 11)
                    if tipo == "Diagnóstico":
                        texto = "Mapeamento da variabilidade espacial dos nutrientes para identificação de zonas de manejo."
                    else:
                        texto = "Cálculo de taxa variável v43 focado no equilíbrio de bases e otimização de custos."
                    pdf.multi_cell(0, 7, texto)
                    
                    os.remove(img_name) # Limpa a imagem após usar

                pdf_out = pdf.output(dest='S').encode('latin-1')
                st.download_button("📥 Baixar Relatório Full", data=pdf_out, file_name="Relatorio_Total_Triade.pdf")
