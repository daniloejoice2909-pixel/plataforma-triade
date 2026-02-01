import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from fpdf import FPDF
import base64
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- INICIALIZAÇÃO DO BANCO DE DADOS (PERSISTÊNCIA EM SESSÃO) ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}  # Estrutura: {Produtor: {Fazenda: {Talhão: {dados: df, contorno: file}}}}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card {
        background-color: #ffffff; padding: 15px; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center;
        border-top: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 24px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 15px; margin: 20px 0; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO V43 (REGRAS DE OURO TRÍADE) ---
def motor_calculo_v43(df, params):
    # Tipagem rigorosa
    cols_numericas = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P res', 'K%', 'V%', 'pH', 'prem', 'K']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    p_p = params["fosforo"]
    k_p = params["potassio"]
    g_p = params["gesso"]
    c_p = params["calagem"]
    prod_esperada = params["global"]["produtividade"]

    # 1. GESSAGEM: Argila (g/kg) * Fator (Editável)
    df['REC_GESSO'] = (df['Argila'] * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    # 2. CALAGEM (Equilíbrio Ca e Mg na CTC)
    df['NC_CA'] = ((c_p["target_ca"] - df['Ca%']).clip(lower=-999) * df['CTC'] / 100)
    df['NC_MG'] = ((c_p["target_mg"] - df['Mg%']).clip(lower=-999) * df['CTC'] / 100)
    
    dose_ca = (df['NC_CA'].clip(lower=0) * 560 * 100) / (c_p["cao"] * c_p["prnt"])
    dose_mg = (df['NC_MG'].clip(lower=0) * 400 * 100) / (c_p["mgo"] * c_p["prnt"])
    
    df['REC_CALCARIO'] = ((np.maximum(dose_ca, dose_mg) * 1000) + c_p["reserva"]).round(2) # kg/ha

    # 3. FÓSFORO (NC P-rem + Argila + Exportação)
    def calc_p(row):
        prem = row['prem']
        if prem <= 4: nc_alvo = p_p["nc_0_4"]
        elif prem <= 10: nc_alvo = p_p["nc_4_10"]
        elif prem <= 19: nc_alvo = p_p["nc_10_19"]
        elif prem <= 30: nc_alvo = p_p["nc_19_30"]
        elif prem <= 45: nc_alvo = p_p["nc_30_45"]
        else: nc_alvo = p_p["nc_45_60"]

        arg = row['Argila']
        if arg > 600: f_arg = p_p["f_muito_arg"]
        elif arg > 350: f_arg = p_p["f_argiloso"]
        elif arg > 150: f_arg = p_p["f_medio"]
        else: f_arg = p_p["f_arenoso"]

        delta_p = nc_alvo - row['P res'] # Se P solo > NC, delta é negativo (subtrai)
        p_correcao_p2o5 = delta_p * f_arg
        p_exportacao = prod_esperada * p_p["f_exp"]
        
        total_p2o5 = p_correcao_p2o5 + p_exportacao
        return (max(total_p2o5, 0) * 100) / (p_p["teor_adubo"] / 100 * 100) # kg/ha adubo

    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 4. POTÁSSIO (Correção + Exportação Obrigatória)
    df['K_CORRECAO'] = (k_p["target_k"] - df['K%']).clip(lower=-999) * df['CTC'] / 100 * 941
    k_exportacao = prod_esperada * k_p["f_exp"]
    
    total_k2o = df['K_CORRECAO'].clip(lower=0) + k_exportacao
    df['REC_K_ADUBO'] = (total_k2o * 100 / k_p["teor_adubo"]).round(2)

    # 5. CUSTOS (R$ / ha)
    df['CUSTO_CALC'] = (df['REC_CALCARIO'] / 1000) * c_p["preco"]
    df['CUSTO_P'] = (df['REC_P_ADUBO'] / 1000) * p_p["preco"]
    df['CUSTO_K'] = (df['REC_K_ADUBO'] / 1000) * k_p["preco"]
    df['CUSTO_GESSO'] = (df['REC_GESSO'] / 1000) * g_p["preco"]
    df['CUSTO_TOTAL'] = df['CUSTO_CALC'] + df['CUSTO_P'] + df['CUSTO_K'] + df['CUSTO_GESSO']

    # 6. ZONEAMENTO
    df['SCORE_ZONA'] = (df['V%'] / 100 * 0.5) + (df['Argila'] / 1000 * 0.25) + (df['pH'] / 10 * 0.25)
    try: df['ZONA_MANEJO'] = pd.qcut(df['SCORE_ZONA'], 3, labels=["Baixa", "Média", "Alta"], duplicates='drop')
    except: df['ZONA_MANEJO'] = "Zona Única"

    return df

# --- INTERFACE LATERAL (PASTAS DE ATRIBUTOS) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    
    st.sidebar.header("📍 Localização")
    produtores = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_prod = st.sidebar.selectbox("Produtor", produtores)
    
    if sel_prod == "+ Novo Produtor":
        sel_prod = st.sidebar.text_input("Nome do Produtor")
        if sel_prod and sel_prod not in st.session_state['db']:
            st.session_state['db'][sel_prod] = {}

    fazendas = []
    if sel_prod in st.session_state['db']:
        fazendas = list(st.session_state['db'][sel_prod].keys()) + ["+ Nova Fazenda"]
    sel_faz = st.sidebar.selectbox("Fazenda", fazendas)

    if sel_faz == "+ Nova Fazenda":
        sel_faz = st.sidebar.text_input("Nome da Fazenda")
        if sel_faz and sel_faz not in st.session_state['db'][sel_prod]:
            st.session_state['db'][sel_prod][sel_faz] = {}

    talhoes = []
    if sel_prod in st.session_state['db'] and sel_faz in st.session_state['db'][sel_prod]:
        talhoes = list(st.session_state['db'][sel_prod][sel_faz].keys()) + ["+ Novo Talhão"]
    sel_tal = st.sidebar.selectbox("Talhão", talhoes)

    if sel_tal == "+ Novo Talhão":
        sel_tal = st.sidebar.text_input("Identificação do Talhão")
        if sel_tal and sel_tal not in st.session_state['db'][sel_prod][sel_faz]:
            st.session_state['db'][sel_prod][sel_faz][sel_tal] = {"df": None, "contorno": None}

    st.sidebar.divider()
    st.sidebar.header("⚙️ Atributos Tríade")

    with st.sidebar.expander("🌍 Global & Produtividade"):
        prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT (%)", 80.0); c_cao = st.number_input("CaO (%)", 36.0); c_mgo = st.number_input("MgO (%)", 9.0)
        c_t_ca = st.number_input("Alvo Ca/CTC (%)", 60.0); c_t_mg = st.number_input("Alvo Mg/CTC (%)", 18.0)
        c_res = st.number_input("Calcário Reserva (kg/ha)", 0.0); c_preco = st.number_input("R$ / Tonelada (Calc)", 250.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Níveis Críticos**")
        nc04 = st.number_input("0-4 P-rem", 8.0); nc410 = st.number_input("4.1-10 P-rem", 10.0)
        nc1019 = st.number_input("10.1-19 P-rem", 12.0); nc1930 = st.number_input("19.1-30 P-rem", 15.0)
        nc3045 = st.number_input("30.1-45 P-rem", 18.0); nc4560 = st.number_input("45.1-60 P-rem", 22.0)
        st.write("**Fatores Argila**")
        f_m_arg = st.number_input("Muito Argiloso (x10)", 10.0); f_arg = st.number_input("Argiloso (x8)", 8.0)
        f_med = st.number_input("Médio (x4)", 4.0); f_are = st.number_input("Arenoso (x2)", 2.0)
        p_teor = st.number_input("Teor P2O5 Adubo (%)", 21.0); p_exp = st.number_input("Fator Exp P (kg/sc)", 0.8)
        p_preco = st.number_input("R$ / Tonelada (P)", 3200.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K na CTC (%)", 3.2); k_teor = st.number_input("Teor K2O Adubo (%)", 60.0)
        k_exp = st.number_input("Fator Exp K (kg/sc)", 1.2); k_preco = st.number_input("R$ / Tonelada (K)", 2800.0)

    with st.sidebar.expander("⚪ Gesso"):
        g_fator = st.number_input("Fator Argila (Gesso)", 15.0); g_min = st.number_input("Dose Mín (kg/ha)", 400.0)
        g_max = st.number_input("Dose Máx (kg/ha)", 900.0); g_preco = st.number_input("R$ / Tonelada (Gesso)", 180.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {
            "nc_0_4": nc04, "nc_4_10": nc410, "nc_10_19": nc1019, "nc_19_30": nc1930, "nc_30_45": nc3045, "nc_45_60": nc4560,
            "f_muito_arg": f_m_arg, "f_argiloso": f_arg, "f_medio": f_med, "f_arenoso": f_are, "teor_adubo": p_teor, "f_exp": p_exp, "preco": p_preco
        },
        "potassio": {"target_k": k_target, "teor_adubo": k_teor, "f_exp": k_exp, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco},
        "path": (sel_prod, sel_faz, sel_tal)
    }
    return params

# --- PÁGINA PRODUTORES ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Talhão: {t} | {f} | {p}</h2>", unsafe_allow_html=True)
    
    tab_dados, tab_mapas = st.tabs(["📁 Dados do Talhão", "🗺️ Mapas de Fertilidade"])
    
    with tab_dados:
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### ➕ Adicionar Dados")
            up_csv = st.file_uploader("Subir Planilha Solo (A-Y)", type=['csv'], key=f"csv_{t}")
            
            # ATUALIZAÇÃO SÊNIOR: Suporte a KML, JSON e GEOJSON adicionado aqui
            up_contorno = st.file_uploader("Subir Contorno (KML, JSON, GEOJSON, ZIP)", 
                                          type=['kml', 'json', 'geojson', 'zip'], 
                                          key=f"contorno_{t}")
            
            if st.button("💾 Salvar no Banco de Dados"):
                if up_csv:
                    df_up = pd.read_csv(up_csv, sep=';', decimal='.', encoding='utf-8-sig')
                    df_up.columns = df_up.columns.str.strip()
                    st.session_state['db'][p][f][t]["df"] = df_up
                    st.success("Planilha Salva!")
                if up_contorno:
                    st.session_state['db'][p][f][t]["contorno"] = up_contorno
                    st.success("Arquivo de Contorno Salvo!")
        
        with c2:
            st.write("#### 📋 Planilha Atual")
            if st.session_state['db'][p][f][t]["df"] is not None:
                st.dataframe(st.session_state['db'][p][f][t]["df"])
            else:
                st.info("Nenhum dado salvo para este talhão.")

    with tab_mapas:
        df_base = st.session_state['db'][p][f][t]["df"]
        if df_base is not None:
            if st.button("🚀 Gerar / Atualizar Mapas"):
                df_final = motor_calculo_v43(df_base, params)
                st.session_state['db'][p][f][t]["resultado"] = df_final
            
            if "resultado" in st.session_state['db'][p][f][t]:
                res = st.session_state['db'][p][f][t]["resultado"]
                
                # KPIs Financeiros
                k1, k2, k3, k4 = st.columns(4)
                k1.markdown(f"<div class='kpi-card'><small>Custo Médio Calcário</small><div class='kpi-value'>R$ {res['CUSTO_CALC'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
                k2.markdown(f"<div class='kpi-card'><small>Custo Médio Fósforo</small><div class='kpi-value'>R$ {res['CUSTO_P'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
                k3.markdown(f"<div class='kpi-card'><small>Custo Médio Potássio</small><div class='kpi-value'>R$ {res['CUSTO_K'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
                k4.markdown(f"<div class='kpi-card'><small>INVESTIMENTO TOTAL</small><div class='kpi-value' style='color:#27ae60'>R$ {res['CUSTO_TOTAL'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
                
                st.write("### Recomendações (kg/ha)")
                cols_view = ['id', 'CAMPO', 'ZONA_MANEJO', 'REC_CALCARIO', 'REC_GESSO', 'REC_P_ADUBO', 'REC_K_ADUBO']
                st.dataframe(res[cols_view])
                
                fig = px.scatter(res, x='Longitude', y='Latitude', color='ZONA_MANEJO',
                                 color_discrete_map={"Baixa":"#313695", "Média":"#fee090", "Alta":"#a50026"},
                                 hover_data=['REC_CALCARIO', 'REC_P_ADUBO'])
                st.plotly_chart(fig, use_container_width=True)

                if st.button("⚙️ Motor Tríade (Ver Fórmulas)"):
                    st.dialog("Fórmulas de Recomendação v43")
                    st.markdown("""
                    **1. Gesso:** Argila (g/kg) * Fator_Gesso. Travado entre Min/Max.  
                    **2. Calcário:** Max(NC_Ca, NC_Mg) + Reserva.  
                       * NC_Ca = (AlvoCa - AtualCa) * CTC / 100 * 560 / (CaO * PRNT)  
                    **3. Fósforo:** ((NC_P_rem - P_solo) * Fator_Argila + Prod * F_exp) * 100 / Teor_P2O5.  
                       * *Se P_solo > NC, o excedente subtrai da exportação.* **4. Potássio:** ((AlvoK - AtualK) * CTC / 100 * 941 + Prod * F_exp) * 100 / Teor_K2O.  
                       * *Exportação é sempre somada.*
                    """)
        else:
            st.warning("Suba os dados na aba 'Dados do Talhão' primeiro.")

# --- EXECUÇÃO ---
params = configurar_interface()
p, f, t = params["path"]

if not p or not f or not t:
    st.info("Selecione ou crie um Produtor, Fazenda e Talhão na barra lateral para começar.")
else:
    pag_produtores(params)
