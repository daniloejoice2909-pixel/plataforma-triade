import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from fpdf import FPDF
import io
import base64

# --- INICIALIZAÇÃO DO ECOSSISTEMA DE DADOS ---
if 'db' not in st.session_state:
    st.session_state['db'] = {} # {Produtor: {Fazenda: {Talhão: {df: pd.DataFrame, contorno: file, resultado: df}}}}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- INTERFACE VISUAL PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; }
    .stApp { background-color: #f8faf9; }
    .kpi-card {
        background-color: #ffffff; padding: 15px; border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center;
        border-top: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 22px; font-weight: 700; color: #1e3d59; }
    .section-header { color: #1e3d59; border-left: 6px solid #1e3d59; padding-left: 15px; margin: 25px 0; font-weight: bold; }
    .report-args { font-style: italic; color: #2c3e50; font-size: 11px; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE CÁLCULO TRÍADE V43 (REGRAS DE OURO) ---
def motor_calculo_v43(df, params):
    # 0. Normalização Case-Insensitive de Colunas
    mapeamento = {
        'ph': 'pH', 'argila': 'Argila', 'v%': 'V%', 'ctc': 'CTC', 'p mehl': 'P mehl', 
        'prem': 'prem', 'ca%': 'Ca%', 'mg%': 'Mg%', 'k%': 'K%', 'ca': 'Ca', 'mg': 'Mg', 'k': 'K'
    }
    df = df.rename(columns=lambda x: mapeamento.get(x.lower().strip(), x))
    
    cols_numericas = ['Argila', 'Ca%', 'Mg%', 'CTC', 'P mehl', 'K%', 'V%', 'pH', 'prem', 'K', 'Ca', 'Mg']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0

    p_p = params["fosforo"]; k_p = params["potassio"]; g_p = params["gesso"]; c_p = params["calagem"]
    prod_esp = params["global"]["produtividade"]

    # 1. CALAGEM (Fatores 560/400 + Elevação Ca/Mg Independente)
    df['NC_CA_CMOL'] = ((c_p["target_ca"] - df['Ca%']) * df['CTC'] / 100).clip(lower=0)
    df['NC_MG_CMOL'] = ((c_p["target_mg"] - df['Mg%']) * df['CTC'] / 100).clip(lower=0)
    
    # Conversão Estequiométrica para kg/ha
    df['DOSE_CA_KG'] = (df['NC_CA_CMOL'] * 560 * 100 * 100) / (c_p["cao"] * c_p["prnt"])
    df['DOSE_MG_KG'] = (df['NC_MG_CMOL'] * 400 * 100 * 100) / (c_p["mgo"] * c_p["prnt"])
    
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CA_KG'], df['DOSE_MG_KG']) + c_p["reserva"]).round(2)
    # Relação final teórica
    df['RATIO_CA_MG'] = (df['Ca%'] + (df['NC_CA_CMOL']/df['CTC']*100)) / (df['Mg%'] + (df['NC_MG_CMOL']/df['CTC']*100 + 0.001))

    # 2. FÓSFORO (NC P-rem + Abatimento de Excesso)
    def calc_p_v43(row):
        prem = row['prem']
        # Busca NC na tabela editável
        if prem <= 4: nc = p_p["nc_0_4"]
        elif prem <= 10: nc = p_p["nc_4_10"]
        elif prem <= 19: nc = p_p["nc_10_19"]
        elif prem <= 30: nc = p_p["nc_19_30"]
        elif prem <= 45: nc = p_p["nc_30_45"]
        else: nc = p_p["nc_45_60"]
        
        # Fator Argila
        arg = row['Argila']
        if arg > 60: f_arg = p_p["f_muito_arg"]
        elif arg > 35: f_arg = p_p["f_argiloso"]
        elif arg > 15: f_arg = p_p["f_medio"]
        else: f_arg = p_p["f_arenoso"]
        
        delta_p = nc - row['P mehl'] # Negativo se solo estiver acima do NC
        p_correcao = delta_p * f_arg
        p_exportacao = prod_esp * p_p["f_exp"]
        
        # Balanço de massa: se solo tem excesso, subtrai da exportação
        total_p2o5 = p_correcao + p_exportacao
        return (max(total_p2o5, 0) * 100) / p_p["teor_adubo"]

    df['REC_P_ADUBO'] = df.apply(calc_p_v43, axis=1).round(2)

    # 3. POTÁSSIO (Correção p/ 3.2% CTC + Exportação Obrigatória)
    df['K_CORR_KG'] = ((k_p["target_k"] - df['K%']).clip(lower=0) * df['CTC'] / 100 * 941)
    df['K_EXP_KG'] = prod_esp * k_p["f_exp"]
    df['REC_K_ADUBO'] = ((df['K_CORR_KG'] + df['K_EXP_KG']) * 100 / k_p["teor_adubo"]).round(2)

    # 4. GESSO (Argila % -> g/kg -> Fator 15)
    df['REC_GESSO'] = (df['Argila'] * 10 * g_p["fator"]).clip(lower=g_p["min"], upper=g_p["max"]).round(2)

    # 5. FINANCEIRO
    df['C_CALC'] = (df['REC_CALCARIO']/1000) * c_p["preco"]
    df['C_P'] = (df['REC_P_ADUBO']/1000) * p_p["preco"]
    df['C_K'] = (df['REC_K_ADUBO']/1000) * k_p["preco"]
    df['C_GESSO'] = (df['REC_GESSO']/1000) * g_p["preco"]
    df['C_TOTAL'] = df['C_CALC'] + df['C_P'] + df['C_K'] + df['C_GESSO']

    return df

# --- FUNÇÃO DE INTERPOLAÇÃO GEOESTATÍSTICA (KRIGAGEM RBF) ---
def gerar_mapa_krigagem(df, col, title):
    # Proteção de tipos
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    x, y, z = df['Longitude'].values, df['Latitude'].values, df[col].values
    
    # Grid de Alta Resolução (Padrão Profissional)
    xi = np.linspace(x.min(), x.max(), 100)
    yi = np.linspace(y.min(), y.max(), 100)
    xi, yi = np.meshgrid(xi, yi)
    
    # Interpolação Krigagem Linear
    try:
        rbf = Rbf(x, y, z, function='linear', smooth=0.1)
        zi = rbf(xi, yi)
    except:
        zi = np.full(xi.shape, z.mean())

    fig = go.Figure(data=go.Contour(
        z=zi, x=np.linspace(x.min(), x.max(), 100), y=np.linspace(y.min(), y.max(), 100),
        colorscale='RdYlBu_r', # Visual Térmico InCeres
        contours=dict(showlines=False, project_z=True),
        line_width=0, colorbar=dict(title=dict(text=col, font=dict(size=10)))
    ))
    
    # Layout do Mapa
    fig.update_layout(
        title=f"<b>{title}</b>", margin=dict(l=10, r=10, t=40, b=10), height=380,
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        plot_bgcolor='white'
    )
    
    # Estatísticas abaixo do mapa
    stats = f"Mín: {z.min():.2f} | Máx: {z.max():.2f} | Méd: {z.mean():.2f}"
    return fig, stats

# --- INTERFACE LATERAL (RESTAURADA E BIDIRECIONAL) ---
def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.header("📍 Localização Estratégica")
    
    # Hierarquia Persistente
    p_names = list(st.session_state['db'].keys()) + ["+ Novo Produtor"]
    sel_p = st.sidebar.selectbox("Produtor", p_names)
    if sel_p == "+ Novo Produtor":
        sel_p = st.sidebar.text_input("Nome do Cliente")
        if sel_p and sel_p not in st.session_state['db']: st.session_state['db'][sel_p] = {}

    faz_names = list(st.session_state['db'].get(sel_p, {}).keys()) + ["+ Nova Fazenda"]
    sel_f = st.sidebar.selectbox("Fazenda", faz_names)
    if sel_f == "+ Nova Fazenda":
        sel_f = st.sidebar.text_input("Nome da Fazenda")
        if sel_f and sel_f not in st.session_state['db'][sel_p]: st.session_state['db'][sel_p][sel_f] = {}

    tal_names = list(st.session_state['db'].get(sel_p, {}).get(sel_f, {}).keys()) + ["+ Novo Talhão"]
    sel_t = st.sidebar.selectbox("Talhão", tal_names)
    if sel_t == "+ Novo Talhão":
        sel_t = st.sidebar.text_input("ID do Talhão")
        if sel_t and sel_t not in st.session_state['db'][sel_p][sel_f]:
            st.session_state['db'][sel_p][sel_f][sel_t] = {"df": None, "contorno": None}

    st.sidebar.divider()
    st.sidebar.header("⚙️ Atributos (Flexibilidade Total)")
    
    with st.sidebar.expander("🌍 Global & Produtividade"):
        prod = st.number_input("Produtividade Alvo (sc/ha)", value=80.0, step=1.0)

    with st.sidebar.expander("🪨 Calagem Atômica"):
        c_prnt = st.number_input("PRNT (%)", 80.0); c_cao = st.number_input("CaO (%)", 36.0); c_mgo = st.number_input("MgO (%)", 9.0)
        c_t_ca = st.number_input("Alvo Ca/CTC (%)", 60.0); c_t_mg = st.number_input("Alvo Mg/CTC (%)", 18.0)
        c_res = st.number_input("Reserva (kg/ha)", 0.0); c_preco = st.number_input("R$/Ton Calcário", 280.0)

    with st.sidebar.expander("🧪 Fósforo Remanescente"):
        st.write("**Níveis Críticos**")
        nc04 = st.number_input("0-4 P-rem", 8.0); nc410 = st.number_input("4-10 P-rem", 10.0); nc1019 = st.number_input("10-19 P-rem", 12.0)
        nc1930 = st.number_input("19-30 P-rem", 15.0); nc3045 = st.number_input("30-45 P-rem", 18.0); nc4560 = st.number_input("45-60 P-rem", 22.0)
        st.write("**Fatores Argila**")
        f_m_arg = st.number_input("M. Argiloso (x10)", 10.0); f_arg = st.number_input("Argiloso (x8)", 8.0)
        f_med = st.number_input("Médio (x4)", 4.0); f_are = st.number_input("Arenoso (x2)", 2.0)
        p_teor = st.number_input("Teor Adubo (%)", 21.0); p_exp = st.number_input("Fator Exp P", 0.8); p_preco = st.number_input("R$/Ton Adubo P", 3200.0)

    with st.sidebar.expander("🍌 Potássio & Gesso"):
        k_target = st.number_input("Alvo K CTC (%)", 3.2); k_teor = st.number_input("Teor K2O (%)", 60.0); k_exp = st.number_input("Fator Exp K", 1.2); k_preco = st.number_input("R$/Ton Adubo K", 2900.0)
        st.divider()
        g_fator = st.number_input("Fator Argila (Gesso)", 15.0); g_min = st.number_input("Mínimo Gesso", 400.0); g_max = st.number_input("Máximo Gesso", 900.0); g_preco = st.number_input("R$/Ton Gesso", 190.0)

    params = {
        "global": {"produtividade": prod},
        "calagem": {"prnt": c_prnt, "cao": c_cao, "mgo": c_mgo, "target_ca": c_t_ca, "target_mg": c_t_mg, "reserva": c_res, "preco": c_preco},
        "fosforo": {"nc_0_4": nc04, "nc_4_10": nc410, "nc_10_19": nc1019, "nc_19_30": nc1930, "nc_30_45": nc3045, "nc_45_60": nc4560, "f_muito_arg": f_m_arg, "f_argiloso": f_arg, "f_medio": f_med, "f_arenoso": f_are, "teor_adubo": p_teor, "f_exp": p_exp, "preco": p_preco},
        "potassio": {"target_k": k_target, "teor_adubo": k_teor, "f_exp": k_exp, "preco": k_preco},
        "gesso": {"fator": g_fator, "min": g_min, "max": g_max, "preco": g_preco},
        "path": (sel_p, sel_f, sel_t)
    }
    return params

# --- PÁGINA PRINCIPAL ---
def pag_produtores(params):
    p, f, t = params["path"]
    st.markdown(f"<h2 class='section-header'>Consultoria: {p} | {f} | {t}</h2>", unsafe_allow_html=True)
    tab_dados, tab_fert, tab_vrt, tab_report, tab_export = st.tabs(["📁 Dados", "📊 Fertilidade", "🗺️ Recomendações VRT", "📄 Relatório", "📥 Exportar"])
    
    with tab_dados:
        c1, c2 = st.columns(2)
        with c1:
            up_csv = st.file_uploader("Análise de Solo (A-Y)", type=['csv'], key=f"csv_{t}")
            up_kml = st.file_uploader("Contorno Geográfico", type=['kml','json','geojson'], key=f"kml_{t}")
            if st.button("🚀 Processar e Salvar Talhão"):
                if up_csv:
                    df = pd.read_csv(up_csv, sep=None, engine='python', encoding='utf-8-sig')
                    st.session_state['db'][p][f][t]["df"] = df
                    st.success("Dados vinculados com sucesso!")
        with c2:
            if st.session_state['db'][p][f][t]["df"] is not None:
                st.dataframe(st.session_state['db'][p][f][t]["df"].head(10))

    if st.session_state['db'][p][f][t]["df"] is not None:
        df_res = motor_calculo_v43(st.session_state['db'][p][f][t]["df"], params)
        st.session_state['db'][p][f][t]["resultado"] = df_res

        # Balão de Alerta Ca/Mg
        avg_ratio = df_res['RATIO_CA_MG'].mean()
        if avg_ratio < 2 or avg_ratio > 4:
            st.toast(f"Relação Ca/Mg ({avg_ratio:.2f}) fora do equilíbrio Tríade (2-4)!", icon="⚖️")

        with tab_fert:
            st.write("### Mapas de Atributos de Solo")
            attrs = ["pH", "Argila", "Ca", "Mg", "K", "V%", "Ca%", "Mg%", "K%", "P mehl", "prem"]
            for i in range(0, len(attrs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(attrs):
                        with cols[j]:
                            fig, stats = gerar_mapa_krigagem(df_res, attrs[i+j], attrs[i+j])
                            st.plotly_chart(fig, use_container_width=True)
                            st.info(stats)

        with tab_vrt:
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f"<div class='kpi-card'><small>Custo Calcário</small><div class='kpi-value'>R$ {df_res['C_CALC'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='kpi-card'><small>Custo Fósforo</small><div class='kpi-value'>R$ {df_res['C_P'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='kpi-card'><small>Custo Potássio</small><div class='kpi-value'>R$ {df_res['C_K'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='kpi-card'><small>TOTAL</small><div class='kpi-value' style='color:#27ae60'>R$ {df_res['C_TOTAL'].mean():.2f}/ha</div></div>", unsafe_allow_html=True)

            recs = [("REC_CALCARIO", "Calcário"), ("REC_P_ADUBO", "Fosfatado"), ("REC_K_ADUBO", "Potássico"), ("REC_GESSO", "Gesso")]
            args_tec = {
                "Calcário": "Equilíbrio atômico de bases para máxima eficiência da CTC.",
                "Fosfatado": "Balanço via P-remanescente que abate o excesso do solo e foca na produtividade.",
                "Potássico": "Correção de saturação somada à exportação real da cultura.",
                "Gesso": "Melhoria do perfil subsuperficial baseada no teor real de argila."
            }
            
            for i in range(0, len(recs), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(recs):
                        with cols[j]:
                            fig, stats = gerar_mapa_krigagem(df_res, recs[i+j][0], recs[i+j][1])
                            st.plotly_chart(fig, use_container_width=True)
                            st.success(stats)
                            st.markdown(f"<div class='report-args'><b>Vantagem Tríade:</b> {args_tec[recs[i+j][1]]}</div>", unsafe_allow_html=True)

            if st.button("⚙️ Ver Motor Tríade (Fórmulas)"):
                st.dialog("Memória de Cálculo Técnica")
                st.markdown(r"""
                **1. Calagem:** $\Delta B = \frac{(Alvo\% - Atual\%) \times CTC}{100}$. Dose = $\frac{\Delta B \times Fator \times 10^4}{Teor \times PRNT}$.  
                **2. Fósforo:** $Dose = \frac{((NC_{Prem} - P_{solo}) \times F_{Arg} + Prod \times F_{exp}) \times 100}{Teor_{Adubo}}$.  
                **3. Potássio:** Elevação para 3,2% da CTC + Exportação obrigatória.  
                **4. Gesso:** $(Argila\% \times 10) \times Fator_{Gesso}$.
                """)

        with tab_report:
            st.write("### Gerador de Relatório Profissional")
            if st.button("📝 Consolidar Relatório para PDF"):
                st.info("O sistema está processando as imagens de Krigagem para o documento final...")
                st.download_button("⬇️ Baixar Relatório (Simulado)", data="PDF_DATA", file_name=f"Relatorio_{t}.pdf")

        with tab_export:
            st.write("### Exportação para Monitores")
            st.columns(3)[0].selectbox("Selecione o Formato", ["John Deere (Rx)", "Case/NH (CN1)", "Trimble", "Stara", "Shapefile Isolado"])
            st.button("📦 Gerar Pacote de Exportação (.ZIP)")

# --- EXECUÇÃO ---
params = configurar_interface()
p, f, t = params["path"]
if not p or not f or not t: st.info("Selecione ou crie um cliente na barra lateral para começar.")
else: pag_produtores(params)
