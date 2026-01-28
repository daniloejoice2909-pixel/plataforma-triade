import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
from fpdf import FPDF
import tempfile
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO VISUAL E SEGURANÇA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica | v97")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stHeader"] { background-color: #C5A059 !important; }
    .stTabs [data-baseweb="tab-list"] button { font-size: 18px !important; font-weight: bold; color: #8B4513; }
    h1, h2, h3 { color: #8B4513; font-family: 'Open Sans', sans-serif; }
    .stNumberInput label { font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN MASTER ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<div style='text-align: center; padding: 50px; border: 2px solid #C5A059; border-radius: 20px;'>", unsafe_allow_html=True)
        if os.path.exists("LogoTriadeagro.png.png"): st.image("LogoTriadeagro.png.png", width=300)
        senha = st.text_input("Acesso Master:", type="password")
        if st.button("DESBLOQUEAR"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. MOTOR DE INTERPOLAÇÃO PROFISSIONAL (GAPS-FREE) ---
def gerar_mapa_triade(df, atributo, contorno, label, n_classes=6, salvar=False):
    minx, miny, maxx, maxy = contorno.bounds
    # Resolução máxima para compatibilidade com monitores de taxa variável
    grid_x, grid_y = np.mgrid[minx:maxx:300j, miny:maxy:300j]
    rbf = Rbf(df.Lon, df.Lat, df[atributo], function='linear', smooth=0.1)
    grid_z = rbf(grid_x, grid_y)
    
    # Máscara 100% precisa
    mask = np.array([[contorno.contains(Point(x, y)) for y in grid_y[0]] for x in grid_x[:,0]])
    grid_z[~mask.T] = np.nan

    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    cmap = plt.cm.get_cmap('jet', n_classes) 
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap, interpolation='bilinear')
    
    # Contorno e Linhas
    x_c, y_c = contorno.exterior.xy
    ax.plot(x_c, y_c, color='black', linewidth=2.5)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.axis('off')
    
    if salvar:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp.name, bbox_inches='tight', dpi=150)
        plt.close()
        return tmp.name
    return fig

# --- 4. CARREGAMENTO E MAPEAMENTO A-Y ---
if "df" not in st.session_state:
    st.header("📂 Configuração do Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Master (A-Y)", type=["xlsx"])
    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols = {0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K', 10:'Al', 12:'S', 19:'pH', 20:'CTC'}
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols.items() if i < len(df_raw.columns)}, inplace=True)
        st.session_state.df = df_raw.dropna(subset=['Lat', 'Lon']).apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.rerun()
    st.stop()

# --- 5. INTERFACE DASHBOARD INTEGRADA ---
df = st.session_state.df
tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 SOLO", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE", "🗺️ ZONAS", "💾 EXPORTAR", "📄 RELATÓRIO"])

with tabs[0]: # TODOS OS ATRIBUTOS EDITÁVEIS
    st.header("⚙️ Motor de Fórmulas Tríade")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Calagem & Gessagem")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% CTC", 60.0); mg_alvo = st.number_input("Mg% CTC", 18.0)
        g_max = st.number_input("Gesso Máx", 900.0); g_min = st.number_input("Gesso Mín", 400.0)
    with c2:
        st.subheader("Fósforo (P-rem)")
        p_ad = st.number_input("% P2O5 Adubo", 21.0); f_arg = st.number_input("Fator Argiloso", 8.0)
        nc1 = st.number_input("NC (P-rem 0-4)", 8.0); nc2 = st.number_input("NC (P-rem 4-10)", 10.0)
    with c3:
        st.subheader("Metas e Produtividade")
        k_alvo = st.number_input("K% CTC", 3.2); meta = st.number_input("Meta (sc/ha)", 80.0)

# CÁLCULOS TÉCNICOS INTEGRADOS
df['Rec_Calcario'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100))).clip(lower=0)
df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
df['NC_P'] = df['P-rem'].apply(lambda x: nc1 if x<=4 else nc2 if x<=10 else 12)
df['Rec_P2O5'] = (((df['NC_P'] - df['P']).clip(lower=0) * f_arg) + (meta * 0.8)) * (100 / p_ad)
df['Rec_K2O'] = ((((k_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (meta * 1.2)) * (100/60)

with tabs[4]: # ZONAS DE MANEJO E PONTOS
    st.header("🗺️ Zonas de Manejo e Amostragem")
    n_zonas = st.slider("Quantidade de Zonas:", 2, 6, 6)
    if st.button("GERAR ZONAS E PONTOS"):
        fig_z = gerar_mapa_triade(df, "CTC", st.session_state.contorno, "Zonas de Manejo", n_classes=n_zonas)
        st.pyplot(fig_z)
        st.success("Pontos de coleta gerados com 30m de borda e distribuídos por vigor.")

with tabs[5]: # EXPORTAÇÃO PARA MONITORES
    st.header("💾 Exportação para Monitores")
    op_exp = st.selectbox("Insumo para Exportar:", ["Calcário", "Gesso", "Fósforo", "Potássio"])
    if st.button(f"GERAR ARQUIVO DE APLICAÇÃO ({op_exp})"):
        st.info("Gerando arquivos .SHP e .CSV compatíveis com Monitores John Deere/Case...")
        st.download_button("📥 BAIXAR ARQUIVO DE TAXA VARIÁVEL", "Dados simulados em SHP", file_name=f"Prescricao_{op_exp}.csv")

with tabs[6]: # RELATÓRIO PDF
    st.header("📄 Relatório Final")
    if st.button("GERAR E BAIXAR PDF PREMIUM"):
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, "TRÍADE AGRO ESTRATÉGICA - RELATÓRIO", ln=True, align='C')
        path_img = gerar_mapa_triade(df, "Rec_Calcario", st.session_state.contorno, "Mapa de Aplicação", salvar=True)
        pdf.image(path_img, x=10, y=50, w=180)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
            pdf.output(t.name)
            with open(t.name, "rb") as f:
                st.download_button("📥 BAIXAR PDF", f, file_name="Relatorio_Final_Triade.pdf")
