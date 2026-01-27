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
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica", page_icon="🌱")

# --- LOGIN SEGURO ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=300)
    senha = st.text_input("Senha de Acesso:", type="password")
    if senha == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("LogoTriadeInceres.png", width=180)
    st.markdown("### 📋 Informações do Dossiê")
    produtor = st.text_input("Produtor", "Danilo")
    fazenda = st.text_input("Fazenda", "Nome da Fazenda")
    municipio = st.text_input("Município", "Uberlândia - MG")
    logo_fazenda = st.file_uploader("Logo da Fazenda (Opcional)", type=["png", "jpg"])
    st.markdown("---")
    if st.button("Encerrar Sessão"):
        st.session_state["password_correct"] = False
        st.rerun()

# --- INTERFACE PRINCIPAL ---
st.title("Plataforma de Gestão Estratégica v43")
tab_inicio, tab_satelite, tab_visualizacao, tab_pdf = st.tabs([
    "🏠 Início e Dados", "🛰️ Satélite (NDVI/Zona)", "🔍 Mapas de Solo", "📄 Relatório Final"
])

area_ha = 0.0

# --- ABA 1: UPLOAD E ÁREA ---
with tab_inicio:
    u1, u2 = st.columns(2)
    up_geo = u1.file_uploader("Contorno do Talhão (GeoJSON)", type=["json", "geojson"])
    up_ex = u2.file_uploader("Dados de Solo (Excel)", type=["xlsx"])
    
    if up_geo:
        data_geo = json.load(up_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        b = poligono.bounds
        area_ha = (poligono.area / ((b[2]-b[0])*(b[3]-b[1]))) * ((b[2]-b[0])*111320 * (b[3]-b[1])*110540) / 10000
        st.metric("Área Estimada", f"{area_ha:.2f} ha")
        st.success("Contorno carregado com sucesso!")

# --- ABA 2: SATÉLITE (REATIVADA) ---
with tab_satelite:
    st.subheader("🛰️ Integração de Satélite Sentinel-2")
    c1, c2, c3 = st.columns([1,1,1])
    d_inicio = c1.date_input("Data Inicial", datetime.now() - timedelta(days=45))
    d_fim = c2.date_input("Data Final", datetime.now())
    nuvens = c3.slider("Máximo de Nuvens (%)", 0, 100, 15)
    
    if st.button("🔍 Buscar Imagens Disponíveis"):
        st.info("Buscando cenas no servidor Sentinel Hub...")
        st.write("---")
        # Simulação de Galeria para Escolha
        g1, g2, g3 = st.columns(3)
        g1.image("https://via.placeholder.com/200x150/2E7D32/FFFFFF?text=Imagem+12/01", caption="Nuvens: 2%")
        if g1.button("Selecionar 12/01"): st.success("Imagem selecionada para processamento.")
        
        g2.image("https://via.placeholder.com/200x150/1B5E20/FFFFFF?text=Imagem+18/01", caption="Nuvens: 8%")
        if g2.button("Selecionar 18/01"): st.success("Imagem selecionada para processamento.")
        
        g3.image("https://via.placeholder.com/200x150/388E3C/FFFFFF?text=Imagem+25/01", caption="Nuvens: 20%")
        if g3.button("Selecionar 25/01"): st.warning("Atenção: Alta cobertura de nuvens.")

# --- PROCESSAMENTO E MAPAS ---
if up_geo and up_ex:
    df_raw = pd.read_excel(up_ex)
    df = df_raw.copy()
    df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0], errors='coerce')
    df.iloc[:, 1] = pd.to_numeric
