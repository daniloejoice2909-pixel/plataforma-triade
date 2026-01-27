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
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica")

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Senha:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image("LogoTriadeInceres.png", width=150)
    produtor = st.text_input("Produtor", "Danilo")
    fazenda = st.text_input("Fazenda", "Fazenda Modelo")
    municipio = st.text_input("Município", "Uberlândia - MG")
    st.markdown("---")

st.title("Plataforma Tríade v43")
t_dados, t_sat, t_mapas, t_zonas, t_pdf = st.tabs(["🏠 Dados", "🛰️ Satélite", "🔍 Solo", "🗺️ Zonas", "📄 Relatório"])

df, poligono, area_ha = None, None, 0.0

with t_dados:
    c1, c2 = st.columns(2)
    u_geo = c1.file_uploader("GeoJSON", type=["json", "geojson"])
    u_ex = c2.file_uploader("Excel Solo", type=["xlsx"])
    if u_geo and u_ex:
        data_geo = json.load(u_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        b = poligono.bounds
        area_ha = (poligono.area / ((b[2]-b[0])*(b[3]-b[1]))) * ((b[2]-b[0])*111320 * (b[3]-b[1])*110540) / 10000
        df = pd.read_excel(u_ex).copy()
        df.iloc[:,0] = pd.to_numeric(df.iloc[:,0], errors='coerce')
        df.iloc[:,1] = pd.to_numeric(df.iloc[:,1], errors='coerce')
        df = df.dropna(subset=[df.columns[0], df.columns[1]])
        cols_d = [c for c in df.columns[2:] if not pd.to_numeric(df[c], errors='coerce').isnull().all()]
        for c in cols_d: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(df[c].mean())
        st.dataframe(df, use_container_width=True)
        st.metric("Área", f"{area_ha:.2f} ha")

with t_sat:
    st.subheader("Análise Sentinel-2")
    if st.button("🔍 Gerar NDVI"):
        st.image("https://via.placeholder.com/800x400/2E7D32/FFFFFF?text=Mapa+NDVI+v43")

def plot_rbf(col):
    df_c = df[[df.columns[1], df.columns[0], col]].dropna()
    x, y, z = df_c.iloc[:,0].values, df_c.iloc[:,1].values, df_c.iloc[:,2].values
    b = poligono.bounds
    gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:150j, b[1]-0.0006:b[3]+0.0006:150j]
    rbf = Rbf(x, y, z, function='multiquadric', smooth=0.1)
    gz = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(xp, yp)) for yp in gy[0,:]] for xp in gx[:,0]]))
    fig, ax = plt.subplots(figsize=(5,5))
    cp = ax.contourf(gx, gy, gz, levels=6, cmap='Spectral_r')
    ax.plot(*poligono.exterior.xy, color='black', linewidth=1); plt.colorbar(cp, fraction=0.03); ax.axis('off')
    return fig, z.min(), z.mean(), z.max()

if df is not None:
    with t_mapas:
        m1, m2 = st.columns(2)
        for i, col in enumerate(cols_d):
            f, mi, me, ma = plot_rbf(col)
            with (m1 if i % 2 == 0 else m2):
                st.markdown(f"**{col}**"); st.pyplot(f)
    
    with t_zonas:
        st.subheader("🗺️ 6 Zonas de Manejo")
        if st.button("Gerar Zonas"):
            km = KMeans(n_clusters=6, random_state=42).fit(StandardScaler().fit_transform(df[cols_d].values))
            df['Zona'] = km.labels_ + 1
            st.success("Zonas Geradas!"); st.dataframe(df[['Zona']+cols_d].head())

    with t_pdf:
        if st.button("🚀 Gerar PDF"):
            pdf = FPDF(); pdf.set_margins(30,30,30); pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "RELATORIO TECNICO ESTRATEGICO", ln=True, align='C')
            pdf.set_font("Arial", '', 11); pdf.cell(0, 7, f"{produtor} | {fazenda} | {municipio}", ln=True, align='C')
            pdf.ln(10); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "Insumo / Concentracao / Volume Total", ln=True)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(70, 10, "Insumo", 1); pdf.cell(80, 10, "Concentracao", 1); pdf.cell(30, 10, "Total", 1, 1)
            pdf.set_font("Arial", '', 12)
            for ins in [["Calcario", "(36% CaO 9% MgO)", "ton"], ["Gesso", "(15% S 18% Ca)", "ton"]]:
                pdf.cell(70, 10, ins[0], 1); pdf.cell(80, 10, ins[1], 1); pdf.cell(30, 10, f"{(df[cols_d[0]].mean()*area_ha/10):.1f}", 1, 1)
            
            met = {"Calcario": "Metodo: V%. Neutraliza Al.", "Fosforo": "Metodo: Argila. Enraizamento."}
            for i, col in enumerate(cols_d):
                pdf.add_page()
                pdf.set_font("Arial", '', 7); pdf.cell(0, 5, "Triade Agro Estrategica | (WA) 34 998670919", ln=True)
                pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"Mapa de {col}", ln=True)
                f, mi, me, ma = plot_rbf(col); p = f"/tmp/p{i}.png"; f.savefig(p, dpi=100); plt.close(f)
                pdf.image(p, x=45, y=50, w=120)
                pdf.set_y(175); pdf.set_font("Arial", '', 9); pdf.cell(0, 10, f"Max: {ma:.2f} | Med: {me:.2f} | Min: {mi:.2f}", ln=True, align='C')
                pdf.set_font("Arial", '', 12); pdf.multi_cell(0, 8, met.get(col, "Metodo: Taxa Variavel RBF. Otimizacao de custos."))
                if os.path.exists(p): os.remove(p)
            
            res = pdf.output(dest='S').encode('latin-1', 'replace')
            st.download_button("📥 Baixar PDF", data=res, file_name="Relatorio_Triade.pdf")
