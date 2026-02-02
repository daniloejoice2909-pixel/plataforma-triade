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

if 'fert_ready' not in st.session_state: st.session_state['fert_ready'] = False
if 'vrt_ready' not in st.session_state: st.session_state['vrt_ready'] = False
if 'df_results' not in st.session_state: st.session_state['df_results'] = None

# --- CSS PREMIUM TRÍADE ---
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
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: INTERFACE SIDEBAR (AUDITADA V43) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### ⚙️ Gestão Técnica")
    
    produtor = st.sidebar.text_input("Produtor", value="Gilson Berneck")
    fazenda = st.sidebar.text_input("Fazenda", value="Brasnorte")
    talhao = st.sidebar.text_input("Talhão", value="T1")

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
        # Listas explicitamente fechadas para evitar SyntaxError
        nc_vals = [st.number_input(f"NC {f}", value=v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        f_arg_vals = [st.number_input(f, value=v, step=0.1) for f, v in zip(["M.Argiloso", "Argiloso", "Médio", "Arenoso"], [10.0, 8.0, 4.0, 2.0])]
        p_teor = st.number_input("Teor Adubo P %", value=21.0)
        p_exp = st.number_input("Exp (kg/sc) P", value=0.8)
        p_preco = st.number_input("R$/Ton Adubo P", value=2000.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_t = st.number_input("Alvo K % CTC", value=3.2, step=0.1)
        k_e = st.number_input("Exp (kg/sc) K", value=1.2)
        k_te = st.number_input("Teor Adubo K %", value=60.0)
        k_p = st.number_input("R$/Ton Adubo K", value=2800.0)

    with st.sidebar.expander("📦 Gesso"):
        g_f = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_mi = st.number_input("Mín kg/ha", value=400.0)
        g_ma = st.number_input("Máx kg/ha", value=900.0)
        g_pr = st.number_input("R$/Ton Gesso", value=400.0)

    # Retorno estruturado conforme PROTOCOLO V43 (Sem locals())
    return {
        "p_nome": produtor, "f_nome": fazenda, "t_nome": talhao, "prod": prod,
        "calc": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg, "res": c_res, "pre": c_pre},
        "fosf": {"nc": nc_vals, "f_arg": f_arg_vals, "teor": p_teor, "exp": p_exp, "pre": p_preco},
        "pot": {"target": k_t, "exp": k_e, "teor": k_te, "pre": k_p},
        "gesso": {"fator": g_f, "min": g_mi, "max": g_ma, "pre": g_pr}
    }

# --- CAMADA 2: MOTOR LÓGICO V43 ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'})
    
    # Gesso: Argila % x Fator 15
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])

    # Calagem: Dose Max Ca/Mg
    df['nc_ca'] = ((p['calc']['t_ca'] - df.get('ca_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['nc_mg'] = ((p['calc']['t_mg'] - df.get('mg_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['rec_calcario'] = (np.maximum((df['nc_ca']*5600000/(p['calc']['cao']*p['calc']['prnt']+0.1)), 
                                     (df['nc_mg']*4000000/(p['calc']['mgo']*p['calc']['prnt']+0.1))) + p['calc']['res']).round(2)

    # Potássio: Alvo + Reposição Mandatória
    df['k_eleva'] = ((p['pot']['target'] - df.get('k_p', 0)).clip(lower=0) * df.get('ctc', 0) / 100 * 391)
    df['rec_potassio'] = (df['k_eleva'] + (p['prod'] * p['pot']['exp'])) * 100 / p['pot']['teor']

    return df

# --- CAMADA 3: GEOPROCESSAMENTO (RIGOR GEOMÉTRICO 1:1) ---
def plot_v43_master(df, col, title, poly=None):
    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    xi = np.linspace(x.min(), x.max(), 150); yi = np.linspace(y.min(), y.max(), 150)
    xi, yi = np.meshgrid(xi, yi); rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    fig = go.Figure()
    fig.add_trace(go.Contour(z=zi, x=xi[0], y=yi[:,0], colorscale='RdBu_r', contours=dict(showlines=False), line_width=0))
    
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

    with tabs[0]: # FERTILIDADE
        if st.button("🚀 GERAR MAPAS DE FERTILIDADE"): st.session_state['fert_ready'] = True
        if st.session_state['fert_ready']:
            for col, label in [('ph', 'Acidez (pH)'), ('argila', 'Argila (%)'), ('v_p', 'V%')]:
                if col in df_res.columns:
                    c_m, c_i = st.columns([3, 1])
                    c_m.plotly_chart(plot_v43_master(df_res, col, label, poly_obj), use_container_width=True)
                    v = df_res[col].dropna(); c_i.info(f"**{label}**\nMín: {v.min():.1f} | Máx: {v.max():.1f} | Méd: {v.mean():.1f}")

    with tabs[1]: # VRT
        if st.button("🗺️ PROCESSAR RECOMENDAÇÕES VRT"): st.session_state['vrt_ready'] = True
        if st.session_state['vrt_ready']:
            for col, label, preco in [('rec_calcario', 'Calcário', sb['calc']['pre']), ('rec_potassio', 'Potássio', sb['pot']['pre']), ('rec_gesso', 'Gesso', sb['gesso']['pre'])]:
                c_m, c_i = st.columns([3, 1])
                c_m.plotly_chart(plot_v43_master(df_res, col, f"VRT {label}", poly_obj), use_container_width=True)
                v = df_res[col].dropna(); custo = (v.mean()/1000)*preco
                c_i.markdown(f"<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo:.2f}/ha</span></div>", unsafe_allow_html=True)
                c_i.markdown("<div class='arg-tecnico'><b>Argumento:</b> Conforme Protocolo V43.</div>", unsafe_allow_html=True)

    with tabs[2]: # EXPORTAÇÃO
        c_p, c_z = st.columns(2)
        # PDF
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"RELATÓRIO TRIADE - {sb['p_nome']}", ln=True, align='C')
        pdf_b = pdf.output(dest='S').encode('latin-1')
        c_p.download_button("📄 Baixar PDF", data=pdf_b, file_name="Relatorio_V43.pdf")
        
        # ZIP Monitores
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for m in ["JOHN_DEERE", "TRIMBLE", "HORSCH"]:
                z.writestr(f"{m}/Prescricao_{sb['t_nome']}.csv", df_res.to_csv(index=False))
        c_z.download_button("📦 Exportar ZIP", data=buf.getvalue(), file_name="Triade_Monitores.zip")
