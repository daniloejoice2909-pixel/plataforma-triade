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

# --- INICIALIZAÇÃO E CONFIGURAÇÃO ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

if 'db' not in st.session_state:
    st.session_state['db'] = {}

# --- CSS PREMIUM (OPEN SANS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 13px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #fff; padding: 15px; border-radius: 8px; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; 
        text-align: center; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { 
        font-size: 11px; color: #333; background: #eef5f8; padding: 10px; 
        border-radius: 5px; border-left: 5px solid #27ae60; margin-top: 5px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO DE CACHE PARA O MOTOR LÓGICO (EVITA TRAVAMENTO) ---
@st.cache_data
def processar_motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'})
    
    # Gesso: Argila % x Fator (15)
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])

    # Calagem: Maior dose Ca (560) ou Mg (400) + Reserva
    df['nc_ca'] = ((p['calcario']['t_ca'] - df['ca_p']) * df['ctc'] / 100).clip(lower=0)
    df['nc_mg'] = ((p['calcario']['t_mg'] - df['mg_p']) * df['ctc'] / 100).clip(lower=0)
    df['dose_ca'] = (df['nc_ca'] * 5600000) / (p['calcario']['cao'] * p['calcario']['prnt'] + 0.1)
    df['dose_mg'] = (df['nc_mg'] * 4000000) / (p['calcario']['mgo'] * p['calcario']['prnt'] + 0.1)
    df['rec_calcario'] = (np.maximum(df['dose_ca'], df['dose_mg']) + p['calcario']['res']).round(2)

    # Fósforo: NC P-rem com Crédito de Solo + Exportação
    def calc_p(row):
        nc_idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
        nc = p['fosforo']['nc'][nc_idx]
        f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
        f_arg = p['fosforo']['f_arg'][f_idx]
        p_nec = (nc - row['p_mehl']) * f_arg
        p_exp = p['global']['prod'] * p['fosforo']['exp']
        return (max(p_nec, 0) + p_exp) * 100 / p['fosforo']['teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)

    # Potássio: Elevação 3.2% + Exportação Mandatória (1.2 kg/sc)
    df['k_eleva'] = ((p['potassio']['target'] - df['k_p']).clip(lower=0) * df['ctc'] / 100 * 391)
    df['k_export'] = p['global']['prod'] * p['potassio']['exp']
    df['rec_potassio'] = (df['k_eleva'] + df['k_export']) * 100 / p['potassio']['teor']

    return df

# --- CAMADA 1: INTERFACE SIDEBAR (CONTROLE TOTAL +/-) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    produtor = st.sidebar.text_input("Produtor", "Gilson Berneck")
    fazenda = st.sidebar.text_input("Fazenda", "Gleba A")
    talhao = st.sidebar.text_input("Talhão", "T1")

    st.sidebar.divider()
    
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0, max_value=1000.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT %", 80.0, step=1.0, min_value=0.0)
        c_cao = st.number_input("CaO %", 36.0, step=0.1, min_value=0.0)
        c_mgo = st.number_input("MgO %", 9.0, step=0.1, min_value=0.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0, step=1.0, min_value=0.0)
        c_t_mg = st.number_input("Alvo Mg %", 18.0, step=1.0, min_value=0.0)
        c_res = st.number_input("Reserva (kg/ha)", 0.0, step=10.0, min_value=0.0)
        c_preco = st.number_input("Preço R$/Ton Calc", 190.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc = [st.number_input(f"NC {f}", v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        f_arg = [st.number_input(f, v, step=0.1) for f, v in zip(["M. Argiloso", "Argiloso", "Médio", "Arenoso"], [10.0, 8.0, 4.0, 2.0])]
        p_teor = st.number_input("Teor Adubo P %", 21.0, step=0.1)
        p_exp = st.number_input("Exp (kg/sc) P", 0.8, step=0.01)
        p_preco = st.number_input("Preço R$/Ton P", 2000.0, step=1.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K % CTC", 3.2, step=0.1)
        k_exp = st.number_input("Exp (kg/sc) K", 1.2, step=0.01)
        k_teor = st.number_input("Teor Adubo K %", 60.0, step=0.1)
        k_preco = st.number_input("Preço R$/Ton K", 2800.0, step=1.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", 15.0, step=0.1)
        g_min = st.number_input("Mín (kg/ha)", 400.0, step=10.0)
        g_max = st.number_input("Máx (kg/ha)", 900.0, step=10.0)
        g_preco = st.number_input("Preço R$/Ton Gesso", 400.0, step=1.0)

    return {
        "global": {"prod": prod},
        "calcario": {"cao": c_cao, "mgo": c_mgo, "prnt": c_prnt, "t_ca": c_t_ca, "t_mg": c_t_mg, "res": c_res, "preco": c_preco},
        "fosforo": {"nc": nc, "f_arg": f_arg, "teor": p_teor, "exp": p_exp, "preco": p_preco},
        "potassio": {"target": k_target, "exp": k_exp, "teor": k_teor, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco},
        "meta": {"produtor": produtor, "fazenda": fazenda, "talhao": talhao}
    }

# --- CAMADA 3: GEOPROCESSAMENTO (OTIMIZADO) ---
def plot_v43(df, col, title, poly=None):
    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    # Grid de 80x80 para evitar travamento mantendo qualidade
    xi = np.linspace(x.min(), x.max(), 80); yi = np.linspace(y.min(), y.max(), 80)
    xi, yi = np.meshgrid(xi, yi); rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    fig = go.Figure()
    fig.add_trace(go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 80), y=np.linspace(y.min(), y.max(), 80), 
                             colorscale='RdYlBu_r', contours=dict(showlines=False), line_width=0,
                             colorbar=dict(title=dict(text="Unidade", font=dict(size=10)), thickness=15, x=1.02)))
    
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scatter(x=cx, y=cy, mode='lines', line=dict(color='black', width=2), showlegend=False))

    fig.update_layout(title=f"<b>{title}</b>", height=500, margin=dict(l=10,r=100,b=10,t=50), 
                      xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='white')
    return fig

# --- APLICAÇÃO ---
p = configurar_interface()
st.title("🌱 Plataforma Tríade Agro Estratégica v43")

up_csv = st.file_uploader("1. Planilha Solo (CSV)", type="csv")
up_geo = st.file_uploader("2. Contorno (GeoJSON)", type="geojson")

if up_csv:
    df_raw = pd.read_csv(up_csv)
    df_res = processar_motor_v43(df_raw, p) # USANDO CACHE AQUI
    poly_obj = shape(json.load(up_geo)['features'][0]['geometry']) if up_geo else None

    tabs = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT", "📥 Exportar"])

    with tabs[0]:
        fert_attrs = [('ph', 'Acidez (pH)'), ('argila', 'Argila (%)'), ('v_p', 'Saturação por Bases (V%)'), ('prem', 'P-Remanescente (mg/L)')]
        for col, label in fert_attrs:
            if col in df_res.columns:
                c_map, c_info = st.columns([3, 1])
                c_map.plotly_chart(plot_v43(df_res, col, label, poly_obj), use_container_width=True, key=f"f_{col}")
                stats = df_res[col].dropna()
                c_info.info(f"**{label}**\nMín: {stats.min():.2f}\nMáx: {stats.max():.2f}\nMéd: {stats.mean():.2f}")

    with tabs[1]:
        vrt_list = [('rec_calcario', 'Calcário (kg/ha)', p['calcario']['preco'], "Equilíbrio Ca/Mg."), 
                    ('rec_fosforo', 'Fosfatado (kg/ha)', p['fosforo']['preco'], "NC P-rem + Exp."), 
                    ('rec_potassio', 'Potássico (kg/ha)', p['potassio']['preco'], "Alvo 3.2% + Exp."),
                    ('rec_gesso', 'Gesso (kg/ha)', p['gesso']['preco'], "Argila% x 15.")]
        
        for col, label, preco, arg in vrt_list:
            c_map, c_info = st.columns([3, 1])
            c_map.plotly_chart(plot_v43(df_res, col, label, poly_obj), use_container_width=True, key=f"v_{col}")
            custo = (df_res[col].mean() / 1000) * preco
            c_info.markdown(f"<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo:.2f}/ha</span></div>", unsafe_allow_html=True)
            c_info.markdown(f"<div class='arg-tecnico'><b>Argumento:</b> {arg}</div>", unsafe_allow_html=True)

    with tabs[2]:
        st.button("📝 Gerar Relatório PDF A4")
        st.button("📦 Exportar ZIP para Monitores")
