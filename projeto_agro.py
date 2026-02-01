import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica", layout="wide", page_icon="🌱")

# --- CSS CUSTOMIZADO PARA PADRÃO PREMIUM ---
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
    .safe-zone-alert { color: #d35400; font-weight: bold; background-color: #fff3e0; padding: 5px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE EXPORTAÇÃO PDF (A4, 2cm MARGENS) ---
class TriadePDF(FPDF):
    def header(self):
        try:
            self.image("LogoTriadeagro.png.png", 10, 8, 40)
        except:
            self.set_font("helvetica", "B", 12)
            self.text(10, 15, "TRÍADE AGRO ESTRATÉGICA")
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Relatório Gerado em 2026 - Página {self.page_no()}", 0, 0, "C")

def gerar_pdf_relatorio(df_res, produtor, area_total, params_fin):
    pdf = TriadePDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20) # Margens de 2cm
    pdf.add_page()
    
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"Relatório Técnico: {produtor}", ln=True)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 10, f"Área Monitorada: {area_total} ha", ln=True)
    pdf.ln(5)

    # Argumentos Técnicos
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "Metodologia e Vantagens VRT", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 5, "A recomendação por Taxa Variável (VRT) otimiza a aplicação de insumos "
                         "baseada na real necessidade de cada zona de manejo. Comparado ao método convencional, "
                         "esta abordagem reduz desperdícios em áreas saturadas e evita sub-dosagem em áreas críticas.")
    pdf.ln(5)

    # Tabela de Resultados
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(20, 8, "ID", 1)
    pdf.cell(40, 8, "Calcário (t/ha)", 1)
    pdf.cell(40, 8, "P2O5 (kg/ha)", 1)
    pdf.cell(40, 8, "Custo (R$/ha)", 1)
    pdf.ln()

    pdf.set_font("helvetica", "", 10)
    for i, row in df_res.iterrows():
        pdf.cell(20, 8, str(row['ID']), 1)
        pdf.cell(40, 8, str(row['REC_CALCARIO']), 1)
        pdf.cell(40, 8, str(row['REC_P_VRT']), 1)
        pdf.cell(40, 8, f"R$ {row['CUSTO_HA']:.2f}", 1)
        pdf.ln()

    return pdf.output()

