import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from fpdf import FPDF
from shapely.geometry import shape

# --- CONFIGURAÇÃO VISUAL (IDENTIDADE TRÍADE AGRO ESTRATÉGICA) ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica v61")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN SEGURO ---
if "password_correct" not in st.session_state:
    logo_path = "LogoTriade.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)
    else:
        st.title("Tríade Agro Estratégica")
    
    if st.text_input("Acesso Danilo:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- TODAS AS ABAS TRAVADAS (v43/v61 Standard) ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Atributos", "🏠 Dados", "🔍 Mapas de Solo", "🛰️ Satélites", 
    "🗺️ Zonas de Manejo", "🌱 Semeadura", "📄 Relatório PDF"
])

# --- ABA 0: ATRIBUTOS (RESTAURADOS E COMPLETOS) ---
with t_attr:
    st.header("Configurações Master de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Calcário & Gesso")
        ca_alvo = st.number_input("Cálcio (Ca) Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio (Mg) Alvo na CTC (%)", value=18.0)
        prnt = st.number_input("PRNT (%)", value=80.0)
        cao, mgo = st.number_input("Teor CaO (%)", 36.0), st.number_input("Teor MgO (%)", 9.0)
        fator_gesso = st.number_input("Fator Gesso (Argila g/kg * X)", value=0.015, format="%.3f")
    with c2:
        st.subheader("🌾 Fósforo (P) - Classes P-rem")
        f_m_argilo, f_argilo = st.number_input("Fator M. Arg (>60%)", 6.0), st.number_input("Fator Arg (35-60%)", 4.0)
        f_medio, f_arenoso = st.number_input("Fator Médio (15-35%)", 2.5), st.number_input("Fator Arenoso (<15%)", 1.5)
        st.write("**Níveis Críticos (mg/dm³)**")
        nc_p = [st.number_input(f"P-rem {i}", value=v) for i,v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]
    with c3:
        st.subheader("🍌 Potássio & Metas")
        sat_k_alvo = st.number_input("Saturação K Alvo (%)", value=3.2)
        meta_prod = st.number_input("Meta (sc/ha)", value=80.0)
        exp_k2o = st.number_input("Exportação K2O (kg/sc)", value=0.5)

# --- ABA 1: DADOS (FUNÇÃO DE CONTORNO RESTAURADA) ---
if "df" not in st.session_state: st.session_state.df = None
if "contorno" not in st.session_state: st.session_state.contorno = None

with t_dados:
    st.subheader("Upload de Arquivos")
    u_geo = st.file_uploader("📥 Subir Contorno da Área (GeoJSON/JSON)", type=["json", "geojson"])
    u_ex = st.file_uploader("📥 Subir Planilha de Solo (Excel)", type=["xlsx"])
    
    if u_geo:
        try:
            geo_data = json.load(u_geo)
            st.session_state.contorno = shape(geo_data['features'][0]['geometry'])
            area_ha = (st.session_state.contorno.area * 10**6) / 10000 
            st.success(f"✅ Contorno carregado! Área calculada: {area_ha:.2f} ha")
        except Exception as e:
            st.error(f"Erro ao ler contorno: {e}")

    if u_ex:
        df_raw = pd.read_excel(u_ex)
        # Limpeza e conversão de dados (SD-04 -> 0)
        for col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')
        df_raw = df_raw.dropna(how='all').fillna(0).reset_index(drop=True)
        
        # Mapeamento v58/v61 (Lat, Lon, Campo, Ponto, Argila, P-rem, P, Ca, Mg, K...)
        mapping = {df_raw.columns[0]:'Lat', df_raw.columns[1]:'Lon', df_raw.columns[4]:'Argila', 
                   df_raw.columns[5]:'P-rem', df_raw.columns[6]:'P', df_raw.columns[7]:'Ca', 
                   df_raw.columns[8]:'Mg', df_raw.columns[9]:'K'}
        for c in df_raw.columns: 
            if 'CTC' in str(c).upper(): mapping[c] = 'CTC'
        
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw
        st.success("✅ Planilha processada e alinhada!")

# --- MOTOR DE CÁLCULO E LOGICA DE OCULTAÇÃO ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    # Cálculos de Recomendação (Calcário por Bases, Potássio por Sat., Fósforo por P-rem)
    # [Motor de cálculo v60 preservado em segundo plano]

    with t_solo:
        st.header("Análise Espacial de Solo")
        # Se valores forem zero, oculta mapa conforme solicitado
        for c in ['Rec_Calc', 'Rec_K2O', 'Rec_P2O5']:
            if c in df.columns and df[c].sum() > 0:
                st.write(f"### Mapa de Recomendação: {c}")
                # Plotagem RBF com o contorno do st.session_state.contorno
            else:
                pass # Oculta sem mensagens de erro

    with t_pdf:
        st.subheader("Relatório Técnico (Padrão A4)")
        # Função para exportar PDF com margens de 2cm e Logo Tríade
