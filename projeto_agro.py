import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
from fpdf import FPDF
import os
from datetime import datetime, timedelta
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
        produtor = st.text_input("Nome do Produtor", "Não Informado")
        fazenda = st.text_input("Nome da Fazenda", "Não Informado")
        logo_fazenda_file = st.file_uploader("Logo da Fazenda (PNG/JPG)", type=["png", "jpg", "jpeg"])
        st.markdown("---")
        if st.button("Sair"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("Plataforma de Gestão Estratégica")
    
    tab_inicio, tab_satelite, tab_visualizacao, tab_pdf = st.tabs([
        "🏠 Início", "🛰️ Satélite", "🔍 Mapas de Solo", "📄 Relatório Final"
    ])

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

    with tab_satelite:
        st.subheader("Análise de Imagens de Satélite")
        c1, c2 = st.columns(2)
        data_i = c1.date_input("Início", datetime.now() - timedelta(days=30))
        data_f = c2.date_input("Fim", datetime.now())
        st.info("Filtre as melhores datas para gerar sua zona de produtividade.")
        if st.button("🔍 Buscar Imagens"):
            st.write("---")
            st.image("https://via.placeholder.com/600x200/2E7D32/FFFFFF?text=Galeria+de+Datas+Disponíveis", caption="Escolha a imagem com menor índice de nuvens.")

    if up_geo and up_ex:
        df_raw = pd.read_excel(up_ex)
        df_raw.iloc[:, 0] = pd.to_numeric(df_raw.iloc[:, 0], errors='coerce')
        df_raw.iloc[:, 1] = pd.to_numeric(df_raw.iloc[:, 1], errors='coerce')
        df = df_raw.dropna(subset=[df_raw.columns[0], df_raw.columns[1]]).copy()
        lat, lon = df.iloc[:, 0].values, df.iloc[:, 1].values
        
        colunas_dados = []
        for c in df.columns[2:]:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            if not df[c].isnull().all():
                df[c] = df[c].fillna(df[c].mean())
                colunas_dados.append(c)

        def plot_fidedigno(data_series):
            data_clean = data_series.values
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon, lat, data_clean, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            
            fig, ax = plt.subplots(figsize=(6, 6))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=1.2)
            ax.set_aspect('equal')
            cbar = plt.colorbar(cp, fraction=0.03, pad=0.04)
            cbar.ax.tick_params(labelsize=6)
            ax.axis('off')
            return fig, data_clean.min(), data_clean.mean(), data_clean.max()

        with tab_visualizacao:
            c1, c2 = st.columns(2)
            for i, col in enumerate(colunas_dados):
                fig, v_min, v_med, v_max = plot_fidedigno(df[col])
                with (c1 if i % 2 == 0 else c2):
                    st.pyplot(fig)
                    st.caption(f"Atributo: {col} | Mín: {v_min:.2f} | Média: {v_med:.2f} | Máx: {v_max:.2f}")

        with tab_pdf:
            if st.button("🚀 Gerar Relatório PDF"):
                # Salvar logo da fazenda temporariamente se existir
                logo_fazenda_path = None
                if logo_fazenda_file:
                    logo_fazenda_path = f"/tmp/logo_fazenda.png"
                    img_faz = Image.open(logo_fazenda_file)
                    img_faz.save(logo_fazenda_path)

                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_margins(30, 30, 30)
                
                # Capa
                pdf.add_page()
                try: pdf.image("LogoTriadeInceres.png", x=90, y=15, w=30)
                except: pass
                
                pdf.ln(45)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, u"RELATÓRIO TÉCNICO ESTRATÉGICO".encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
                pdf.set_font("Arial", '', 11)
                pdf.cell(0, 8, f"Produtor: {produtor}", ln=True, align='C')
                pdf.cell(0, 8, f"Fazenda: {fazenda}", ln=True, align='C')
                pdf.cell(0, 8, f"Área Total: {area_ha:.2f} ha", ln=True, align='C')

                # Tabela de Insumos
                pdf.ln(10); pdf.set_font("Arial", 'B', 10)
                pdf.cell(90, 10, "Atributo Analisado", 1); pdf.cell(60, 10, "Volume Total Est.", 1, 1, 'C')
                pdf.set_font("Arial", '', 9)
                for col in colunas_dados:
                    pdf.cell(90, 8, f"{col}", 1)
                    pdf.cell(60, 8, f"{(df[col].mean() * area_ha):.2f}", 1, 1, 'C')

                # Mapas
                for i, col in enumerate(colunas_dados):
                    pdf.add_page()
                    try: pdf.image("LogoTriadeInceres.png", x=30, y=10, w=25)
                    except: pass
                    if logo_fazenda_path:
                        pdf.image(logo_fazenda_path, x=155, y=10, w=25)

                    pdf.set_y(35); pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, f"Mapa de {col}", ln=True, align='C')
                    
                    fig, v_min, v_med, v_max = plot_fidedigno(df[col])
                    img_path = f"/tmp/map_{i}.png"
                    fig.savefig(img_path, bbox_inches='tight', dpi=120)
                    plt.close(fig)
                    
                    pdf.image(img_path, x=45, y=55, w=120)
                    pdf.set_y(180); pdf.set_font("Arial", '', 7)
                    pdf.cell(0, 5, f"Estatísticas: Mínimo {v_min:.2f} | Médio {v_med:.2f} | Máximo {v_max:.2f}", ln=True, align='C')
                    
                    pdf.set_y(-25); pdf.set_font("Arial", 'I', 8)
                    pdf.cell(0, 10, u"Tríade Agro Estratégica".encode('latin-1', 'replace').decode('latin-1'), align='C')
                    if os.path.exists(img_path): os.remove(img_path)

                if logo_fazenda_path and os.path.exists(logo_fazenda_path):
                    os.remove(logo_fazenda_path)

                pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
                st.download_button("📥 Baixar Relatório Final", data=pdf_out, file_name=f"Relatorio_{fazenda}.pdf")