# --- FUNÇÃO DE CÁLCULO (MOTOR AGRONÔMICO + FINANCEIRO + SAFE ZONE) ---
def motor_calculo_vrt_v43(df, params):
    p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg = params["calagem"]
    niveis_p, f_text_config, p_exp, p_teor_adubo = params["fosforo"]
    preco_calc, preco_fosf, prod_alvo = params["financeiro"]
    
    # 1. CALAGEM
    df['NC_CA'] = ((target_ca - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100)
    df['NC_MG'] = ((target_mg - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100)
    df['DOSE_CAO'] = (df['NC_CA'] * f_ca * 100) / (p_cao * p_prnt)
    df['DOSE_MGO'] = (df['NC_MG'] * f_mg * 100) / (p_mgo * p_prnt)
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CAO'], df['DOSE_MGO']) + calc_extra).round(2)

    # 2. FÓSFORO (P-rem)
    def buscar_nc_p(prem):
        if prem <= 4: return niveis_p["0-4"]
        elif prem <= 10: return niveis_p["4-10"]
        elif prem <= 19: return niveis_p["10-19"]
        elif prem <= 30: return niveis_p["19-30"]
        elif prem <= 45: return niveis_p["30-45"]
        else: return niveis_p["45-60"]

    def definir_fator_textura(argila):
        if argila > 600: return f_text_config[0]
        elif argila > 360: return f_text_config[1]
        elif argila > 150: return f_text_config[2]
        else: return f_text_config[3]

    df['NC_P'] = df['PREM'].apply(buscar_nc_p)
    df['F_TEXT'] = df['ARGILA'].apply(definir_fator_textura)
    df['REC_P_VRT'] = (((df['NC_P'] - df['P']).clip(lower=0) * df['F_TEXT']) * 100 / p_teor_adubo).round(2)
    
    # 3. FINANCEIRO & SAFE ZONE (Sugestões Senior)
    df['CUSTO_HA'] = (df['REC_CALCARIO'] * preco_calc) + (df['REC_P_VRT'] * preco_fosf / 1000)
    df['SAFE_ZONE_MSG'] = df['REC_CALCARIO'].apply(lambda x: "⚠️ Dose Alta: Parcelar aplicação" if x > 6 else "✅ Dose Segura")
    
    return df

# --- INTERFACE LATERAL ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    menu = st.sidebar.radio("Navegação", ["🏠 Home", "👥 Produtores", "📊 Market Intelligence"])
    
    st.sidebar.header("⚙️ Parâmetros Técnicos")
    with st.sidebar.expander("🪨 Calagem & Fósforo", expanded=False):
        p_prnt = st.number_input("PRNT (%)", 80.0)
        p_cao = st.number_input("Teor CaO (%)", 36.0)
        p_mgo = st.number_input("Teor MgO (%)", 9.0)
        target_ca = st.number_input("Alvo Ca (%)", 60.0)
        target_mg = st.number_input("Alvo Mg (%)", 18.0)
        calc_extra = st.number_input("Adicional (t/ha)", 0.0)
        
        st.divider()
        niveis_p = {"0-4": 8.0, "4-10": 10.0, "10-19": 12.0, "19-30": 15.0, "30-45": 18.0, "45-60": 22.0}
        f_text = [st.number_input("Fator >60%", 10.0), st.number_input("Fator 36-60%", 8.0), 
                  st.number_input("Fator 15-36%", 4.0), st.number_input("Fator <15%", 2.0)]
        p_teor_adubo = st.number_input("% P2O5 no Adubo", 21.0)

    with st.sidebar.expander("💰 Balanço Financeiro", expanded=True):
        p_calc = st.number_input("Preço Calcário (R$/t)", 185.0)
        p_fosf = st.number_input("Preço Adubo (R$/t)", 3400.0)
        prod_alvo = st.number_input("Produtividade Alvo (sc/ha)", 85.0)

    params = {
        "calagem": (p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, 560, 400),
        "fosforo": (niveis_p, f_text, 0.8, p_teor_adubo),
        "financeiro": (p_calc, p_fosf, prod_alvo)
    }
    return menu, params

# --- PÁGINAS ---
def pag_home():
    st.markdown("<h2 style='color: #1e3d59;'>Painel Estratégico Tríade</h2>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("<div class='kpi-card'><div class='kpi-label'>Hectares</div><div class='kpi-value'>17.000</div></div>", unsafe_allow_html=True)
    c2.markdown("<div class='kpi-card'><div class='kpi-label'>Cliente Ativo</div><div class='kpi-value'>G. Berneck</div></div>", unsafe_allow_html=True)
    c3.markdown("<div class='kpi-card'><div class='kpi-label'>Investimento/ha</div><div class='kpi-value'>R$ 485,20</div></div>", unsafe_allow_html=True)
    c4.markdown("<div class='kpi-card'><div class='kpi-label'>ROI Est.</div><div class='kpi-value' style='color:#27ae60'>22%</div></div>", unsafe_allow_html=True)

def pag_produtores(params):
    st.subheader("Foco: Gilson Berneck")
    tab1, tab2, tab3 = st.tabs(["🗺️ Planejamento VRT", "📊 Visão 3D & Solo", "📄 Exportar PDF"])
    
    # Mock de Dados para o Gilson
    df_gilson = pd.DataFrame({
        'ID': range(1, 6), 'CA_PERC': [42,50,35,48,52], 'MG_PERC': [11,14,9,13,15],
        'CTC': [12.5, 11, 14, 13, 10.5], 'PREM': [5, 12, 45, 22, 9], 'P': [4, 10, 3, 7, 5],
        'ARGILA': [620, 410, 130, 590, 380], 'X': [1, 2, 3, 2, 1], 'Y': [1, 1, 2, 3, 3]
    })
    
    df_res = motor_calculo_vrt_v43(df_gilson, params)

    with tab1:
        st.dataframe(df_res[['ID', 'REC_CALCARIO', 'REC_P_VRT', 'CUSTO_HA', 'SAFE_ZONE_MSG']])
    
    with tab2:
        st.write("### Variabilidade Espacial de Fósforo (Visualização 3D)")
        fig = go.Figure(data=[go.Mesh3d(x=df_res['X'], y=df_res['Y'], z=df_res['P'], color='royalblue', opacity=0.5)])
        fig.add_scatter3d(x=df_res['X'], y=df_res['Y'], z=df_res['P'], mode='markers', marker=dict(size=10, color=df_res['P'], colorscale='coolwarm'))
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        if st.button("Gerar PDF v43 (Padronizado)"):
            pdf_bytes = gerar_pdf_relatorio(df_res, "Gilson Berneck", 17000, params["financeiro"])
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Relatorio_Berneck_Triade.pdf">Clique aqui para baixar o PDF</a>'
            st.markdown(href, unsafe_allow_html=True)

# EXECUÇÃO
menu, params = configurar_interface()
if menu == "🏠 Home": pag_home()
elif menu == "👥 Produtores": pag_produtores(params)
