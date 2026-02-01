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

# --- CLASSE PDF PROFISSIONAL (A4, 2cm MARGENS) ---
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
    # Tipagem: Garante que os cálculos não falhem por colunas 'texto'
    cols_numericas = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P res', 'K%', 'V%', 'pH', 'prem']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p = params["fosforo"]
    k_params = params["potassio"]
    g_params = params["gesso"]
    c_params = params["calagem"]
    prod_esperada = params["global"]["produtividade"]

    # 1. GESSAGEM: Argila (g/kg) * 15
    df['REC_GESSO'] = (df['Argila'] * g_params["fator"]).clip(lower=g_params["min"], upper=g_params["max"])

    # 2. CALAGEM (Fatores 560/400)
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
        if arg > 600: f_arg = p["f_muito_arg"]
        elif arg > 350: f_arg = p["f_argiloso"]
        elif arg > 150: f_arg = p["f_medio"]
        else: f_arg = p["f_arenoso"]

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

# --- INTERFACE E DOWNLOADS ---
def pag_produtores(params):
    st.markdown("<h2 class='section-header'>Area Tecnica: Consultoria Triade</h2>", unsafe_allow_html=True)
    tab_dados, tab_mapas = st.tabs(["📁 Dados e Upload", "🗺️ Mapas e Recomendacoes"])
    
    with tab_dados:
        st.write("### 1. Upload de Dados")
        uploaded_file = st.file_uploader("Selecione o arquivo CSV (A-Y)", type=['csv'])
        
        if uploaded_file:
            try:
                # Ajuste para ler com ponto decimal e separador de ponto-e-virgula (padrao Excel BR)
                df_input = pd.read_csv(uploaded_file, sep=';', decimal='.', encoding='utf-8-sig')
                df_input.columns = df_input.columns.str.strip() 
                
                if 'Argila' in df_input.columns:
                    st.success("Dados carregados e validados para o padrao v43!")
                    st.session_state['df_base'] = df_input
                else:
                    st.error(f"Erro: Coluna 'Argila' nao encontrada. Verifique o cabeçalho.")
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

    with tab_mapas:
        if 'df_base' in st.session_state:
            df_final = motor_calculo_v43(st.session_state['df_base'], params)
            st.dataframe(df_final[['id', 'ZONA_MANEJO', 'REC_CALCARIO', 'REC_GESSO', 'REC_P_ADUBO', 'REC_K_ADUBO']], use_container_width=True)
            
            fig = px.scatter(df_final, x='Longitude', y='Latitude', color='ZONA_MANEJO',
                             color_discrete_map={"Baixa":"#313695", "Média":"#fee090", "Alta":"#a50026"},
                             title="Zoneamento Triade (Coolwarm Palette)")
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("📄 Gerar Relatório PDF Final"):
                pdf_bytes = gerar_relatorio_completo(df_final, params)
                st.download_button("⬇️ Baixar PDF", pdf_bytes, "Relatorio_Triade_v43.pdf", "application/pdf")

def gerar_relatorio_completo(df, params):
    pdf = TriadePDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "Argumentos Tecnicos da Recomendacao", ln=True)
    pdf.set_font("helvetica", "", 12)
    pdf.multi_cell(0, 7, "A metodologia Triade foca no rooting profundo (enraizamento) "
                         "atraves da gessagem estrategica e reducao da toxicidade de aluminio. "
                         "O equilibrio Ca/Mg na CTC assegura a estabilidade quimica do solo.")
    pdf.ln(5)
    # Tabela simplificada no PDF
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(30, 10, "Zona", 1); pdf.cell(40, 10, "Gesso (kg/ha)", 1); pdf.cell(40, 10, "Calcario (t/ha)", 1); pdf.ln()
    pdf.set_font("helvetica", "", 10)
    for zona in ["Alta", "Média", "Baixa"]:
        val = df[df['ZONA_MANEJO'] == zona].mean(numeric_only=True)
        pdf.cell(30, 10, zona, 1)
        pdf.cell(40, 10, f"{val['REC_GESSO']:.0f}", 1)
        pdf.cell(40, 10, f"{val['REC_CALCARIO']:.1f}", 1)
        pdf.ln()
    return pdf.output()

# --- EXECUÇÃO ---
menu, params = configurar_interface()
if menu == "🏠 Home":
    st.markdown("<h2 class='section-header'>Dashboard de Controle Triade</h2>", unsafe_allow_html=True)
    st.info("Plataforma v43 pronta para processamento de Gilson Berneck.")
else:
    pag_produtores(params)
