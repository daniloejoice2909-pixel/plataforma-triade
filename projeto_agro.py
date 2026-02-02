import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from fpdf import FPDF
import base64
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
if 'db' not in st.session_state:
    st.session_state['db'] = {}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card {
        background-color: #ffffff; padding: 15px; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center;
        border-top: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 22px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 15px; margin: 20px 0; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO V43 ---
def motor_calculo_v43(df, params):
    # Normalização de colunas
    mapeamento = {
        'ph': 'pH', 'PH': 'pH', 'argila': 'Argila', 'ARGILA': 'Argila',
        'v%': 'V%', 'ctc': 'CTC', 'p res': 'P res', 'p mehl': 'P mehl', 'P mehl': 'P mehl',
        'prem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 'k%': 'K%', 'ca': 'Ca', 'mg': 'Mg', 'k': 'K', 'al': 'Al'
    }
    df = df.rename(columns=mapeamento)
    
    cols_nec = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'K', 'Ca', 'Mg', 'Al']
    for col in cols_nec:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0

    p_p = params["fosforo"]
    k_p = params["potassio"]
    g_p = params["gesso"]
    c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # --- 1. CALAGEM (Equilíbrio Ca/Mg) ---
    # Centimol necessário para atingir os alvos
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    
    # Conversão para dose (kg/ha) usando fatores 560 e 400
    df['DOSE_CA_KG'] = (df['NC_CA_CMOL'] * 560 * 100 * 100) / (c_p["cao"] * c_p["prnt"])
    df['DOSE_MG_KG'] = (df['NC_MG_CMOL'] * 400 * 100 * 100) / (c_p["mgo"] * c_p["prnt"])
    
    # Maior dose + Reserva
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CA_KG'], df['DOSE_MG_KG']) + c_p["reserva"]).round(2)
    
    # Verificação da relação Ca/Mg final teórica
    df['RATIO_CA_MG'] = (df['Ca%'] + (df['NC_CA_CMOL']/df['CTC']*100)) / (df['Mg%'] + (df['NC_MG_CMOL']/df['CTC']*100))

    # --- 2. FÓSFORO (NC P-rem + Exportação) ---
    def calc_p_vrt(row):
        # Determina NC baseado na classe de Prem
        prem = row['prem']
        if prem <= 4: nc = p_p["nc_0_4"]
        elif prem <= 10: nc = p_p["nc_4_10"]
        elif prem <= 19: nc = p_p["nc_10_19"]
        elif prem <= 30: nc = p_p["nc_19_30"]
        elif prem <= 45: nc = p_p["nc_30_45"]
        else: nc = p_p["nc_45_60"]
        
        # Determina Fator Argila
        arg = row['Argila']
        if arg > 600: f_arg = p_p["f_muito_arg"]
        elif arg > 350: f_arg = p_p["f_argiloso"]
        elif arg > 150: f_arg = p_p["f_medio"]
        else: f_arg = p_p["f_arenoso"]
        
        delta_p = nc - row['P mehl']
        p_corr_p2o5 = delta_p * f_arg # Se delta_p for negativo, vira crédito
        p_exp_p2o5 = prod_esp * p_p["f_exp"]
        
        total_p2o5 = p_corr_p2o5 + p_exp_p2o5
        return (max(total_p2o5, 0) * 100) / p_p["teor_adubo"]

    df['REC_P_ADUBO'] = df.apply(calc_p_vrt, axis=1).round(2)

    # --- 3. POTÁSSIO ---
    df['K_CORR_P2O5'] = ((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941)
    df['K_EXP_P2O5'] = prod_esp * k_p["f_exp"]
    df['REC_K_ADUBO'] = ((df['K_CORR_P2O5'] + df['K_EXP_P2O5']) * 100 / k_p["teor_adubo"]).round(2)

    # --- 4. GESSO ---
    df['REC_GESSO'] = (df['Argila'] * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    # --- 5. ZONEAMENTO & CUSTOS ---
    df['CUSTO_TOTAL'] = ((df['REC_CALCARIO']/1000)*c_p["preco"]) + ((df['REC_P_ADUBO']/1000)*p_p["preco"]) + \
                        ((df['REC_K_ADUBO']/1000)*k_p["preco"]) + ((df['REC_GESSO']/1000)*g_p["preco"])
    
    df['SCORE_ZONA'] = (df['V%'] / 100 * 0.5) + (df['Argila'] / 1000 * 0.25) + (df['pH'] / 10 * 0.25)
    try: df['ZONA_MANEJO'] = pd.qcut(df['SCORE_ZONA'], 3, labels=["Baixa", "Média", "Alta"], duplicates='drop')
    except: df['ZONA_MANEJO'] = "Zona Única"
    
    return df

# --- INTERFACE LATERAL ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.header("📍 Localização")
    
    produtores = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_prod = st.sidebar.selectbox("Produtor", produtores)
    if sel_prod == "+ Novo Produtor":
        sel_prod = st.sidebar.text_input("Nome do Produtor")
        if sel_prod and sel_prod not in st.session_state['db']: st.session_state['db'][sel_prod] = {}

    fazendas = []
    if sel_prod in st.session_state['db']:
        fazendas = list(st.session_state['db'][sel_prod].keys()) + ["+ Nova Fazenda"]
    sel_faz = st.sidebar.selectbox("Fazenda", fazendas)
    if sel_faz == "+ Nova Fazenda":
        sel_faz = st.sidebar.text_input("Nome da Fazenda")
        if sel_faz and sel_faz not in st.session_state['db'][sel_prod]: st.session_state['db'][sel_prod][sel_faz] = {}

    talhoes = []
    if sel_prod in st.session_state['db'] and sel_faz in st.session_state['db'][sel_prod]:
        talhoes = list(st.session_state['db'][sel_prod][sel_faz].keys()) + ["+ Novo Talhão"]
    sel_tal = st.sidebar.selectbox("Talhão", talhoes)
    if sel_tal == "+ Novo Talhão":
        sel_tal = st.sidebar.text_input("ID do Talhão")
        if sel_tal and sel_tal not in st.session_state['db'][sel_prod][sel_faz]:
            st.session_state['db'][sel_prod][sel_faz][sel_tal] = {"df": None, "contorno": None}

    st.sidebar.divider()
    st.sidebar.header("⚙️ Atributos Tríade")
    with st.sidebar.expander("🌍 Global & Produtividade"):
        prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT (%)", 80.0); c_cao = st.number_input("CaO (%)", 36.0); c_mgo = st.number_input("MgO (%)", 9.0)
        c_t_ca = st.number_input("Alvo Ca/CTC (%)", 60.0); c_t_mg = st.number_input("Alvo Mg/CTC (%)", 18.0)
        c_res = st.number_input("Calcário Reserva (kg/ha)", 0.0); c_preco = st.number_input("Preço R$/Ton (Calc)", 250.0)

    with st.sidebar.expander("🧪 Fósforo"):
        st.write("**Níveis Críticos**")
        nc04 = st.number_input("0-4 P-rem", 8.0); nc410 = st.number_input("4.1-10 P-rem", 10.0)
        nc1019 = st.number_input("10.1-19 P-rem", 12.0); nc1930 = st.number_input("19.1-30 P-rem", 15.0)
        nc3045 = st.number_input("30.1-45 P-rem", 18.0); nc4560 = st.number_input("45.1-60 P-rem", 22.0)
        st.write("**Fatores Argila**")
        f_m_arg = st.number_input("Muito Argiloso (x10)", 10.0); f_arg = st.number_input("Argiloso (x8)", 8.0)
        f_med = st.number_input("Médio (x4)", 4.0); f_are = st.number_input("Arenoso (x2)", 2.0)
        p_teor = st.number_input("Teor P2O5 Adubo (%)", 21.0); p_exp = st.number_input("Fator Exp P (kg/sc)", 0.8)
        p_preco = st.number_input("Preço R$/Ton (P)", 3200.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K na CTC (%)", 3.2); k_teor = st.number_input("Teor K2O Adubo (%)", 60.0)
        k_exp = st.number_input("Fator Exp K (kg/sc)", 1.2); k_preco = st.number_input("Preço R$/Ton (K)", 2800.0)

    with st.sidebar.expander("⚪ Gesso"):
        g_fator = st.number_input("Fator Argila (Gesso)", 15.0); g_min = st.number_input("Dose Mín", 400.0)
        g_max = st.number_input("Dose Máx", 900.0); g_preco = st.number_input("Preço R$/Ton (Gesso)", 180.0)

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
    tab_dados, tab_fert, tab_vrt = st.tabs(["📁 Dados", "📊 Fertilidade", "🗺️ Recomendações VRT"])
    
    with tab_dados:
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### ➕ Inserir Dados")
            up_csv = st.file_uploader("CSV Solo", type=['csv'], key=f"c_{t}")
            up_kml = st.file_uploader("Contorno", type=['kml','json','geojson'], key=f"k_{t}")
            if st.button("💾 Salvar Dados"):
                if up_csv:
                    try:
                        df_up = pd.read_csv(up_csv, sep=None, engine='python', encoding='utf-8-sig')
                        df_up.columns = df_up.columns.str.strip()
                        st.session_state['db'][p][f][t]["df"] = df_up
                        st.success("Salvo!")
                    except Exception as e: st.error(f"Erro: {e}")
        with c2:
            if st.session_state['db'][p][f][t]["df"] is not None:
                st.dataframe(st.session_state['db'][p][f][t]["df"])

    if st.session_state['db'][p][f][t]["df"] is not None:
        df_res = motor_calculo_v43(st.session_state['db'][p][f][t]["df"], params)
        
        # Alerta de Relação Ca/Mg
        avg_ratio = df_res['RATIO_CA_MG'].mean()
        if avg_ratio < 2 or avg_ratio > 4:
            st.toast(f"⚠️ Atenção: Relação Ca/Mg desequilibrada ({avg_ratio:.2f}). Ajuste os teores do calcário.", icon="⚖️")

        with tab_fert:
            st.write("### Mapas de Fertilidade (Padrão InCeres)")
            attr = st.selectbox("Selecione o Atributo", ["pH", "Argila", "Ca", "Mg", "K", "Al", "P mehl", "V%", "Ca%", "Mg%", "K%"])
            fig_f = px.scatter(df_res, x='Longitude', y='Latitude', color=attr, 
                               color_continuous_scale='coolwarm', title=f"Mapa de {attr}")
            fig_f.update_traces(marker=dict(size=12, opacity=0.8))
            st.plotly_chart(fig_f, use_container_width=True)

        with tab_vrt:
            st.write("### Mapas de Recomendação VRT (kg/ha)")
            rec = st.selectbox("Insumo", ["REC_CALCARIO", "REC_P_ADUBO", "REC_K_ADUBO", "REC_GESSO"])
            fig_v = px.scatter(df_res, x='Longitude', y='Latitude', color=rec, 
                               color_continuous_scale='coolwarm', title=f"Taxa Variável: {rec}")
            fig_v.update_traces(marker=dict(size=14, symbol='square'))
            st.plotly_chart(fig_v, use_container_width=True)
            
            if st.button("⚙️ Motor Tríade"):
                st.dialog("Metodologia Técnica Tríade v43")
                st.markdown(r"""
                ### 1. Calagem (Equilíbrio de Bases)
                * **Cálculo Ca:** $\Delta Ca = \frac{(AlvoCa\% - AtualCa\%) \times CTC}{100}$
                * **Cálculo Mg:** $\Delta Mg = \frac{(AlvoMg\% - AtualMg\%) \times CTC}{100}$
                * **Conversão:** Usa fator 560 para $Ca$ e 400 para $Mg$.
                * **Dose Final:** $Max(Dose_{Ca}, Dose_{Mg}) + Reserva$.
                * **Trava:** Alerta visual se $Ca/Mg$ sair do intervalo $[2, 4]$.

                ### 2. Fósforo (Balanço P-Remanescente)
                * **Correção:** Compara $P\text{-}mehl$ com o Nível Crítico da classe de $P\text{-}rem$.
                * **Crédito:** Se $P\text{-}solo > NC$, o excesso é subtraído da exportação.
                * **Exportação:** $Produtividade \times Fator_{Exp}$.
                * **Dose Final:** $((NC - P_{solo}) \times Fator_{Argila} + Exportação) \times \frac{100}{Teor_{Adubo}}$.

                ### 3. Potássio & Gesso
                * **K:** Elevação da saturação na CTC + Exportação obrigatória.
                * **Gesso:** $Argila (g/kg) \times Fator$, respeitando limites mín/max.
                """)

# --- EXECUÇÃO ---
params = configurar_interface()
p, f, t = params["path"]
if not p or not f or not t: st.info("Selecione a localização na barra lateral.")
else: pag_produtores(params)
