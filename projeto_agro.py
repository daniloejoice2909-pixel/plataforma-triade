import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
import json

# --- INICIALIZAÇÃO DO BANCO DE DADOS PERSISTENTE ---
if 'db' not in st.session_state:
    st.session_state['db'] = {} # {Produtor: {Fazenda: {Talhão: {df: pd.DataFrame, contorno: bytes}}}}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- ESTILIZAÇÃO CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card {
        background-color: #ffffff; padding: 12px; border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05); text-align: center;
        border-top: 4px solid #1e3d59; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 12px; margin: 15px 0; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO V43 (INTEGRIDADE TOTAL) ---
def motor_calculo_v43(df, params):
    # 0. Normalização e Tipagem
    mapeamento = {
        'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 
        'prem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 'k%': 'K%', 'ca': 'Ca', 'mg': 'Mg', 'k': 'K', 'al': 'Al'
    }
    df = df.rename(columns=lambda x: mapeamento.get(x.lower().strip(), x))
    
    cols_foc = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'K', 'Ca', 'Mg', 'Al']
    for col in cols_foc:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # 1. CALAGEM (Alvos Ca/Mg + Fatores 560/400)
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    
    df['DOSE_CA_KG'] = (df['NC_CA_CMOL'] * 560 * 100 * 100) / (c_p["cao"] * c_p["prnt"])
    df['DOSE_MG_KG'] = (df['NC_MG_CMOL'] * 400 * 100 * 100) / (c_p["mgo"] * c_p["prnt"])
    
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CA_KG'], df['DOSE_MG_KG']) + c_p["reserva"]).round(2)
    df['RATIO_CA_MG'] = (df['Ca%'] + (df['NC_CA_CMOL']/df['CTC']*100)) / (df['Mg%'] + (df['NC_MG_CMOL']/df['CTC']*100 + 0.001))

    # 2. FÓSFORO (P-rem + Balanço + Exportação)
    def calc_p(row):
        prem = row['prem']
        nc = p_p["nc_0_4"] if prem <= 4 else p_p["nc_4_10"] if prem <= 10 else p_p["nc_10_19"] if prem <= 19 else p_p["nc_19_30"] if prem <= 30 else p_p["nc_30_45"] if prem <= 45 else p_p["nc_45_60"]
        arg = row['Argila']
        f_arg = p_p["f_muito_arg"] if arg > 60 else p_p["f_argiloso"] if arg > 35 else p_p["f_medio"] if arg > 15 else p_p["f_arenoso"]
        
        delta_p = nc - row['P mehl']
        p_corr = delta_p * f_arg # Valor negativo = excesso vira crédito
        p_exp = prod_esp * p_p["f_exp"]
        return (max(p_corr + p_exp, 0) * 100) / p_p["teor_adubo"]
    df['REC_P_ADUBO'] = df.apply(calc_p, axis=1).round(2)

    # 3. POTÁSSIO (3.2% CTC + Exportação Obrigatória)
    df['K_CORR'] = ((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941)
    df['REC_K_ADUBO'] = ((df['K_CORR'] + (prod_esp * k_p["f_exp"])) * 100 / k_p["teor_adubo"]).round(2)

    # 4. GESSO (Argila % * 10 * Fator 15) -> Convertendo % para g/kg
    df['REC_GESSO'] = (df['Argila'] * 10 * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    # 5. CUSTOS FINANCEIROS
    df['C_CALC'] = (df['REC_CALCARIO']/1000) * c_p["preco"]
    df['C_P'] = (df['REC_P_ADUBO']/1000) * p_p["preco"]
    df['C_K'] = (df['REC_K_ADUBO']/1000) * k_p["preco"]
    df['C_GESSO'] = (df['REC_GESSO']/1000) * g_p["preco"]
    df['C_TOTAL'] = df['C_CALC'] + df['C_P'] + df['C_K'] + df['C_GESSO']

    return df

# --- FUNÇÃO DE INTERPOLAÇÃO KRIGAGEM (ESTILO INCERES) ---
def plot_kriging(df, col, title):
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    x, y, z = df['Longitude'].values, df['Latitude'].values, df[col].values
    xi = np.linspace(x.min(), x.max(), 80)
    yi = np.linspace(y.min(), y.max(), 80)
    xi, yi = np.meshgrid(xi, yi)
    
    # Krigagem via Rbf (Radial Basis Function)
    rbf = Rbf(x, y, z, function='linear', smooth=0.1)
    zi = rbf(xi, yi)

    fig = go.Figure(data=go.Contour(
        z=zi, x=np.linspace(x.min(), x.max(), 80), y=np.linspace(y.min(), y.max(), 80),
        colorscale='coolwarm', # Padrão InCeres/Tríade
        contours=dict(showlines=False, project_z=True),
        line_width=0, colorbar=dict(title=col)
    ))
    fig.update_layout(title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=350,
                      plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    return fig

# --- INTERFACE LATERAL (RESTAURADA) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.header("📍 Navegação e Hierarquia")
    
    # Hierarquia
    p_names = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_p = st.sidebar.selectbox("Produtor", p_names)
    if sel_p == "+ Novo Produtor":
        sel_p = st.sidebar.text_input("Nome Produtor")
        if sel_p and sel_p not in st.session_state['db']: st.session_state['db'][sel_p] = {}

    faz_names = list(st.session_state['db'].get(sel_p, {}).keys()) + ["+ Nova Fazenda"]
    sel_f = st.sidebar.selectbox("Fazenda", faz_names)
    if sel_f == "+ Nova Fazenda":
        sel_f = st.sidebar.text_input("Nome Fazenda")
        if sel_f and sel_f not in st.session_state['db'][sel_p]: st.session_state['db'][sel_p][sel_f] = {}

    tal_names = list(st.session_state['db'].get(sel_p, {}).get(sel_f, {}).keys()) + ["+ Novo Talhão"]
    sel_t = st.sidebar.selectbox("Talhão", tal_names)
    if sel_t == "+ Novo Talhão":
        sel_t = st.sidebar.text_input("ID Talhão")
        if sel_t and sel_t not in st.session_state['db'][sel_p][sel_f]:
            st.session_state['db'][sel_p][sel_f][sel_t] = {"df": None, "contorno": None}

    st.sidebar.divider()
    st.sidebar.header("⚙️ Atributos Técnicos")
    with st.sidebar.expander("🌍 Global"):
        prod = st.number_input("Produtividade Esperada (sc/ha)", 80.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_prnt = st.number_input("PRNT (%)", 80.0); c_cao = st.number_input("CaO (%)", 36.0); c_mgo = st.number_input("MgO (%)", 9.0)
        c_t_ca = st.number_input("Alvo Ca (%)", 60.0); c_t_mg = st.number_input("Alvo Mg (%)", 18.0)
        c_res = st.number_input("Reserva (kg/ha)", 0.0); c_preco = st.number_input("R$/Ton Calcário", 250.0)

    with st.sidebar.expander("🧪 Fósforo"):
        nc04 = st.number_input("0-4 Prem", 8.0); nc410 = st.number_input("4,1-10 Prem", 10.0); nc4560 = st.number_input("45-60 Prem", 22.0)
        f_m_arg = st.number_input("Muito Argiloso (x10)", 10.0); f_are = st.number_input("Arenoso (x2)", 2.0)
        p_teor = st.number_input("Teor P2O5 (%)", 21.0); p_exp = st.number_input("Exp. P (kg/sc)", 0.8); p_preco = st.number_input("R$/Ton P", 3200.0)

    with st.sidebar.expander("🍌 Potássio"):
        k_target = st.number_input("Alvo K CTC (%)", 3.2); k_teor = st.number_input("Teor K2O (%)", 60.0)
        k_exp = st.number_input("Exp. K (kg/sc)", 1.2); k_preco = st.number_input("R$/Ton K", 2800.0)

    with st.sidebar.expander("⚪ Gesso"):
        g_fator = st.number_input("Fator Gesso", 15.0); g_min = st.number_input("Mín (kg/ha)", 400.0)
        g_max = st.number_input("Máx (kg/ha)", 900.0); g_preco = st.number_input("R$/Ton Gesso", 180.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {"nc_0_4": nc04, "nc_4_10": nc410, "nc_10_19": 12.0, "nc_19_30": 15.0, "nc_30_45": 18.0, "nc_45_60": nc4560, "f_muito_arg": f_m_arg, "f_argiloso": 8.0, "f_medio": 4.0, "f_arenoso": f_are, "teor_adubo": p_teor, "f_exp": p_exp, "preco": p_preco},
        "potassio": {"target_k": k_target, "teor_adubo": k_teor, "f_exp": k_exp, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco},
        "path": (sel_p, sel_f, sel_t)
    }
    return params

# --- PÁGINA PRODUTORES ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Talhão: {t} | Fazenda: {f} | Cliente: {p}</h2>", unsafe_allow_html=True)
    tab_dados, tab_fert, tab_vrt = st.tabs(["📁 Dados e Contorno", "📊 Fertilidade Krigagem", "🗺️ Recomendações VRT"])
    
    with tab_dados:
        c1, c2 = st.columns(2)
        with c1:
            up_csv = st.file_uploader("Subir CSV Solo (A-Y)", type=['csv'], key=f"csv_{t}")
            up_kml = st.file_uploader("Subir Contorno (KML/JSON/GEOJSON)", type=['kml','json','geojson','zip'], key=f"kml_{t}")
            if st.button("💾 Salvar no Banco de Dados"):
                if up_csv:
                    df = pd.read_csv(up_csv, sep=None, engine='python', encoding='utf-8-sig')
                    st.session_state['db'][p][f][t]["df"] = df
                    st.success("Dados Salvos!")
                if up_kml:
                    st.session_state['db'][p][f][t]["contorno"] = up_kml
                    st.success("Contorno Salvo!")
        with c2:
            if st.session_state['db'][p][f][t]["df"] is not None:
                st.dataframe(st.session_state['db'][p][f][t]["df"])

    if st.session_state['db'][p][f][t]["df"] is not None:
        df_res = motor_calculo_v43(st.session_state['db'][p][f][t]["df"], params)
        
        # Alerta Ca/Mg
        avg_ratio = df_res['RATIO_CA_MG'].mean()
        if avg_ratio < 2 or avg_ratio > 4:
            st.toast(f"Relação Ca/Mg ({avg_ratio:.2f}) Fora do Intervalo!", icon="⚖️")

        with tab_fert:
            st.write("### Mapas de Fertilidade (Alta Resolução)")
            if st.button("🔄 Gerar Mapas de Fertilidade"):
                attrs = ["pH", "Argila", "Ca", "Mg", "K", "Al", "P mehl", "V%", "Ca%", "Mg%", "K%"]
                for i in range(0, len(attrs), 2):
                    cols = st.columns(2)
                    with cols[0]: st.plotly_chart(plot_kriging(df_res, attrs[i], f"Mapa de {attrs[i]}"), use_container_width=True)
                    if i+1 < len(attrs):
                        with cols[1]: st.plotly_chart(plot_kriging(df_res, attrs[i+1], f"Mapa de {attrs[i+1]}"), use_container_width=True)

        with tab_vrt:
            # KPIs Financeiros
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><small>Custo Calcário</small><div class='kpi-value'>R$ {df_res['C_CALC'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><small>Custo Fósforo</small><div class='kpi-value'>R$ {df_res['C_P'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><small>Custo Potássio</small><div class='kpi-value'>R$ {df_res['C_K'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><small>TOTAL INVESTIDO</small><div class='kpi-value' style='color:#27ae60'>R$ {df_res['C_TOTAL'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)

            if st.button("🚀 Gerar Mapas VRT"):
                recs = [("REC_CALCARIO", "Calcário"), ("REC_P_ADUBO", "Fósforo"), ("REC_K_ADUBO", "Potássio"), ("REC_GESSO", "Gesso")]
                for i in range(0, len(recs), 2):
                    cols = st.columns(2)
                    with cols[0]: st.plotly_chart(plot_kriging(df_res, recs[i][0], f"VRT: {recs[i][1]} (kg/ha)"), use_container_width=True)
                    if i+1 < len(recs):
                        with cols[1]: st.plotly_chart(plot_kriging(df_res, recs[i+1][0], f"VRT: {recs[i+1][1]} (kg/ha)"), use_container_width=True)

            if st.button("⚙️ Motor Tríade"):
                st.dialog("Memória de Cálculo Técnica v43")
                st.markdown(r"""
                ### 1. Calagem (Ca/Mg na CTC)
                - **Passo 1:** Centimol de correção $\Delta Ca$ e $\Delta Mg$ baseado nos alvos editáveis.
                - **Passo 2:** Dose individual usando fatores 560 ($Ca$) e 400 ($Mg$).
                - **Dose Final:** $MAX(Dose_{Ca}, Dose_{Mg}) + Reserva$ (em kg/ha).
                - **Trava:** Verificação visual da relação final $Ca/Mg$ (ideal 2-4).

                ### 2. Fósforo (P-rem)
                - **P-mehl vs NC:** Se $P_{solo} > NC$, o excedente é subtraído da exportação.
                - **Exportação:** $Produtividade \times Fator_{Exp}$.
                - **Resultado:** Dose comercial corrigida por classe de Argila.

                ### 3. Potássio e Gesso
                - **Potássio:** Elevação para 3,2% da CTC **somado** à exportação da safra.
                - **Gesso:** $Argila (\%) \times 10 \times Fator_{Gesso}$. Travas de dose mínima e máxima.
                """)

# --- EXECUÇÃO ---
params = configurar_interface()
p, f, t = params["path"]
if not p or not f or not t: st.info("Selecione os dados na lateral para processar.")
else: pag_produtores(params)
