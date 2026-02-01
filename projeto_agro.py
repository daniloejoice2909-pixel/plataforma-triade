import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
import base64
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica", layout="wide", page_icon="🌱")

# --- CSS CUSTOMIZADO (PADRÃO PREMIUM) ---
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
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 15px; margin-top: 25px; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSES E FUNÇÕES AUXILIARES (PDF E DOWNLOADS) ---
class TriadePDF(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 40)
        except: pass
        self.ln(20)

def gerar_pdf_relatorio(df_res, produtor, area_total, params_fin):
    pdf = TriadePDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"Relatório Técnico: {produtor}", ln=True)
    pdf.ln(10)
    # Tabela de Resultados
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(20, 8, "ID", 1); pdf.cell(40, 8, "Calcário (t/ha)", 1); pdf.cell(40, 8, "P2O5 (kg/ha)", 1); pdf.cell(40, 8, "Custo (R$/ha)", 1); pdf.ln()
    pdf.set_font("helvetica", "", 10)
    for _, row in df_res.iterrows():
        pdf.cell(20, 8, str(row['ID']), 1); pdf.cell(40, 8, str(row['REC_CALCARIO']), 1); pdf.cell(40, 8, str(row['REC_P_VRT']), 1); pdf.cell(40, 8, f"{row['CUSTO_HA']:.2f}", 1); pdf.ln()
    return pdf.output()

def converter_csv_download(df):
    return df.to_csv(index=False).encode('utf-8')

