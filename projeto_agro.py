import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import json
from shapely.geometry import shape
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(layout="wide", page_title="Tríade Agro v51")

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

# --- ABA 0: PARÂMETROS MASTER (v51) ---
with t_attr:
    st.header("🛠️ Configurações Master v51")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário e Gesso")
        ca_alvo = st.number_input("Ca Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Mg Alvo na CTC (%)", value=18.0)
        prnt = st.number_input("PRNT (%)", value=80.0)
        cao, mgo = st.number_input("CaO (%)", value=36.0), st.number_input("MgO (%)", value=9.0)
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")
    with c2:
        st.subheader("🌾 Fósforo (P-rem e Fatores)")
        f_med, f_are = st.number_input("Fator Médio", value=2.5), st.number_input("Fator Arenoso", value=1.5)
        nc_list = [st.number_input(f"P-rem {cat}", value=v) for cat, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]
    with c3:
        st.subheader("🍌 Potássio e Meta")
        sat_k_alvo = st.number_input("Sat. K Alvo (%)", value=3.2)
        meta_prod = st.number_input("Meta (sc/ha)", value=80.0)

# --- ABA 1: DADOS (LEITURA POR POSIÇÃO) ---
df, poligono, area_ha = None, None, 0.0
if "df" not in st.session_state: st.session_state.df = None

with t_dados:
    u_geo = st.file_uploader("Contorno", type=["json", "geojson"])
    u_ex = st.file_uploader("Planilha v51 (Lat, Lon, Argila, CTC, P, K, Ca, Mg, P-rem, V%)", type=["xlsx"])
    if u_geo and u_ex:
        # Lê todas as linhas, preenche zeros onde estiver vazio
        raw_df = pd.read_excel(u_ex).fillna(0)
        # Força os nomes de coluna baseados na sua estrutura enviada
        # Ordem: 0:Lat, 1:Lon, 2:Argila, 3:CTC, 4:P, 5:K, 6:Ca, 7:Mg, 8:P-rem, 9:V%
        raw_df.columns = ['Lat', 'Lon', 'Argila', 'CTC', 'P', 'K', 'Ca', 'Mg', 'P-rem', 'V_atual'] + list(raw_df.columns[10:])
        st.session_state.df = raw_df
        poligono = shape(json.load(u_geo)['features'][0]['geometry'])
        area_ha = (poligono.area * 10**6) / 10000 
        st.success(f"Planilha v51 mapeada com sucesso! Área: {area_ha:.2f} ha")

# --- MOTOR DE CÁLCULO v51 (PROTEGIDO) ---
if st.session_state.df is not None:
    df = st.session_state.df
    
    # 1. CALCÁRIO (ELEVAÇÃO DE BASES)
    df['Rec_Calc'] = np.maximum(
        ((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt/100),
        ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt/100)
    ).clip(lower=0)

    # 2. POTÁSSIO
    df['Rec_K2O'] = (((sat_k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(0) + (meta_prod * 0.5)

    # 3. FÓSFORO (ECONÔMICO)
    def calc_p_v51(row):
        arg = row['Argila'] / 10
        fator = 6.0 if arg > 60 else 4.0 if arg > 35 else f_med if arg > 15 else f_are
        pr = row['P-rem']
        # Seleção de Nível Crítico simplificada
        idx = 0 if pr<=4 else 1 if pr<=10 else 2 if pr<=19 else 3 if pr<=30 else 4 if pr<=45 else 5
        nc = nc_list[idx]
        return max(0, (nc - row['P']) * fator + (meta_prod * 0.6) - max(0, (row['P'] - nc) * fator))
    df['Rec_P2O5'] = df.apply(calc_p_v51, axis=1)

    # 4. GESSO
    df['Rec_Gesso'] = df['Argila'] * fator_gesso

    # --- ABA SOLO (OCULTAÇÃO SE ZERADO) ---
    with t_solo:
        mapas_ativos = ['P', 'K', 'Ca', 'Mg', 'Rec_Calc', 'Rec_P2O5', 'Rec_K2O', 'Rec_Gesso']
        for col in mapas_ativos:
            if col in df.columns and df[col].sum() > 0:
                st.subheader(f"Mapa de {col}")
                # Plotagem RBF aqui...
            else:
                st.info(f"O atributo {col} está zerado na planilha e foi ocultado.")

    # --- ABA ZONAS E PDF ---
    # Segue a mesma lógica de ocultação de tabelas zeradas no PDF
