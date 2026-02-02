import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
from fpdf import FPDF
import json
import io
import zipfile

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM TRÍADE (OPEN SANS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card {
        background-color: #ffffff; padding: 15px; border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 5px solid #1e3d59;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 6px solid #1e3d59; padding-left: 12px; margin: 25px 0; font-weight: bold; }
    .arg-tecnico { font-size: 11px; color: #444; background: #f0f4f5; padding: 12px; border-radius: 5px; border-left: 4px solid #27ae60; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSE DE RELATÓRIO PDF (A4, 2CM MARGENS) ---
class RelatorioTriade(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 33)
        except: pass
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'TRÍADE AGRO ESTRATÉGICA - V43', 0, 1, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# --- MOTOR DE CÁLCULO TRÍADE V43 ---
def motor_calculo_v43(df, params):
    df.columns = df.columns.str.strip().str.lower()
    mapping = {'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 'prem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 'k%': 'K%'}
    df = df.rename(columns=mapping)
    
    for col in ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'Longitude', 'Latitude']:
        if col not in df.columns: df[col] = 0.0
        else: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # 1. Calagem Atômica
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    df['REC_CALCARIO'] = (np.maximum((df['NC_CA_CMOL']*5600000/(c_p["cao"]*c_p["prnt"])), 
                                     (df['NC_MG_CMOL']*4000000/(c_p["mgo"]*c_p["prnt"]))) + c_p["reserva"]).round(2)

    # 2. Fósforo (6 Classes P-rem)
    def calc_p(row):
        nc = (p_p["nc_0_4"] if row['prem'] <= 4 else p_p["nc_4_10"] if row['prem'] <= 10 else 
              p_p["nc_10_19"] if row['prem'] <= 19 else p_p["nc_19_30"] if row['prem'] <= 30 else 
              p_p["nc_30_45"] if row['prem'] <= 45 else p_p["nc_45_60"])
        f_arg = (p_p["f_muito_arg"] if row['Argila'] > 600 else p_p["f_argiloso"] if row['Argila'] > 350 else 
                 p_p["f_medio"] if row['Argila'] > 150 else p_p["f_arenoso"])
        p_total = ((nc - row['P mehl']) * f_arg) + (prod_esp * p_p["f_exp"])
        return (max(p_total, 0) * 100) / p_p["teor_adubo"]
    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 3. Potássio e Gesso (Gesso = Clay g/kg * Fator)
    df['REC_K_ADUBO'] = (((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941) + (prod_esp * k_p["f_exp"])) * 100 / k_p["teor_adubo"]
    df['REC_GESSO'] = (df['Argila'] * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    df['C_TOTAL'] = ((df['REC_CALCARIO']/1000)*c_p["preco"]) + ((df['REC_P_ADUBO']/1000)*p_p["preco"]) + \
                    ((df['REC_K_ADUBO']/1000)*k_p["preco"]) + ((df['REC_GESSO']/1000)*g_p["preco"])
    return df

# --- MOTOR GEOESTATÍSTICO COM CLIPPING ---
def plot_geostats(df, col, title, geo_json=None):
    x, y, z = df['Longitude'].values, df['Latitude'].values, df[col].values
    if len(np.unique(x)) < 2: return go.Figure(), "N/A"
    xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100); xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear', smooth=0.1); zi = rbf(xi, yi)
    if geo_json:
        try:
            poly = shape(geo_json['features'][0]['geometry'])
            for i in range(len(xi)):
                for j in range(len(yi)):
                    if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan
        except: pass
    fig = go.Figure(data=go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100), colorscale='coolwarm', contours=dict(showlines=False), line_width=0))
    fig.update_layout(title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=350, xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='white')
    stats = f"Mín: {np.nanmin(zi):.2f} | Máx: {np.nanmax(zi):.2f} | Méd: {np.nanmean(zi):.2f}"
    return fig, stats

# --- INTERFACE SIDEBAR (TOTALMENTE EDITÁVEL) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.header("📍 Navegação")
    p_names = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_p = st.sidebar.selectbox("Produtor", p_names)
    if sel_p == "+ Novo Produtor":
        sel_p = st.sidebar.text_input("Nome Cliente")
        if sel_p and sel_p not in st.session_state['db']: st.session_state['db'][sel_p] = {}

    st.sidebar.divider()
    with st.sidebar.expander("🌍 Global & Produtividade", expanded=True):
        prod = st.number_input("Produtividade Alvo (sc/ha)", 80.0, step=1.0)
    with st.sidebar.expander("🪨 Calagem Atômica"):
        c_cao = st.number_input("CaO %", 36.0); c_mgo = st.number_input("MgO %", 9.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0); c_t_mg = st.number_input("Alvo Mg %", 18.0)
        c_res = st.number_input("Reserva kg", 0.0); c_preco = st.number_input("R$/Ton Calc", 280.0)
    with st.sidebar.expander("🧪 Fósforo (6 Classes P-rem)"):
        nc04 = st.number_input("NC 0-4", 8.0); nc410 = st.number_input("NC 4-10", 10.0); nc1019 = st.number_input("NC 10-19", 12.0)
        nc1930 = st.number_input("NC 19-30", 15.0); nc3045 = st.number_input("NC 30-45", 18.0); nc4560 = st.number_input("NC 45-60", 22.0)
        f_m_arg = st.number_input("Fator M. Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0); f_med = st.number_input("Médio", 4.0); f_are = st.number_input("Arenoso", 2.0)
        p_teor = st.number_input("Teor Adubo P %", 21.0); p_exp = st.number_input("Exp. P (kg/sc)", 0.8); p_preco = st.number_input("R$/Ton P", 3200.0)
    with st.sidebar.expander("🍌 Potássio & Gesso"):
        k_target = st.number_input("Alvo K %", 3.2); k_preco = st.number_input("R$/Ton K", 2900.0)
        g_fator = st.number_input("Fator Gesso", 15.0); g_min = st.number_input("Mín kg", 400.0); g_max = st.number_input("Máx kg", 900.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": 80.0, "cao": c_cao, "mgo": c_mgo, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {"nc_0_4": nc04, "nc_4_10": nc410, "nc_10_19": nc1019, "nc_19_30": nc1930, "nc_30_45": nc3045, "nc_45_60": nc4560, "f_muito_arg": f_m_arg, "f_argiloso": f_arg, "f_medio": f_med, "f_arenoso": f_are, "teor_adubo": p_teor, "f_exp": p_exp, "preco": p_preco},
        "potassio": {"target_k": k_target, "teor_adubo": 60.0, "f_exp": 1.2, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": 190.0},
        "path": (sel_p, "Fazenda", "Talhão")
    }
    return params

# --- PÁGINA DE OPERAÇÕES ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Consultoria Tríade: {p}</h2>", unsafe_allow_html=True)
    tabs = st.tabs(["📁 Dados", "📊 Fertilidade", "🗺️ VRT", "📄 Relatório", "📥 Exportar"])
    
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            up_csv = st.file_uploader("Subir CSV (A-Y)", type=['csv'], key=f"csv_{p}")
            up_geo = st.file_uploader("Subir Contorno (GeoJSON)", type=['geojson','json'], key=f"geo_{p}")
            if st.button("🚀 Processar"):
                if up_csv: st.session_state['db'][p] = {"df": pd.read_csv(up_csv, sep=None, engine='python'), "contorno": json.load(up_geo) if up_geo else None}
                st.success("Dados prontos!")

    if st.session_state['db'].get(p) is not None:
        df_raw = st.session_state['db'][p]["df"]
        contorno = st.session_state['db'][p].get("contorno")
        df_res = motor_calculo_v43(df_raw, params)

        with tabs[1]:
            attrs = ["pH", "Argila", "Ca%", "Mg%", "K%", "V%", "P mehl", "prem"]
            for i in range(0, len(attrs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(attrs):
                        fig, stats = plot_geostats(df_res, attrs[i+j], attrs[i+j], contorno)
                        cols[j].plotly_chart(fig, use_container_width=True, key=f"f_{attrs[i+j]}_{p}")
                        cols[j].info(stats)

        with tabs[2]:
            recs = [("REC_CALCARIO", "Calcário"), ("REC_P_ADUBO", "Fosfatado"), ("REC_K_ADUBO", "Potássico"), ("REC_GESSO", "Gesso")]
            args_tec = {"Calcário": "Equilíbrio atômico de bases.", "Fosfatado": "NC via P-rem com crédito de solo.", "Potássio": "Saturação ideal + exportação real.", "Gesso": "Melhoria radicular por Argila %."}
            for i in range(0, len(recs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(recs):
                        label = recs[i+j][1]
                        fig, stats = plot_geostats(df_res, recs[i+j][0], f"VRT {label}", contorno)
                        cols[j].plotly_chart(fig, use_container_width=True, key=f"v_{label}_{p}")
                        cols[j].success(stats)
                        cols[j].markdown(f"<div class='arg-tecnico'><b>Argumento Tríade:</b> {args_tec.get(label)}</div>", unsafe_allow_html=True)

        with tabs[3]:
            if st.button("📝 Consolidar PDF Profissional"):
                pdf = RelatorioTriade(); pdf.add_page()
                pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"Talhão: {t} - Cliente: {p}", ln=True)
                pdf.set_font("Arial", '', 12); pdf.multi_cell(0, 10, f"Investimento médio: R$ {df_res['C_TOTAL'].mean():.2f}/ha.")
                st.download_button("⬇️ Baixar Relatório", data=pdf.output(dest='S').encode('latin-1'), file_name=f"Relatorio_{p}.pdf")

        with tabs[4]:
            if st.button("📦 Gerar ZIP para Máquinas"):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w') as z:
                    z.writestr(f"Rx/VRT_Calcario_{p}.csv", df_res[['Longitude', 'Latitude', 'REC_CALCARIO']].to_csv(index=False))
                st.download_button("⬇️ Baixar ZIP", data=buf.getvalue(), file_name=f"Tríade_VRT_{p}.zip")

# --- EXECUÇÃO ---
params = configurar_interface()
if params["path"][0] != "+ Novo Produtor": pag_produtores(params)
