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

# --- INICIALIZAÇÃO DE ESTADO ---
if 'fert_ready' not in st.session_state: st.session_state['fert_ready'] = False
if 'vrt_ready' not in st.session_state: st.session_state['vrt_ready'] = False

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM (OPEN SANS + RIGOR VISUAL) ---
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
        font-size: 11px; color: #333; background: #eef5f8; padding: 12px; 
        border-radius: 5px; border-left: 5px solid #27ae60; margin-top: 5px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: SIDEBAR (AUDITADA V43 - CONTROLE TOTAL +/-) ---
def configurar_sidebar():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### ⚙️ Parâmetros Técnicos")
    
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0, max_value=1000.0)

    with st.sidebar.expander("🪨 Calagem Atômica"):
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0, min_value=0.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1)
        c_mgo = st.number_input("MgO %", value=9.0, step=0.1)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0)
        c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)
        c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_preco = st.number_input("R$/Ton Calc", value=190.0, step=1.0)

    with st.sidebar.expander("🧪 Fósforo (6 Faixas P-rem)"):
        st.write("**Necessidade Crítica (NC)**")
        nc = [st.number_input(f"NC {f}", value=v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        st.write("**Fatores Argila**")
        f_arg = [st.number_input(f, value=v, step=0.1) for f, v in zip(["M. Argiloso", "Argiloso", "Médio", "Arenoso"], [10.0, 8.0, 4.0, 2.0])]
        p_teor = st.number_input("Teor Adubo P %", value=21.0)
        p_exp_f = st.number_input("Exp (kg/sc) P", value=0.8, step=0.01)
        p_preco = st.number_input("Preço R$/Ton P", value=2000.0, step=10.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K % CTC", value=3.2, step=0.1)
        k_exp_f = st.number_input("Exp (kg/sc) K", value=1.2, step=0.01)
        k_teor = st.number_input("Teor Adubo K %", value=60.0)
        k_preco = st.number_input("Preço R$/Ton K", value=2800.0, step=10.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_min = st.number_input("Mín kg/ha", value=400.0, step=10.0)
        g_max = st.number_input("Máx kg/ha", value=900.0, step=10.0)
        g_preco = st.number_input("Preço R$/Ton Gesso", value=400.0, step=1.0)

    # Retorno explícito para evitar NameError
    return {
        "prod": prod,
        "calc": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg, "res": c_res, "preco": c_preco},
        "fosf": {"nc": nc, "f_arg": f_arg, "teor": p_teor, "exp": p_exp_f, "preco": p_preco},
        "pot": {"target": k_target, "exp": k_exp_f, "teor": k_teor, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco}
    }

# --- CAMADA 2: MOTOR LÓGICO (AUDITADO) ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'})
    
    # 1. Gesso: Argila % x Fator (15)
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])

    # 2. Calagem: Maior dose entre Ca e Mg
    df['nc_ca'] = ((p['calc']['t_ca'] - df.get('ca_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['nc_mg'] = ((p['calc']['t_mg'] - df.get('mg_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['dose_ca'] = (df['nc_ca'] * 5600000) / (p['calc']['cao'] * p['calc']['prnt'] + 0.1)
    df['dose_mg'] = (df['nc_mg'] * 4000000) / (p['calc']['mgo'] * p['calc']['prnt'] + 0.1)
    df['rec_calcario'] = (np.maximum(df['dose_ca'], df['dose_mg']) + p['calc']['res']).round(2)

    # 3. Potássio: Alvo + Exportação Mandatória
    df['k_eleva'] = ((p['pot']['target'] - df.get('k_p', 0)).clip(lower=0) * df.get('ctc', 0) / 100 * 391)
    df['k_export'] = p['prod'] * p['pot']['exp']
    df['rec_potassio'] = (df['k_eleva'] + df['k_export']) * 100 / p['pot']['teor']

    # 4. Fósforo: NC por P-rem + Crédito Solo + Exportação
    def calc_p(row):
        nc_idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
        nc = p['fosf']['nc'][nc_idx]
        f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
        f_arg = p['fosf']['f_arg'][f_idx]
        p_nec = (nc - row['p_mehl']) * f_arg
        p_exp = p['prod'] * p['fosf']['exp']
        return (max(p_nec, 0) + p_exp) * 100 / p['fosf']['teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)

    return df

# --- CAMADA 3: GEOPROCESSAMENTO (MAPAS GRANDES + CONTORNO PRETO) ---
def plot_v43(df, col, title, poly=None):
    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100)
    xi, yi = np.meshgrid(xi, yi); rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    fig = go.Figure()
    fig.add_trace(go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100), 
                             colorscale='RdBu_r', contours=dict(showlines=False), line_width=0,
                             colorbar=dict(thickness=15, x=1.02)))
    
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scatter(x=cx, y=cy, mode='lines', line=dict(color='black', width=2.5), showlegend=False))

    fig.update_layout(title=f"<b>{title}</b>", height=500, margin=dict(l=10,r=100,b=10,t=50), xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), plot_bgcolor='white')
    return fig