# --- MOTOR AGRONÔMICO (NÃO ALTERADO) ---
def motor_calculo_vrt_v43(df, params):
    p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg = params["calagem"]
    niveis_p, f_text_config, p_exp, p_teor_adubo = params["fosforo"]
    preco_calc, preco_fosf, prod_alvo = params["financeiro"]
    
    df['NC_CA'] = ((target_ca - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100)
    df['NC_MG'] = ((target_mg - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100)
    df['DOSE_CAO'] = (df['NC_CA'] * f_ca * 100) / (p_cao * p_prnt)
    df['DOSE_MGO'] = (df['NC_MG'] * f_mg * 100) / (p_mgo * p_prnt)
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CAO'], df['DOSE_MGO']) + calc_extra).round(2)

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
    df['CUSTO_HA'] = (df['REC_CALCARIO'] * preco_calc) + (df['REC_P_VRT'] * preco_fosf / 1000)
    df['SAFE_ZONE_MSG'] = df['REC_CALCARIO'].apply(lambda x: "⚠️ Dose Alta: Parcelar" if x > 6 else "✅ Segura")
    return df

# --- INTERFACE LATERAL ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    menu = st.sidebar.radio("Navegação Principal", ["🏠 Home / Onboarding", "👥 Módulo Produtores", "📊 Market Intelligence"])
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
        f_text = [st.number_input("Fator >60%", 10.0), st.number_input("Fator 36-60%", 8.0), st.number_input("Fator 15-36%", 4.0), st.number_input("Fator <15%", 2.0)]
        p_teor_adubo = st.number_input("% P2O5 no Adubo", 21.0)
    with st.sidebar.expander("💰 Balanço Financeiro", expanded=True):
        p_calc = st.number_input("Preço Calcário (R$/t)", 185.0)
        p_fosf = st.number_input("Preço Adubo (R$/t)", 3400.0)
        prod_alvo = st.number_input("Produtividade Alvo (sc/ha)", 85.0)
    return menu, {"calagem": (p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, 560, 400), "fosforo": (niveis_p, f_text, 0.8, p_teor_adubo), "financeiro": (p_calc, p_fosf, prod_alvo)}

# --- PÁGINA HOME / ONBOARDING ---
def pag_home():
    st.markdown("<h2 class='section-header'>Dashboard de Controle Tríade</h2>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("<div class='kpi-card'><div class='kpi-label'>Hectares Totais</div><div class='kpi-value'>17.000</div></div>", unsafe_allow_html=True)
    c2.markdown("<div class='kpi-card'><div class='kpi-label'>Fins de Ciclo</div><div class='kpi-value'>04</div></div>", unsafe_allow_html=True)
    c3.markdown("<div class='kpi-card'><div class='kpi-label'>Alertas NDVI</div><div class='kpi-value' style='color:#e74c3c'>02</div></div>", unsafe_allow_html=True)
    c4.markdown("<div class='kpi-card'><div class='kpi-label'>Novos Contornos</div><div class='kpi-value'>01</div></div>", unsafe_allow_html=True)

    st.markdown("<h3 class='section-header'>📂 Onboarding de Dados e Áreas</h3>", unsafe_allow_html=True)
    col_dl, col_map = st.columns([1, 1.5])

    with col_dl:
        st.write("#### 1. Preparação de Dados")
        st.info("Baixe os modelos para preencher os dados de solo de forma compatível com o sistema.")
        
        # Gerar planilha modelo
        df_modelo = pd.DataFrame(columns=['ID', 'CA_PERC', 'MG_PERC', 'CTC', 'PREM', 'P', 'ARGILA', 'X', 'Y'])
        st.download_button(label="⬇️ Baixar Modelo de Planilha de Solo", data=converter_csv_download(df_modelo), file_name="modelo_solo_triade.csv", mime="text/csv")
        
        st.divider()
        st.write("#### 2. Arquivos de Contorno")
        st.write("Se você já possui o arquivo `.shp` ou `.geojson`, baixe o padrão Tríade para conferência.")
        st.button("⬇️ Baixar Padrão de Contorno (.json)")
        
        st.divider()
        st.write("#### 3. Upload Rápido")
        st.file_uploader("Subir Novo Contorno (SHP/KML/ZIP)", type=['zip', 'kml', 'geojson'])

    with col_map:
        st.write("#### 📍 Definição Espacial (Mapa de Contorno)")
        st.caption("Localize a fazenda e desenhe o talhão manualmente usando a ferramenta de polígono à esquerda.")
        
        # Integração Folium com Desenho
        m = folium.Map(location=[-18.42, -47.41], zoom_start=13, tiles="CartoDB positron")
        Draw(
            export=True,
            position='topleft',
            draw_options={'polyline': False, 'rectangle': True, 'circle': False, 'circlemarker': False, 'marker': False},
            edit_options={'edit': True}
        ).add_to(m)
        
        st_folium(m, width=800, height=450)
        st.success("Dica: Após desenhar, o sistema processará automaticamente as coordenadas.")

# --- PÁGINA PRODUTORES ---
def pag_produtores(params):
    st.subheader("Foco: Gilson Berneck")
    tab1, tab2, tab3 = st.tabs(["🗺️ Planejamento VRT", "📊 Visão 3D & Solo", "📄 Exportar PDF"])
    df_gilson = pd.DataFrame({
        'ID': range(1, 6), 'CA_PERC': [42,50,35,48,52], 'MG_PERC': [11,14,9,13,15],
        'CTC': [12.5, 11, 14, 13, 10.5], 'PREM': [5, 12, 45, 22, 9], 'P': [4, 10, 3, 7, 5],
        'ARGILA': [620, 410, 130, 590, 380], 'X': [1, 2, 3, 2, 1], 'Y': [1, 1, 2, 3, 3]
    })
    df_res = motor_calculo_vrt_v43(df_gilson, params)
    with tab1: st.dataframe(df_res[['ID', 'REC_CALCARIO', 'REC_P_VRT', 'CUSTO_HA', 'SAFE_ZONE_MSG']])
    with tab2:
        fig = go.Figure(data=[go.Mesh3d(x=df_res['X'], y=df_res['Y'], z=df_res['P'], color='royalblue', opacity=0.5)])
        fig.add_scatter3d(x=df_res['X'], y=df_res['Y'], z=df_res['P'], mode='markers', marker=dict(size=10, color=df_res['P'], colorscale='coolwarm'))
        st.plotly_chart(fig, use_container_width=True)
    with tab3:
        if st.button("Gerar PDF v43 (Padronizado)"):
            pdf_bytes = gerar_pdf_relatorio(df_res, "Gilson Berneck", 17000, params["financeiro"])
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Relatorio_Berneck_Triade.pdf">Download PDF</a>'
            st.markdown(href, unsafe_allow_html=True)

# --- EXECUÇÃO ---
menu, params = configurar_interface()
if menu == "🏠 Home / Onboarding": pag_home()
elif menu == "👥 Módulo Produtores": pag_produtores(params)
