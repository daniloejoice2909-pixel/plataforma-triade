import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json
import os

# --- 1. CONFIGURAÇÃO VISUAL (A4, MARGENS 2CM, OPEN SANS) ---
st.set_page_config(layout="wide", page_title="Tríade Agro - v144.0")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }

    .titulo-relatorio { 
        font-size: 13pt; font-weight: 700; text-transform: uppercase; 
        margin-top: 15px; margin-bottom: 5px; color: #000;
    }
    .texto-corpo { 
        font-size: 12pt; text-align: justify; line-height: 1.4; margin-bottom: 8px;
    }
    .estatistica-container {
        font-size: 12pt; font-weight: 700; color: #1a1a1a;
        margin-top: -10px; margin-bottom: 15px; text-align: center;
        text-transform: uppercase; background-color: #f8f9fa; padding: 5px;
    }
    .page-break { page-break-before: always; }

    @media print {
        @page { size: A4; margin: 2cm; }
        .no-print, header, .stTabs, .stFileUploader, .stExpander, .stButton, .stSelectbox { display: none !important; }
        .main .block-container { padding: 0 !important; margin: 0 !important; }
        .section-container { page-break-inside: avoid; margin-bottom: 20px; border-bottom: 0.5px solid #eee; }
        .capa-container { height: 95vh; display: flex; flex-direction: column; justify-content: center; align-items: center; page-break-after: always; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INTERFACE DE ENTRADA (ATRIBUTOS VISÍVEIS) ---
LOGO_PATH = "LogoTriadeInceres.png"
st.markdown('<div class="no-print">', unsafe_allow_html=True)
if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=220)
st.title("Plataforma v43 - Relatório de Fertilidade")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("**⚪ Calagem**")
    prnt = st.number_input("PRNT (%)", value=80.0)
    v_ca_alvo = st.number_input("Alvo Ca (%)", value=60.0)
    v_mg_alvo = st.number_input("Alvo Mg (%)", value=18.0)
with c2:
    st.markdown("**🧪 Fósforo**")
    f_m_arg = st.number_input("Fator Mt Arg", value=10.0)
    f_arg = st.number_input("Fator Arg", value=8.0)
    teor_p_prod = st.number_input("% P2O5 no Adubo", value=52.0)
with c3:
    st.markdown("**🌿 Potássio & Metas**")
    v_k_alvo = st.number_input("Alvo K (%)", value=3.2)
    prod_alvo = st.number_input("Meta (sc/ha)", value=80.0)
    teor_k_prod = st.number_input("% K2O no KCl", value=60.0)
with c4:
    st.markdown("**🚜 Gesso & Exportação**")
    f_gesso = st.number_input("Fator Gesso", value=15.0)
    exp_p = st.number_input("Exp. P2O5 (kg/sc)", value=0.8)
    exp_k = st.number_input("Exp. K2O (kg/sc)", value=1.2)

u1, u2 = st.columns(2)
up_geo = u1.file_uploader("📂 GeoJSON do Talhão", type=["json", "geojson"])
up_ex = u2.file_uploader("📊 Dados de Solo (Excel)", type=["xlsx"])
st.markdown('</div>', unsafe_allow_html=True)

# --- 3. MOTOR DE PROCESSAMENTO ---
if up_ex and up_geo:
    data_geo = json.load(up_geo)
    poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
    df = pd.read_excel(up_ex).apply(pd.to_numeric, errors='coerce').fillna(0)
    
    # Mapeamento de Colunas (CTC na Coluna U = Índice 20)
    lat, lon = df.iloc[:,0], df.iloc[:,1]
    arg, p_rem, p_solo = df.iloc[:,4], df.iloc[:,5], df.iloc[:,6]
    ca, mg, k, al = df.iloc[:,7], df.iloc[:,8], df.iloc[:,9], df.iloc[:,10]
    ctc = df.iloc[:,20] 

    # Cálculos v43
    df['REC_CALCARIO'] = (np.maximum(((v_ca_alvo/100*ctc)-ca)*0.56*(100/36), ((v_mg_alvo/100*ctc)-mg)*0.40*(100/9)) * 1000 * (100/prnt)).clip(lower=0)
    conds_p = [(p_rem <= 4), (p_rem <= 10), (p_rem <= 19), (p_rem <= 30), (p_rem <= 44), (p_rem > 44)]
    nc_p = np.select(conds_p, [6.0, 8.0, 10.0, 12.0, 15.0, 20.0])
    f_p_val = np.select(conds_p, [f_m_arg, f_m_arg, f_arg, f_arg, 4.0, 2.0])
    df['REC_ADUBO_P'] = (((nc_p - p_solo) * f_p_val) + (prod_alvo * exp_p)) / (teor_p_prod/100)
    df['REC_ADUBO_K'] = (((v_k_alvo/100 * ctc) - k).clip(lower=0) * 1200 + (prod_alvo * exp_k)) / (teor_k_prod/100)
    df['REC_GESSO'] = ((arg / 10) * f_gesso).clip(lower=0)

    def plot_map_v43(data_vals, unit=""):
        b = poligono.bounds
        gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:300j, b[1]-0.0006:b[3]+0.0006:300j]
        rbf = Rbf(lon, lat, data_vals, function='multiquadric', smooth=0.1)
        z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
        
        fig, ax = plt.subplots(figsize=(8.5, 5)) 
        cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
        ax.plot(*poligono.exterior.xy, color='black', linewidth=1.5)
        ax.set_aspect('equal')
        cbar = plt.colorbar(cp, fraction=0.03, pad=0.04)
        cbar.ax.tick_params(labelsize=10)
        ax.axis('off')
        st.pyplot(fig)
        plt.close()
        st.markdown(f'<div class="estatistica-container">MÍN: {data_vals.min():.1f} | MÉD: {data_vals.mean():.1f} | MÁX: {data_vals.max():.1f} ({unit})</div>', unsafe_allow_html=True)

    # --- 4. RELATÓRIO PDF (ESTRUTURA A4) ---
    st.markdown('<div class="capa-container">', unsafe_allow_html=True)
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=450)
    st.markdown(f'<div class="titulo-relatorio" style="font-size:28pt; text-align:center;">RELATÓRIO TÉCNICO ESTRATÉGICO</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="texto-corpo" style="text-align:center; font-size:16pt;">SAFRA 2026 | UNIDADE DE GESTÃO DIFERENCIADA</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # SEÇÃO 1: DIAGNÓSTICO
    st.markdown('<div class="titulo-relatorio">1. MAPAS DE DIAGNÓSTICO DE FERTILIDADE</div>', unsafe_allow_html=True)
    st.markdown('<div class="texto-corpo">Abaixo, a caracterização espacial dos atributos químicos e físicos. O uso de 6 zonas de manejo permite identificar manchas de compactação ou exaustão nutricional com alta precisão.</div>', unsafe_allow_html=True)
    
    diagnosticos = [
        (arg, "ARGILA", "g/kg", "Essencial para determinar a CTC potencial e retenção hídrica."),
        (ctc, "CTC TOTAL (Coluna U)", "cmolc/dm³", "Capacidade total do solo em reter cátions para a planta."),
        (p_solo, "FÓSFORO (Mehlich-1)", "mg/dm³", "Disponibilidade imediata para o arranque da cultura."),
        (p_rem, "P-REMANESCENTE", "mg/L", "Indicador do poder de adsorção de Fósforo no solo."),
        (ca, "CÁLCIO", "cmolc/dm³", "Cátion fundamental para o crescimento radicular e parede celular."),
        (mg, "MAGNÉSIO", "cmolc/dm³", "Elemento central da molécula de clorofila."),
        (k, "POTÁSSIO", "cmolc/dm³", "Ativador enzimático e regulador do balanço hídrico."),
        (al, "ALUMÍNIO", "cmolc/dm³", "Indicador de toxicidade que limita o desenvolvimento radicular.")
    ]

    for d, t, u, desc in diagnosticos:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown(f'<div class="titulo-relatorio" style="font-size:11pt;">{t}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="texto-corpo">{desc}</div>', unsafe_allow_html=True)
        plot_map_v43(d, u)
        st.markdown('</div>', unsafe_allow_html=True)

    # SEÇÃO 2: RECOMENDAÇÕES
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True)
    st.markdown('<div class="titulo-relatorio">2. PRESCRIÇÕES DE MANEJO (METODOLOGIA v43)</div>', unsafe_allow_html=True)
    st.markdown('<div class="texto-corpo">As recomendações abaixo superam o método convencional por considerar o equilíbrio de bases e a exportação real da meta de produtividade estabelecida.</div>', unsafe_allow_html=True)

    prescricoes = [
        (df['REC_CALCARIO'], "RECOMENDAÇÃO DE CALCÁRIO", "kg/ha", "Ajuste por saturação de bases visando Ca (60%) e Mg (18%)."),
        (df['REC_ADUBO_P'], "RECOMENDAÇÃO DE FÓSFORO", "kg/ha", "Cálculo dinâmico baseado no P-Rem e meta produtiva."),
        (df['REC_ADUBO_K'], "RECOMENDAÇÃO DE POTÁSSIO", "kg/ha", "Reposição de exportação e elevação para 3,2% da CTC."),
        (df['REC_GESSO'], "RECOMENDAÇÃO DE GESSO", "kg/ha", "Melhoria do ambiente radicular em subsuperfície via argila.")
    ]

    for d, t, u, desc in prescricoes:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown(f'<div class="titulo-relatorio" style="font-size:11pt;">{t}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="texto-corpo">{desc}</div>', unsafe_allow_html=True)
        plot_map_v43(d, u)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="no-print">', unsafe_allow_html=True)
    st.success("🚀 Relatório Completo Gerado! Use Ctrl+P para salvar em PDF.")
    st.markdown('</div>', unsafe_allow_html=True)