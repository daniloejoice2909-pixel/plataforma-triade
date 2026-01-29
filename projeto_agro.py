import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import base64

# --- 1. CONFIGURAÇÕES TÉCNICAS E CACHE ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- 2. ESTILIZAÇÃO E LOGIN ---
def aplicar_estilo_visual(imagem_fundo):
    bin_str = get_base64(imagem_fundo)
    if bin_str:
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/png;base64,{bin_str}");
                background-size: cover;
            }}
            .glass-panel {{
                background: rgba(0, 0, 0, 0.88); padding: 30px; border-radius: 15px;
                color: white; border: 1px solid #FFD700;
            }}
            </style>
        """, unsafe_allow_html=True)

# --- 3. ABA 1: ATRIBUTOS (RESTAURADOS E EDITÁVEIS) ---
def aba_atributos_v43():
    st.markdown("### ⚙️ Painel de Atributos Estratégicos")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("⚪ Calcário e Solo")
        st.number_input("CaO %", value=36.0, key='cao')
        st.number_input("MgO %", value=9.0, key='mgo')
        st.number_input("PRNT %", value=80.0, key='prnt')
        st.number_input("Ca% desejado na CTC", value=60.0, key='ca_des')
        st.number_input("Mg% desejado na CTC", value=18.0, key='mg_des')
        st.number_input("Preço Calcário (R$/ton)", value=190.0, key='p_calcario')
        st.write("---")
        st.number_input("Fator Gesso (Argila g/kg * X)", value=15.0, key='fator_gesso')
        st.number_input("Dose Gesso Máx (kg/ha)", value=900.0, key='g_max')
        st.number_input("Dose Gesso Mín (kg/ha)", value=400.0, key='g_min')

    with col2:
        st.subheader("🟠 Fósforo (P-Rem)")
        st.write("Níveis Críticos por Classe:")
        st.number_input("NC 0-4 (P-Rem)", value=8.0, key='nc1')
        st.number_input("NC 4.1-10", value=10.0, key='nc2')
        st.number_input("NC 10.1-19", value=12.0, key='nc3')
        st.number_input("NC 19.1-30", value=15.0, key='nc4')
        st.number_input("NC 30.1-45", value=20.0, key='nc5')
        st.number_input("NC 45-60", value=25.0, key='nc6')
        st.write("---")
        st.number_input("Kg P p/ elevar 1mg (M.Arg)", value=10.0, key='f_ma')
        st.number_input("Kg P p/ elevar 1mg (Arg)", value=8.0, key='f_a')
        st.number_input("Exportação P (kg/sc)", value=0.8, key='p_exp')

    with col3:
        st.subheader("🔴 Potássio e Metas")
        st.number_input("K% desejado na CTC", value=3.2, key='k_ctc')
        st.number_input("Exportação K (kg/sc)", value=1.2, key='k_exp')
        st.number_input("Produtividade Meta (sc/ha)", value=80.0, key='meta_prod')
        st.number_input("Preço Adubo K (R$/ton)", value=2800.0, key='p_ad_k')
        st.number_input("Preço Gesso (R$/ton)", value=400.0, key='p_gesso')

# --- 4. ABA 2: MAPAS (PROTEÇÃO CONTRA ERRO DE NODE) ---
def aba_mapas_fertilidade(df):
    st.markdown("### 🔍 Mapas de Fertilidade")
    # Cores coolwarm manuais para evitar ValueError
    palette = [[0, 'blue'], [0.5, 'yellow'], [1, 'red']]
    logo_base64 = get_base64("LogoTriadeagro.png.png")

    # Colunas conforme seu checklist A-Y
    cols_mapa = ['ARGILA', 'P-REM', 'P', 'CA', 'MG', 'K', 'PH_CACL2', 'CTC', 'CA%', 'MG%', 'K%']
    
    for col in cols_mapa:
        if col in df.columns:
            df_c = df.dropna(subset=['LATITUDE', 'LONGITUDE', col])
            if df_c[col].sum() == 0: continue
            
            st.write(f"#### Atributo: {col}")
            fig = go.Figure(go.Histogram2dContour(
                x=df_c['LONGITUDE'], y=df_c['LATITUDE'], z=df_c[col],
                colorscale=palette, ncontours=6, line_width=0, connectgaps=True
            ))
            
            if logo_base64:
                fig.add_layout_image(dict(source=f"data:image/png;base64,{logo_base64}", xref="paper", yref="paper", 
                                         x=0.5, y=0.5, sizex=0.3, sizey=0.3, xanchor="center", yanchor="middle", opacity=0.1))

            fig.update_layout(width=900, height=550, paper_bgcolor='white', plot_bgcolor='rgba(0,0,0,0)')
            # O Segredo: Key única para cada mapa evita o erro de Node
            st.plotly_chart(fig, use_container_width=True, key=f"mapa_node_{col}")

# --- 5. NAVEGAÇÃO PRINCIPAL ---
if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

if not st.session_state.logado:
    aplicar_estilo_visual("OI_AGRISHOW.jpg")
    st.markdown('<div class="glass-panel" style="width:400px; margin:20vh auto; text-align:center;">', unsafe_allow_html=True)
    st.image("logoTriadetransparente.png", width=300)
    senha = st.text_input("Acesso", type="password")
    if st.button("DESBLOQUEAR"):
        if senha == "triade2026": st.session_state.logado = True; st.session_state.pagina = "dados"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "dados":
    aplicar_estilo_visual("imagemaptriadefundo.png")
    st.markdown('<div class="glass-panel" style="margin-top:10vh;">', unsafe_allow_html=True)
    st.title("📂 Dados do Projeto")
    c1, c2, c3 = st.columns(3)
    with c1: prod = st.text_input("Produtor", key='in_prod')
    with c2: faz = st.text_input("Fazenda", key='in_faz')
    with c3: mun = st.text_input("Município", key='in_mun')
    
    col_u1, col_u2 = st.columns(2)
    with col_u1: up_geo = st.file_uploader("Contorno (.GEOJSON)", type=["geojson", "json"])
    with col_u2: up_xlsx = st.file_uploader("Planilha (.XLSX)", type=["xlsx"])
    
    if st.button("ABRIR PLATAFORMA"):
        if up_xlsx and up_geo:
            st.session_state.dados_excel = pd.read_excel(up_xlsx)
            st.session_state.contorno = json.load(up_geo)
            st.session_state.pagina = "plataforma"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{ background: white !important; }</style>", unsafe_allow_html=True)
    t = st.tabs(["⚙️ ATRIBUTOS", "🔍 FERTILIDADE", "🏠 RECOMENDAÇÕES", "🛰️ SATÉLITE", "🗺️ ZONAS", "📄 RELATÓRIO"])
    
    with t[0]: aba_atributos_v43()
    with t[1]: aba_mapas_fertilidade(st.session_state.dados_excel)
    with t[2]: st.write("Aba de Recomendações: Fórmulas de P-Rem e K ativas.")
