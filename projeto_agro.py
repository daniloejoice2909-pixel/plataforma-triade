import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica", layout="wide", page_icon="🌱")

# --- CSS CUSTOMIZADO (UI/UX PREMIUM) ---
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
    .safe-zone-warning { color: #e67e22; font-weight: bold; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSE DE EXPORTAÇÃO PDF (PADRÃO TRÍADE) ---
class ReportPDF(FPDF):
    def header(self):
        # Logo no topo (ajustado conforme solicitado)
        try: self.image("LogoTriadeagro.png.png", 10, 8, 33)
        except: pass
        self.set_font("helvetica", "B", 15)
        self.cell(80)
        self.cell(30, 10, "Relatório Técnico de Recomendação VRT", 0, 0, "C")
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()} - Tríade Agro Estratégica", 0, 0, "C")

def gerar_pdf(df, produtor, area):
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=20) # Margem 2cm
    pdf.add_page()
    pdf.set_font("helvetica", "", 12)
    
    pdf.cell(0, 10, f"Produtor: {produtor}", ln=True)
    pdf.cell(0, 10, f"Área Total: {area} ha", ln=True)
    pdf.ln(10)
    
    # Tabela de Recomendações
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(30, 10, "Zona/ID", 1)
    pdf.cell(80, 10, "Rec. Calcário (t/ha)", 1)
    pdf.cell(80, 10, "Rec. Fósforo (kg/ha)", 1)
    pdf.ln()
    
    pdf.set_font("helvetica", "", 10)
    for i, row in df.iterrows():
        pdf.cell(30, 10, str(row['ID']), 1)
        pdf.cell(80, 10, str(row['REC_CALCARIO']), 1)
        pdf.cell(80, 10, str(row['REC_P_VRT']), 1)
        pdf.ln()
    
    return pdf.output()

