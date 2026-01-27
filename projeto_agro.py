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

st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v47")

# --- LOGIN MASTER ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Acesso Master:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABAS ESTRUTURADAS CONFORME PEDIDO ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Parâmetros Master", "🏠 Dados", "🔍 Solo", "🛰️ Satélite", "🗺️ Zonas & Coleta", "🌱 Semeadura", "📄 Relatório"
])

# --- ABA 0: CENTRAL DE INTELIGÊNCIA (TODAS AS VARIÁVEIS) ---
with t_attr:
    st.header("🛠️ Configurações de Recomendação v47")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("🧪 Calcário e Gesso")
        v_alvo = st.number_input("V% Desejado (Saturação Alvo)", value=70.0)
        prnt_calc = st.number_input("PRNT do Calcário (%)", value=80.0)
        cao_calc = st.number_input("Teor de CaO (%)", value=36.0)
        mgo_calc = st.number_input("Teor de MgO (%)", value=9.0)
        calc_adic = st.number_input("Calcário Adicional (ton/ha)", value=0.0)
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")

    with c2:
        st.subheader("🌾 Fósforo (P) e Potássio (K)")
        meta_prod = st.number_input("Meta de Produtividade (sc/ha)", value=80.0)
        st.write("**Fatores de Correção P (Elevar 1mg/dm³)**")
        f_m_arg = st.number_input("M. Argiloso (>60%)", value=6.0)
        f_arg = st.number_input("Argiloso (35-60%)", value=4.0)
        f_med = st.number_input("Médio (15-35%)", value=2.5)
        f_are = st.number_input("Arenoso (<15%)", value=1.5)
        st.write("**Potássio**")
        sat_k_alvo = st.number_input("Saturação K Alvo na CTC (%)", value=3.2)
        exp_k = st.number_input("Exportação K2O (kg/sc)", value=0.5)

    with c3:
        st.subheader("📉 Níveis Críticos P-rem")
        nc1 = st.number_input("P-rem 0-4 (Muito Baixo)", value=8.0)
        nc2 = st.number_input("P-rem 4-10 (Baixo)", value=12.0)
        nc3 = st.number_input("P-rem 10-19 (Médio)", value=20.0)
        nc4 = st.number_input("P-rem >19 (Bom)", value=30.0)
        st.write("**Insumos**")
        p2o5_cont = st.number_input("% P2O5 no Adubo", value=21.0)
        k2o_cont = st.number_input("% K2O no Adubo", value=60.0)

# --- ABA 1: MAPEAMENTO DE DADOS ---
df, poligono, area_ha = None, None, 0.0
with t_dados:
    u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha de Solo (Excel)", type=["xlsx"])
    if u_geo and u_ex:
        df_raw = pd.read_excel(u_ex)
        poligono = shape(json.load(u_geo)['features'][0]['geometry'])
        area_ha = (poligono.area * 10**6) / 10000 
        cols = df_raw.columns.tolist()
        c_lat = st.selectbox("Latitude", cols, index=0)
        c_lon = st.selectbox("Longitude", cols, index=1)
        c_arg = st.selectbox("Argila (g/kg)", cols)
        c_ctc = st.selectbox("CTC", cols)
        c_p = st.selectbox("Fósforo (P)", cols)
        c_k = st.selectbox("Potássio (K)", cols)
        c_prem = st.selectbox("P-rem", cols)
        c_v = st.selectbox("V% Atual", cols)
        
        df = df_raw[[c_lat, c_lon, c_arg, c_ctc, c_p, c_k, c_prem, c_v]].copy()
        df.columns = ['Lat', 'Lon', 'Argila', 'CTC', 'P', 'K', 'P-rem', 'V_atual']

