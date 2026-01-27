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

# --- CONFIGURAÇÃO DE MEMÓRIA E TELA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v45")

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Senha Master:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABA 0: CENTRAL DE ATRIBUTOS TÉCNICOS (EDITÁVEL) ---
with st.sidebar:
    st.image("LogoTriadeInceres.png", width=150)
    st.title("Configurações v45")
    produtor = st.text_input("Produtor", "Danilo")
    fazenda = st.text_input("Fazenda", "Fazenda Modelo")
    meta_prod = st.number_input("Meta de Produtividade (sc/ha)", value=80.0)
    logo_faz_file = st.file_uploader("Logo da Fazenda", type=["png", "jpg"])

t_attr, t_dados, t_zonas, t_pdf = st.tabs(["⚙️ Parâmetros Técnicos", "🏠 Dados", "🗺️ Zonas e Coleta", "📄 Relatório"])

with t_attr:
    st.header("🛠️ Motor de Fórmulas v43 - Parâmetros de Recomendação")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("🧪 Calcário e Gesso")
        ca_teor = st.number_input("% CaO no Calcário", value=36.0)
        mg_teor = st.number_input("% MgO no Calcário", value=9.0)
        prnt = st.number_input("% PRNT", value=80.0)
        v_desejado = st.number_input("V% Desejado (Saturação)", value=70.0)
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg x ...)", value=0.015, format="%.3f")
        
    with col2:
        st.subheader("🌾 Fósforo (P)")
        p_adubo = st.number_input("% P2O5 no Adubo", value=21.0)
        export_p = st.number_input("P2O5 Exportado (kg/sc)", value=0.6) # Valor para meta
        st.write("**Nível Crítico P-rem (Editável)**")
        nc_prem = st.slider("Ajuste Nível Crítico P-rem", 0.0, 60.0, 20.0)
        
    with col3:
        st.subheader("🍌 Potássio (K)")
        sat_k_desejada = st.number_input("Saturação K desejada na CTC (%)", value=3.2)
        export_k = st.number_input("K2O Exportado (kg/sc)", value=0.5)
        k_adubo = st.number_input("% K2O no Adubo", value=60.0)

# --- ABA 1: DADOS E PROCESSAMENTO ---
with t_dados:
    u1, u2 = st.columns(2)
    u_geo = u1.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = u2.file_uploader("Planilha Solo (Lat, Lon, Arg, CTC, P, K, P-rem, V%)", type=["xlsx"])
    
    if u_geo and u_ex:
        df = pd.read_excel(u_ex).dropna(subset=['Lat', 'Lon'])
        poligono = shape(json.load(u_geo)['features'][0]['geometry'])
        st.success("Dados carregados. Motor v43 pronto.")

# --- MOTOR DE CÁLCULOS TRAVADO ---
if u_geo and u_ex:
    # 1. CÁLCULO DE GESSO (Argila em g/kg * 0.015)
    df['Rec_Gesso'] = df['Argila'] * fator_gesso 

    # 2. CÁLCULO DE POTÁSSIO (Saturação 3.2% + Exportação Meta)
    # K_rec = ((SatK_desejada * CTC / 100) - K_atual) * 940 + (Meta * Export_K)
    df['Rec_K2O'] = (((sat_k_desejada * df['CTC'] / 100) - df['K']) * 940).clip(0) + (meta_prod * export_k)

    # 3. CÁLCULO DE FÓSFORO (Econômico - P-rem + Meta)
    # Se P_solo > Nivel_Critico, usa reserva. Se não, corrige + exportação.
    def calc_p(row):
        nc = nc_prem # Nível crítico baseado no P-rem simplificado
        necessidade_corr = max(0, (nc - row['P']) * 2.3)
        exportacao = meta_prod * export_p
        # Se houver reserva (P_solo > NC), subtrai da exportação
        reserva = max(0, (row['P'] - nc) * 2.3)
        return max(0, necessidade_corr + exportacao - reserva)

    df['Rec_P2O5'] = df.apply(calc_p, axis=1)

    # --- ABA ZONAS (3 ZONAS: NDVI, BRILHO, CTC) ---
    with t_zonas:
        st.subheader("🗺️ Zonas de Manejo e Coincidência")
        scaler = MinMaxScaler()
        # Simulando camadas de satélite para o exemplo, unindo à CTC
        df_z = pd.DataFrame(scaler.fit_transform(df[['Argila', 'CTC', 'P']]), columns=['NDVI', 'Brilho', 'CTC'])
        
        coincidencia = df_z.corr().mean().mean() * 100
        km = KMeans(n_clusters=3, random_state=42).fit(df_z)
        df['ZONA'] = km.labels_
        
        st.metric("Índice de Coincidência (Qualidade)", f"{coincidencia:.1f}%")
        
        # Pontos de Coleta
        st.subheader("📍 Pontos de Coleta Georreferenciados")
        pontos = df.groupby('ZONA').sample(3) if len(df) > 9 else df
        st.dataframe(pontos[['Lat', 'Lon', 'ZONA']])
        
        csv = pontos[['Lat', 'Lon', 'ZONA']].to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar CSV para APP de Coleta", csv, "coleta_triade.csv")

    # --- RELATÓRIO PDF ---
    with t_pdf:
        if st.button("🚀 Gerar PDF v45"):
            pdf = FPDF(); pdf.set_margins(20, 20, 20); pdf.add_page()
            
            # TIMBRE
            if logo_faz_file: pdf.image(logo_faz_file, x=160, y=10, w=30)
            pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "DOSSIE ESTRATEGICO v45", ln=True, align='C')
            
            # TABELA DE INSUMOS
            pdf.ln(10); pdf.set_font("Arial", 'B', 12)
            pdf.cell(60, 10, "Insumo", 1); pdf.cell(60, 10, "Dose Media (kg/ha)", 1); pdf.cell(60, 10, "Total (ton)", 1, 1)
            pdf.set_font("Arial", '', 12)
            pdf.cell(60, 10, "Fosforo (P2O5)", 1); pdf.cell(60, 10, f"{df['Rec_P2O5'].mean():.1f}", 1); pdf.cell(60, 10, "...", 1, 1)
            pdf.cell(60, 10, "Potassio (K2O)", 1); pdf.cell(60, 10, f"{df['Rec_K2O'].mean():.1f}", 1); pdf.cell(60, 10, "...", 1, 1)
            pdf.cell(60, 10, "Gesso", 1); pdf.cell(60, 10, f"{df['Rec_Gesso'].mean():.1f}", 1); pdf.cell(60, 10, "...", 1, 1)

            st.download_button("📥 Baixar Relatório", pdf.output(dest='S').encode('latin-1'), "Dossie_V45.pdf")
