import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import base64

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- INTERFACE VISUAL (LOGIN E DADOS) ---
def aplicar_estilo(imagem_fundo):
    bin_str = get_base64(imagem_fundo)
    st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
        }}
        .glass {{
            background: rgba(0, 0, 0, 0.8); padding: 30px; border-radius: 15px;
            color: white; border: 1px solid #FFD700;
        }}
        </style>
    """, unsafe_allow_html=True)

# --- ABA 1: ATRIBUTOS (LÓGICA V43) ---
def aba_atributos():
    st.header("⚙️ Configuração de Atributos e Metas")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("⚪ Calcário e Gesso")
        cao = st.number_input("CaO %", value=36.0)
        mgo = st.number_input("MgO %", value=9.0)
        prnt = st.number_input("PRNT %", value=80.0)
        ca_ctc_des = st.number_input("Ca% desejado na CTC", value=60.0)
        mg_ctc_des = st.number_input("Mg% desejado na CTC", value=18.0)
        preco_ca = st.number_input("Preço Calcário (R$/ton)", value=190.0)
        st.write("---")
        fator_gesso = st.number_input("Fator Gesso (Argila * X)", value=15.0)
        g_min = st.number_input("Dose Mín Gesso", value=400.0)
        g_max = st.number_input("Dose Máx Gesso", value=900.0)
        preco_g = st.number_input("Preço Gesso (R$/ton)", value=400.0)

    with c2:
        st.subheader("🟠 Fósforo (P-Rem)")
        st.write("Níveis Críticos (mg/dm³):")
        nc = {
            "0-4": st.number_input("0 a 4", value=8.0),
            "4-10": st.number_input("4.1 a 10", value=10.0),
            "10-19": st.number_input("10.1 a 19", value=12.0),
            "19-30": st.number_input("19.1 a 30", value=15.0),
            "30-45": st.number_input("30.1 a 45", value=20.0),
            "45-60": st.number_input("45.1 a 60", value=25.0)
        }
        st.write("Fator Correção (kg P/ha para elevar 1mg):")
        f_text = {
            "Muito Arg": st.number_input(">60% Argila", value=10.0),
            "Argiloso": st.number_input("35-60% Argila", value=8.0),
            "Medio": st.number_input("15-35% Argila", value=4.0),
            "Arenoso": st.number_input("<15% Argila", value=2.0)
        }
        p_export_fator = st.number_input("Exportação P (kg/sc)", value=0.8)
        p_teor_adubo = st.number_input("% P2O5 no Adubo", value=21.0)
        p_preco = st.number_input("Preço Adubo P (R$/ton)", value=2800.0)

    with c3:
        st.subheader("🔴 Potássio e Produtividade")
        k_ctc_des = st.number_input("K% desejado na CTC", value=3.2)
        k_export_fator = st.number_input("Exportação K (kg/sc)", value=1.2)
        prod_esperada = st.number_input("Produtividade Meta (sc/ha)", value=80.0)
        k_teor_adubo = st.number_input("% K2O no Adubo (Ex: 60)", value=60.0)
        k_preco = st.number_input("Preço Adubo K (R$/ton)", value=2800.0)
    
    return locals()

# --- ABA 2: MAPAS DE FERTILIDADE ---
def aba_mapas_fertilidade(df):
    st.header("🔍 Mapas de Fertilidade")
    # Mapeamento conforme sua planilha (Colunas A-Y)
    colunas_excel = {
        'E': 'ARGILA', 'F': 'P-REM', 'G': 'P', 'H': 'CA', 'I': 'MG', 'J': 'K', 
        'U': 'CTC', 'V': 'CA%', 'W': 'MG%', 'X': 'K%'
    }
    
    palette_coolwarm = [[0, 'blue'], [0.25, 'cyan'], [0.5, 'yellow'], [0.75, 'orange'], [1, 'red']]
    
    for letra, nome in colunas_excel.items():
        if nome in df.columns:
            df_plot = df.dropna(subset=['LATITUDE', 'LONGITUDE', nome])
            if df_plot[nome].sum() == 0: continue # Ocultar se não houver dados
            
            st.subheader(f"Mapa de {nome}")
            fig = go.Figure(go.Histogram2dContour(
                x=df_plot['LONGITUDE'], y=df_plot['LATITUDE'], z=df_plot[nome],
                colorscale=palette_coolwarm, ncontours=6, line_width=0, connectgaps=True
            ))
            fig.update_layout(width=900, height=500, paper_bgcolor='white')
            st.plotly_chart(fig)
            st.caption(f"Mín: {df_plot[nome].min()} | Méd: {df_plot[nome].mean():.2f} | Máx: {df_plot[nome].max()}")

# --- FLUXO DE TELAS ---
if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

if not st.session_state.logado:
    aplicar_estilo("OI_AGRISHOW.jpg")
    st.markdown('<div class="glass" style="width:400px; margin:20vh auto; text-align:center;">', unsafe_allow_html=True)
    st.image("logoTriadetransparente.png", width=300)
    senha = st.text_input("Acesso", type="password")
    if st.button("ENTRAR"):
        if senha == "triade2026": st.session_state.logado = True; st.session_state.pagina = "dados"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "dados":
    aplicar_estilo("imagemaptriadefundo.png")
    st.markdown('<div class="glass" style="margin-top:10vh;">', unsafe_allow_html=True)
    st.title("⚙️ Configuração Inicial do Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: st.text_input("Produtor", key='prod')
    with c2: st.text_input("Fazenda", key='faz')
    with c3: st.text_input("Município", key='mun')
    
    up_geo = st.file_uploader("Contorno (.GEOJSON)", type=["geojson", "json"])
    up_xlsx = st.file_uploader("Planilha de Dados (.XLSX)", type=["xlsx"])
    
    if st.button("ABRIR PLATAFORMA"):
        if up_xlsx and up_geo:
            st.session_state.dados_excel = pd.read_excel(up_xlsx)
            st.session_state.contorno = json.load(up_geo)
            st.session_state.pagina = "plataforma"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{ background: white !important; }</style>", unsafe_allow_html=True)
    tabs = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE", "🗺️ ZONAS", "📄 RELATÓRIO"])
    
    with tabs[0]: config = aba_atributos()
    with tabs[1]: aba_mapas_fertilidade(st.session_state.dados_excel)
    with tabs[2]: st.write("Aba de Recomendações em Desenvolvimento com as fórmulas enviadas.")
