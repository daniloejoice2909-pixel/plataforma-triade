import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from fpdf import FPDF
import base64
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS CUSTOMIZADO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card {
        background-color: #ffffff; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center;
        border-bottom: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 28px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 15px; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO V43 (REGRAS DE NEGÓCIO) ---
def motor_calculo_v43(df, params):
    # Desempacotamento de Parâmetros
    p = params["fosforo"]
    k_params = params["potassio"]
    g_params = params["gesso"]
    c_params = params["calagem"]
    prod_esperada = params["global"]["produtividade"]

    # 1. GESSAGEM (Argila g/kg * Fator) com travas Min/Max
    # O .clip garante que a dose não saia da faixa permitida pelo agrônomo
    df['REC_GESSO'] = (df['Argila'] * g_params["fator"]).clip(lower=g_params["min"], upper=g_params["max"])

    # 2. CALAGEM (Máximo entre Ca e Mg)
    df['NC_CA'] = ((c_params["target_ca"] - df['Ca%']).clip(lower=0) * df['CTC'] / 100)
    df['NC_MG'] = ((c_params["target_mg"] - df['Mg%']).clip(lower=0) * df['CTC'] / 100)
    
    dose_ca = (df['NC_CA'] * 560 * 100) / (c_params["cao"] * c_params["prnt"])
    dose_mg = (df['NC_MG'] * 400 * 100) / (c_params["mgo"] * c_params["prnt"])
    
    df['REC_CALCARIO'] = (np.maximum(dose_ca, dose_mg) + c_params["reserva"]).round(2)

    # 3. FÓSFORO (Nível Crítico + Fator Argila + Exportação)
    def calc_p(row):
        prem = row['prem']
        # Identifica Nível Crítico (P-rem)
        if prem <= 4: nc_alvo = p["nc_0_4"]
        elif prem <= 10: nc_alvo = p["nc_4_10"]
        elif prem <= 19: nc_alvo = p["nc_10_19"]
        elif prem <= 30: nc_alvo = p["nc_19_30"]
        elif prem <= 45: nc_alvo = p["nc_30_45"]
        else: nc_alvo = p["nc_45_60"]

        # Identifica Fator de Correção pela Classe de Argila
        arg = row['Argila']
        if arg > 600: f_arg = p["f_muito_arg"]
        elif arg > 350: f_arg = p["f_argiloso"]
        elif arg > 150: f_arg = p["f_medio"]
        else: f_arg = p["f_arenoso"]

        # Balanço: (Alvo - Atual) * Fator + Exportação
        delta_p = nc_alvo - row['P res']
        p_correcao_p2o5 = delta_p * f_arg 
        p_exportacao = prod_esperada * p["f_exp"]
        
        total_p2o5 = p_correcao_p2o5 + p_exportacao
        # Converte para kg/ha do adubo escolhido
        return (max(total_p2o5, 0) * 100) / p["teor_adubo"]

    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 4. POTÁSSIO (Correção na CTC + Exportação)
    df['NC_K_CORRECAO'] = (k_params["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941
    df['K_EXPORTACAO'] = prod_esperada * k_params["f_exp"]
    
    # Soma correção + exportação (mesmo se solo alto, soma exportação)
    total_k2o = df['NC_K_CORRECAO'] + df['K_EXPORTACAO']
    df['REC_K_ADUBO'] = (total_k2o * 100 / k_params["teor_adubo"]).round(2)

    # 5. ZONEAMENTO (SCORE)
    df['SCORE_ZONA'] = (df['V%'] / 100 * 0.5) + (df['Argila'] / 1000 * 0.25) + (df['pH'] / 10 * 0.25)
    try:
        df['ZONA_MANEJO'] = pd.qcut(df['SCORE_ZONA'], 3, labels=["Baixa", "Média", "Alta"], duplicates='drop')
    except:
        df['ZONA_MANEJO'] = "Zona Única"

    return df

# --- INTERFACE LATERAL (PARAMETRIZAÇÃO EDITÁVEL) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    menu = st.sidebar.radio("Navegação", ["🏠 Home", "👥 Produtores"])
    
    st.sidebar.header("⚙️ Parâmetros da Metodologia")
    
    with st.sidebar.expander("🌍 Global & Produtividade"):
        prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)

    with st.sidebar.expander("🪨 Atributos: Calcário"):
        c_prnt = st.number_input("PRNT (%)", 80.0)
        c_cao = st.number_input("Teor CaO (%)", 36.0)
        c_mgo = st.number_input("Teor MgO (%)", 9.0)
        c_t_ca = st.number_input("Alvo Ca/CTC (%)", 60.0)
        c_t_mg = st.number_input("Alvo Mg/CTC (%)", 18.0)
        c_res = st.number_input("Calcário Reserva (kg/ha)", 0)
        c_preco = st.number_input("Preço R$/Ton (Calcário)", 250.0)

    with st.sidebar.expander("🧪 Atributos: Fósforo"):
        st.write("**Níveis Críticos (mg/dm³)**")
        nc04 = st.number_input("0 a 4 P-rem", 8.0)
        nc410 = st.number_input("4,1 a 10 P-rem", 10.0)
        nc1019 = st.number_input("10,1 a 19 P-rem", 12.0)
        nc1930 = st.number_input("19,1 a 30 P-rem", 15.0)
        nc3045 = st.number_input("30,1 a 45 P-rem", 18.0)
        nc4560 = st.number_input("45,1 a 60 P-rem", 22.0)
        
        st.write("**Fatores de Correção (Argila)**")
        f_m_arg = st.number_input("Muito Argiloso (x10)", 10.0)
        f_arg = st.number_input("Argiloso (x8)", 8.0)
        f_med = st.number_input("Médio (x4)", 4.0)
        f_are = st.number_input("Arenoso (x2)", 2.0)
        
        st.write("**Adubo & Exportação**")
        p_teor = st.number_input("Teor P2O5 no Adubo (%)", 21.0)
        p_exp = st.number_input("Fator Exportação (kg/sc)", 0.8)
        p_preco = st.number_input("Preço R$/Ton (Fosfatado)", 3200.0)

    with st.sidebar.expander("🍌 Atributos: Potássio"):
        k_target = st.number_input("Alvo K na CTC (%)", 3.2)
        k_teor = st.number_input("Teor K2O no Adubo (%)", 60.0)
        k_exp = st.number_input("Fator Exportação (kg/sc)", 1.2)
        k_preco = st.number_input("Preço R$/Ton (Potássico)", 2800.0)

    with st.sidebar.expander("⚪ Atributos: Gesso"):
        g_fator = st.number_input("Fator Multiplicação Argila", 15.0)
        g_min = st.number_input("Dose Mínima (kg/ha)", 400.0)
        g_max = st.number_input("Dose Máxima (kg/ha)", 900.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {
            "nc_0_4": nc04, "nc_4_10": nc410, "nc_10_19": nc1019, "nc_19_30": nc1930, "nc_30_45": nc3045, "nc_45_60": nc4560,
            "f_muito_arg": f_m_arg, "f_argiloso": f_arg, "f_medio": f_med, "f_arenoso": f_are,
            "teor_adubo": p_teor, "f_exp": p_exp, "preco": p_preco
        },
        "potassio": {"target_k": k_target, "teor_adubo": k_teor, "f_exp": k_exp, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max}
    }
    return menu, params

# --- PÁGINA PRODUTORES ---
def pag_produtores(params):
    st.markdown("<h2 class='section-header'>Área Técnica: Consultoria Tríade</h2>", unsafe_allow_html=True)
    
    tab_dados, tab_mapas = st.tabs(["📁 Dados e Upload", "🗺️ Mapas e Recomendações"])
    
    with tab_dados:
        st.write("### 1. Preparação da Planilha")
        cols_triade = ['Latitude', 'Longitude', 'CAMPO', 'id', 'prof', 'pH', 'P res', 'P mehl', 'K', 'Ca', 'Mg', 'Al', 'CTC', 'V%', 'Argila', 'Silte', 'K%', 'Ca%', 'prem', 'Areia gross', 'Areia total', 'Areia fina', 'Ca/Mg', 'H/Al', 'Mg%']
        df_mod = pd.DataFrame(columns=cols_triade)
        csv = df_mod.to_csv(index=False, sep=';').encode('utf-8-sig')
        st.download_button("⬇️ Baixar Modelo Oficial A-Y", data=csv, file_name="modelo_triade_v43.csv", mime="text/csv")
        
        st.divider()
        st.write("### 2. Upload de Dados")
        uploaded_file = st.file_uploader("Selecione o arquivo CSV", type=['csv'])
        
        if uploaded_file:
            try:
                # O segredo da correção está aqui:
                df_input = pd.read_csv(uploaded_file, sep=';')
                # Remove espaços em branco dos nomes das colunas
                df_input.columns = df_input.columns.str.strip() 
                
                # Verifica se a coluna 'Argila' existe após a limpeza
                if 'Argila' in df_input.columns:
                    st.success("Dados carregados e colunas validadas!")
                    st.session_state['df_base'] = df_input
                else:
                    st.error(f"Erro: A coluna 'Argila' não foi encontrada. Colunas detectadas: {list(df_input.columns)}")
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

    with tab_mapas:
        if 'df_base' in st.session_state:
            # Roda o motor de cálculo
            df_final = motor_calculo_v43(st.session_state['df_base'], params)
            
            st.write("### Recomendações Geradas")
            # Exibe as principais colunas de resultado
            res_cols = ['id', 'ZONA_MANEJO', 'REC_CALCARIO', 'REC_GESSO', 'REC_P_ADUBO', 'REC_K_ADUBO']
            st.dataframe(df_final[res_cols], use_container_width=True)
            
            # Visualização Espacial
            fig = px.scatter(df_final, x='Longitude', y='Latitude', color='ZONA_MANEJO',
                             color_discrete_map={"Baixa":"#313695", "Média":"#fee090", "Alta":"#a50026"},
                             title="Mapa de Zonas de Manejo (Coolwarm)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aguardando upload dos dados na aba anterior.")

# --- EXECUÇÃO PRINCIPAL ---
menu, params = configurar_interface()

if menu == "🏠 Home":
    st.markdown("<h2 class='section-header'>Dashboard Administrativo</h2>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("<div class='kpi-card'><div class='kpi-label'>Área Monitorada</div><div class='kpi-value'>17.000 ha</div></div>", unsafe_allow_html=True)
    c2.markdown("<div class='kpi-card'><div class='kpi-label'>Cliente Foco</div><div class='kpi-value'>G. Berneck</div></div>", unsafe_allow_html=True)
    c3.markdown("<div class='kpi-card'><div class='kpi-label'>Safra</div><div class='kpi-value'>25/26</div></div>", unsafe_allow_html=True)
    c4.markdown("<div class='kpi-card'><div class='kpi-label'>Status</div><div class='kpi-value' style='color:#27ae60'>Ativo</div></div>", unsafe_allow_html=True)
else:
    pag_produtores(params)
