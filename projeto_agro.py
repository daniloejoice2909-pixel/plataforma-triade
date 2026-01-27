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

# --- CONFIGURAÇÃO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica")

if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    senha = st.text_input("Senha:", type="password")
    if senha == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

with st.sidebar:
    st.image("LogoTriadeInceres.png", width=150)
    produtor = st.text_input("Produtor", "Danilo")
    fazenda = st.text_input("Fazenda", "Nome da Fazenda")
    municipio = st.text_input("Município", "Uberlândia - MG")
    logo_faz_file = st.file_uploader("Logo da Fazenda", type=["png", "jpg"])

tab_dados, tab_mapas, tab_pdf = st.tabs(["🏠 Dados", "🔍 Mapas", "📄 Relatório"])

area_ha = 0.0
up_geo = tab_dados.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
up_ex = tab_dados.file_uploader("Planilha (Excel)", type=["xlsx"])

if up_geo:
    data_geo = json.load(up_geo)
    poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
    b = poligono.bounds
    area_ha = (poligono.area / ((b[2]-b[0])*(b[3]-b[1]))) * ((b[2]-b[0])*111320 * (b[3]-b[1])*110540) / 10000
    tab_dados.metric("Área", f"{area_ha:.2f} ha")

if up_geo and up_ex:
    df = pd.read_excel(up_ex)
    df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors='coerce')
    df.iloc[:, 1] = pd.to_numeric(df.iloc[:, 1], errors='coerce')
    df = df.dropna(subset=[df.columns[0], df.columns[1]])
    cols = [c for c in df.columns[2:] if pd.api.types.is_numeric_dtype(df[c])]

    def gerar_mapa(col):
        v = df[col].fillna(df[col].mean()).values
        b = poligono.bounds
        gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
        rbf = Rbf(df.iloc[:, 1].values, df.iloc[:, 0].values, v, function='multiquadric', smooth=0.1)
        z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
        fig, ax = plt.subplots(figsize=(5, 5))
        cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
        ax.plot(*poligono.exterior.xy, color='black', linewidth=1)
        cbar = plt.colorbar(cp, fraction=0.03); cbar.ax.tick_params(labelsize=6)
        ax.axis('off')
        return fig, v.min(), v.mean(), v.max()

    with tab_mapas:
        c1, c2 = st.columns(2)
        for i, col in enumerate(cols):
            f, mi, me, ma = gerar_mapa(col)
            (c1 if i % 2 == 0 else c2).pyplot(f)
            (c1 if i % 2 == 0 else c2).caption(f"{col} | Méd: {me:.2f}")

    if tab_pdf.button("🚀 Gerar PDF Final"):
        pdf = FPDF(); pdf.set_margins(30, 30, 30); pdf.add_page()
        try: pdf.image("LogoTriadeInceres.png", x=85, y=15, w=40)
        except: pass
        pdf.set_y(60); pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "RELATORIO TECNICO ESTRATEGICO", ln=True, align='C')
        pdf.set_font("Arial", '', 11); pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 7, f"Produtor: {produtor} | Fazenda: {fazenda} | Mun: {municipio}", ln=True, align='C')
        pdf.ln(10); pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Insumo / Concentracao / Volume Total", ln=True)
        
        insumos = [["Calcario", "(36% CaO 9% MgO 80% PRNT)", "ton"], ["Gesso", "(15% S 18% Ca)", "ton"], ["Super Simples", "(21% P2O5)", "ton"]]
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, "Insumo", 1); pdf.cell(80, 10, "Concentracao", 1); pdf.cell(30, 10, "Total", 1, 1)
        pdf.set_font("Arial", '', 12)
        for item in insumos:
            total = (df[cols[0]].mean() * area_ha) / 10
            pdf.cell(70, 10, item[0], 1); pdf.cell(80, 10, item[1], 1); pdf.cell(30, 10, f"{total:.1f}", 1, 1)

        metodos = {"Calcario": "Metodo: V%. Vantagem: Neutraliza Alumínio.", "Fosforo": "Metodo: Argila. Vantagem: Enraizamento.", "Gesso": "Metodo: Al profundo. Vantagem: Resistencia a seca."}
        
        for i, col in enumerate(cols):
            pdf.add_page()
            # Timbre
            try: pdf.image("LogoTriadeInceres.png", x=30, y=10, w=8)
            except: pass
            pdf.set_xy(40, 11); pdf.set_font("Arial", '', 7)
            pdf.cell(0, 5, "Triade Agro Estrategica | (WA) 34 998670919")
            try: pdf.image("LogoTriadeInceres.png", x=175, y=10, w=8)
            except: pass
            
            pdf.set_y(30); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"Mapa de {col}", ln=True)
            f, mi, me, ma = gerar_mapa(col); p = f"/tmp/m{i}.png"; f.savefig(p, dpi=120); plt.close(f)
            pdf.image(p, x=45, y=50, w=120)
            pdf.set_y(170); pdf.set_font("Arial", '', 9)
            pdf.cell(0, 10, f"Min: {mi:.2f} | Med: {me:.2f} | Max: {ma:.2f}", ln=True, align='C')
            pdf.set_font("Arial", '', 12)
            m_txt = next((v for k,v in metodos.items() if k.lower() in col.lower()), "Metodo: Taxa Variavel RBF. Vantagem: Precisao.")
            pdf.multi_cell(0, 8, m_txt)
            if os.path.exists(p): os.remove(p)

        res = pdf.output(dest='S').encode('latin-1', 'replace')
        tab_pdf.download_button("📥 Baixar PDF", data=res, file_name="Relatorio.pdf")
