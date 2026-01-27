import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point, MultiPoint
import json
from fpdf import FPDF
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

# --- CONFIGURAÇÃO ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v44")

# --- LOGIN (Simplificado para o código) ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False
    with st.sidebar:
        st.image("LogoTriadeInceres.png", width=150)
        if st.text_input("Senha:", type="password") == "triade2026":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image("LogoTriadeInceres.png", width=150)
    st.header("⚙️ Configurações v44")
    produtor = st.text_input("Produtor", "Danilo")
    fazenda = st.text_input("Fazenda", "Fazenda Modelo")
    municipio = st.text_input("Município", "Uberlândia - MG")
    logo_faz_file = st.file_uploader("Upload Logo da Fazenda", type=["png", "jpg"])
    st.markdown("---")
    metodo_coleta = st.radio("Método de Pontos de Coleta", ["Automático", "Manual"])

tab_dados, tab_zonas, tab_coleta, tab_pdf = st.tabs(["🏠 Dados", "🗺️ Zonas de Manejo", "📍 Coleta de Solo", "📄 Relatório Final"])

df, poligono, area_ha = None, None, 0.0

with tab_dados:
    c1, c2 = st.columns(2)
    u_geo = c1.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = c2.file_uploader("Dados de Solo/Satélite (Excel)", type=["xlsx"])
    
    if u_geo and u_ex:
        data_geo = json.load(u_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        area_ha = (poligono.area * 10**6) / 10000 # Cálculo simplificado ha
        
        df = pd.read_excel(u_ex)
        # Padronização: Lat, Lon, NDVI, Brilho, CTC...
        df = df.dropna(subset=[df.columns[0], df.columns[1]])
        st.dataframe(df.head())
        st.success(f"Área detectada: {area_ha:.2f} ha")

# --- MOTOR DE ZONAS E COINCIDÊNCIA ---
if df is not None:
    with tab_zonas:
        st.subheader("Análise Multivariada: NDVI + Brilho + CTC")
        
        # Seleção de colunas para o motor
        cols_analise = st.multiselect("Selecione as camadas para a Zona:", df.columns[2:], default=df.columns[2:5].tolist())
        
        if len(cols_analise) >= 2:
            # Normalização para comparação (0 a 1)
            scaler = MinMaxScaler()
            df_norm = pd.DataFrame(scaler.fit_transform(df[cols_analise]), columns=cols_analise)
            
            # Cálculo de Coincidência (Correlação Média entre camadas)
            coincidencia = df_norm.corr().mean().mean() * 100
            
            # KMeans para 3 Zonas
            kmeans = KMeans(n_clusters=3, random_state=42).fit(df_norm)
            df['ZONA_ID'] = kmeans.labels_
            
            # Mapear IDs para nomes de produtividade baseados na média dos valores
            df['Score'] = df_norm.mean(axis=1)
            ranking = df.groupby('ZONA_ID')['Score'].mean().sort_values().index
            mapa_zonas = {ranking[0]: "Baixa Produtividade", ranking[1]: "Média Produtividade", ranking[2]: "Alta Produtividade"}
            df['ZONA_NOME'] = df['ZONA_ID'].map(mapa_zonas)

            c1, c2 = st.columns([2, 1])
            with c1:
                st.metric("Índice de Coincidência das Camadas", f"{coincidencia:.1f}%")
                st.info("Quanto maior o percentual, mais estável é a zona de manejo gerada.")
                # Mapa Visual Simulado (RBF da Zona)
                st.write("### Mapa de Produtividade Estimada")
                # (Aqui entraria o código de plotagem RBF da coluna 'Score')
                
            with c2:
                st.write("### Resumo de Áreas")
                resumo = df['ZONA_NOME'].value_counts(normalize=True) * area_ha
                st.table(resumo)

    with tab_coleta:
        st.subheader("📍 Planejamento de Amostragem")
        pontos_df = pd.DataFrame()
        
        if metodo_coleta == "Automático":
            num_pontos = st.number_input("Quantidade de pontos por zona:", 1, 10, 3)
            # Lógica para pegar o centroide ou pontos espalhados por zona
            pontos_df = df.groupby('ZONA_NOME').head(num_pontos)
        else:
            st.info("Clique no mapa (Funcionalidade em desenvolvimento para interface web direta).")
            pontos_df = df.sample(5) # Simulação manual

        st.write("#### Pontos Georreferenciados (Padrão APP de Coleta)")
        st.dataframe(pontos_df[[df.columns[0], df.columns[1], 'ZONA_NOME']])
        
        csv = pontos_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar Pontos para APP (.CSV)", csv, "pontos_coleta_triade.csv", "text/csv")

    with tab_pdf:
        if st.button("🚀 Gerar Dossiê v44"):
            pdf = FPDF(); pdf.set_margins(20, 20, 20); pdf.add_page()
            
            # TIMBRE COM LOGO DA FAZENDA E TRÍADE
            try: 
                pdf.image("LogoTriadeInceres.png", x=20, y=10, w=30)
                if logo_faz_file:
                    pdf.image(logo_faz_file, x=160, y=10, w=30)
            except: pass
            
            pdf.set_y(45); pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, f"DOSSIE DE MANEJO: {fazenda}", ln=True, align='C')
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 7, f"Produtor: {produtor} | Municipio: {municipio}", ln=True, align='C')
            
            # SEÇÃO DE ZONAS
            pdf.ln(10); pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "Estabilidade e Qualidade das Zonas", ln=True)
            pdf.set_font("Arial", '', 12)
            pdf.multi_cell(0, 8, f"O indice de coincidencia entre NDVI, Brilho do Solo e CTC foi de {coincidencia:.1f}%. "
                                f"Este percentual indica que as zonas de manejo possuem alta fidelidade com o histórico da area.")
            
            # TABELA DE PONTOS DE COLETA
            pdf.ln(10); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "Coordenadas para Coleta de Solo", ln=True)
            pdf.set_font("Arial", '', 8)
            pdf.cell(50, 8, "Latitude", 1); pdf.cell(50, 8, "Longitude", 1); pdf.cell(60, 8, "Zona", 1, 1)
            for _, row in pontos_df.head(15).iterrows():
                pdf.cell(50, 7, str(row[0]), 1); pdf.cell(50, 7, str(row[1]), 1); pdf.cell(60, 7, str(row['ZONA_NOME']), 1, 1)

            res_pdf = pdf.output(dest='S').encode('latin-1', 'replace')
            st.download_button("📥 Baixar PDF v44", res_pdf, "Dossie_V44.pdf")
