import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
import json
import io
import zipfile
from fpdf import FPDF

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM TRÍADE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card { 
        background: #ffffff; padding: 15px; border-radius: 10px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; 
        text-align: center; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { 
        font-size: 11px; color: #444; background: #f0f4f5; padding: 10px; 
        border-radius: 5px; border-left: 4px solid #27ae60; margin-top: 5px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: INTERFACE (SIDEBAR REVISADA) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.title("📍 Gestão de Talhão")
    
    produtor = st.sidebar.text_input("Produtor", "Gilson Berneck")
    fazenda = st.sidebar.text_input("Fazenda", "Fazenda Modelo")
    talhao = st.sidebar.text_input("Talhão", "T1")

    st.sidebar.divider()
    
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod = st.number_input("Alvo (sc/ha)", value=80.0, step=1.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_cao = st.number_input("CaO %", 36.0); c_mgo = st.number_input("MgO %", 9.0); c_prnt = st.number_input("PRNT %", 80.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0); c_t_mg = st.number_input("Alvo Mg %", 18.0)
        c_res = st.number_input("Reserva (kg/ha)", 0.0); c_preco = st.number_input("Preço R$/Ton Calc", 190.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc04 = st.number_input("NC 0-4", 8.0); nc410 = st.number_input("NC 4-10", 10.0); nc1019 = st.number_input("NC 10-19", 12.0)
        nc1930 = st.number_input("NC 19-30", 15.0); nc3045 = st.number_input("NC 30-45", 18.0); nc4560 = st.number_input("NC 45-60", 22.0)
        f_m_arg = st.number_input("Fator M. Argiloso", 10.0); f_arg = st.number_input("Fator Argiloso", 8.0)
        p_teor = st.number_input("Teor Adubo P %", 21.0); p_exp_fator = st.number_input("Exp. P (kg/sc)", 0.8); p_preco = st.number_input("Preço R$/Ton P", 2000.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K %", 3.2); k_exp_fator = st.number_input("Exp. K (kg/sc)", 1.2)
        k_teor = st.number_input("Teor Adubo K %", 60.0); k_preco = st.number_input("Preço R$/Ton K", 2800.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", 15.0); g_min = st.number_input("Mín kg/ha", 400.0); g_max = st.number_input("Máx kg/ha", 900.0); g_preco = st.number_input("Preço R$/Ton Gesso", 400.0)

    # Dicionário de parâmetros explícito para evitar KeyError
    return {
        "prod": prod,
        "calcario": {"cao": c_cao, "mgo": c_mgo, "prnt": c_prnt, "t_ca": c_t_ca, "t_mg": c_t_mg, "res": c_res, "preco": c_preco},
        "fosforo": {"nc": [nc04, nc410, nc1019, nc1930, nc3045, nc4560], "f_arg": [f_m_arg, f_arg], "teor": p_teor, "exp": p_exp_fator, "preco": p_preco},
        "potassio": {"target": k_target, "exp": k_exp_fator, "teor": k_teor, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco},
        "meta": {"produtor": produtor, "fazenda": fazenda, "talhao": talhao}
    }

# --- CAMADA 2: MOTOR LÓGICO ---
def motor_v43(df, p):
    df.columns = df.columns.str.strip().str.lower()
    
    # Gesso: Argila % * Fator 15
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])

    # Calagem: Maior entre Ca e Mg
    df['nc_ca'] = ((p['calcario']['t_ca'] - df['ca%']) * df['ctc'] / 100).clip(lower=0)
    df['nc_mg'] = ((p['calcario']['t_mg'] - df['mg%']) * df['ctc'] / 100).clip(lower=0)
    df['dose_calc_ca'] = (df['nc_ca'] * 560 * 10000) / (p['calcario']['cao'] * p['calcario']['prnt'] + 0.01)
    df['dose_calc_mg'] = (df['nc_mg'] * 400 * 10000) / (p['calcario']['mgo'] * p['calcario']['prnt'] + 0.01)
    df['rec_calcario'] = (np.maximum(df['dose_calc_ca'], df['dose_calc_mg']) + p['calcario']['res']).round(2)

    # Fósforo: NC P-rem + Crédito Solo
    def calc_p(row):
        nc_list = p['fosforo']['nc']; pr = row['prem']
        nc = nc_list[0] if pr <= 4 else nc_list[1] if pr <= 10 else nc_list[2] if pr <= 19 else nc_list[3] if pr <= 30 else nc_list[4] if pr <= 45 else nc_list[5]
        f_arg = p['fosforo']['f_arg'][0] if row['argila'] > 60 else p['fosforo']['f_arg'][1]
        p_nec = (nc - row['p mehl']) * f_arg
        p_exp = p['prod'] * p['fosforo']['exp']
        return (max(p_nec, 0) + p_exp) * 100 / p['fosforo']['teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)

    # Potássio: Elevação 3.2% + Exportação Mandatória
    df['k_eleva'] = ((p['potassio']['target'] - df['k%']).clip(lower=0) * df['ctc'] / 100 * 391)
    df['k_export'] = p['prod'] * p['potassio']['exp']
    df['rec_potassio'] = (df['k_eleva'] + df['k_export']) * 100 / p['potassio']['teor']

    return df

# --- CAMADA 3: GEOPROCESSAMENTO ---
def plot_krigagem(df, col, title, poly=None):
    try:
        x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
        xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100)
        xi, yi = np.meshgrid(xi, yi)
        rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
        
        if poly:
            for i in range(len(xi)):
                for j in range(len(yi)):
                    if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

        fig = go.Figure(data=go.Contour(
            z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100), 
            colorscale='RdBu_r', contours=dict(showlines=False), line_width=0
        ))
        fig.update_layout(title=f"<b>{title}</b>", height=380, margin=dict(l=10,r=10,b=10,t=40), xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False))
        return fig
    except: return go.Figure().update_layout(title="Aguardando dados geográficos...")

# --- EXECUÇÃO ---
p_params = configurar_interface()
st.title("🌱 Tríade Agro Estratégica v43")

up_csv = st.file_uploader("1. Planilha Solo (CSV)", type="csv")
up_geo = st.file_uploader("2. Contorno (GeoJSON)", type="geojson")

if up_csv:
    df_solo = pd.read_csv(up_csv)
    df_res = motor_v43(df_solo, p_params)
    
    poly_obj = None
    if up_geo:
        poly_obj = shape(json.load(up_geo)['features'][0]['geometry'])

    st.divider()
    tabs = st.tabs(["🗺️ Mapas de Recomendação", "📄 Relatório & Exportação"])
    
    with tabs[0]:
        c1, c2 = st.columns(2)
        recs = [('rec_calcario', 'Calcário (kg/ha)', 'calcario'), ('rec_fosforo', 'Fosfatado (kg/ha)', 'fosforo'), 
                ('rec_potassio', 'Potássico (kg/ha)', 'potassio'), ('rec_gesso', 'Gesso (kg/ha)', 'gesso')]
        
        for idx, (col, label, key_p) in enumerate(recs):
            target = c1 if idx % 2 == 0 else c2
            fig = plot_krigagem(df_res, col, label, poly_obj)
            target.plotly_chart(fig, use_container_width=True, key=f"map_{col}")
            
            # Financeiro (Auditoria Camada 5)
            custo_ha = (df_res[col].mean() / 1000) * p_params[key_p]['preco']
            target.markdown(f"<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo_ha:.2f}/ha</span></div>", unsafe_allow_html=True)
            
    with tabs[1]:
        st.button("📝 Gerar Relatório PDF")
        st.button("📦 Gerar ZIP Monitores")