# --- MOTOR AGRONÔMICO E FINANCEIRO ---
def motor_calculo_vrt(df, params):
    p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg = params["calagem"]
    niveis_p, f_text_config, p_exp, p_teor_adubo = params["fosforo"]
    p_calcario, p_fosforo, prod_esperada = params["financeiro"]
    
    # 1. CALAGEM (Regra Máximo CaO/MgO)
    df['NC_CA'] = ((target_ca - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100)
    df['NC_MG'] = ((target_mg - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100)
    df['DOSE_CAO'] = (df['NC_CA'] * f_ca * 100) / (p_cao * p_prnt)
    df['DOSE_MGO'] = (df['NC_MG'] * f_mg * 100) / (p_mgo * p_prnt)
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CAO'], df['DOSE_MGO']) + calc_extra).round(2)

    # 2. FÓSFORO (P-rem)
    def buscar_nc_p(prem):
        for limite, valor in zip([4,10,19,30,45,60], niveis_p.values()):
            if prem <= limite: return valor
        return list(niveis_p.values())[-1]

    def definir_fator_textura(argila):
        if argila > 600: return f_text_config[0]
        elif argila > 360: return f_text_config[1]
        elif argila > 150: return f_text_config[2]
        return f_text_config[3]

    df['NC_P'] = df['PREM'].apply(buscar_nc_p)
    df['F_TEXT'] = df['ARGILA'].apply(definir_fator_textura)
    df['REC_P_VRT'] = (((df['NC_P'] - df['P']).clip(lower=0) * df['F_TEXT']) * 100 / p_teor_adubo).round(2)
    
    # 3. FINANCEIRO & SAFE ZONE
    df['CUSTO_HA'] = (df['REC_CALCARIO'] * p_calcario) + (df['REC_P_VRT'] * p_fosforo / 1000)
    df['ALERTA_TECNICO'] = df['REC_CALCARIO'].apply(lambda x: "⚠️ Dose Alta! Parcelar?" if x > 5 else "✅ OK")
    
    return df

# --- INTERFACE LATERAL ---
def sidebar_triade():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    menu = st.sidebar.radio("Navegação", ["🏠 Home", "👥 Produtores"])
    
    st.sidebar.header("⚙️ Parâmetros Técnicos")
    with st.sidebar.expander("🪨 Calagem & Fósforo", expanded=False):
        # Mantendo seus inputs originais conforme pedido
        p_prnt = st.number_input("PRNT Calcário (%)", 80.0)
        p_cao = st.number_input("Teor CaO (%)", 36.0)
        p_mgo = st.number_input("Teor MgO (%)", 9.0)
        target_ca = st.number_input("Alvo Ca (%)", 60.0)
        target_mg = st.number_input("Alvo Mg (%)", 18.0)
        calc_extra = st.number_input("Adicional (t/ha)", 0.0)
        
        st.divider()
        niveis_p = {"0-4": 8.0, "4-10": 10.0, "10-19": 12.0, "19-30": 15.0, "30-45": 18.0, "45-60": 22.0}
        for k in niveis_p: niveis_p[k] = st.number_input(f"P-rem {k}", niveis_p[k])
        
        f_text = [st.number_input("Fator Argila >60%", 10.0), st.number_input("Fator 36-60%", 8.0), 
                  st.number_input("Fator 15-36%", 4.0), st.number_input("Fator <15%", 2.0)]
        p_teor_adubo = st.number_input("% P2O5 no Adubo", 21.0)

    with st.sidebar.expander("💰 Mercado & ROI", expanded=True):
        p_calcario = st.number_input("Preço Calcário (R$/ton)", 180.0)
        p_fosforo = st.number_input("Preço Adubo Fosfatado (R$/ton)", 3200.0)
        prod_esperada = st.number_input("Produtividade Alvo (sc/ha)", 80.0)

    params = {
        "calagem": (p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, 560, 400),
        "fosforo": (niveis_p, f_text, 0.8, p_teor_adubo),
        "financeiro": (p_calcario, p_fosforo, prod_esperada)
    }
    return menu, params

# --- PÁGINAS ---
def pag_home():
    st.markdown("<h2 style='color: #1e3d59;'>Dashboard de Gestão Estratégica</h2>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("<div class='kpi-card'><div class='kpi-label'>Hectares</div><div class='kpi-value'>17.000</div></div>", unsafe_allow_html=True)
    c2.markdown("<div class='kpi-card'><div class='kpi-label'>Clientes</div><div class='kpi-value'>01</div></div>", unsafe_allow_html=True)
    c3.markdown("<div class='kpi-card'><div class='kpi-label'>Custo Médio/ha</div><div class='kpi-value'>R$ 420</div></div>", unsafe_allow_html=True)
    c4.markdown("<div class='kpi-card'><div class='kpi-label'>ROI Estimado</div><div class='kpi-value' style='color:#27ae60'>18%</div></div>", unsafe_allow_html=True)

def pag_produtores(params):
    st.title("Gestão: Gilson Berneck")
    t1, t2, t3 = st.tabs(["🗺️ Planejamento VRT", "📊 Análise 3D", "📄 Exportar PDF"])
    
    # Simulação de Dados
    df_mock = pd.DataFrame({
        'ID': range(1, 6), 'CA_PERC': [40,55,30,48,50], 'MG_PERC': [12,18,8,14,15],
        'CTC': [12,11,14,13,10], 'PREM': [5,25,42,12,8], 'P': [3,8,2,6,4],
        'ARGILA': [650,420,110,580,400], 'LAT': [-18.1, -18.2, -18.3, -18.4, -18.5], 'LON': [-47.1, -47.2, -47.3, -47.4, -47.5]
    })
    df_res = motor_calculo_vrt(df_mock, params)

    with t1:
        st.subheader("Mapa de Recomendação e Safe Zone")
        st.dataframe(df_res[['ID', 'REC_CALCARIO', 'REC_P_VRT', 'CUSTO_HA', 'ALERTA_TECNICO']])
        
    with t2:
        st.subheader("Visualização 3D de Fertilidade")
        fig = go.Figure(data=[go.Scatter3d(
            x=df_res['LAT'], y=df_res['LON'], z=df_res['P'],
            mode='markers', marker=dict(size=10, color=df_res['P'], colorscale='Viridis', opacity=0.8)
        )])
        fig.update_layout(title="Variabilidade de Fósforo no Relevo", scene=dict(zaxis_title='P (mg/dm³)'))
        st.plotly_chart(fig, use_container_width=True)
        
    with t3:
        st.subheader("Gerar Relatório v43")
        if st.button("🚀 Gerar PDF para Gilson Berneck"):
            pdf_data = gerar_pdf(df_res, "Gilson Berneck", 17000)
            b64 = base64.b64encode(pdf_data).decode('utf-8')
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="Relatorio_Triade_Berneck.pdf">Clique aqui para baixar o PDF</a>'
            st.markdown(href, unsafe_allow_html=True)

# EXECUÇÃO
menu, params = sidebar_triade()
if menu == "🏠 Home": pag_home()
else: pag_produtores(params)
