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

# --- CSS CUSTOMIZADO (UX PREMIUM) ---
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
    .legend-box { padding: 10px; border-radius: 5px; font-weight: bold; color: white; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSE PDF PROFISSIONAL ---
class TriadePDF(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 40)
        except: pass
        self.set_font("helvetica", "B", 12)
        self.cell(0, 10, "Relatório Técnico de Manejo Estratégico", ln=True, align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Tríade Agro Estratégica v43 - Página {self.page_no()}", 0, 0, "C")

# --- MOTOR DE CÁLCULO (AGRONOMIA & ÁLGEBRA) ---
def motor_calculo_v43(df, params):
    # Unpack Params
    v_alvo = params['v_alvo']
    k_alvo = params['k_alvo']
    niveis_p = params['niveis_p']
    f_text = params['f_text']
    
    # 1. Gessagem (Argila em g/kg * 15)
    df['REC_GESSO'] = (df['ARGILA'] * 15).round(2)
    
    # 2. Calagem (Saturação por Bases V%)
    # NC (t/ha) = (V2 - V1) * CTC / PRNT
    df['V1'] = (df['SB'] / df['CTC']) * 100
    df['REC_CALCARIO'] = (((v_alvo - df['V1']).clip(lower=0) * df['CTC']) / 85).round(2) # PRNT padrão 85
    
    # 3. Fósforo (P-rem 6 classes)
    def calc_p(row):
        prem = row['PREM']
        if prem <= 4: nc = niveis_p["0-4"]
        elif prem <= 10: nc = niveis_p["4-10"]
        elif prem <= 19: nc = niveis_p["10-19"]
        elif prem <= 30: nc = niveis_p["19-30"]
        elif prem <= 45: nc = niveis_p["30-45"]
        else: nc = niveis_p["45-60"]
        return ((nc - row['P']).clip(lower=0) * 10).round(2) # Exemplo de fator 10
    
    df['REC_P2O5'] = df.apply(calc_p, axis=1)
    
    # 4. Potássio (Reposição por CTC e Alvo)
    df['REC_K2O'] = ((k_alvo - df['K']).clip(lower=0) * 2.4).round(2)

    # 5. Álgebra de Mapas: Zonas de Produtividade (3 Zonas)
    # 50% NDVI + 25% CTC + 25% Solo
    df['POTENCIAL_SCORE'] = (df['NDVI_HIST'] * 0.5) + (df['CTC_NORM'] * 0.25) + (df['BRIGHTNESS'] * 0.25)
    df['ZONA_MANEJO'] = pd.qcut(df['POTENCIAL_SCORE'], 3, labels=["Baixo", "Médio", "Alto"])
    
    return df

# --- INTERFACE ---
def pag_produtores(params):
    st.title("Gestão de Produtores")
    produtor = st.selectbox("Selecione o Cliente:", ["Gilson Berneck"])
    
    # Estrutura de Abas v43
    tab_safra, tab_config = st.tabs(["🌾 Safra 2025/26", "⚙️ Configurar Área"])
    
    with tab_config:
        st.subheader("Delimitação de Área")
        col_shp, col_map = st.columns([1, 2])
        with col_shp:
            st.file_uploader("Upload SHP/KML", type=['shp', 'kml', 'zip'])
            st.info("Ou utilize a ferramenta de desenho ao lado.")
        with col_map:
            m = folium.Map(location=[-18.42, -47.41], zoom_start=14)
            Draw(export=True).add_to(m)
            st_folium(m, width=700, height=400)

    with tab_safra:
        # Hierarquia de Subpastas
        exp_solo = st.expander("🧪 Análises de Solo", expanded=False)
        exp_foliar = st.expander("🍃 Análises Foliares e DRIS", expanded=False)
        exp_fert = st.expander("🗺️ Mapas de Fertilidade VRT", expanded=False)
        exp_reco = st.expander("🚜 Mapas de Recomendações (v43)", expanded=True)
        exp_sat = st.expander("🛰️ Imagens de Satélite", expanded=False)
        exp_zonas = st.expander("🎯 Zonas de Produtividade (Álgebra)", expanded=True)

        # Mock de dados para o motor
        data = {
            'ID': range(1, 7),
            'ARGILA': [450, 200, 600, 350, 480, 150], # g/kg
            'SB': [2.1, 1.5, 4.0, 2.8, 3.1, 1.2],
            'CTC': [8.5, 6.0, 12.0, 9.5, 10.0, 5.5],
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

        with exp_zonas:
            st.write("### Álgebra de Mapas (50% NDVI | 25% CTC | 25% Brilho)")
            fig_zonas = px.scatter(df, x='LON', y='LAT', color='ZONA_MANEJO', 
                                   size='POTENCIAL_SCORE',
                                   color_discrete_map={"Baixo":"#313695", "Médio":"#fee090", "Alto":"#a50026"},
                                   title="Zonas de Manejo (Coolwarm Palette)")
            st.plotly_chart(fig_zonas, use_container_width=True)

        with exp_reco:
            col_a, col_b = st.columns(2)
            col_a.metric("Dose Média Gesso", f"{df['REC_GESSO'].mean():.0f} kg/ha")
            col_b.metric("Calcário Médio", f"{df['REC_CALCARIO'].mean():.1f} t/ha")
            st.dataframe(df[['ID', 'ZONA_MANEJO', 'REC_GESSO', 'REC_CALCARIO', 'REC_P2O5', 'REC_K2O']])
            
            if st.button("📄 Gerar Relatório PDF Profissional"):
                gerar_pdf_v43(df)

# --- GERADOR DE PDF ---
def gerar_pdf_v43(df):
    pdf = TriadePDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "Relatório de Recomendação Estratégica", ln=True)
    
    pdf.set_font("helvetica", "", 12)
    pdf.multi_cell(0, 7, "Este relatório contempla o rooting profundo (enraizamento) através da gessagem "
                         "e a redução da toxicidade de alumínio. A metodologia V% assegura o equilíbrio de bases "
                         "essencial para alta produtividade.")
    
    # Tabela simplificada
    pdf.ln(5)
    pdf.set_fill_color(30, 61, 89)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(30, 10, "Zona", 1, 0, 'C', True)
    pdf.cell(40, 10, "Gesso (kg/ha)", 1, 0, 'C', True)
    pdf.cell(40, 10, "Calcário (t/ha)", 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    for zona in ["Alto", "Médio", "Baixo"]:
        val = df[df['ZONA_MANEJO'] == zona].mean(numeric_only=True)
        pdf.cell(30, 10, zona, 1)
        pdf.cell(40, 10, f"{val['REC_GESSO']:.0f}", 1)
        pdf.cell(40, 10, f"{val['REC_CALCARIO']:.1f}", 1)
        pdf.ln()

    html = f'<a href="data:application/pdf;base64,{base64.b64encode(pdf.output()).decode()}" download="Relatorio_v43.pdf">Baixar PDF</a>'
    st.markdown(html, unsafe_allow_html=True)

# --- APP RUN ---
params = {
    'v_alvo': 70, 
    'k_alvo': 0.35,
    'niveis_p': {"0-4": 9.0, "4-10": 10.5, "10-19": 12.5, "19-30": 15.0, "30-45": 17.5, "45-60": 19.3},
    'f_text': 10
}

menu = st.sidebar.radio("Navegação", ["🏠 Home", "👥 Produtores"])
if menu == "🏠 Home":
    st.header("Painel de Controle Tríade")
else:
    pag_produtores(params)
