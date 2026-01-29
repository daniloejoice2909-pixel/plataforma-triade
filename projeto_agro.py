import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import base64

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")

def get_base64(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- 2. CSS PARA DESIGN E IDENTIDADE (LOGIN E CONFIG) ---
def aplicar_visual_fixo(nome_imagem):
    bin_str = get_base64(nome_imagem)
    if bin_str:
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: 100% 100%;
            background-repeat: no-repeat;
        }}
        .glass-panel {{
            background: rgba(0, 0, 0, 0.85); 
            padding: 25px; border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            width: 850px; margin: auto;
        }}
        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. ABA 1: ATRIBUTOS (SCRIPT COMPLETO) ---
def exibir_aba_atributos():
    st.markdown("## ⚙️ Painel de Atributos Estratégicos")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("⚪ Calcário")
        ca_cao = st.number_input("CaO %", value=36.0)
        ca_mgo = st.number_input("MgO %", value=9.0)
        ca_prnt = st.number_input("PRNT %", value=80.0)
        ca_ctc_des = st.number_input("Ca% desejado na CTC", value=60.0)
        mg_ctc_des = st.number_input("Mg% desejado na CTC", value=18.0)
        ca_preco = st.number_input("Preço Calcário (R$/ton)", value=190.0)

    with col2:
        st.subheader("🟠 Fósforo (P)")
        st.write("**Níveis Críticos (P-Rem)**")
        p_nc = {
            "0-4": st.number_input("0 a 4 (P-Rem)", value=8.0),
            "4-10": st.number_input("4.1 a 10 (P-Rem)", value=10.0),
            "10-19": st.number_input("10.1 a 19 (P-Rem)", value=12.0),
            "19-30": st.number_input("19.1 a 30 (P-Rem)", value=15.0),
            "30-45": st.number_input("30.1 a 45 (P-Rem)", value=20.0),
            "45-60": st.number_input("45.1 a 60 (P-Rem)", value=25.0)
        }
        st.write("**Fator Correção (kg P p/ elevar 1mg)**")
        f_textura = {
            "m_arg": st.number_input("M. Argiloso (>60%)", value=10.0),
            "arg": st.number_input("Argiloso (35-60%)", value=8.0),
            "med": st.number_input("Médio (15-35%)", value=6.0),
            "san": st.number_input("Arenoso (<15%)", value=4.0)
        }
        p_export = st.number_input("Exportação P (kg/sc)", value=0.8)
        p_adubo_perc = st.number_input("% P2O5 no Adubo", value=21.0)
        p_preco = st.number_input("Preço Adubo P (R$/ton)", value=2800.0)

    with col3:
        st.subheader("🔴 Potássio (K) & Gesso")
        k_perc_ctc = st.number_input("K% desejado na CTC", value=3.2)
        k_export = st.number_input("Exportação K (kg/sc)", value=1.2)
        k_adubo_perc = st.number_input("% K2O no Adubo", value=60.0)
        k_preco = st.number_input("Preço Adubo K (R$/ton)", value=2800.0)
        st.write("---")
        g_fator = st.number_input("Fator Gesso (Argila g/kg * X)", value=15.0)
        g_max = st.number_input("Dose Máxima Gesso", value=900.0)
        g_min = st.number_input("Dose Mínima Gesso", value=400.0)
        g_preco = st.number_input("Preço Gesso (R$/ton)", value=400.0)
        prod_exp = st.number_input("Produtividade Esperada (sc/ha)", value=80.0)

    return locals() # Retorna todas as variáveis configuradas

