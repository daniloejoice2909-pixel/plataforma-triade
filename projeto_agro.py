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
        st.subheader("Dados do Relatório")
        produtor = st.text_input("Nome do Produtor", "Produtor Exemplo")
        fazenda = st.text_input("Nome da Fazenda", "Fazenda Exemplo")
        logo_fazenda = st.file_uploader("Logo da Fazenda (Opcional)", type=["png", "jpg"])
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
            st.metric("Área Identificada", f"{area_ha:.2f} ha")

    with tab_satelite:
        st.subheader("Busca de Imagens Sentinel-2")
        c1, c2 = st.columns(2)
        data_i = c1.date_input("Início", datetime.now() - timedelta(days=30))
        data_f = c2.date_input("Fim", datetime.now())
        st.info("O sistema buscará imagens sem nuvens no período selecionado.")
        if st.button("🔍 Buscar Satélite"):
            st.write("---")
            st.image("https://via.placeholder.com/600x200/2E7D32/FFFFFF?text=Galeria+de+Imagens+Disponiveis", caption="Simulação: Escolha a melhor data")

    if up_geo and up_ex:
        # Carregamento e limpeza pesada de dados
        df_raw = pd.read_excel(up_ex)
        df_raw.iloc[:, 0] = pd.to_numeric(df_raw.iloc[:, 0], errors='coerce')
        df_raw.iloc[:, 1] = pd.to_numeric(df_raw.iloc[:, 1], errors='coerce')
        df = df_raw.dropna(subset=[df_raw.columns[0], df_raw.columns[1]]).copy()
        
        lat, lon = df.iloc[:, 0].values, df.iloc[:, 1].values
        
        colunas_dados = []
        for c in df.columns[2:]:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            if not df[c].isnull().all():
                df[c] = df[c].fillna(df[c].mean()) # Preenche NaNs com a média para evitar o erro do Rbf
                colunas_dados.append(c)

        def plot_fidedigno(data_series, titulo):
            data_clean = data_series.values
            b = poligono.bounds
            # Criar grade de pontos
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            
            # PROTEÇÃO: Verificar se há NaNs ou Infs antes do Rbf
            if np.isnan(data_clean).any() or np.isinf(data_clean).any():
                return None, 0, 0, 0

            rbf = Rbf(lon, lat, data_clean, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            
            fig, ax = plt.subplots(figsize=(6, 6))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=1.2)
            ax.set_aspect('equal')
            
            cbar = plt.colorbar(cp, fraction=0.03, pad=0.04)
            cbar.ax.tick_params(labelsize=6) # Legendas reduzidas pela metade
            ax.axis('off')
            return fig, data_clean.min(), data_clean.mean(), data_clean.max()

        with tab_visualizacao:
            c1, c2 = st.columns(2)
            for i, col in enumerate(colunas_dados):
                fig, v_min, v_med, v_max = plot_fidedigno(df[col], col)
                if fig:
                    with (c1 if i % 2 == 0 else c2):
                        st.pyplot(fig)
                        st.caption(f"Min: {v_min:.2f} | Média: {v_med:.2f} | Máx: {v_max:.2f}")

        with tab_pdf:
            if st.button("📥 Baixar Relatório Completo"):
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_margins(30, 30, 30) # Margens de 3cm
                
                # Capa
                pdf.add_page()
                try: pdf.image("LogoTriadeInceres.png", x=90, y=15, w=30)
                except: pass
                pdf.ln(45)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, u"RELATÓRIO TÉCNICO ESTRATÉGICO".encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
                pdf.set_font("Arial", '', 11)
                pdf.cell(0, 10, f"Produtor: {produtor} | Fazenda: {fazenda} | Área: {area_ha:.2f} ha", ln=True, align='C')

                # Tabela de Insumos
                pdf.ln(10); pdf.set_font("Arial", 'B', 10)
                pdf.cell(90, 10, "Item", 1); pdf.cell(60, 10, "Total Est.", 1, 1, 'C')
                pdf.set_font("Arial", '', 9)
                for col in colunas_dados:
                    pdf.cell(90, 8, f"{col}", 1)
                    pdf.cell(60, 8, f"{(df[col].mean() * area_ha):.2f}", 1, 1, 'C')

                for i, col in enumerate(colunas_dados):
                    fig, v_min, v_med, v_max = plot_fidedigno(df[col], col)
                    if fig:
                        pdf.add_page()
                        try: pdf.image("LogoTriadeInceres.png", x=30, y=10, w=25)
                        except: pass
                        if logo_fazenda: pdf.image(logo_fazenda, x=155, y=10, w=25)
                        
                        pdf.set_y(35); pdf.set_font("Arial", 'B', 12)
                        pdf.cell(0, 10, f"Mapa de {col}", ln=True, align='C')
                        
                        img_path = f"/tmp/p_{i}.png"
                        fig.savefig(img_path, bbox_inches='tight', dpi=120)
                        plt.close(fig)
                        
                        pdf.image(img_path, x=45, y=55, w=120)
                        pdf.set_y(180); pdf.set_font("Arial", '', 7)
                        pdf.cell(0, 5, f"Mínimo: {v_min:.2f} | Médio: {v_med:.2f} | Máximo: {v_max:.2f}", ln=True, align='C')
                        
                        pdf.set_y(-25); pdf.set_font("Arial", 'I', 8)
                        pdf.cell(0, 10, u"Tríade Agro Estratégica".encode('latin-1', 'replace').decode('latin-1'), align='C')
                        if os.path.exists(img_path): os.remove(img_path)

                pdf_data = pdf.output(dest='S').encode('latin-1', 'replace')
                st.download_button("Clique para Salvar", data=pdf_data, file_name="Relatorio_Triade.pdf")
