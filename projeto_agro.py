import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
from fpdf import FPDF
import json
import io

# --- INICIALIZAÇÃO DO BANCO DE DADOS PERSISTENTE ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- ESTILIZAÇÃO CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card {
        background-color: #ffffff; padding: 12px; border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); text-align: center;
        border-top: 4px solid #1e3d59; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 6px solid #1e3d59; padding-left: 12px; margin: 15px 0; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO TRÍADE V43 ---
def motor_calculo_v43(df, params):
    mapeamento = {
        'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 
        'prem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 'k%': 'K%', 'ca': 'Ca', 'mg': 'Mg', 'k': 'K'
    }
    df = df.rename(columns=lambda x: mapeamento.get(x.lower().strip(), x))
    cols_foc = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'K', 'Ca', 'Mg']
    for col in cols_foc:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # 1. Calagem Atômica
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    df['REC_CALCARIO'] = (np.maximum((df['NC_CA_CMOL']*5600000/(c_p["cao"]*c_p["prnt"])), 
                                     (df['NC_MG_CMOL']*4000000/(c_p["mgo"]*c_p["prnt"]))) + c_p["reserva"]).round(2)
    df['RATIO_CA_MG'] = (df['Ca%'] + (df['NC_CA_CMOL']/df['CTC']*100)) / (df['Mg%'] + (df['NC_MG_CMOL']/df['CTC']*100 + 0.001))

    # 2. Fósforo (NC P-rem + Crédito de Solo)
    def calc_p(row):
        prem = row['prem']
        nc = p_p["nc_0_4"] if prem <= 4 else p_p["nc_4_10"] if prem <= 10 else p_p["nc_10_19"] if prem <= 19 else p_p["nc_19_30"] if prem <= 30 else p_p["nc_30_45"] if prem <= 45 else p_p["nc_45_60"]
        arg = row['Argila']
        f_arg = p_p["f_muito_arg"] if arg > 60 else p_p["f_argiloso"] if arg > 35 else p_p["f_medio"] if arg > 15 else p_p["f_arenoso"]
        total_p2o5 = ((nc - row['P mehl']) * f_arg) + (prod_esp * p_p["f_exp"])
        return (max(total_p2o5, 0) * 100) / p_p["teor_adubo"]
    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 3. Potássio e Gesso (Argila % * 10)
    df['REC_K_ADUBO'] = (((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941) + (prod_esp * k_p["f_exp"])) * 100 / k_p["teor_adubo"]
    df['REC_GESSO'] = (df['Argila'] * 10 * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    # Financeiro
    df['C_CALC'] = (df['REC_CALCARIO']/1000) * c_p["preco"]
    df['C_P'] = (df['REC_P_ADUBO']/1000) * p_p["preco"]
    df['C_K'] = (df['REC_K_ADUBO']/1000) * k_p["preco"]
    df['C_GESSO'] = (df['REC_GESSO']/1000) * g_p["preco"]
    df['C_TOTAL'] = df['C_CALC'] + df['C_P'] + df['C_K'] + df['C_GESSO']
    return df

# --- MOTOR DE KRIGAGEM ---
def plot_kriging(df, col, title, geo_json=None):
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    x, y, z = df['Longitude'].values, df['Latitude'].values, df[col].values
    xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100); xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear', smooth=0.1); zi = rbf(xi, yi)
    if geo_json:
        try:
            poly = shape(geo_json['features'][0]['geometry'])
            for i in range(len(xi)):
                for j in range(len(yi)):
                    if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan
        except: pass
    fig = go.Figure(data=go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100),
                                    colorscale='RdYlBu_r', contours=dict(showlines=False), line_width=0))
    fig.update_layout(title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=350,
                      xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='rgba(0,0,0,0)')
    stats = f"Mín: {np.nanmin(zi):.2f} | Máx: {np.nanmax(zi):.2f} | Méd: {np.nanmean(zi):.2f}"
    return fig, stats

# --- CLASSE PDF PROFISSIONAL TRÍADE ---
class PDF_Triade(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 33)
        except: pass
        self.set_font('Arial', 'B', 12)
        self.cell(80)
        self.cell(30, 10, 'Relatório de Recomendação Estratégica VRT', 0, 0, 'C')
        self.ln(20)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Tríade Agro Estratégica v43 - Página {self.page_no()}', 0, 0, 'C')

