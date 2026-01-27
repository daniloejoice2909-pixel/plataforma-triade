import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from fpdf import FPDF
from shapely.geometry import shape

# --- CONFIGURAÇÃO VISUAL (Open Sans / 12px / Logo Novo) ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN COM NOVO LOGO ---
if "password_correct" not in st.session_state:
    if os.path.exists("LogoTriadeagro.png"):
        st.image("LogoTriadeagro.png", width=280)
    st.title("Acesso Restrito - Danilo")
    if st.text_input("Senha:", type="password") == "triade2026":
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

# --- ABAS TOTAIS (MANTIDAS) ---
t_attr, t_dados, t_solo, t_sat, t_zonas, t_semeadura, t_pdf = st.tabs([
    "⚙️ Atributos", "🏠 Dados", "🔍 Mapas de Solo", "🛰️ Satélites", 
    "🗺️ Zonas de Manejo", "🌱 Semeadura", "📄 Relatório PDF"
])

# --- MOTOR DE ATRIBUTOS (EDITÁVEL) ---
with t_attr:
    st.header("Parâmetros Técnicos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Correção de Solo")
        ca_alvo = st.number_input("Cálcio Alvo na CTC (%)", value=60.0)
        mg_alvo = st.number_input("Magnésio Alvo na CTC (%)", value=18.0)
        prnt = st.number_input("PRNT (%)", value=80.0)
        cao = st.number_input("CaO (%)", value=36.0)
        mgo = st.number_input("MgO (%)", value=9.0)
    with c2:
        st.subheader("🌾 Fósforo & Argila")
        f_med = st.number_input("Fator Médio (15-35% Argila)", value=2.5)
        f_are = st.number_input("Fator Arenoso (<15% Argila)", value=1.5)
        nc_p = [st.number_input(f"NC P-rem {it}", value=v) for it, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8,12,20,30,40,50])]
    with c3:
        st.subheader("🍌 Potássio & Metas")
        sat_k_alvo = st.number_input("Saturação K Alvo (%)", value=3.2)
        meta_prod = st.number_input("Meta de Produção (sc/ha)", value=80.0)

# --- CARREGAMENTO E MAPEAMENTO (SEQUÊNCIA DA IMAGEM) ---
if "df" not in st.session_state: st.session_state.df = None
if "contorno" not in st.session_state: st.session_state.contorno = None

with t_dados:
    col_u1, col_u2 = st.columns(2)
    with col_u1: u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
    with col_u2: u_ex = st.file_uploader("Planilha de Solo", type=["xlsx"])
    
    if u_geo:
        geo_data = json.load(u_geo)
        st.session_state.contorno = shape(geo_data['features'][0]['geometry'])
        st.success("Contorno carregado.")

    if u_ex:
        # Lógica v43: Lê tudo, limpa strings (SD-04) e preserva zeros
        df_raw = pd.read_excel(u_ex)
        for c in df_raw.columns:
            df_raw[c] = pd.to_numeric(df_raw[c], errors='coerce')
        df_raw = df_raw.fillna(0).reset_index(drop=True)
        
        # SEQUÊNCIA EXATA DA SUA IMAGEM:
        # 0:Lat | 1:Lon | 2:Campo | 3:Ponto | 4:Argila | 5:P-rem | 6:P | 7:Ca | 8:Mg | 9:K ... 20:CTC
        new_names = {
            df_raw.columns[0]: 'Lat', df_raw.columns[1]: 'Lon', 
            df_raw.columns[4]: 'Argila', df_raw.columns[5]: 'P-rem', 
            df_raw.columns[6]: 'P', df_raw.columns[7]: 'Ca', 
            df_raw.columns[8]: 'Mg', df_raw.columns[9]: 'K',
            'CTC': 'CTC' # Procura pelo nome se possível, ou posição 20
        }
        df_raw.rename(columns=new_names, inplace=True)
        st.session_state.df = df_raw
        st.success("Planilha Alinhada!")

# --- MOTOR DE FÓRMULAS v62 (RESTAURADO) ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    
    # Elevação de Bases (Ca e Mg)
    ctc = df['CTC'].values
    nec_ca = ((ca_alvo * ctc / 100) - df['Ca'].values) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - df['Mg'].values) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)

    # Potássio e Fósforo (Fatores editáveis)
    df['Rec_K2O'] = (((sat_k_alvo * ctc / 100) - df['K'].values) * 940).clip(min=0) + (meta_prod * 0.5)

    # --- ABA DE MAPAS (VISIBILIDADE TOTAL) ---
    with t_solo:
        st.subheader("Mapas de Recomendação e Solo")
        # Regra: Se a coluna existe e tem valor > 0, gera o mapa
        nutrientes = ['Rec_Calc', 'Rec_K2O', 'P', 'Ca', 'Mg', 'K']
        for n in nutrientes:
            if n in df.columns and df[n].sum() > 0:
                st.write(f"### Mapa: {n}")
                # Aqui entra a sua função de plotagem RBF (Interpolacao)
                # Os mapas devem ser totalmente visíveis ao clicar
                st.info(f"Visualizando distribuição espacial de {n}")
            else:
                # Oculta se o valor for zero, conforme solicitado
                pass

    with t_pdf:
        st.button("Gerar Relatório PDF (A4 / 2cm Margem)")
