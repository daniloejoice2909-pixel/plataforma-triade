import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.interpolate import Rbf # Interpolador de alta qualidade (Estilo Krigagem)
import json

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

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # 1. CALAGEM (Fatores 560/400)
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    df['DOSE_CA_KG'] = (df['NC_CA_CMOL'] * 560 * 100 * 100) / (c_p["cao"] * c_p["prnt"])
    df['DOSE_MG_KG'] = (df['NC_MG_CMOL'] * 400 * 100 * 100) / (c_p["mgo"] * c_p["prnt"])
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CA_KG'], df['DOSE_MG_KG']) + c_p["reserva"]).round(2)
    df['RATIO_CA_MG'] = (df['Ca%'] + (df['NC_CA_CMOL']/df['CTC']*100)) / (df['Mg%'] + (df['NC_MG_CMOL']/df['CTC']*100 + 0.001))

    # 2. FÓSFORO (NC P-rem)
    def calc_p_vrt(row):
        prem = row['prem']
        nc = p_p["nc_0_4"] if prem <= 4 else p_p["nc_4_10"] if prem <= 10 else p_p["nc_10_19"] if prem <= 19 else p_p["nc_19_30"] if prem <= 30 else p_p["nc_30_45"] if prem <= 45 else p_p["nc_45_60"]
        arg = row['Argila']
        f_arg = p_p["f_muito_arg"] if arg > 600 else p_p["f_argiloso"] if arg > 350 else p_p["f_medio"] if arg > 150 else p_p["f_arenoso"]
        total_p2o5 = ((nc - row['P mehl']) * f_arg) + (prod_esp * p_p["f_exp"])
        return (max(total_p2o5, 0) * 100) / p_p["teor_adubo"]
    df['REC_P_ADUBO'] = df.apply(calc_p_vrt, axis=1).round(2)

    # 3. POTÁSSIO & 4. GESSO
    df['REC_K_ADUBO'] = (((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941) + (prod_esp * k_p["f_exp"])) * 100 / k_p["teor_adubo"]
    df['REC_GESSO'] = (df['Argila'] * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"])

    return df

# --- FUNÇÃO DE INTERPOLAÇÃO (PADRÃO INCERES) ---
def gerar_mapa_interpolado(df, coluna, titulo, contorno=None):
    # Força numérica para evitar ValueError
    df[coluna] = pd.to_numeric(df[coluna], errors='coerce').fillna(0)
    
    # Criação do Grid
    x = df['Longitude'].values
    y = df['Latitude'].values
    z = df[coluna].values
    
    xi = np.linspace(x.min(), x.max(), 100)
    yi = np.linspace(y.min(), y.max(), 100)
    xi, yi = np.meshgrid(xi, yi)
    
    # Interpolação Krigagem/Rbf
    rbf = Rbf(x, y, z, function='multiquadric', smooth=0.1)
    zi = rbf(xi, yi)
    
    fig = go.Figure()
    # Superfície contínua
    fig.add_trace(go.Contour(
        z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100),
        colorscale='Spectral_r', # Escala profissional estilo InCeres
        contours=dict(showlines=False, project_z=True),
        colorbar=dict(title=titulo)
    ))
    
    # Borda Preta do Contorno (se houver)
    if contorno:
         # Simulação de contorno no Plotly (em produção real, aqui entraria a leitura do GeoJSON)
         fig.update_layout(shapes=[dict(type="rect", x0=x.min(), y0=y.min(), x1=x.max(), y1=y.max(), line=dict(color="Black", width=2))])

    fig.update_layout(title=titulo, width=500, height=400, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# --- INTERFACE LATERAL ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.header("📍 Localização")
    produtores = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_prod = st.sidebar.selectbox("Produtor", produtores)
    if sel_prod == "+ Novo Produtor":
        sel_prod = st.sidebar.text_input("Nome")
        if sel_prod and sel_prod not in st.session_state['db']: st.session_state['db'][sel_prod] = {}
    
    # Hierarquia simplificada para o código
    fazendas = ["Fazenda Principal"]
    talhoes = ["Talhão 01"]
    params = {
        "global": {"produtividade": st.sidebar.number_input("Prod. Esperada (sc/ha)", 80.0)},
        "calagem": {"prnt": 80.0, "cao": 36.0, "mgo": 9.0, "target_ca": 60.0, "target_mg": 18.0, "reserva": 0.0, "preco": 250.0},
        "fosforo": {"nc_0_4": 8.0, "nc_4_10": 10.0, "nc_10_19": 12.0, "nc_19_30": 15.0, "nc_30_45": 18.0, "nc_45_60": 22.0, "f_muito_arg": 10.0, "f_argiloso": 8.0, "f_medio": 4.0, "f_arenoso": 2.0, "teor_adubo": 21.0, "f_exp": 0.8, "preco": 3200.0},
        "potassio": {"target_k": 3.2, "teor_adubo": 60.0, "f_exp": 1.2, "preco": 2800.0},
        "gesso": {"fator": 15.0, "min": 400.0, "max": 900.0, "preco": 180.0},
        "path": (sel_prod, fazendas[0], talhoes[0])
    }
    return params

# --- PÁGINA PRODUTORES ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Central de Mapas: {p}</h2>", unsafe_allow_html=True)
    tab_dados, tab_fert, tab_vrt = st.tabs(["📁 Dados e Contorno", "📊 Fertilidade", "🗺️ Recomendações VRT"])
    
    with tab_dados:
        c1, c2 = st.columns(2)
        with c1:
            up_csv = st.file_uploader("Subir Dados (A-Y)", type=['csv'])
            up_kml = st.file_uploader("Subir Contorno (KML/GeoJSON)", type=['kml','json','geojson'])
            if st.button("💾 Salvar e Processar"):
                if up_csv:
                    df = pd.read_csv(up_csv, sep=None, engine='python')
                    st.session_state['db'][p][f][t] = {"df": df, "kml": up_kml}
                    st.success("Dados Processados!")

    if p in st.session_state['db'] and f in st.session_state['db'][p] and t in st.session_state['db'][p][f]:
        data = st.session_state['db'][p][f][t]["df"]
        df_res = motor_calculo_v43(data, params)

        with tab_fert:
            st.write("### Análise Espacial de Fertilidade")
            if st.button("🔄 Gerar Mapas de Fertilidade"):
                attrs = ["pH", "Argila", "Ca", "Mg", "K", "Al", "P mehl", "V%", "Ca%", "Mg%", "K%"]
                for i in range(0, len(attrs), 2):
                    cols = st.columns(2)
                    with cols[0]: st.plotly_chart(gerar_mapa_interpolado(df_res, attrs[i], attrs[i]), use_container_width=True)
                    if i+1 < len(attrs):
                        with cols[1]: st.plotly_chart(gerar_mapa_interpolado(df_res, attrs[i+1], attrs[i+1]), use_container_width=True)

        with tab_vrt:
            st.write("### Prescrições em Taxa Variável")
            if st.button("🚀 Gerar Mapas de Recomendação"):
                recs = ["REC_CALCARIO", "REC_P_ADUBO", "REC_K_ADUBO", "REC_GESSO"]
                for i in range(0, len(recs), 2):
                    cols = st.columns(2)
                    with cols[0]: st.plotly_chart(gerar_mapa_interpolado(df_res, recs[i], recs[i]), use_container_width=True)
                    if i+1 < len(recs):
                        with cols[1]: st.plotly_chart(gerar_mapa_interpolado(df_res, recs[i+1], recs[i+1]), use_container_width=True)

            if st.button("⚙️ Motor Tríade"):
                st.dialog("Memória de Cálculo Tríade v43")
                st.markdown(r"""
                **1. Calagem (Equilíbrio de Bases):** - $\Delta Ca = \frac{(AlvoCa\% - AtualCa\%) \times CTC}{100}$  
                - $Dose_{Ca} = \frac{\Delta Ca \times 560 \times 10^4}{CaO\% \times PRNT\%}$  
                - $Dose_{Final} = Max(Dose_{Ca}, Dose_{Mg}) + Reserva$

                **2. Fósforo (P-Remanescente):** - $Dose_{P} = ((NC_{Prem} - P_{mehl}) \times F_{Argila} + Prod \times F_{exp}) \times \frac{100}{Teor_{Adubo}}$  
                - *Nota: Se Solo > NC, o excesso é subtraído da manutenção.*
                """)

# --- EXECUÇÃO ---
params = configurar_interface()
if not params["path"][0]: st.info("Selecione um produtor para começar.")
else: pag_produtores(params)
