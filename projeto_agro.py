import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
from fpdf import FPDF
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v46")

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Acesso Master:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABAS v46 ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Parâmetros", "🏠 Dados", "🔍 Mapas de Solo", "🛰️ Satélite", "🗺️ Zonas & Coleta", "🌱 Semeadura", "📄 Relatório"
])

# --- ABA 0: PARÂMETROS TÉCNICOS ---
with t_attr:
    st.header("🛠️ Configurações Master v46")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Fatores de Correção P (por Argila)")
        f_m_argilo = st.number_input("Muito Argiloso (>60%)", value=6.0)
        f_argilo = st.number_input("Argiloso (35-60%)", value=4.0)
        f_medio = st.number_input("Médio (15-35%)", value=2.5)
        f_arenoso = st.number_input("Arenoso (<15%)", value=1.5)
    
    with c2:
        st.subheader("📉 Níveis Críticos P-rem")
        nc_1 = st.number_input("P-rem 0-4 (Muito Baixo)", value=8.0)
        nc_2 = st.number_input("P-rem 4-10 (Baixo)", value=12.0)
        nc_3 = st.number_input("P-rem 10-19 (Médio)", value=20.0)
        nc_4 = st.number_input("P-rem >19 (Bom)", value=30.0)

    with c3:
        st.subheader("🚜 Configurações de Máquina")
        variedade = st.text_input("Variedade da Semente", "Ex: Pioneer P30F53")
        p2o5_adubo = st.number_input("% P2O5 Adubo", value=21.0)
        k2o_adubo = st.number_input("% K2O Adubo", value=60.0)

# --- ABA 1 & 2: DADOS E SOLO ---
with t_dados:
    u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha Master (Lat, Lon, Arg, P, K, P-rem, CTC, V%)", type=["xlsx"])
    if u_geo and u_ex:
        df = pd.read_excel(u_ex)
        poligono = shape(json.load(u_geo)['features'][0]['geometry'])
        st.success("Dados v46 Carregados.")

# --- ABA 4: SATÉLITES (PENÚLTIMA ANTES DAS ZONAS) ---
with t_sat:
    st.subheader("🛰️ Galeria Sentinel-2 (Brilho, NDRE, NDVI)")
    if st.button("Buscar Imagens de Satélite"):
        st.write("Analisando Brilho de Solo e NDRE...")
        st.image("https://via.placeholder.com/600x300/333333/FFFFFF?text=Mapa+de+Brilho+de+Solo", width=400)
        st.image("https://via.placeholder.com/600x300/1B5E20/FFFFFF?text=Mapa+NDRE+(Vigor)", width=400)

# --- ABA 5: ZONAS DE MANEJO & COLETA ---
if u_geo and u_ex:
    # Lógica de 3 Zonas
    scaler = MinMaxScaler()
    df_z = pd.DataFrame(scaler.fit_transform(df[['Argila', 'CTC', 'P']]), columns=['A','C','P'])
    km = KMeans(n_clusters=3, random_state=42).fit(df_z)
    df['ZONA_ID'] = km.labels_
    
    # Classificação por produtividade
    df['Score'] = df_z.mean(axis=1)
    ranks = df.groupby('ZONA_ID')['Score'].mean().sort_values().index
    mapa_n = {ranks[0]: "Baixa Prod", ranks[1]: "Média Prod", ranks[2]: "Alta Prod"}
    df['ZONA_NOME'] = df['ZONA_ID'].map(mapa_n)

    with t_zonas:
        st.subheader("📍 Gestão de Zonas e Amostragem")
        pts_per_zona = st.number_input("Pontos por Zona", 1, 10, 3)
        if st.button("Gerar Pontos Automaticamente"):
            pontos = df.groupby('ZONA_NOME').head(pts_per_zona)
            st.dataframe(pontos[['Lat', 'Lon', 'ZONA_NOME']])
            csv = pontos.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exportar para APP de Coleta", csv, "coleta.csv")

    # --- ABA 6: SEMEADURA TAXA VARIÁVEL ---
    with t_semeadura:
        st.subheader(f"🌱 Planejamento: {variedade}")
        c1, c2, c3 = st.columns(3)
        pop_baixa = c1.number_input("População Baixa (sem/ha)", value=55000)
        pop_media = c2.number_input("População Média (sem/ha)", value=62000)
        pop_alta = c3.number_input("População Alta (sem/ha)", value=70000)
        
        # Mapeamento de populações
        map_pop = {"Baixa Prod": pop_baixa, "Média Prod": pop_media, "Alta Prod": pop_alta}
        df['POPULACAO'] = df['ZONA_NOME'].map(map_pop)
        
        st.write("### Mapa de Recomendação de Semeadura")
        st.info("Arquivo otimizado para monitores: John Deere, Case IH, Stara.")

    # --- ABA 7: RELATÓRIO E SUMÁRIO ---
    with t_pdf:
        if st.button("🚀 Gerar Relatório e Sumário de Insumos"):
            pdf = FPDF(); pdf.set_margins(20,20,20); pdf.add_page()
            
            # CABEÇALHO v46
            pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "SUMARIO DE RECOMENDACOES v46", ln=True, align='C')
            pdf.ln(5); pdf.set_font("Arial", 'B', 12)
            pdf.cell(70, 10, "Insumo", 1); pdf.cell(60, 10, "Concentracao", 1); pdf.cell(50, 10, "Volume Total", 1, 1)
            
            pdf.set_font("Arial", '', 12)
            # Cálculo de Sementes Total
            total_sementes = df['POPULACAO'].mean() * (poligono.area * 10**6 / 10000)
            
            itens = [
                ["Sementes", variedade, f"{total_sementes:,.0f} sem"],
                ["Fosforo (P2O5)", f"{p2o5_adubo}%", "Calculado"],
                ["Potassio (K2O)", f"{k2o_adubo}%", "Calculado"]
            ]
            for i in itens:
                pdf.cell(70, 10, i[0], 1); pdf.cell(60, 10, i[1], 1); pdf.cell(50, 10, i[2], 1, 1)
            
            st.download_button("📥 Baixar Dossiê Completo", pdf.output(dest='S').encode('latin-1'), "Dossie_v46.pdf")
