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

# --- 2. CSS PARA DESIGN E IDENTIDADE ---
def aplicar_visual_fixo(nome_imagem):
    bin_str = get_base64(nome_imagem)
    if bin_str:
        st.markdown(f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            height: 100vh !important;
            width: 100vw !important;
            overflow: hidden !important;
        }}
        .stApp {{
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
        label, p, span, h3 {{ color: white !important; font-weight: bold !important; text-transform: uppercase; font-size: 0.85rem !important; text-shadow: 2px 2px 4px rgba(0,0,0,1) !important; }}
        .titulo-dourado {{ color: #FFD700 !important; font-weight: 900 !important; font-size: 1.7rem !important; text-align: center; text-shadow: 3px 3px 6px rgba(0,0,0,0.9) !important; }}
        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. FUNÇÕES DAS ABAS ---

def exibir_aba_atributos():
    st.markdown("## ⚙️ Painel de Atributos Estratégicos")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("⚪ Calcário")
        ca_prnt = st.number_input("PRNT %", value=80.0)
        ca_ctc_des = st.number_input("Ca% desejado na CTC", value=60.0)
        mg_ctc_des = st.number_input("Mg% desejado na CTC", value=18.0)
        ca_preco = st.number_input("Preço Calcário (R$/ton)", value=190.0)
    with col2:
        st.subheader("🟠 Fósforo (P)")
        p_nc1 = st.number_input("0 a 4 (P-Rem)", value=8.0); p_nc2 = st.number_input("4.1 a 10 (P-Rem)", value=10.0)
        p_nc3 = st.number_input("10.1 a 19 (P-Rem)", value=12.0); p_nc4 = st.number_input("19.1 a 30 (P-Rem)", value=15.0)
        p_export = st.number_input("Exportação P (kg/sc)", value=0.8)
        p_adubo_perc = st.number_input("% P2O5 no Adubo", value=21.0)
        p_preco = st.number_input("Preço Adubo P (R$/ton)", value=2800.0)
    with col3:
        st.subheader("🔴 Potássio & Gesso")
        k_perc_ctc = st.number_input("K% desejado na CTC", value=3.2)
        k_export = st.number_input("Exportação K (kg/sc)", value=1.2)
        k_adubo_perc = st.number_input("% K2O no Adubo", value=60.0)
        k_preco = st.number_input("Preço Adubo K (R$/ton)", value=2800.0)
        g_fator = st.number_input("Fator Gesso (Argila * 15)", value=15.0)
        g_max = st.number_input("Dose Máxima Gesso", value=900.0)
        g_min = st.number_input("Dose Mínima Gesso", value=400.0)
        g_preco = st.number_input("Preço Gesso (R$/ton)", value=400.0)
        prod_exp = st.number_input("Produtividade Esperada (sc/ha)", value=80.0)
    
    return {
        "gesso_fator": g_fator, "gesso_min": g_min, "gesso_max": g_max, 
        "p_nc1": p_nc1, "p_nc2": p_nc2, "p_nc3": p_nc3, "p_nc4": p_nc4,
        "p_export_sc": p_export, "prod_esperada": prod_exp, "ca_prnt": ca_prnt,
        "ca_ctc_des": ca_ctc_des, "mg_ctc_des": mg_ctc_des, "k_perc_ctc": k_perc_ctc,
        "k_export_sc": k_export, "ca_preco": ca_preco, "p_preco": p_preco,
        "k_preco": k_preco, "gesso_preco": g_preco, "p_adubo_perc": p_adubo_perc,
        "k_adubo_perc": k_adubo_perc
    }

def exibir_aba_mapas_fertilidade(df):
    st.markdown("### 🗺️ Mapas de Fertilidade (Zonas de Manejo)")
    logo_path = "LogoTriadeagro.png.png"
    logo_base64 = get_base64(logo_path)
    colunas_dados = [c for c in df.columns if c not in ['LATITUDE', 'LONGITUDE', 'CAMPO', 'PONTO']]
    
    for col in colunas_dados:
        df_clean = df[df[col].notna() & (df[col] != 0)].copy()
        if df_clean.empty: continue
        
        st.markdown(f"#### Atributo: {col}")
        fig = go.Figure(go.Histogram2dContour(
            x=df_clean['LONGITUDE'], y=df_clean['LATITUDE'], z=df_clean[col],
            colorscale='coolwarm', ncontours=6, line_width=0
        ))
        
        if logo_base64:
            fig.add_layout_image(dict(
                source=f"data:image/png;base64,{logo_base64}",
                xref="paper", yref="paper", x=0.5, y=0.5,
                sizex=0.4, sizey=0.4, xanchor="center", yanchor="middle",
                opacity=0.15, layer="above"
            ))
            
        fig.update_layout(width=900, height=500, margin={"r":10,"t":10,"l":10,"b":10},
                          coloraxis_colorbar=dict(thickness=12, tickfont=dict(size=9, color="white")))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(f"<div style='text-align: center; font-size: 11px; color: #CCCCCC;'>MÍN: {df_clean[col].min():.2f} | MÉD: {df_clean[col].mean():.2f} | MÁX: {df_clean[col].max():.2f}</div>", unsafe_allow_html=True)

def exibir_aba_recomendacoes(df, attr):
    st.markdown("## 💰 Recomendações Técnicas e Custos por Zona")
    df_calc = df.fillna(0).copy()
    
    # Cálculos
    df_calc['Dose_Gesso'] = (df_calc['ARGILA'] * attr['gesso_fator']).clip(lower=attr['gesso_min'], upper=attr['gesso_max'])
    exp_k = attr['prod_esperada'] * attr['k_export_sc']
    df_calc['Dose_K2O'] = exp_k + (((attr['k_perc_ctc'] - df_calc['K%']).clip(lower=0) / 100) * df_calc['CTC'] * 391 * 2)
    
    def calc_p(row):
        prem = row['P-REM']
        if prem <= 4: nc = attr['p_nc1']
        elif prem <= 10: nc = attr['p_nc2']
        elif prem <= 19: nc = attr['p_nc3']
        else: nc = attr['p_nc4']
        return (attr['prod_esperada'] * attr['p_export_sc']) - ((row['P'] - nc) * 8)

    df_calc['Dose_P2O5'] = df_calc.apply(calc_p, axis=1).clip(lower=0)
    df_calc['Custo_Total_HA'] = ((df_calc['Dose_Gesso']/1000)*attr['gesso_preco']) + \
                                ((df_calc['Dose_P2O5']/(attr['p_adubo_perc']/100)/1000)*attr['p_preco'])
    
    df_calc['Zona_Investimento'] = pd.qcut(df_calc['Custo_Total_HA'].rank(method='first'), 6, 
                                          labels=["Muito Baixo", "Baixo", "Médio-Baixo", "Médio-Alto", "Alto", "Crítico"])
    
    resumo = df_calc.groupby('Zona_Investimento', observed=True).agg({
        'Dose_Gesso': 'mean', 'Dose_P2O5': 'mean', 'Dose_K2O': 'mean', 'Custo_Total_HA': 'mean'
    }).reset_index()
    
    st.table(resumo.style.format(precision=2))

# --- 4. FLUXO DE NAVEGAÇÃO ---

if "logado" not in st.session_state: st.session_state.logado = False
if "pagina" not in st.session_state: st.session_state.pagina = "login"

# TELA 1: LOGIN
if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    st.markdown('<div style="position: absolute; top: 58%; left: 50%; transform: translateX(-50%); width: 380px; text-align: center;">', unsafe_allow_html=True)
    logo_64 = get_base64("logoTriadetransparente.png")
    if logo_64: st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 10px;">', unsafe_allow_html=True)
    senha = st.text_input("Acesso", type="password", placeholder="CHAVE DE ACESSO", label_visibility="collapsed")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026": 
            st.session_state.logado = True; st.session_state.pagina = "dados"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# TELA 2: CONFIGURAÇÃO E UPLOAD
elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    st.write("<br><br><br>", unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="titulo-dourado">⚙️ CONFIGURAÇÃO DO PROJETO</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state.produtor = st.text_input("PRODUTOR")
        with c2: st.session_state.fazenda = st.text_input("FAZENDA")
        with c3: st.session_state.municipio = st.text_input("MUNICÍPIO / UF")
        
        col_up1, col_up2 = st.columns(2)
        with col_up1: up_geojson = st.file_uploader("ARQUIVO DE CONTORNO (.GEOJSON)", type=["json", "geojson"])
        with col_up2: up_excel = st.file_uploader("PLANILHA DE DADOS (.XLSX)", type=["xlsx"])
            
        if st.button("🚀 INICIAR ANÁLISE ESTRATÉGICA"):
            if up_excel and up_geojson:
                st.session_state.dados_excel = pd.read_excel(up_excel)
                st.session_state.pagina = "plataforma"; st.rerun()
            else:
                st.warning("CARREGUE AMBOS OS ARQUIVOS PARA CONTINUAR")
        st.markdown('</div>', unsafe_allow_html=True)

# TELA 3: PLATAFORMA (ABAS)
elif st.session_state.pagina == "plataforma":
    st.markdown("<style>[data-testid='stAppViewContainer']{background-image:none !important; background-color:#0e1117 !important; overflow:auto !important;}</style>", unsafe_allow_html=True)
    aba1, aba2, aba3, aba4 = st.tabs(["⚙️ ATRIBUTOS", "🗺️ MAPAS FERTILIDADE", "💰 RECOMENDAÇÕES", "🛰️ SATÉLITE"])
    
    with aba1:
        atributos = exibir_aba_atributos()
    with aba2:
        exibir_aba_mapas_fertilidade(st.session_state.dados_excel)
    with aba3:
        exibir_aba_recomendacoes(st.session_state.dados_excel, atributos)
    with aba4:
        st.subheader("🛰️ Monitoramento Sentinel Hub")
        st.text_input("SENTINEL CLIENT ID", type="password")
        st.text_input("SENTINEL CLIENT SECRET", type="password")
        st.info("Conexão pronta para integração de NDVI/EVI.")
