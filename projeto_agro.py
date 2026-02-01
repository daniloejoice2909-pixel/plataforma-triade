import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
import base64
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS CUSTOMIZADO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card {
        background-color: #ffffff; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center;
        border-bottom: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 28px; font-weight: 700; color: #1e3d59; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSE PDF PROFISSIONAL ---
class TriadePDF(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 40)
        except: pass
        self.set_font("helvetica", "B", 12)
        self.cell(0, 10, "Relatório Técnico - Tríade Agro", ln=True, align="R")
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")

# --- MOTOR DE CÁLCULO V43 (REGRAS ATÔMICAS TRÍADE) ---
def motor_calculo_v43(df, params):
    # Parâmetros de Calagem
    p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg = params["calagem"]
    # Parâmetros de Fósforo/Potássio
    niveis_p, k_alvo = params["fosforo"], params["k_alvo"]
    
    # 1. GESSAGEM: Dose (kg/ha) = Argila (g/kg) * 15
    df['REC_GESSO'] = (df['ARGILA'] * 15).round(2)
    
    # 2. CALAGEM (Elevação de Ca e Mg na CTC - Fatores 560/400)
    # NC (cmolc/dm³) = (Alvo % - Atual %) * CTC / 100
    df['NC_CA'] = ((target_ca - df['CA_PERC']).map(lambda x: max(0, x)) * df['CTC'] / 100)
    df['NC_MG'] = ((target_mg - df['MG_PERC']).map(lambda x: max(0, x)) * df['CTC'] / 100)
    
    # Doses Individuais: (NC * Fator * 100) / (Teor no Calcário * PRNT)
    df['DOSE_CAO'] = (df['NC_CA'] * f_ca * 100) / (p_cao * p_prnt)
    df['DOSE_MGO'] = (df['NC_MG'] * f_mg * 100) / (p_mgo * p_prnt)
    
    # REGRA DE OURO: Máximo entre as doses + adicional
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CAO'], df['DOSE_MGO']) + calc_extra).round(2)
    
    # 3. FÓSFORO (6 Classes P-rem)
    def calc_p(row):
        prem = row['PREM']
        if prem <= 4: nc = niveis_p["0-4"]
        elif prem <= 10: nc = niveis_p["4-10"]
        elif prem <= 19: nc = niveis_p["10-19"]
        elif prem <= 30: nc = niveis_p["19-30"]
        elif prem <= 45: nc = niveis_p["30-45"]
        else: nc = niveis_p["45-60"]
        return round(max(0, nc - row['P']) * 10, 2)
    
    df['REC_P2O5'] = df.apply(calc_p, axis=1)
    
    # 4. POTÁSSIO
    df['REC_K2O'] = df['K'].map(lambda x: round(max(0, k_alvo - x) * 2.4, 2))

    # 5. ÁLGEBRA DE ZONAS (50% NDVI | 25% CTC | 25% Brilho)
    df['POTENCIAL_SCORE'] = (df['NDVI_HIST'] * 0.5) + (df['CTC_NORM'] * 0.25) + (df['BRIGHTNESS'] * 0.25)
    df['ZONA_MANEJO'] = pd.qcut(df['POTENCIAL_SCORE'], 3, labels=["Baixo", "Médio", "Alto"])
    
    return df

# --- INTERFACE ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    menu = st.sidebar.radio("Navegação", ["🏠 Home", "👥 Produtores"])
    
    st.sidebar.header("⚙️ Parâmetros Técnicos")
    with st.sidebar.expander("🪨 Calagem Atômica (Ca/Mg)", expanded=True):
        p_prnt = st.number_input("PRNT Calcário (%)", 80.0)
        p_cao = st.number_input("Teor CaO (%)", 36.0)
        p_mgo = st.number_input("Teor MgO (%)", 9.0)
        target_ca = st.number_input("Alvo Ca na CTC (%)", 60.0)
        target_mg = st.number_input("Alvo Mg na CTC (%)", 18.0)
        calc_extra = st.number_input("Adicional (t/ha)", 0.0)
        f_ca, f_mg = 560, 400

    with st.sidebar.expander("🧪 Fósforo e Potássio", expanded=False):
        niveis_p = {"0-4": 9.0, "4-10": 10.5, "10-19": 12.5, "19-30": 15.0, "30-45": 17.5, "45-60": 19.3}
        k_alvo = st.number_input("Alvo K na CTC (%)", 0.35)

    params = {
        "calagem": (p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg),
        "fosforo": niveis_p,
        "k_alvo": k_alvo
    }
    return menu, params

# --- PÁGINAS ---
def pag_produtores(params):
    st.title("Gestão de Produtores")
    produtor = st.selectbox("Selecione o Cliente:", ["Gilson Berneck"])
    
    tab_safra, tab_config = st.tabs(["🌾 Safra 2025/26", "⚙️ Configurar Área"])
    
    with tab_safra:
        with st.expander("🎯 Zonas de Produtividade & Recomendações", expanded=True):
            data = {
                'ID': range(1, 7),
                'ARGILA': [450, 200, 600, 350, 480, 150],
                'CA_PERC': [45, 52, 38, 55, 42, 30],
                'MG_PERC': [10, 12, 9, 14, 11, 8],
                'CTC': [10.5, 8.0, 12.0, 11.0, 10.0, 7.5],
                'P': [5, 12, 4, 18, 6, 25],
                'PREM': [3, 15, 8, 35, 22, 50],
                'K': [0.15, 0.10, 0.30, 0.20, 0.25, 0.08],
                'NDVI_HIST': [0.85, 0.60, 0.90, 0.75, 0.82, 0.55],
                'CTC_NORM': [0.7, 0.4, 1.0, 0.8, 0.9, 0.3],
                'BRIGHTNESS': [0.6, 0.8, 0.5, 0.7, 0.6, 0.9],
                'LAT': [-18.42, -18.43, -18.44, -18.42, -18.41, -18.40],
                'LON': [-47.41, -47.42, -47.41, -47.40, -47.39, -47.41]
            }
            df = motor_calculo_v43(pd.DataFrame(data), params)
            
            st.write("### Mapa de Variabilidade (3 Zonas)")
            fig = px.scatter(df, x='LON', y='LAT', color='ZONA_MANEJO', 
                             color_discrete_map={"Baixo":"#313695", "Médio":"#fee090", "Alto":"#a50026"})
            st.plotly_chart(fig, use_container_width=True)
            
            st.write("### Tabela de Recomendação VRT")
            st.dataframe(df[['ID', 'ZONA_MANEJO', 'REC_GESSO', 'REC_CALCARIO', 'REC_P2O5', 'REC_K2O']])

# --- EXECUÇÃO ---
menu, params = configurar_interface()
if menu == "🏠 Home":
    st.header("Tríade Agro Estratégica - Dashboard")
else:
    pag_produtores(params)
