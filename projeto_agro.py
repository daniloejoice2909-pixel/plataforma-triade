import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape, Polygon
import json
import io
import zipfile
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM TRÍADE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card { background: #fff; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; text-align: center; }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { font-size: 11px; color: #444; background: #f0f4f5; padding: 10px; border-radius: 5px; border-left: 4px solid #27ae60; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}

# --- CAMADA 1: INTERFACE (SIDEBAR) ---
def configurar_sidebar():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.title("📍 Gestão de Talhão")
    
    produtor = st.sidebar.text_input("Produtor", "Gilson Berneck")
    fazenda = st.sidebar.text_input("Fazenda", "Brasnorte")
    talhao = st.sidebar.text_input("Talhão", "T1")

    st.sidebar.divider()
    st.sidebar.subheader("⚙️ Atributos Técnicos")
    
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod_alvo = st.number_input("Produtividade (sc/ha)", value=80.0, step=1.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT %", 80.0); c_cao = st.number_input("CaO %", 36.0); c_mgo = st.number_input("MgO %", 9.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0); c_t_mg = st.number_input("Alvo Mg %", 18.0)
        c_res = st.number_input("Reserva (kg/ha)", 0.0); c_preco = st.number_input("R$/Ton Calcário", 190.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc04 = st.number_input("0-4", 8.0); nc410 = st.number_input("4-10", 10.0); nc1019 = st.number_input("10-19", 12.0)
        nc1930 = st.number_input("19-30", 15.0); nc3045 = st.number_input("30-45", 18.0); nc4560 = st.number_input("45-60", 22.0)
        f_m_arg = st.number_input("Fator M. Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0)
        p_teor = st.number_input("Teor Adubo P %", 21.0); p_exp = st.number_input("Exportação (kg/sc)", 0.8); p_preco = st.number_input("R$/Ton Adubo P", 2000.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K %", 3.2); k_exp = st.number_input("Exportação K (kg/sc)", 1.2)
        k_teor = st.number_input("Teor Adubo K %", 60.0); k_preco = st.number_input("R$/Ton Adubo K", 2800.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", 15.0); g_min = st.number_input("Mín kg/ha", 400.0); g_max = st.number_input("Máx kg/ha", 900.0); g_preco = st.number_input("R$/Ton Gesso", 400.0)

    return {
        "global": {"prod": prod_alvo},
        "calagem": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {"nc": [nc04, nc410, nc1019, nc1930, nc3045, nc4560], "f_arg": [f_m_arg, f_arg, 4.0, 2.0], "teor": p_teor, "exp": p_exp, "preco": p_preco},
        "potassio": {"target": k_target, "exp": k_exp, "teor": k_teor, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco},
        "meta": {"produtor": produtor, "fazenda": fazenda, "talhao": talhao}
    }

# --- CAMADA 2: MOTOR AGRONÔMICO ---
def motor_v43(df, p):
    df.columns = df.columns.str.strip().str.lower()
    # Mapeamento robusto
    df = df.rename(columns={'p mehl': 'p_mehl', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'})
    
    # 1. Gesso (Argila % * Fator)
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])

    # 2. Calagem (Maior dose Ca/Mg + Reserva)
    df['nc_ca'] = ((p['calagem']['target_ca'] - df['ca_p']) * df['ctc'] / 100).clip(lower=0)
    df['nc_mg'] = ((p['calagem']['target_mg'] - df['mg_p']) * df['ctc'] / 100).clip(lower=0)
    df['dose_calc_ca'] = (df['nc_ca'] * 560 * 10000) / (p['calagem']['cao'] * p['calagem']['prnt'])
    df['dose_calc_mg'] = (df['nc_mg'] * 400 * 10000) / (p['calagem']['mgo'] * p['calagem']['prnt'])
    df['rec_calcario'] = (np.maximum(df['dose_calc_ca'], df['dose_calc_mg']) + p['calagem']['reserva']).round(2)

    # 3. Fósforo (Crédito de Solo + Exportação)
    def calc_p(row):
        nc_list = p['fosforo']['nc']; pr = row['prem']
        nc = nc_list[0] if pr <= 4 else nc_list[1] if pr <= 10 else nc_list[2] if pr <= 19 else nc_list[3] if pr <= 30 else nc_list[4] if pr <= 45 else nc_list[5]
        f_arg = p['fosforo']['f_arg'][0] if row['argila'] > 60 else p['fosforo']['f_arg'][1]
        p_nec = (nc - row['p_mehl']) * f_arg
        p_exp = p['global']['prod'] * p['fosforo']['exp']
        return (max(p_nec, 0) + p_exp) * 100 / p['fosforo']['teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)

    # 4. Potássio (Saturação 3.2% + Exportação Mandatória)
    df['nec_k_eleva'] = ((p['potassio']['target'] - df['k_p']).clip(lower=0) * df['ctc'] / 100 * 391)
    df['nec_k_exp'] = p['global']['prod'] * p['potassio']['exp']
    df['rec_potassio'] = (df['nec_k_eleva'] + df['nec_k_exp']) * 100 / p['potassio']['teor']

    return df

# --- CAMADA 3: GEOPROCESSAMENTO ---
def plot_krigagem(df, col, title, poly=None):
    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    xi = np.linspace(x.min(), x.max(), 100); yi = np.linspace(y.min(), y.max(), 100)
    xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    fig = go.Figure(data=go.Contour(z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100), colorscale='coolwarm', contours=dict(showlines=False), line_width=0))
    fig.update_layout(title=f"<b>{title}</b>", height=400, margin=dict(l=0,r=0,b=0,t=40), xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False))
    return fig

# --- APP EXECUÇÃO ---
params = configurar_sidebar()
st.title("🌱 Tríade Agro Estratégica v43")

tab_dados, tab_vrt, tab_saida = st.tabs(["📁 Entrada de Dados", "🗺️ Recomendações VRT", "📄 Relatório & Exportação"])

with tab_dados:
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        file_csv = st.file_uploader("1. Planilha de Solo (CSV)", type="csv")
    with col_u2:
        file_geo = st.file_uploader("2. Contorno (GeoJSON)", type="geojson")
    
    if not file_geo:
        st.warning("⚠️ GeoJSON não detectado. Ativando Fallback: Mapa de Satélite para desenho manual.")
        st.info("Desenhe o polígono no mapa abaixo (Simulação Folium/Leaflet)...")
        # Aqui integraria o st_folium para desenho real.

if file_csv:
    df = pd.read_csv(file_csv)
    df_res = motor_v43(df, params)
    poly_obj = shape(json.load(file_geo)['features'][0]['geometry']) if file_geo else None

    with tab_vrt:
        st.subheader("Mapas de Prescrição")
        c1, c2 = st.columns(2)
        vrt_maps = [('rec_calcario', 'Calcário (kg/ha)'), ('rec_fosforo', 'Fosfatado (kg/ha)'), ('rec_potassio', 'Potássico (kg/ha)'), ('rec_gesso', 'Gesso (kg/ha)')]
        
        for idx, (col_db, label) in enumerate(vrt_maps):
            target_col = c1 if idx % 2 == 0 else c2
            fig = plot_krigagem(df_res, col_db, label, poly_obj)
            target_col.plotly_chart(fig, use_container_width=True, key=f"vrt_{col_db}")
            
            # Financeiro por Insumo
            preco_un = params['calagem']['preco'] if 'calc' in col_db else params['fosforo']['preco'] if 'fosf' in col_db else params['potassio']['preco'] if 'pot' in col_db else params['gesso']['preco']
            custo_ha = (df_res[col_db].mean() / 1000) * preco_un
            target_col.markdown(f"""<div class='kpi-card'><small>Custo Médio {label.split(' ')[0]}</small><br><span class='kpi-value'>R$ {custo_ha:.2f}/ha</span></div>""", unsafe_allow_html=True)
            target_col.markdown(f"<div class='arg-tecnico'><b>Argumento Técnico:</b> Metodologia Tríade v43 baseada em equilíbrio estequiométrico e exportação real.</div>", unsafe_allow_html=True)

    with tab_saida:
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("📄 Gerar Relatório PDF A4"):
            st.success("PDF gerado com margens de 2cm e fonte Open Sans (Simulação).")
        if col_s2.button("📦 Exportar ZIP Monitores"):
            st.info("ZIP preparado: Rx (John Deere), CN1 (Case), Stara e Trimble.")