# --- 4. ABA 2: MAPAS FERTILIDADE (SCRIPT COMPLETO) ---
def exibir_aba_mapas_fertilidade(df):
    st.markdown("### 🗺️ Mapas de Fertilidade (Zonas de Manejo)")
    logo_path = "LogoTriadeagro.png.png"
    logo_base64 = get_base64(logo_path)
    colunas_dados = [c for c in df.columns if c not in ['LATITUDE', 'LONGITUDE', 'CAMPO', 'PONTO']]
    
    for col in colunas_dados:
        df_clean = df[df[col].notnull()].copy()
        if df_clean.empty or df_clean[col].sum() == 0: continue
        
        st.markdown(f"#### Atributo: {col}")
        fig = go.Figure(go.Histogram2dContour(
            x=df_clean['LONGITUDE'], y=df_clean['LATITUDE'], z=df_clean[col],
            colorscale='coolwarm', ncontours=6, line_width=0
        ))
        
        if logo_base64:
            fig.add_layout_image(dict(source=f"data:image/png;base64,{logo_base64}", xref="paper", yref="paper", x=0.5, y=0.5, sizex=0.5, sizey=0.5, xanchor="center", yanchor="middle", opacity=0.1, layer="above"))
            
        fig.update_layout(width=1000, height=600, plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

# --- 5. ABA 3: RECOMENDAÇÕES (SCRIPT COMPLETO V43) ---
def exibir_aba_recomendacoes(df, attr):
    st.markdown("## 💰 Recomendações Técnicas e Custos por Zona")
    df_reco = df.copy()

    # Lógica de Gesso
    df_reco['Dose_Gesso'] = (df_reco['ARGILA'] * attr['g_fator']).clip(lower=attr['g_min'], upper=attr['g_max'])

    # Lógica de Fósforo (P)
    def calcular_p_v43(row):
        prem = row['P-REM']
        if prem <= 4: nc = attr['p_nc']['0-4']
        elif prem <= 10: nc = attr['p_nc']['4-10']
        elif prem <= 19: nc = attr['p_nc']['10-19']
        elif prem <= 30: nc = attr['p_nc']['19-30']
        elif prem <= 45: nc = attr['p_nc']['30-45']
        else: nc = attr['p_nc']['45-60']
        
        arg = row['ARGILA']
        f_t = attr['f_textura']['m_arg'] if arg > 600 else attr['f_textura']['arg'] if arg > 350 else attr['f_textura']['med'] if arg > 150 else attr['f_textura']['san']
        
        exp_p = attr['prod_exp'] * attr['p_export']
        return exp_p + ((nc - row['P']) * f_t)

    df_reco['Dose_P2O5'] = df_reco.apply(calcular_p_v43, axis=1).clip(lower=0)
    
    # Lógica de Custos
    df_reco['Custo_Total'] = ((df_reco['Dose_Gesso']/1000)*attr['g_preco']) + ((df_reco['Dose_P2O5']/(attr['p_adubo_perc']/100)/1000)*attr['p_preco'])
    
    # Gerar 6 Zonas de Manejo por Custo
    df_reco['Zona'] = pd.qcut(df_reco['Custo_Total'].rank(method='first'), 6, labels=["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"])
    
    resumo = df_reco.groupby('Zona', observed=True).agg({
        'Dose_Gesso': 'mean', 'Dose_P2O5': 'mean', 'Custo_Total': 'mean'
    }).reset_index()
    
    st.table(resumo.style.format(precision=2))
    
    # Mapa de Recomendação (Gesso como exemplo)
    st.subheader("🗺️ Mapa de Recomendação de Gesso (kg/ha)")
    fig_g = go.Figure(go.Histogram2dContour(x=df_reco['LONGITUDE'], y=df_reco['LATITUDE'], z=df_reco['Dose_Gesso'], colorscale='Reds', ncontours=6))
    st.plotly_chart(fig_g, use_container_width=True)

# --- 6. FLUXO DE NAVEGAÇÃO E LOGIN ---

if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    st.markdown('<div style="height: 55vh;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="glass-panel" style="width: 400px; text-align: center;">', unsafe_allow_html=True)
    logo = get_base64("logoTriadetransparente.png")
    if logo: st.markdown(f'<img src="data:image/png;base64,{logo}" style="width: 300px;">', unsafe_allow_html=True)
    senha = st.text_input("Acesso", type="password", placeholder="CHAVE DE ACESSO", label_visibility="collapsed")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026": st.session_state.logado = True; st.session_state.pagina = "dados"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    st.markdown('<div style="height: 20vh;"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown("<h2 style='color:#FFD700; text-align:center;'>⚙️ CONFIGURAÇÃO</h2>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: st.text_input("PRODUTOR")
        with c2: st.text_input("FAZENDA")
        with c3: st.text_input("MUNICÍPIO")
        up_excel = st.file_uploader("PLANILHA (.XLSX)", type=["xlsx"])
        up_geo = st.file_uploader("CONTORNO (.GEOJSON)", type=["geojson", "json"])
        if st.button("🚀 INICIAR"):
            if up_excel:
                st.session_state.dados_excel = pd.read_excel(up_excel)
                st.session_state.pagina = "plataforma"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{ background: white !important; }</style>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["⚙️ ATRIBUTOS", "🗺️ FERTILIDADE", "💰 RECOMENDAÇÕES", "🛰️ SATÉLITE"])
    
    with tab1:
        dados_atributos = exibir_aba_atributos()
    with tab2:
        exibir_aba_mapas_fertilidade(st.session_state.dados_excel)
    with tab3:
        exibir_aba_recomendacoes(st.session_state.dados_excel, dados_atributos)
    with tab4:
        st.subheader("🛰️ Sentinel Hub"); st.text_input("Client ID"); st.text_input("Client Secret")