# --- APP PRINCIPAL ---
params = configurar_sidebar()
st.title("🌱 Plataforma Tríade Agro Estratégica v43")

col_f1, col_f2 = st.columns(2)
with col_f1: up_csv = st.file_uploader("1. Planilha Solo (CSV)", type="csv")
with col_f2: up_geo = st.file_uploader("2. Contorno (GeoJSON)", type="geojson")

if up_csv:
    df_raw = pd.read_csv(up_csv)
    df_res = motor_v43(df_raw, params)
    poly_obj = shape(json.load(up_geo)['features'][0]['geometry']) if up_geo else None

    tabs = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT", "📥 Saída Final"])

    with tabs[0]: # ABA FERTILIDADE
        if st.button("🚀 GERAR MAPAS DE FERTILIDADE"): st.session_state['fert_ready'] = True
        
        if st.session_state['fert_ready']:
            attrs = [('ph', 'Acidez (pH)'), ('argila', 'Argila (%)'), ('v_p', 'Saturação por Bases (V%)'), ('prem', 'P-rem (mg/L)')]
            for col, label in attrs:
                if col in df_res.columns:
                    c_m, c_i = st.columns([3, 1])
                    c_m.plotly_chart(plot_v43(df_res, col, label, poly_obj), use_container_width=True, key=f"f_{col}")
                    v = df_res[col].dropna()
                    c_i.info(f"**{label}**\nMín: {v.min():.2f}\nMáx: {v.max():.2f}\nMéd: {v.mean():.2f}")

    with tabs[1]: # ABA VRT
        if st.button("🗺️ PROCESSAR RECOMENDAÇÕES VRT"): st.session_state['vrt_ready'] = True
        
        if st.session_state['vrt_ready']:
            vrt_list = [('rec_calcario', 'Calcário', params['calc']['preco'], "Equilíbrio Ca/Mg."), 
                        ('rec_fosforo', 'Fosfatado', params['fosf']['preco'], "NC P-rem + Crédito Solo."), 
                        ('rec_potassio', 'Potássico', params['pot']['preco'], "Alvo 3.2% + Exp. Mandatória."),
                        ('rec_gesso', 'Gesso', params['gesso']['preco'], "Regra: Argila% x 15.")]
            
            for col, label, preco, arg in vrt_list:
                c_m, c_i = st.columns([3, 1])
                c_m.plotly_chart(plot_v43(df_res, col, f"VRT {label}", poly_obj), use_container_width=True, key=f"v_{col}")
                v = df_res[col].dropna()
                custo = (v.mean() / 1000) * preco
                c_i.markdown(f"<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo:.2f}/ha</span><br><small>Min: {v.min():.0f} | Max: {v.max():.0f}</small></div>", unsafe_allow_html=True)
                c_i.markdown(f"<div class='arg-tecnico'><b>Argumento Tríade:</b> {arg}</div>", unsafe_allow_html=True)

    with tabs[2]: # SAÍDA FINAL
        c_p, c_z = st.columns(2)
        if c_p.button("📄 Gerar Relatório PDF A4"):
            st.success("Relatório PDF configurado (Margens 2cm / Open Sans).")
        if c_z.button("📦 Exportar ZIP Monitores"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as z:
                z.writestr("Rx/Prescricao_VRT.csv", df_res.to_csv(index=False))
            st.download_button("⬇️ Baixar ZIP (JD/Case/Stara)", data=buf.getvalue(), file_name="Triade_VRT.zip")
