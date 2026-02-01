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
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 15px; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSE PDF PROFISSIONAL ---
class TriadePDF(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 40)
        except: pass
        self.set_font("helvetica", "B", 12)
        self.cell(0, 10, "Relatorio Tecnico de Recomendacao Estrategica", ln=True, align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()} - Triade Agro Estrategica", 0, 0, "C")

# --- MOTOR DE CÁLCULO V43 ---
def motor_calculo_v43(df, params):
    # Tipagem para evitar erros com colunas lidas como 'Geral' ou Texto
    cols_numericas = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P res', 'K%', 'V%', 'pH', 'prem']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p = params["fosforo"]
    k_params = params["potassio"]
    g_params = params["gesso"]
    c_params = params["calagem"]
    prod_esperada = params["global"]["produtividade"]

    # 1. GESSAGEM: Argila (g/kg) * Fator
    df['REC_GESSO'] = (df['Argila'] * g_params["fator"]).clip(lower=g_params["min"], upper=g_params["max"])

    # 2. CALAGEM (Equilíbrio Atômico - Fatores 560/400)
    df['NC_CA'] = ((c_params["target_ca"] - df['Ca%']).clip(lower=0) * df['CTC'] / 100)
    df['NC_MG'] = ((c_params["target_mg"] - df['Mg%']).clip(lower=0) * df['CTC'] / 100)
    
    dose_ca = (df['NC_CA'] * 560 * 100) / (c_params["cao"] * c_params["prnt"])
    dose_mg = (df['NC_MG'] * 400 * 100) / (c_params["mgo"] * c_params["prnt"])
    
    df['REC_CALCARIO'] = (np.maximum(dose_ca, dose_mg) + c_params["reserva"]).round(2)

    # 3. FÓSFORO (6 Classes P-rem)
    def calc_p(row):
        prem = row['prem']
        if prem <= 4: nc_alvo = p["nc_0_4"]
        elif prem <= 10: nc_alvo = p["nc_4_10"]
        elif prem <= 19: nc_alvo = p["nc_10_19"]
        elif prem <= 30: nc_alvo = p["nc_19_30"]
        elif prem <= 45: nc_alvo = p["nc_30_45"]
        else: nc_alvo = p["nc_45_60"]

        arg = row['Argila']
        f_arg = p["f_muito_arg"] if arg > 600 else p["f_argiloso"] if arg > 350 else p["f_medio"] if arg > 150 else p["f_arenoso"]

        delta_p = nc_alvo - row['P res']
        total_p2o5 = (max(delta_p, 0) * f_arg) + (prod_esperada * p["f_exp"])
        return (total_p2o5 * 100) / p["teor_adubo"]

    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 4. POTÁSSIO
    df['NC_K_CORRECAO'] = (k_params["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941
    total_k2o = df['NC_K_CORRECAO'] + (prod_esperada * k_params["f_exp"])
    df['REC_K_ADUBO'] = (total_k2o * 100 / k_params["teor_adubo"]).round(2)

    # 5. ZONEAMENTO (3 Zonas Coolwarm)
    df['SCORE_ZONA'] = (df['V%'] / 100 * 0.5) + (df['Argila'] / 1000 * 0.25) + (df['pH'] / 10 * 0.25)
    df['ZONA_MANEJO'] = pd.qcut(df['SCORE_ZONA'], 3, labels=["Baixa", "Média", "Alta"], duplicates='drop')
    
    return df

# --- FUNÇÃO QUE FALTAVA: CONFIGURAÇÃO DA INTERFACE ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    menu = st.sidebar.radio("Navegação", ["🏠 Home", "👥 Produtores"])
    
    st.sidebar.header("⚙️ Parâmetros Técnicos")
    
    with st.sidebar.expander("🌍 Global"):
        prod = st.number_input("Produtividade (sc/ha)", 80.0)

    with st.sidebar.expander("🪨 Calcário"):
        c_prnt = st.number_input("PRNT (%)", 80.0); c_cao = st.number_input("CaO (%)", 36.0); c_mgo = st.number_input("MgO (%)", 9.0)
        c_t_ca = st.number_input("Alvo Ca (%)", 60.0); c_t_mg = st.number_input("Alvo Mg (%)", 18.0); c_res = st.number_input("Reserva (kg)", 0)

    with st.sidebar.expander("🧪 Fósforo"):
        nc04 = st.number_input("NC P-rem 0-4", 8.0); nc4560 = st.number_input("NC P-rem 45-60", 22.0)
        p_teor = st.number_input("Teor Adubo P (%)", 21.0); p_exp = st.number_input("Exp. P (kg/sc)", 0.8)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K (%)", 3.2); k_teor = st.number_input("Teor Adubo K (%)", 60.0); k_exp = st.number_input("Exp. K (kg/sc)", 1.2)

    with st.sidebar.expander("⚪ Gesso"):
        g_fator = st.number_input("Fator Argila", 15.0); g_min = st.number_input("Min (kg/ha)", 400.0); g_max = st.number_input("Max (kg/ha)", 900.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res},
        "fosforo": {"nc_0_4": nc04, "nc_4_10": 10.0, "nc_10_19": 12.0, "nc_19_30": 15.0, "nc_30_45": 18.0, "nc_45_60": nc4560, "f_muito_arg": 10.0, "f_argiloso": 8.0, "f_medio": 4.0, "f_arenoso": 2.0, "teor_adubo": p_teor, "f_exp": p_exp},
        "potassio": {"target_k": k_target, "teor_adubo": k_teor, "f_exp": k_exp},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max}
    }
    return menu, params

# --- PÁGINA PRODUTORES ---
def pag_produtores(params):
    st.markdown("<h2 class='section-header'>Area Tecnica: Consultoria Triade</h2>", unsafe_allow_html=True)
    tab_dados, tab_mapas = st.tabs(["📁 Upload", "🗺️ Mapas"])
    
    with tab_dados:
        uploaded_file = st.file_uploader("Subir CSV (A-Y)", type=['csv'])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file, sep=';', decimal='.', encoding='utf-8-sig')
                df.columns = df.columns.str.strip()
                if 'Argila' in df.columns:
                    st.session_state['df_base'] = df
                    st.success("Dados carregados!")
            except Exception as e: st.error(f"Erro: {e}")

    with tab_mapas:
        if 'df_base' in st.session_state:
            df_final = motor_calculo_v43(st.session_state['df_base'], params)
            st.dataframe(df_final[['id', 'ZONA_MANEJO', 'REC_CALCARIO', 'REC_GESSO']])
            fig = px.scatter(df_final, x='Longitude', y='Latitude', color='ZONA_MANEJO', color_discrete_map={"Baixa":"#313695", "Média":"#fee090", "Alta":"#a50026"})
            st.plotly_chart(fig, use_container_width=True)

# --- EXECUÇÃO ---
menu, params = configurar_interface()
if menu == "🏠 Home":
    st.markdown("<h2 class='section-header'>Dashboard Triade</h2>", unsafe_allow_html=True)
    st.info("Pronto para processar dados.")
else:
    pag_produtores(params)
