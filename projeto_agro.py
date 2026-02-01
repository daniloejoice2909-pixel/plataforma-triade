import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from fpdf import FPDF
import base64
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS CUSTOMIZADO (PADRÃO PREMIUM TRÍADE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card {
        background-color: #ffffff; padding: 25px; border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center;
        border-bottom: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 32px; font-weight: 700; color: #1e3d59; margin-bottom: 5px; }
    .kpi-label { font-size: 14px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 1px; }
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 15px; margin-top: 25px; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSE PDF PROFISSIONAL (A4, MARGENS 2CM, OPEN SANS) ---
class TriadePDF(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 40)
        except: pass
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Relatório de Recomendação Estratégica", ln=True, align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Tríade Agro Estratégica v43 - Página {self.page_no()}", 0, 0, "C")

# --- MOTOR DE CÁLCULO V43 (AGRONOMIA + ÁLGEBRA DE MAPAS) ---
def motor_calculo_v43(df, params):
    """
    Executa os cálculos de gessagem, calagem (fatores 560/400) e álgebra de mapas para 3 zonas.
    """
    p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg = params["calagem"]
    niveis_p = params["fosforo"]
    
    # 1. GESSAGEM: Dose (kg/ha) = Argila (g/kg) * 15
    df['REC_GESSO'] = (df['Argila'] * 15).round(2)
    
    # 2. CALAGEM (Equilíbrio Ca/Mg na CTC - Fatores 560/400)
    # NC (cmolc/dm3) = (Alvo % - Atual %) * CTC / 100
    df['NC_CA_REQ'] = ((target_ca - df['Ca%']).clip(lower=0) * df['CTC'] / 100)
    df['NC_MG_REQ'] = ((target_mg - df['Mg%']).clip(lower=0) * df['CTC'] / 100)
    
    # Dose (t/ha) = (NC * Fator * 100) / (Teor no Calcário * PRNT)
    df['DOSE_CAO'] = (df['NC_CA_REQ'] * f_ca * 100) / (p_cao * p_prnt)
    df['DOSE_MGO'] = (df['NC_MG_REQ'] * f_mg * 100) / (p_mgo * p_prnt)
    
    # Regra do Máximo estabelecida
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CAO'], df['DOSE_MGO']) + calc_extra).round(2)

    # 3. FÓSFORO (6 Classes P-rem)
    def buscar_nc_p(prem):
        if prem <= 4: return niveis_p["0-4"]
        elif prem <= 10: return niveis_p["4-10"]
        elif prem <= 19: return niveis_p["10-19"]
        elif prem <= 30: return niveis_p["19-30"]
        elif prem <= 45: return niveis_p["30-45"]
        else: return niveis_p["45-60"]

    df['NC_P_ALVO'] = df['prem'].apply(buscar_nc_p)
    df['REC_P2O5'] = ((df['NC_P_ALVO'] - df['P res']).clip(lower=0) * 10).round(2) # Fator 10 de exemplo

    # 4. ÁLGEBRA DE MAPAS (3 ZONAS: 50% NDVI | 25% CTC | 25% Brilho)
    # Normalização simples para o mock (0-1)
    df['NDVI_NORM'] = (df['pH'] / 10) # Simulando NDVI via pH para o mock
    df['SCORE_ZONA'] = (df['NDVI_NORM'] * 0.5) + (df['V%'] / 100 * 0.25) + (df['Argila'] / 1000 * 0.25)
    df['ZONA_MANEJO'] = pd.qcut(df['SCORE_ZONA'], 3, labels=["Baixa", "Média", "Alta"])
    
    return df

# --- INTERFACE E NAVEGAÇÃO ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    menu = st.sidebar.radio("Navegação", ["🏠 Home / Onboarding", "👥 Produtores"])
    
    st.sidebar.header("⚙️ Parâmetros Técnicos")
    with st.sidebar.expander("🪨 Calagem Atômica (Ca/Mg)", expanded=True):
        p_prnt = st.number_input("PRNT Calcário (%)", 80.0)
        p_cao = st.number_input("Teor CaO (%)", 36.0)
        p_mgo = st.number_input("Teor MgO (%)", 9.0)
        target_ca = st.number_input("Alvo Ca na CTC (%)", 60.0)
        target_mg = st.number_input("Alvo Mg na CTC (%)", 18.0)
        calc_extra = st.number_input("Adicional (t/ha)", 0.0)
        f_ca, f_mg = 560, 400

    niveis_p = {"0-4": 9.0, "4-10": 10.5, "10-19": 12.5, "19-30": 15.0, "30-45": 17.5, "45-60": 19.3}

    params = {
        "calagem": (p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg),
        "fosforo": niveis_p
    }
    return menu, params

# --- PÁGINA HOME / ONBOARDING ---
def pag_home():
    st.markdown("<h2 class='section-header'>Centro de Comando Tríade</h2>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("""<div class='kpi-card'><div class='kpi-label'>Área Monitorada</div><div class='kpi-value'>17.000 ha</div></div>""", unsafe_allow_html=True)
    c2.markdown("""<div class='kpi-card'><div class='kpi-label'>Cliente Ativo</div><div class='kpi-value'>Gilson Berneck</div></div>""", unsafe_allow_html=True)
    c3.markdown("""<div class='kpi-card'><div class='kpi-label'>Alertas NDVI</div><div class='kpi-value' style='color:#e74c3c'>02</div></div>""", unsafe_allow_html=True)
    c4.markdown("""<div class='kpi-card'><div class='kpi-label'>Relatórios Gerados</div><div class='kpi-value'>14</div></div>""", unsafe_allow_html=True)

    st.markdown("<h3 class='section-header'>📂 Gestão de Dados e Contorno</h3>", unsafe_allow_html=True)
    col_dl, col_map = st.columns([1, 1.5])

    with col_dl:
        st.write("#### 1. Planilha de Solo (A-Y)")
        cols = ['Latitude', 'Longitude', 'CAMPO', 'id', 'prof', 'pH', 'P res', 'P mehl', 'K', 'Ca', 'Mg', 'Al', 'CTC', 'V%', 'Argila', 'Silte', 'K%', 'Ca%', 'prem', 'Areia gross', 'Areia total', 'Areia fina', 'Ca/Mg', 'H/Al', 'Mg%']
        df_mod = pd.DataFrame(columns=cols)
        csv = df_mod.to_csv(index=False, sep=';').encode('utf-8-sig')
        st.download_button("⬇️ Baixar Modelo Oficial Tríade (A-Y)", data=csv, file_name="modelo_solo_triade.csv", mime="text/csv")
        
        st.divider()
        st.write("#### 2. Upload de Arquivos")
        st.file_uploader("Subir Planilha Preenchida ou Contorno", type=['csv', 'zip', 'kml'])

    with col_map:
        st.write("#### 📍 Delimitação de Talhões")
        m = folium.Map(location=[-18.42, -47.41], zoom_start=13, tiles="CartoDB positron")
        Draw(export=True).add_to(
