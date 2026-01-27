import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf
from shapely.geometry import shape, Point
import json

# --- 1. CONFIGURAÇÃO DE TELA E TEMA ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica", page_icon="🌱")

# CSS para visual profissional (Cores da Tríade)
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #ffffff; border-radius: 5px 5px 0px 0px; gap: 1px; padding: 10px; }
    .stTabs [aria-selected="true"] { background-color: #e8f5e9; border-bottom: 3px solid #2e7d32; font-weight: bold; }
    .sidebar-content { background-color: #ffffff; padding: 20px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SISTEMA DE LOGIN (PROFISSIONAL) ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "triade2026": # Senha Mestra
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.image("LogoTriadeInceres.png", width=300)
        st.title("Acesso à Plataforma v43")
        st.text_input("Insira sua credencial de acesso:", type="password", on_change=password_entered, key="password")
        st.info("Entre em contato com a Tríade Agro para adquirir sua licença.")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Senha incorreta. Tente novamente:", type="password", on_change=password_entered, key="password")
        return False
    else:
        return True

if check_password():
    # --- 3. BARRA LATERAL (GESTÃO DO USUÁRIO) ---
    with st.sidebar:
        st.image("LogoTriadeInceres.png", width=180)
        st.markdown("### 👤 Usuário Ativo")
        st.write("**Danilo - Administrador**")
        st.markdown("---")
        st.markdown("### ⚙️ Parâmetros de Exportação")
        formato = st.selectbox("Formato do Relatório", ["PDF A4 (Oficial)", "Excel Detalhado"])
        area_ha = st.number_input("Área Total do Talhão (ha)", value=1.0)
        st.markdown("---")
        if st.button("Sair da Plataforma"):
            st.session_state["password_correct"] = False
            st.rerun()

    # --- 4. CORPO DA PLATAFORMA (ABAS) ---
    st.title("Dashboard de Precisão v43")
    
    tab_inicio, tab_diagnostico, tab_recomendacao, tab_ajustes = st.tabs([
        "🏠 Início & Upload", 
        "🔍 Diagnóstico de Solo", 
        "🚜 Prescrições v43", 
        "🛠️ Configurações Técnicas"
    ])

    with tab_inicio:
        st.subheader("Bem-vindo à sua área de trabalho")
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            st.info("1. Primeiro, suba o contorno da área (GeoJSON)")
            up_geo = st.file_uploader("Arquivo Geográfico", type=["json", "geojson"])
        with col_up2:
            st.info("2. Agora, suba os dados laboratoriais (Excel)")
            up_ex = st.file_uploader("Planilha de Solo", type=["xlsx"])
        
        if not up_geo or not up_ex:
            st.warning("Aguardando arquivos para iniciar o processamento...")

    # Variáveis de cálculo (dentro da aba de Ajustes no futuro, mas aqui para funcionar agora)
    prnt = 80.0
    v_ca_alvo = 60.0

    if up_geo and up_ex:
        # Processamento de Dados (Motor v43)
        data_geo = json.load(up_geo)
        poligono = shape(data_geo['features'][0]['geometry'] if 'features' in data_geo else data_geo)
        df = pd.read_excel(up_ex).apply(pd.to_numeric, errors='coerce').fillna(0)
        
        # Mapeamento: CTC na Coluna U (Índice 20)
        lat, lon = df.iloc[:,0], df.iloc[:,1]
        arg, p_rem, p_solo = df.iloc[:,4], df.iloc[:,5], df.iloc[:,6]
        ca, mg, k, al = df.iloc[:,7], df.iloc[:,8], df.iloc[:,9], df.iloc[:,10]
        ctc = df.iloc[:,20]

        # Função de Mapa Profissional
        def plot_mapa(data, titulo, unidade):
            b = poligono.bounds
            gx, gy = np.mgrid[b[0]-0.0006:b[2]+0.0006:200j, b[1]-0.0006:b[3]+0.0006:200j]
            rbf = Rbf(lon, lat, data, function='multiquadric', smooth=0.1)
            z = np.ma.masked_array(rbf(gx, gy), mask=np.array([[not poligono.contains(Point(x, y)) for y in gy[0,:]] for x in gx[:,0]]))
            
            fig, ax = plt.subplots(figsize=(10, 6))
            cp = ax.contourf(gx, gy, z, levels=6, cmap='Spectral_r')
            ax.plot(*poligono.exterior.xy, color='black', linewidth=2)
            plt.colorbar(cp).set_label(unidade)
            ax.axis('off')
            st.write(f"### {titulo}")
            st.pyplot(fig)
            st.metric(label=f"Média de {titulo}", value=f"{data.mean():.2f} {unidade}")
            plt.close()

        with tab_diagnostico:
            st.subheader("Análise da Fertilidade Atual")
            m1, m2 = st.columns(2)
            with m1: plot_mapa(arg, "Teor de Argila", "g/kg")
            with m2: plot_mapa(ctc, "CTC (Coluna U)", "cmolc/dm³")

        with tab_recomendacao:
            st.subheader("Mapas de Aplicação em Taxa Variável")
            # Cálculo de exemplo: Calcário
            rec_calc = (np.maximum(((v_ca_alvo/100*ctc)-ca)*0.56*(100/36), (18/100*ctc-mg)*0.40*(100/9)) * 1000 * (100/prnt)).clip(lower=0)
            plot_mapa(rec_calc, "Recomendação de Calcário", "kg/ha")
            
            st.button("📥 Gerar Relatório PDF Final")

        with tab_ajustes:
            st.subheader("Parâmetros do Algoritmo v43")
            st.write("Ajuste aqui as metas de saturação e fatores de correção.")
            # Colocar os inputs de fórmulas aqui
