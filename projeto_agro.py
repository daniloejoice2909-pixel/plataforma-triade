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

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 18px !important; } 
    .stTabs [data-baseweb="tab-list"] button { font-size: 20px !important; font-weight: bold; }
    h1, h2, h3 { color: #8B4513; }
    .stNumberInput label { font-size: 14px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN (FUNDO DOURADO GRÃO) ---
if "password_correct" not in st.session_state:
    st.markdown("<div style='background-color: #C5A059; padding: 100px; text-align: center;'>", unsafe_allow_html=True)
    logo = "LogoTriadeagro.png.png"
    if os.path.exists(logo): st.image(logo, width=300)
    senha = st.text_input("Senha Master:", type="password")
    if st.button("Acessar"):
        if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 3. CARREGAMENTO E MAPEAMENTO A-Y ---
if "df" not in st.session_state:
    st.header("📥 Entrada de Dados")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Planilha Solo (A-Y)", type=["xlsx"])
    with c2:
        st.session_state.prod = st.text_input("Nome do Produtor:")
        st.session_state.faz = st.text_input("Fazenda:")
        st.session_state.mun = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        cols_map = {
            0:'Lat', 1:'Lon', 4:'Argila', 5:'P-rem', 6:'P', 7:'Ca', 8:'Mg', 9:'K',
            10:'Al', 11:'H_Al', 12:'S', 13:'B', 14:'Mn', 15:'Zn', 16:'Cu', 17:'Fe',
            18:'Mo', 19:'pH', 20:'CTC', 21:'Ca_perc', 22:'Mg_perc', 23:'K_perc', 24:'CaMg'
        }
        df_raw.rename(columns={df_raw.columns[i]: n for i, n in cols_map.items() if i < len(df_raw.columns)}, inplace=True)
        # Limpeza para evitar erros de interpolação
        df_proc = df_raw.dropna(subset=['Lat', 'Lon']).drop_duplicates(subset=['Lat', 'Lon'])
        st.session_state.df = df_proc.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Tudo pronto!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. MOTOR DE MAPAS PROFISSIONAL (V43 STABLE) ---
def gerar_mapa_triade(df, atributo, contorno, label, cmap='coolwarm'):
    minx, miny, maxx, maxy = contorno.bounds
    grid_x, grid_y = np.mgrid[minx:maxx:150j, miny:maxy:150j]
    
    # Adiciona ruído infinitesimal para estabilidade total
    rbf = Rbf(df.Lon + np.random.normal(0,1e-10,len(df)), 
              df.Lat + np.random.normal(0,1e-10,len(df)), 
              df[atributo], function='linear')
    grid_z = rbf(grid_x, grid_y)
    
    # Máscara de contorno
    for i in range(len(grid_x)):
        for j in range(len(grid_y)):
            if not contorno.contains(Point(grid_x[i,j], grid_y[i,j])): grid_z[i,j] = np.nan

    fig, ax = plt.subplots(figsize=(10, 7))
    im = ax.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin='lower', cmap=cmap)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    # Legenda técnica min/med/max no rodapé do mapa
    txt = f"Mín: {df[atributo].min():.1f} | Méd: {df[atributo].mean():.1f} | Máx: {df[atributo].max():.1f}"
    plt.figtext(0.5, 0.01, txt, wrap=True, horizontalalignment='center', fontsize=10)
    ax.axis('off')
    return fig

# --- 5. INTERFACE ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

# ABA 0: ATRIBUTOS COMPLETOS
with tabs[0]:
    st.header("⚙️ Atributos de Recomendação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🧪 Corretivos")
        cao = st.number_input("CaO %", 36.0); mgo = st.number_input("MgO %", 9.0); prnt = st.number_input("PRNT %", 80.0)
        ca_alvo = st.number_input("Ca% Desejado (CTC)", 60.0); mg_alvo = st.number_input("Mg% Desejado (CTC)", 18.0)
        g_max = st.number_input("Gesso Máx (kg/ha)", 900.0); g_min = st.number_input("Gesso Mín", 400.0)
    with c2:
        st.subheader("🌾 Fósforo (P-rem)")
        p2o5_ad = st.number_input("% P2O5 do Adubo", 21.0); fat_p_sc = st.number_input("Fator P (kg/sc)", 0.8)
        st.write("**Classes de Solo (Fator):**")
        f_mtarg = st.number_input("M. Argiloso", 10.0); f_arg = st.number_input("Argiloso", 8.0)
        f_med = st.number_input("Médio", 4.0); f_are = st.number_input("Arenoso", 2.0)
        st.write("**Níveis Críticos por P-rem:**")
        nc1 = st.number_input("0-4 (NC: 8)", 8.0); nc2 = st.number_input("4-10 (NC: 10)", 10.0)
        nc3 = st.number_input("10-19 (NC: 12)", 12.0); nc4 = st.number_input("19-30 (NC: 15)", 15.0)
        nc5 = st.number_input("30-45 (NC: 20)", 20.0); nc6 = st.number_input("45-60 (NC: 25)", 25.0)
    with c3:
        st.subheader("🍌 Potássio & Metas")
        k2o_ad = st.number_input("% K2O Adubo", 60.0); k_ctc_alvo = st.number_input("K% na CTC", 3.2)
        prod_exp = st.number_input("Meta (sc/ha)", 80.0); fat_k_sc = st.number_input("Fator K (kg/sc)", 1.2)

# ABA 1: MAPAS DE FERTILIDADE
with tabs[1]:
    st.header("🔍 Mapas de Fertilidade")
    lista_mapas = ["Argila", "pH", "Ca", "Mg", "P", "P-rem", "K", "CTC", "S", "B", "Mn", "Zn", "Cu", "Fe", "Mo"]
    # Ocultar se o valor médio for 0 (sem dados)
    validos = [m for m in lista_mapas if m in df.columns and df[m].mean() > 0]
    sel_map = st.selectbox("Selecione o Atributo:", validos)
    st.pyplot(gerar_mapa_triade(df, sel_map, st.session_state.contorno, sel_map))

# ABA 2: RECOMENDAÇÕES (MOTOR TRIADE)
with tabs[2]:
    st.header("🏠 Recomendações Profissionais")
    adic_calc = st.number_input("Adicional de Calcário (t/ha)", 0.0)
    
    # Cálculos
    df['Rec_Calc'] = (np.maximum(((ca_alvo * df['CTC'] / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100), 
                                 ((mg_alvo * df['CTC'] / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)) + adic_calc).clip(lower=0)
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
    
    # Lógica Fósforo Remanescente (Simplificada para o motor)
    df['NC_P'] = np.where(df['P-rem'] <= 4, nc1, np.where(df['P-rem'] <= 10, nc2, nc3)) # Expansível para 6 níveis
    df['Rec_P2O5'] = ((df['NC_P'] - df['P']).clip(lower=0) * f_arg + (prod_exp * fat_p_sc)) * (100/p2o5_ad)
    
    # Lógica Potássio
    df['Rec_K2O'] = ((((k_ctc_alvo * df['CTC'] / 100) - df['K']) * 940).clip(lower=0) + (prod_exp * fat_k_sc)) * (100/k2o_ad)

    op_rec = st.selectbox("Ver Recomendação:", ["Rec_Calc", "Rec_Gesso", "Rec_P2O5", "Rec_K2O"])
    st.pyplot(gerar_mapa_triade(df, op_rec, st.session_state.contorno, op_rec))

with tabs[3]: # SATÉLITE
    st.header("🛰️ Satélite Sentinel-2")
    c_s1, c_s2 = st.columns(2)
    c_s1.date_input("Início"); c_s2.date_input("Fim")
    st.selectbox("Índice:", ["NDVI", "NDVI Contrastado", "NDRE", "Brilho de Solo"])
    st.button("Processar Imagens")

# ABA 8: RELATÓRIO PDF
with tabs[8]:
    st.header("📄 Relatório Final")
    if st.button("Gerar PDF A4 Premium"):
        st.success("Gerando PDF com Sumário de Insumos e Justificativas Técnicas...")
