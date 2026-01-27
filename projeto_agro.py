import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
from fpdf import FPDF
import os
from pyproj import Geod

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
        st.subheader("Dados do Cliente")
        produtor = st.text_input("Nome do Produtor")
        fazenda = st.text_input("Nome da Fazenda")
        logo_fazenda = st.file_uploader("Logo da Fazenda (opcional)", type=["png", "jpg"])
        st.markdown("---")
        if st.button("Sair"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("Plataforma de Gestão Estratégica")
    
    tab_inicio, tab_satelite, tab_visualizacao, tab_pdf = st.tabs([
        "🏠 Upload & Dados", "🛰️ Imagens de Satélite", "🔍 Mapas", "📄 Relatório Final"
    ])

    area_ha = 0.0

    with tab_inicio:
        u1, u2 = st.columns(2)
        up_geo = u1.file_uploader("Contorno do Talhão (GeoJSON)", type=["json", "geojson"])
        up_ex = u2.file_uploader("Dados de Solo (Excel)", type=["xlsx"])
        
        if up_geo:
            data_geo = json.load(up_geo)
            poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
            # Cálculo de Área Automático
            geod = Geod(ellps="WGS84")
            area_m2 = abs(geod.geometry_area_perimeter(poligono)[0])
            area_ha = area_m2 / 10000
            st.metric("Área Identificada", f"{area_ha:.2f} ha")

    with tab_satelite:
        st.subheader("Análise de Zonas de Produtividade")
        c1, c2 = st.columns(2)
        data_ini = c1.date_input("Data Inicial")
        data_fim = c2.date_input("Data Final")
        
        tipo_analise = st.multiselect("Camadas para Composição", ["NDVI Contrastado", "Brilho de Solo", "Mapa de CTC"], default=["NDVI Contrastado", "Mapa de CTC"])
        
        if st.button("Gerar Zona de Produtividade"):
            st.info("Buscando imagens Sentinel-2... (Simulação de processamento de média sem nuvens)")
            st.warning("Integração via API de Satélite requer chaves de acesso específicas.")

        st.markdown("---")
        st.subheader("Semeadura em Taxa Variável")
        col_s1, col_s2, col_s3 = st.columns(3)
        pop_alta = col_s1.number_input("População Zona Alta (sem/ha)", value=70000)
        pop_media = col_s2.number_input("População Zona Média (sem/ha)", value=60000)
        pop_baixa = col_s3.number_input("População Zona Baixa (sem/ha)", value=50000)
        st.button("Calcular Prescrição de Sementes")

    if up_geo and up_ex:
        df = pd.read_excel(up_ex)
        df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors='coerce')
        df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors='coerce')
        df = df.dropna(subset=[df.columns[0], df.columns[1]])
        lat, lon = df.iloc[:, 0], df.iloc[:, 1]
        
        colunas_finais = [col for col in df.columns[2:] if not pd.to_numeric(df[col], errors='coerce').isnull().all()]

        def plot_fidedigno(data, titulo):
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon, lat, data, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            
            fig, ax = plt.subplots(figsize=(6, 6))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=1.5)
            ax.set_aspect('equal')
            
            # Legenda reduzida pela metade
            cbar = plt.colorbar(cp, fraction=0.03, pad=0.04)
            cbar.ax.tick_params(labelsize=6) 
            ax.axis('off')
            return fig, data.min(), data.mean(), data.max()

        with tab_visualizacao:
            c1, c2 = st.columns(2)
            for i, col in enumerate(colunas_finais):
                fig, v_min, v_med, v_max = plot_fidedigno(df[col], col)
                with (c1 if i % 2 == 0 else c2):
                    st.pyplot(fig)
                    st.caption(f"Min: {v_min:.2f} | Média: {v_med:.2f} | Máx: {v_max:.2f}")

        with tab_pdf:
            if st.button("🚀 Gerar Relatório Estratégico"):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_margins(30, 30, 30) # Margens de 3cm solicitadas
                
                # Capa e Sumário de Insumos
                pdf.add_page()
                try: pdf.image("LogoTriadeInceres.png", x=85, y=10, w=30)
                except: pass
                
                pdf.ln(40)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "RELATÓRIO TÉCNICO ESTRATÉGICO", ln=True, align='C')
                pdf.set_font("Arial", '', 12)
                pdf.cell(0, 10, f"Produtor: {produtor} | Fazenda: {fazenda}", ln=True, align='C')
                pdf.cell(0, 10, f"Área Total: {area_ha:.2f} ha", ln=True, align='C')

                # Tabela Dinâmica de Insumos
                pdf.ln(10)
                pdf.set_fill_color(230, 230, 230)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(90, 10, "Insumo / Atributo", 1, 0, 'C', True)
                pdf.cell(60, 10, "Volume Total (Est.)", 1, 1, 'C', True)
                
                pdf.set_font("Arial", '', 10)
                for col in colunas_finais:
                    media_val = df[col].mean()
                    total_est = media_val * area_ha
                    pdf.cell(90, 8, f"{col}", 1)
                    pdf.cell(60, 8, f"{total_est:.2f} unid.", 1, 1)

                # Páginas de Mapas
                for i, col in enumerate(colunas_finais):
                    pdf.add_page()
                    # Logo Tríade no Cabeçalho
                    try: pdf.image("LogoTriadeInceres.png", x=30, y=10, w=30)
                    except: pass
                    # Logo Fazenda no Cabeçalho (se houver)
                    if logo_fazenda:
                        pdf.image(logo_fazenda, x=150, y=10, w=30)

                    pdf.set_y(35)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, f"Mapa de {col}", ln=True, align='C')
                    
                    fig, v_min, v_med, v_max = plot_fidedigno(df[col], col)
                    img_path = f"/tmp/m_{i}.png"
                    fig.savefig(img_path, bbox_inches='tight', dpi=120)
                    plt.close(fig)
                    
                    pdf.image(img_path, x=45, y=50, w=120)
                    
                    # Infos abaixo do mapa com letra pequena (tamanho da legenda)
                    pdf.set_y(175)
                    pdf.set_font("Arial", '', 7)
                    pdf.cell(0, 5, f"Valores do Talhão - Mínimo: {v_min:.2f} | Médio: {v_med:.2f} | Máximo: {v_max:.2f}", ln=True, align='C')
                    
                    # Rodapé Fixo
                    pdf.set_y(-30)
                    try: pdf.image("LogoTriadeInceres.png", x=90, w=30)
                    except: pass
                    pdf.set_font("Arial", 'I', 8)
                    pdf.cell(0, 10, "Tríade Agro Estratégica", align='C')
                    if os.path.exists(img_path): os.remove(img_path)

                pdf_bytes = pdf.output(dest='S').encode('latin-1', 'replace')
                st.download_button("📥 Baixar Relatório Personalizado", data=pdf_bytes, file_name="Relatorio_Triade_Final.pdf")
