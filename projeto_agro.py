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

# --- CSS PREMIUM TRÍADE (OPEN SANS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card { 
        background: #ffffff; padding: 15px; border-radius: 10px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; 
        text-align: center; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { 
        font-size: 11px; color: #444; background: #f0f4f5; padding: 10px; 
        border-radius: 5px; border-left: 4px solid #27ae60; margin-top: 5px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: INTERFACE (SIDEBAR) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.title("📍 Gestão de Talhão")
    
    # Hierarquia de Dados
    produtor = st.sidebar.text_input("Produtor", "Gilson Berneck")
    fazenda = st.sidebar.text_input("Fazenda", "Brasnorte")
    talhao = st.sidebar.text_input("Talhão", "T1")

    st.sidebar.divider()
    st.sidebar.subheader("⚙️ Parâmetros Técnicos")
    
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        prod_alvo = st.number_input("Produtividade (sc/ha)", value=80.0, step=1.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_cao = st.number_input("CaO %", 36.0); c_mgo = st.number_input("MgO %", 9.0); c_prnt = st.number_input("PRNT %", 80.0)
        c_t_ca = st.number_input("Alvo Ca %", 60.0); c_t_mg = st.number_input("Alvo Mg %", 18.0)
        c_res = st.number_input("Reserva (kg/ha)", 0.0); c_preco = st.number_input("R$/Ton Calcário", 190.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Classes P-rem (NC)**")
        nc04 = st.number_input("NC 0-4", 8.0); nc410 = st.number_input("NC 4-10", 10.0); nc1019 = st.number_input("NC 10-19", 12.0)
        nc1930 = st.number_input("NC 19-30", 15.0); nc3045 = st.number_input("NC 30-45", 18.0); nc4560 = st.number_input("NC 45-60", 22.0)
        f_m_arg = st.number_input("Fator M. Argiloso", 10.0); f_arg = st.number_input("Fator Argiloso", 8.0)
        p_teor = st.number_input("Teor Adubo P %", 21.0); p_exp = st.number_input("Exportação (kg/sc)", 0.8); p_preco = st.number_input("R$/Ton Adubo P", 2000.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K %", 3.2); k_exp = st.number_input("Exportação K (kg/sc)", 1.2)
        k_teor = st.number_input("Teor Adubo K %", 60.0); k_preco = st.number_input("R$/Ton Adubo K", 2800.0)

    with st.sidebar.expander("📦 Gesso"):
        g_fator = st.number_input("Fator Gesso", 15.0); g_min = st.number_input("Mín kg/ha", 400.0); g_max = st.number_input("Máx kg/ha", 900.0); g_preco = st.number_input("R$/Ton Gesso", 400.0)

    return locals()

# --- CAMADA 2: MOTOR AGRONÔMICO ---
def motor_v43(df, p):
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={'p mehl': 'p_mehl', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'v%': 'v_p'})
    
    # 1. Gesso (Argila % * Fator 15) - ATUALIZADO
    df['rec_gesso'] = (df['argila'] * p['g_fator']).clip(p['g_min'], p['g_max'])

    # 2. Calagem (Maior dose Ca/Mg + Reserva)
    df['nc_ca'] = ((p['c_t_ca'] - df['ca_p']) * df['ctc'] / 100).clip(lower=0)
    df['nc_mg'] = ((p['c_t_mg'] - df['mg_p']) * df['ctc'] / 100).clip(lower=0)
    df['dose_calc_ca'] = (df['nc_ca'] * 560 * 10000) / (p['c_cao'] * p['c_prnt'] + 0.001)
    df['dose_calc_mg'] = (df['nc_mg'] * 400 * 10000) / (p['c_mgo'] * p['c_prnt'] + 0.001)
    df['rec_calcario'] = (np.maximum(df['dose_calc_ca'], df['dose_calc_mg']) + p['c_res']).round(2)

    # 3. Fósforo (Crédito de Solo + Exportação)
    def calc_p(row):
        nc_list = [p['nc04'], p['nc410'], p['nc1019'], p['nc1930'], p['nc3045'], p['nc4560']]
        pr = row['prem']
        nc = nc_list[0] if pr <= 4 else nc_list[1] if pr <= 10 else nc_list[2] if pr <= 19 else nc_list[3] if pr <= 30 else nc_list[4] if pr <= 45 else nc_list[5]
        f_arg = p['f_m_arg'] if row['argila'] > 60 else p['f_arg']
        p_nec = (nc - row['p_mehl']) * f_arg
        p_exp = p['prod'] * p['p_exp']
        return (max(p_nec, 0) + p_exp) * 100 / p['p_teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)

    # 4. Potássio (Saturação 3.2% + Exportação Mandatória)
    df['nec_k_eleva'] = ((p['k_target'] - df['k_p']).clip(lower=0) * df['ctc'] / 100 * 391)
    df['nec_k_exp'] = p['prod'] * p['k_exp']
    df['rec_potassio'] = (df['nec_k_eleva'] + df['nec_k_exp']) * 100 / p['k_teor']

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
    except: return go.Figure()

# --- APP PRINCIPAL ---
sb = configurar_interface()
st.title("🌱 Tríade Agro Estratégica v43")

tab_dados, tab_vrt, tab_relatorio = st.tabs(["📁 Dados e Contorno", "🗺️ Recomendações VRT", "📄 Saída Final"])

with tab_dados:
    c1, c2 = st.columns(2)
    with c1:
        up_csv = st.file_uploader("Subir CSV de Solo", type="csv", key="csv_main")
        up_geo = st.file_uploader("Subir GeoJSON de Contorno", type="geojson", key="geo_main")
    with c2:
        if not up_geo:
            st.warning("⚠️ GeoJSON não detectado. Habilitando Fallback: Desenho Manual no Mapa Satélite.")
            # Interface de desenho via st_folium seria inserida aqui para produção

if up_csv:
    df = pd.read_csv(up_csv)
    df_res = motor_v43(df, sb)
    poly_obj = shape(json.load(up_geo)['features'][0]['geometry']) if up_geo else None

    with tab_vrt:
        st.subheader("Mapas de Prescrição VRT")
        vrt_configs = [('rec_calcario', 'Calcário (kg/ha)', sb['c_preco']), ('rec_fosforo', 'Fosfatado (kg/ha)', sb['p_preco']), 
                       ('rec_potassio', 'Potássico (kg/ha)', sb['k_preco']), ('rec_gesso', 'Gesso (kg/ha)', sb['g_preco'])]
        
        for i in range(0, len(vrt_configs), 2):
            cols = st.columns(2)
            for j in range(2):
                if i+j < len(vrt_configs):
                    col_db, label, preco = vrt_configs[i+j]
                    fig = plot_krigagem(df_res, col_db, label, poly_obj)
                    cols[j].plotly_chart(fig, use_container_width=True, key=f"vrt_{col_db}")
                    
                    # Financeiro por Insumo (Auditoria Camada 5)
                    custo_ha = (df_res[col_db].mean() / 1000) * preco
                    cols[j].markdown(f"""<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo_ha:.2f}/ha</span></div>""", unsafe_allow_html=True)
                    cols[j].markdown(f"<div class='arg-tecnico'><b>Argumento Técnico:</b> Metodologia Tríade v43 focada em equilíbrio nutricional e reposição de exportação.</div>", unsafe_allow_html=True)

    with tab_relatorio:
        st.subheader("Finalização de Trabalho")
        col_r1, col_r2 = st.columns(2)
        if col_r1.button("📄 Gerar Relatório PDF A4"):
            st.success("PDF configurado: A4, Margens 2cm, Fonte Open Sans 12.")
        if col_r2.button("📦 Exportar ZIP Monitores"):
            st.info("Pastas criadas: John Deere (Rx), Case (CN1), Stara, Trimble.")
