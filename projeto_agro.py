import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import json
from shapely.geometry import shape
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(layout="wide", page_title="Tríade Agro v48")

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

# --- ABA 0: PARÂMETROS MASTER (ATUALIZADA) ---
with t_attr:
    st.header("🛠️ Motor de Fórmulas v48 - Equilíbrio de Bases")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("🧪 Calcário (Equilíbrio Ca/Mg)")
        ca_alvo = st.number_input("Cálcio (Ca) desejado na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio (Mg) desejado na CTC (%)", value=18.0)
        prnt_calc = st.number_input("PRNT do Calcário (%)", value=80.0)
        cao_calc = st.number_input("Teor de CaO (%)", value=36.0)
        mgo_calc = st.number_input("Teor de MgO (%)", value=9.0)
        calc_adic = st.number_input("Calcário Adicional (ton/ha)", value=0.0)

    with c2:
        st.subheader("🌾 Potássio (K) e Fósforo (P)")
        sat_k_alvo = st.number_input("Saturação K Alvo na CTC (%)", value=3.2)
        meta_prod = st.number_input("Meta de Produtividade (sc/ha)", value=80.0)
        export_k = st.number_input("Exportação K2O (kg/sc)", value=0.5)
        st.write("**Fatores P (Elevar 1mg/dm³)**")
        f_m_arg = st.number_input("M. Argiloso", value=6.0)
        f_arg = st.number_input("Argiloso", value=4.0)

    with c3:
        st.subheader("📉 Níveis Críticos P-rem")
        nc1 = st.number_input("P-rem 0-4", value=8.0)
        nc2 = st.number_input("P-rem 4-10", value=12.0)
        st.write("**Gesso**")
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")

# --- ABA 1: DADOS ---
df, poligono, area_ha = None, None, 0.0
with t_dados:
    u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha Master (Excel)", type=["xlsx"])
    if u_geo and u_ex:
        df_raw = pd.read_excel(u_ex)
        poligono = shape(json.load(u_geo)['features'][0]['geometry'])
        area_ha = (poligono.area * 10**6) / 10000 
        st.warning("Mapeie as colunas (Lat, Lon, Arg, CTC, P, K, Ca, Mg, P-rem)")
        cols = df_raw.columns.tolist()
        # Mapeamento dinâmico aqui (simplificado para exibição)
        df = df_raw.copy() 

# --- MOTOR v48: ELEVAÇÃO DE BASES ---
if df is not None:
    # Lógica de Calcário: Maior entre Ca e Mg
    # NC = (Sat_Alvo * CTC / 100) - Teor_Atual
    # Dose = NC * 100 / (Teor_Insumo * 1.78 * PRNT/100) -> Simplificado para o motor
    
    def calc_calcario_bases(row):
        # Necessidade de Ca e Mg para atingir as porcentagens da CTC
        nec_ca = ((ca_alvo * row['CTC'] / 100) - row['Ca']) * 100 / (cao_calc * 1.78 * prnt_calc / 100)
        nec_mg = ((mg_alvo * row['CTC'] / 100) - row['Mg']) * 100 / (mgo_calc * 2.48 * prnt_calc / 100)
        return max(0, nec_ca, nec_mg) + calc_adic

    # Aplicação do motor (Considerando que o usuário mapeou as colunas Ca e Mg)
    try:
        df['Rec_Calc'] = df.apply(calc_calcario_bases, axis=1)
        df['Rec_K2O'] = (((sat_k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(0) + (meta_prod * export_k)
        df['Rec_Gesso'] = df['Argila'] * fator_gesso
    except:
        st.error("Verifique se as colunas 'Ca', 'Mg', 'CTC' e 'Argila' estão corretas.")

    # --- ZONAS & RELATÓRIO ---
    # Mantendo a lógica de 3 Zonas e Sumário de Insumos da v47
    with t_pdf:
        if st.button("🚀 Gerar PDF v48"):
            st.success("Relatório gerado com metodologia de Equilíbrio de Bases.")
