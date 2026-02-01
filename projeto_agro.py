import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO DA PÁGINA (UI/UX) ---
st.set_page_config(page_title="Tríade Agro Estratégica", layout="wide")

# --- CSS CUSTOMIZADO PARA PADRÃO PREMIUM ---
st.markdown("""
    <style>
    /* Fundo cinza claro */
    .stApp {
        background-color: #f8f9fa;
    }
    /* Estilização dos Cards de KPI */
    .kpi-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #e9ecef;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 5px;
    }
    .kpi-label {
        font-size: 14px;
        color: #6c757d;
        font-family: 'Open Sans', sans-serif;
    }
    /* Menu Lateral */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e9ecef;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO: BARRA LATERAL (MENU E ATRIBUTOS) ---
def configurar_interface_lateral():
    # Logo e Navegação
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True) # Nome do arquivo salvo no seu histórico
    st.sidebar.markdown("---")
    
    menu = st.sidebar.radio(
        "Navegação",
        ["🏠 Dashboard Principal", "👥 Produtores", "🗺️ Mapas VRT", "📊 Análises de Solo", "⚙️ Configurações"],
        index=0
    )
    
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Parâmetros Técnicos")
    
    # 1. CALAGEM (BASE ATÔMICA - Fatores 560 e 400 mantidos)
    with st.sidebar.expander("🪨 Calcário e Calagem", expanded=False):
        p_prnt = st.number_input("PRNT do Calcário (%)", 80.0)
        p_cao = st.number_input("Teor de CaO no Calcário (%)", 36.0)
        p_mgo = st.number_input("Teor de MgO no Calcário (%)", 9.0)
        target_ca = st.number_input("Alvo Ca na CTC (%)", 60.0)
        target_mg = st.number_input("Alvo Mg na CTC (%)", 18.0)
        calc_extra = st.number_input("Adicional de Reserva (t/ha)", 0.0)
        fator_ca = 560  
        fator_mg = 400  

    # 2. FÓSFORO (TABELA P-REM COMPLETA E EDITÁVEL)
    with st.sidebar.expander("🧪 Fósforo (P-rem)", expanded=True):
        st.write("Níveis Críticos (mg/dm³):")
        niveis_p = {
            "0-4": st.number_input("P-rem 0-4", 9.0),
            "4-10": st.number_input("P-rem 4-10", 10.5),
            "10-19": st.number_input("P-rem 10-19", 12.5),
            "19-30": st.number_input("P-rem 19-30", 15.0),
            "30-45": st.number_input("P-rem 30-45", 17.5),
            "45-60": st.number_input("P-rem 45-60", 19.3)
        }
        f_text = st.number_input("Fator de Textura (Argila >60%)", 10.0)
        p_exp = st.number_input("Exportação P2O5 (kg/sc)", 0.8)
        p_teor_adubo = st.number_input("% P2O5 no Adubo", 21.0)

    return menu, {
        "calagem": (p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, fator_ca, fator_mg),
        "fosforo": (niveis_p, f_text, p_exp, p_teor_adubo)
    }

# --- FUNÇÃO: CÁLCULO VRT (REGRAS DE OURO MANTIDAS) ---
def calcular_recomendacoes(df, params):
    p_prnt, p_cao, p_mgo, target_ca, target_mg, calc_extra, f_ca, f_mg = params["calagem"]
    niveis_p, f_text, p_exp, p_teor_adubo = params["fosforo"]
    
    # A. CALAGEM (REGRA: Máximo entre CaO e MgO)
    df['NC_CA'] = ((target_ca - df['CA_PERC']).clip(lower=0) * df['CTC'] / 100)
    df['NC_MG'] = ((target_mg - df['MG_PERC']).clip(lower=0) * df['CTC'] / 100)
    
    df['DOSE_CAO'] = (df['NC_CA'] * f_ca * 100) / (p_cao * p_prnt)
    df['DOSE_MGO'] = (df['NC_MG'] * f_mg * 100) / (p_mgo * p_prnt)
    
    # REC_CALCARIO é o máximo entre as doses + adicional
    df['REC_CALCARIO'] = (np.maximum(df['DOSE_CAO'], df['DOSE_MGO']) + calc_extra).round(2)

    # B. FÓSFORO (Lógica P-REM)
    def buscar_nc_p(prem):
        if prem <= 4: return niveis_p["0-4"]
        elif prem <= 10: return niveis_p["4-10"]
        elif prem <= 19: return niveis_p["10-19"]
        elif prem <= 30: return niveis_p["19-30"]
        elif prem <= 45: return niveis_p["30-45"]
        else: return niveis_p["45-60"]

    df['NC_P'] = df['PREM'].apply(buscar_nc_p)
    df['REC_P_VRT'] = (((df['NC_P'] - df['P']).clip(lower=0) * f_text) * 100 / p_teor_adubo).round(2)
    
    return df

# --- FUNÇÃO: DASHBOARD VISUAL (HOME) ---
def exibir_home():
    st.markdown("<h2 style='color: #2c3e50;'>Painel de Gestão Estratégica</h2>", unsafe_allow_html=True)
    
    # Grid de Cards KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-label'>Total Monitorado</div>
            <div class='kpi-value'>12.450 ha</div>
        </div>""", unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-label'>Clientes Ativos</div>
            <div class='kpi-value'>24</div>
        </div>""", unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-label'>Alertas NDVI</div>
            <div class='kpi-value' style='color: #e74c3c;'>03 Áreas</div>
        </div>""", unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""<div class='kpi-card'>
            <div class='kpi-label'>Relatórios Pendentes</div>
            <div class='kpi-value' style='color: #f39c12;'>05</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Atividades Recentes")
    # Exemplo de lista de atividades
    st.info("✅ Relatório de Gessagem exportado para: Fazenda Santa Fé - Talhão 02")
    st.warning("⚠️ Nova análise de solo pendente de processamento: Produtor Gilson Berneck")

# --- EXECUÇÃO PRINCIPAL ---
menu_selecionado, parametros = configurar_interface_lateral()

if menu_selecionado == "🏠 Dashboard Principal":
    exibir_home()
else:
    st.write(f"Você está na seção: {menu_selecionado}")
    # Aqui entrariam as lógicas de upload de planilha e geração de mapas
