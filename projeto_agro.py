import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import json
from shapely.geometry import shape
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(layout="wide", page_title="Tríade Agro v50")

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.image("LogoTriadeInceres.png", width=250)
    if st.text_input("Acesso Master:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABAS ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Parâmetros Master", "🏠 Dados", "🔍 Solo", "🛰️ Satélite", "🗺️ Zonas & Coleta", "🌱 Semeadura", "📄 Relatório"
])

# --- ABA 0: PARÂMETROS MASTER (v50) ---
with t_attr:
    st.header("🛠️ Configurações Master v50")
    # (Mantendo todos os parâmetros de Calcário, P-rem, Fatores e K salvos anteriormente)
    # ... [Campos de entrada conforme v49] ...

# --- ABA 1: DADOS (LEITURA INTEGRAL) ---
df, poligono, area_ha = None, None, 0.0
with t_dados:
    u_geo = st.file_uploader("Contorno", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha v49/50 (Lat, Lon, Argila, CTC, P, K, Ca, Mg, P-rem, V%)", type=["xlsx"])
    if u_geo and u_ex:
        # Lê tudo, tratando NaNs como 0 mas mantendo a linha
        df = pd.read_excel(u_ex).fillna(0)
        poligono = shape(json.load(u_geo)['features'][0]['geometry'])
        area_ha = (poligono.area * 10**6) / 10000 
        st.success("Planilha processada. Valores zerados serão ocultados da visualização.")

# --- MOTOR DE CÁLCULO v50 ---
if df is not None:
    # Lógica de Calcário (Bases), Fósforo (Econômico), Potássio (Sat+Exp) e Gesso
    # ... [Cálculos conforme v49] ...
    
    # --- ABA SOLO (EXIBIÇÃO CONDICIONAL) ---
    with t_solo:
        for col in ['P', 'K', 'Ca', 'Mg', 'Rec_Calc', 'Rec_P2O5', 'Rec_K2O', 'Rec_Gesso']:
            if df[col].sum() > 0: # Só mostra se houver valor acumulado maior que zero
                st.subheader(f"Mapa de {col}")
                # [Lógica de Plotagem RBF aqui]
            else:
                pass # Oculta mapa e informações se o valor for zero

    # --- ABA ZONAS & COLETA ---
    with t_zonas:
        # Só gera zonas se houver dados de variabilidade
        if df[['Argila', 'CTC', 'P']].sum().sum() > 0:
            # [Lógica de KMeans 3 Zonas]
            st.write("Zonas de Manejo Geradas.")
        else:
            st.warning("Dados insuficientes para gerar Zonas de Manejo.")

    # --- RELATÓRIO PDF (OCULTAÇÃO DE SEÇÕES ZERADAS) ---
    with t_pdf:
        if st.button("🚀 Gerar PDF v50"):
            pdf = FPDF(); pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "SUMARIO v50", ln=True, align='C')
            
            # Só adiciona ao sumário se o volume total for > 0
            if df['Rec_Calc'].sum() > 0:
                pdf.cell(0, 10, f"Calcário: {df['Rec_Calc'].mean()*area_ha:.1f} ton", ln=True)
            if df['Rec_P2O5'].sum() > 0:
                pdf.cell(0, 10, f"Fósforo: {df['Rec_P2O5'].mean()*area_ha:.1f} ton", ln=True)
            
            st.download_button("Baixar PDF", pdf.output(dest='S').encode('latin-1'), "Dossie_v50.pdf")