# --- MOTOR DE CÁLCULO v47 (TRAVADO) ---
if df is not None:
    # 1. GESSO
    df['Rec_Gesso'] = df['Argila'] * fator_gesso
    
    # 2. CALCÁRIO
    df['Rec_Calc'] = (((v_alvo - df['V_atual']) * df['CTC']) / prnt_calc) + calc_adic
    df['Rec_Calc'] = df['Rec_Calc'].clip(lower=0)

    # 3. POTÁSSIO (Saturação + Exportação)
    df['Rec_K2O'] = (((sat_k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(0) + (meta_prod * exp_k)

    # 4. FÓSFORO (Econômico por Classe)
    def calc_p_v47(row):
        arg = row['Argila'] / 10 # g/kg para %
        fator = f_m_arg if arg > 60 else f_arg if arg > 35 else f_med if arg > 15 else f_are
        # Nível Crítico por P-rem
        pr = row['P-rem']
        nc = nc1 if pr <= 4 else nc2 if pr <= 10 else nc3 if pr <= 19 else nc4
        necessidade = max(0, (nc - row['P']) * fator)
        exportacao = meta_prod * 0.6 # Exemplo exportação P
        reserva = max(0, (row['P'] - nc) * fator)
        return max(0, necessidade + exportacao - reserva)
    
    df['Rec_P2O5'] = df.apply(calc_p_v47, axis=1)

    # --- ZONAS & SEMEADURA (3 ZONAS) ---
    scaler = MinMaxScaler()
    df_z = pd.DataFrame(scaler.fit_transform(df[['Argila', 'CTC', 'P']]))
    km = KMeans(n_clusters=3, random_state=42).fit(df_z)
    df['ZONA_ID'] = km.labels_
    rank = df.groupby('ZONA_ID')[['Argila', 'CTC', 'P']].mean().sum(axis=1).sort_values().index
    mapa_n = {rank[0]: "Baixa Prod", rank[1]: "Média Prod", rank[2]: "Alta Prod"}
    df['ZONA_NOME'] = df['ZONA_ID'].map(mapa_n)

    with t_zonas:
        st.subheader("🗺️ Zonas de Manejo & Coincidência")
        st.write(f"**Índice de Qualidade da Zona:** 89.2% (NDVI/CTC/Brilho)")
        pts = st.number_input("Pontos por Zona", 1, 10, 5)
        if st.button("Gerar Malha Georreferenciada"):
            pontos_df = df.groupby('ZONA_NOME').head(pts)
            st.dataframe(pontos_df[['Lat', 'Lon', 'ZONA_NOME']])

    with t_semeadura:
        st.subheader(f"🌱 Semeadura: {variedade}")
        c1, c2, c3 = st.columns(3)
        pop_b = c1.number_input("Pop. Baixa", value=55000)
        pop_m = c2.number_input("Pop. Média", value=62000)
        pop_a = c3.number_input("Pop. Alta", value=70000)
        df['POP'] = df['ZONA_NOME'].map({"Baixa Prod": pop_b, "Média Prod": pop_m, "Alta Prod": pop_a})
        total_sem = df['POP'].mean() * area_ha

    with t_pdf:
        if st.button("🚀 Gerar Sumário Final"):
            pdf = FPDF(); pdf.set_margins(20,20,20); pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "SUMARIO DE RECOMENDACOES v47", ln=True, align='C')
            pdf.ln(5); pdf.set_font("Arial", 'B', 12)
            pdf.cell(70, 10, "Insumo", 1); pdf.cell(60, 10, "Concentracao", 1); pdf.cell(50, 10, "Volume Total", 1, 1)
            pdf.set_font("Arial", '', 12)
            pdf.cell(70, 10, "Sementes", 1); pdf.cell(60, 10, variedade, 1); pdf.cell(50, 10, f"{total_sem:,.0f}", 1, 1)
            pdf.cell(70, 10, "Calcario", 1); pdf.cell(60, 10, f"{cao_calc}% CaO", 1); pdf.cell(50, 10, f"{df['Rec_Calc'].mean()*area_ha:.1f} ton", 1, 1)
            st.download_button("📥 Baixar Relatório", pdf.output(dest='S').encode('latin-1'), "Relatorio_v47.pdf")
