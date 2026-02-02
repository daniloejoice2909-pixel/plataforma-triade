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

# --- CONFIGURAÇÃO E ESTADO ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# Inicialização de estados para evitar re-processamento e travamentos
if 'fert_ready' not in st.session_state: st.session_state['fert_ready'] = False
if 'vrt_ready' not in st.session_state: st.session_state['vrt_ready'] = False
if 'df_results' not in st.session_state: st.session_state['df_results'] = None

# --- CSS PREMIUM TRÍADE (OPEN SANS + RIGOR VISUAL) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 13px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #fff; padding: 15px; border-radius: 8px; 
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; 
        text-align: center; margin-bottom: 10px;
    }
    .kpi-value { font-size: 22px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { 
        font-size: 11px; color: #333; background: #eef5f8; padding: 12px; 
        border-radius: 6px; border-left: 5px solid #27ae60; margin-top: 5px; 
    }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: INTERFACE SIDEBAR (AUDITADA V43 - CONTROLE TOTAL +/-) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### 📍 Dados do Talhão")
    p_n = st.sidebar.text_input("Produtor", value="Gilson Berneck")
    f_n = st.sidebar.text_input("Fazenda", value="Brasnorte")
    t_n = st.sidebar.text_input("Talhão", value="T1")

    st.sidebar.divider()
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0, min_value=0.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1)
        c_mgo = st.number_input("MgO %", value=9.0, step=0.1)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0)
        c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)
        c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_pre = st.number_input("R$/Ton Calcário", value=190.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc = [st.number_input(f"NC {f}", value=v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        st.write("**Fatores Argila**")
        f_a = [st.number_input(f, value=v, step=0.1) for f, v in zip(["Muito Argiloso", "Argiloso", "Médio", "Arenoso"], [10.0, 8.0, 4.0, 2.0])]
        p_t = st.number_input("Teor Adubo P %", value=21.0)
        p_e = st.number_input("Exp (kg/sc) P", value=0.8)
        p_p = st.number_input("R$/Ton P", value=2000.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_t = st.number_input("Alvo K % CTC", value=3.2, step=0.1)
        k_e = st.number_input("Exp (kg/sc) K", value=1.2)
        k_te = st.number_input("Teor Adubo K %", value=60.0)
        k_p = st.number_input("R$/Ton K", value=2800.0)

    with st.sidebar.expander("📦 Gesso"):
        g_f = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_mi = st.number_input("Mín kg/ha", value=400.0); g_ma = st.number_input("Máx kg/ha", value=900.0)
        g_pr = st.number_input("R$/Ton Gesso", value=400.0)

    return {
        "p_nome": p_n, "f_nome": f_n, "t_nome": t_n, "prod": prod,
        "calc": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg, "res": c_res, "pre": c_pre},
        "fosf": {"nc": nc, "f_arg": f_a, "teor": p_t, "exp": p_e, "pre": p_p},
        "pot": {"target": k_t, "exp": k_e, "teor": k_te, "pre": k_p},
        "gesso": {"fator": g_f, "min": g_mi, "max": g_ma, "pre": g_pr}
    }

# --- CAMADA 2: MOTOR LÓGICO V43 ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    mapping = {'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'}
    df = df.rename(columns=mapping)
    
    # Gesso: Argila % x Fator 15
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])

    # Calagem: Dose Max Ca/Mg
    df['nc_ca'] = ((p['calc']['t_ca'] - df.get('ca_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['nc_mg'] = ((p['calc']['t_mg'] - df.get('mg_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['rec_calcario'] = (np.maximum((df['nc_ca']*5600000/(p['calc']['cao']*p['calc']['prnt']+0.1)), 
                                     (df['nc_mg']*4000000/(p['calc']['mgo']*p['calc']['prnt']+0.1))) + p['calc']['res']).round(2)

    # Potássio: Alvo + Exportação Mandatória (1.2 kg/sc)
    df['k_eleva'] = ((p['pot']['target'] - df.get('k_p', 0)).clip(lower=0) * df.get('ctc', 0) / 100 * 391)
    df['rec_potassio'] = (df['k_eleva'] + (p['prod'] * p['pot']['exp'])) * 100 / p['pot']['teor']

    # Fósforo: NC por P-rem + Crédito Solo + Exportação
    def calc_p(row):
        nc_idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
        f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
        p_nec = (p['fosf']['nc'][nc_idx] - row['p_mehl']) * p['fosf']['f_arg'][f_idx]
        return (max(p_nec, 0) + (p['prod'] * p['fosf']['exp'])) * 100 / p['fosf']['teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)

    return df

# --- CAMADA 3: GEOPROCESSAMENTO (RIGOR 1:1 + PREENCHIMENTO 100%) ---
def plot_v43_master(df, col, title, poly=None):
    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    xi = np.linspace(x.min(), x.max(), 150); yi = np.linspace(y.min(), y.max(), 150)
    xi, yi = np.meshgrid(xi, yi); rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    fig = go.Figure()
    fig.add_trace(go.Contour(z=zi, x=xi[0], y=yi[:,0], colorscale='RdBu_r', contours=dict(showlines=False), line_width=0, colorbar=dict(thickness=15)))
    
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scatter(x=cx, y=cy, mode='lines', line=dict(color='black', width=3), showlegend=False))

    fig.update_layout(title=f"<b>{title}</b>", height=550, plot_bgcolor='white',
                      xaxis=dict(showticklabels=False, scaleanchor="y", scaleratio=1), # ASPECT RATIO 1:1
                      yaxis=dict(showticklabels=False), margin=dict(l=10,r=10,b=10,t=50))
    return fig

# --- APP PRINCIPAL ---
sb = configurar_interface()
st.title("🌱 Plataforma Tríade Agro Estratégica v43")

col_u1, col_u2 = st.columns(2)
with col_u1: up_csv = st.file_uploader("1. Planilha Solo (CSV)", type="csv")
with col_u2: up_geo = st.file_uploader("2. Contorno (GeoJSON)", type="geojson")

if up_csv:
    if st.session_state['df_results'] is None:
        st.session_state['df_results'] = motor_v43(pd.read_csv(up_csv), sb)
    
    df_res = st.session_state['df_results']
    poly_obj = shape(json.load(up_geo)['features'][0]['geometry']) if up_geo else None

    tabs = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT", "📥 Saída Final"])

    with tabs[0]: # ABA FERTILIDADE
        if st.button("🚀 GERAR MAPAS DE FERTILIDADE"): st.session_state['fert_ready'] = True
        
        if st.session_state['fert_ready']:
            attrs = [('ph', 'Acidez (pH)'), ('argila', 'Argila (%)'), ('v_p', 'Saturação Bases (V%)'), ('prem', 'P-rem (mg/L)')]
            for col, label in attrs:
                if col in df_res.columns:
                    c_m, c_i = st.columns([3, 1])
                    c_m.plotly_chart(plot_v43_master(df_res, col, label, poly_obj), use_container_width=True, key=f"f_{col}")
                    v = df_res[col].dropna()
                    c_i.info(f"**{label}**\nMín: {v.min():.2f} | Máx: {v.max():.2f} | Méd: {v.mean():.2f}")

    with tabs[1]: # ABA VRT
        if st.button("🗺️ PROCESSAR RECOMENDAÇÕES VRT"): st.session_state['vrt_ready'] = True
        
        if st.session_state['vrt_ready']:
            vrt_list = [('rec_calcario', 'Calcário', sb['calc']['pre'], "Equilíbrio Ca/Mg."), 
                        ('rec_fosforo', 'Fosfatado', sb['fosf']['pre'], "NC P-rem + Crédito Solo."), 
                        ('rec_potassio', 'Potássico', sb['pot']['pre'], "Alvo 3.2% + Exp. Mandatória."),
                        ('rec_gesso', 'Gesso', sb['gesso']['pre'], "Argila% x 15.")]
            for col, label, preco, arg in vrt_list:
                c_m, c_i = st.columns([3, 1])
                c_m.plotly_chart(plot_v43_master(df_res, col, f"Recomendação {label}", poly_obj), use_container_width=True, key=f"v_{col}")
                v = df_res[col].dropna(); custo = (v.mean() / 1000) * preco
                c_i.markdown(f"<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo:.2f}/ha</span></div>", unsafe_allow_html=True)
                c_i.markdown(f"<div class='arg-tecnico'><b>Argumento Tríade:</b> {arg}</div>", unsafe_allow_html=True)

    with tabs[2]: # ABA EXPORTAÇÃO
        c_p, c_z = st.columns(2)
        # CORREÇÃO DO MOTOR PDF (FPDF2 Syntax)
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, f"RELATÓRIO TRIADE AGRO - {sb['p_nome'].upper()}", ln=True, align='C')
        pdf.set_font("Helvetica", '', 12); pdf.ln(10); pdf.cell(0, 10, f"Fazenda: {sb['f_nome']} | Talhão: {sb['t_nome']}", ln=True)
        pdf_bytes = pdf.output() # No FPDF2, output() retorna bytes por padrão
        c_p.download_button("📄 Baixar Relatório PDF", data=pdf_bytes, file_name=f"Relatorio_{sb['t_nome']}.pdf", mime="application/pdf")
        
        # MOTOR ZIP MULTI-MARCA
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for marca in ["JOHN_DEERE", "TRIMBLE", "HORSCH", "CASE_IH", "STARA"]:
                z.writestr(f"{marca}/Rx_VRT_{sb['t_nome']}.csv", df_res.to_csv(index=False))
        c_z.download_button("📦 Exportar ZIP Monitores", data=buf.getvalue(), file_name="Triade_Export_VRT.zip", mime="application/zip")
