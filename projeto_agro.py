import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
from fpdf import FPDF
import base64

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
    # BARRA LATERAL
    with st.sidebar:
        st.image("LogoTriadeInceres.png", width=180)
        st.markdown("### 👤 Usuário: Danilo")
        if st.button("Sair"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("Plataforma Estratégica v43")
    
    tab_inicio, tab_diagnostico, tab_recomendacao = st.tabs(["🏠 Início", "🔍 Diagnóstico", "🚜 Recomendação & PDF"])

    with tab_inicio:
        u1, u2 = st.columns(2)
        up_geo = u1.file_uploader("GeoJSON do Talhão", type=["json", "geojson"])
        up_ex = u2.file_uploader("Planilha de Solo (Excel)", type=["xlsx"])

    if up_geo and up_ex:
        # Processamento
        data_geo = json.load(up_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        df = pd.read_excel(up_ex).apply(pd.to_numeric, errors='coerce').fillna(0)
        
        lat, lon = df.iloc[:,0], df.iloc[:,1]
        ctc = df.iloc[:,20] # Coluna U
        ca = df.iloc[:,7]
        mg = df.iloc[:,8]
        
        def plot_mapa_global(data, titulo):
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon, lat, data, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            fig, ax = plt.subplots(figsize=(8, 5))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=2)
            plt.colorbar(cp)
            ax.axis('off')
            return fig

        with tab_diagnostico:
            st.subheader("Mapa de CTC")
            fig_ctc = plot_mapa_global(ctc, "CTC")
            st.pyplot(fig_ctc)

        with tab_recomendacao:
            st.subheader("Gerar Relatório Final")
            # Cálculo de Calcário v43
            rec_calc = (np.maximum(((60/100*ctc)-ca)*0.56*(100/36), (18/100*ctc-mg)*0.40*(100/9)) * 1000 * (100/80)).clip(lower=0)
            
            fig_rec = plot_mapa_global(rec_calc, "Calcário")
            st.pyplot(fig_rec)

            # --- FUNÇÃO GERADORA DE PDF ---
            if st.button("Preparar Download do PDF"):
                fig_rec.savefig("temp_mapa.png", bbox_inches='tight', dpi=150)
                
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.add_page()
                pdf.set_margins(20, 20, 20)
                
                # Cabeçalho
                try: pdf.image("LogoTriadeInceres.png", x=80, y=10, w=50)
                except: pass
                
                pdf.ln(35)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "RELATÓRIO DE RECOMENDAÇÃO TÉCNICA", ln=True, align='C')
                
                # Texto Técnico
                pdf.ln(10)
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, "Metodologia v43 - Tríade Agro Estratégica", ln=True)
                pdf.set_font("Arial", '', 11)
                texto = ("A tecnologia de taxa variável permite a correção precisa do solo, "
                         "aplicando apenas o necessário onde a planta realmente precisa. "
                         "Diferente do método convencional, aqui equilibramos as bases (Ca, Mg, K) "
                         "ponto a ponto, garantindo maior eficiência econômica e produtiva.")
                pdf.multi_cell(0, 7, texto)
                
                # Inserir Mapa
                pdf.ln(10)
                pdf.image("temp_mapa.png", x=30, w=150)
                
                pdf_output = pdf.output(dest='S').encode('latin-1')
                
                st.download_button(
                    label="📥 Baixar PDF Agora",
                    data=pdf_output,
                    file_name="Relatorio_Triade_Agro.pdf",
                    mime="application/pdf"
                )