# --- INTERFACE LATERAL ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    p_names = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_p = st.sidebar.selectbox("Produtor", p_names)
    if sel_p == "+ Novo Produtor":
        sel_p = st.sidebar.text_input("Nome Cliente")
        if sel_p and sel_p not in st.session_state['db']: st.session_state['db'][sel_p] = {}
    
    faz_names = list(st.session_state['db'].get(sel_p, {}).keys()) + ["+ Nova Fazenda"]
    sel_f = st.sidebar.selectbox("Fazenda", faz_names)
    if sel_f == "+ Nova Fazenda":
        sel_f = st.sidebar.text_input("Nome Fazenda")
        if sel_f and sel_f not in st.session_state['db'][sel_p]: st.session_state['db'][sel_p][sel_f] = {}
    
    tal_names = list(st.session_state['db'].get(sel_p, {}).get(sel_f, {}).keys()) + ["+ Novo Talhão"]
    sel_t = st.sidebar.selectbox("Talhão", tal_names)
    if sel_t == "+ Novo Talhão":
        sel_t = st.sidebar.text_input("ID Talhão")
        if sel_t and sel_t not in st.session_state['db'][sel_p][sel_f]: st.session_state['db'][sel_p][sel_f][sel_t] = {"df": None, "contorno": None}

    st.sidebar.divider()
    with st.sidebar.expander("⚙️ Atributos Técnicos", expanded=False):
        prod = st.number_input("Produtividade Alvo", 80.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0); c_t_mg = st.number_input("Alvo Mg %", 18.0)
        c_res = st.number_input("Reserva kg", 0.0); c_preco = st.number_input("R$/Ton Calc", 280.0)
        k_target = st.number_input("Alvo K %", 3.2); p_exp = st.number_input("Exp. P", 0.8)
        # Adicionar as 6 faixas de Prem aqui se necessário para edição fina
    
    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": 80.0, "cao": 36.0, "mgo": 9.0, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {"nc_0_4": 8.0, "nc_4_10": 10.0, "nc_10_19": 12.0, "nc_19_30": 15.0, "nc_30_45": 18.0, "nc_45_60": 22.0, "f_muito_arg": 10.0, "f_argiloso": 8.0, "f_medio": 4.0, "f_arenoso": 2.0, "teor_adubo": 21.0, "f_exp": p_exp, "preco": 3200.0},
        "potassio": {"target_k": k_target, "teor_adubo": 60.0, "f_exp": 1.2, "preco": 2900.0},
        "gesso": {"fator": 15.0, "min": 400.0, "max": 900.0, "preco": 190.0},
        "path": (sel_p, sel_f, sel_t)
    }
    return params

# --- PÁGINA PRINCIPAL ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Talhão: {t} | {f} | {p}</h2>", unsafe_allow_html=True)
    tabs = st.tabs(["📁 Dados", "📊 Fertilidade", "🗺️ Recomendações VRT", "📄 Relatório", "📥 Exportar"])
    
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            up_csv = st.file_uploader("CSV Solo", type=['csv'], key=f"c_{t}")
            up_geo = st.file_uploader("Contorno (GeoJSON)", type=['geojson','json'], key=f"g_{t}")
            if st.button("💾 Salvar"):
                if up_csv: st.session_state['db'][p][f][t]["df"] = pd.read_csv(up_csv, sep=None, engine='python')
                if up_geo: st.session_state['db'][p][f][t]["contorno"] = json.load(up_geo)
                st.success("Salvo!")

    if st.session_state['db'][p][f][t]["df"] is not None:
        df_res = motor_calculo_v43(st.session_state['db'][p][f][t]["df"], params)
        contorno = st.session_state['db'][p][f][t]["contorno"]

        with tabs[1]: # Fertilidade
            attrs = ["pH", "Argila", "Ca%", "Mg%", "K%", "V%", "P mehl", "prem"]
            for i in range(0, len(attrs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(attrs):
                        fig, stats = plot_kriging(df_res, attrs[i+j], attrs[i+j], contorno)
                        cols[j].plotly_chart(fig, use_container_width=True)
                        cols[j].info(stats)

        with tabs[2]: # VRT
            recs = [("REC_CALCARIO", "Calcário"), ("REC_P_ADUBO", "Fosfatado"), ("REC_K_ADUBO", "Potássio"), ("REC_GESSO", "Gesso")]
            args = {"Calcário": "Máxima eficiência via equilíbrio atômico.", "Fosfatado": "Balanço via P-rem com abatimento de excesso.", "Potássio": "Saturação ideal + exportação obrigatória.", "Gesso": "Melhoria baseada em Argila %."}
            for i in range(0, len(recs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(recs):
                        fig, stats = plot_kriging(df_res, recs[i+j][0], recs[i+j][1], contorno)
                        cols[j].plotly_chart(fig, use_container_width=True)
                        cols[j].success(f"{stats}\n\nArgumento: {args[recs[i+j][1]]}")

        with tabs[3]: # Relatório
            st.write("### Consolidar Relatório Tríade")
            if st.button("📝 Gerar PDF"):
                pdf = PDF_Triade(); pdf.add_page()
                pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"Talhão: {t} - Fazenda: {f}", ln=True)
                pdf.set_font("Arial", '', 10); pdf.cell(0, 10, f"Investimento Médio Total: R$ {df_res['C_TOTAL'].mean():.2f}/ha", ln=True)
                pdf.ln(10)
                pdf.multi_cell(0, 10, "Este relatório contém os mapas de fertilidade e prescrições baseados na metodologia Tríade v43, garantindo o máximo ROI através do balanço estequiométrico de nutrientes.")
                st.download_button("⬇️ Baixar Relatório PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"Relatorio_{t}.pdf")

# --- EXECUÇÃO ---
params = configurar_interface()
p, f, t = params["path"]
if not p or not f or not t: st.info("Selecione o talhão na lateral.")
else: pag_produtores(params)
