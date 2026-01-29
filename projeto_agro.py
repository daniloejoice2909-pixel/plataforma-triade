import streamlit as st
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

# --- 2. CSS PARA TRAVAMENTO TOTAL E CONTRASTE ALTO ---
def aplicar_visual_fixo(nome_imagem):
    bin_str = get_base64(nome_imagem)
    if bin_str:
        st.markdown(f"""
        <style>
        /* Trava de visualização sem rolagem */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMainViewContainer"] {{
            height: 100vh !important;
            width: 100vw !important;
            overflow: hidden !important;
            margin: 0; padding: 0;
        }}
        
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: 100% 100%;
            background-repeat: no-repeat;
            background-position: center;
        }}

        /* Painel de vidro escurecido para proteção do texto */
        .glass-panel {{
            background: rgba(0, 0, 0, 0.85); 
            padding: 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            width: 850px;
            margin: auto;
            box-shadow: 0px 10px 30px rgba(0,0,0,0.7);
        }}

        /* Textos em Branco, Negrito e com Sombra Projetada */
        label, p, span, h3 {{
            color: #FFFFFF !important;
            font-weight: bold !important;
            text-transform: uppercase;
            font-size: 0.85rem !important;
            text-shadow: 2px 2px 4px rgba(0,0,0,1) !important;
        }}

        .titulo-dourado {{
            color: #FFD700 !important;
            font-weight: 900 !important;
            font-size: 1.7rem !important;
            text-align: center;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.9) !important;
        }}

        /* Ajuste dos botões "Browse Files" - Fundo Branco, Letra Preta */
        [data-testid="stFileUploader"] section button {{
            background-color: #FFFFFF !important;
            color: #000000 !important;
            font-weight: bold !important;
            border-radius: 5px !important;
            border: 1px solid #ccc !important;
        }}
        
        /* Inputs de texto Brancos com letra Preta */
        .stTextInput input {{
            background-color: white !important;
            color: black !important;
            font-weight: bold !important;
        }}

        header, footer, [data-testid="stHeader"] {{ display: none !important; }}
        </style>
        """, unsafe_allow_html=True)

# --- 3. CONTROLE DE NAVEGAÇÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
if "pagina" not in st.session_state:
    st.session_state.pagina = "login"

# ==========================================
# PÁGINA 1: LOGIN (Fundo OI_AGRISHOW)
# ==========================================
if not st.session_state.logado:
    aplicar_visual_fixo("OI_AGRISHOW.jpg")
    
    st.markdown('<div style="position: absolute; top: 58%; left: 50%; transform: translateX(-50%); width: 380px; text-align: center;">', unsafe_allow_html=True)
    
    logo_64 = get_base64("logoTriadetransparente.png")
    if logo_64:
        st.markdown(f'<img src="data:image/png;base64,{logo_64}" style="width: 380px; margin-bottom: 5px; filter: drop-shadow(0px 0px 10px rgba(0,0,0,1));">', unsafe_allow_html=True)
    
    st.markdown('<div style="background: rgba(0,0,0,0.8); padding: 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2);">', unsafe_allow_html=True)
    senha = st.text_input("Acesso", type="password", label_visibility="collapsed", placeholder="CHAVE DE ACESSO")
    if st.button("DESBLOQUEAR PLATAFORMA"):
        if senha == "triade2026":
            st.session_state.logado = True
            st.session_state.pagina = "dados"
            st.rerun()
        else:
            st.error("SENHA INCORRETA")
    st.markdown('</div></div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA 2: CONFIGURAÇÃO (Fundo TriadeFundo)
# ==========================================
elif st.session_state.pagina == "dados":
    aplicar_visual_fixo("imagemaptriadefundo.png")
    
    st.write("<br><br><br>", unsafe_allow_html=True)
    _, col_central, _ = st.columns([0.1, 0.8, 0.1])
    
    with col_central:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.markdown('<div class="titulo-dourado">⚙️ CONFIGURAÇÃO DO PROJETO</div>', unsafe_allow_html=True)
        
        # Correção da linha 126: Atribuindo as colunas corretamente
        c1, c2, c3 = st.columns(3)
        with c1: st.text_input("NOME DO PRODUTOR")
        with c2: st.text_input("FAZENDA")
        with c3: st.text_input("MUNICÍPIO / UF")
        
        st.markdown("<hr style='margin: 15px 0; opacity: 0.3;'>", unsafe_allow_html=True)
        
        st.markdown("<h3>IMPORTAÇÃO DE ARQUIVOS (A-Y)</h3>", unsafe_allow_html=True)
        up_geojson = st.file_uploader("CONTORNO DA ÁREA (.GEOJSON)", type=["json", "geojson"])
        up_excel = st.file_uploader("PLANILHA DE DADOS (.XLSX)", type=["xlsx"])
        
        if st.button("🚀 INICIAR ANÁLISE ESTRATÉGICA"):
            if up_geojson and up_excel:
                st.session_state.pagina = "plataforma"
                st.rerun()
            else:
                st.warning("CARREGUE OS ARQUIVOS PARA CONTINUAR")
        
        st.markdown('</div>', unsafe_allow_html=True)
import streamlit as st
import pandas as pd
import numpy as np

# --- 1. FUNÇÃO DE CÁLCULO DE RECOMENDAÇÃO (LOGICA DANILO) ---
def processar_recomendacoes(df, attr):
    # Conversão de Argila g/kg para % se necessário, mas usaremos direto conforme a regra
    # GESSO: Argila (g/kg) * fator (15)
    df['RECO_GESSO'] = df['ARGILA'] * attr['gesso_fator']
    df['RECO_GESSO'] = df['RECO_GESSO'].clip(lower=attr['gesso_min'], upper=attr['gesso_max'])
    
    # FÓSFORO: Lógica de Nível Crítico por P-Rem
    def nivel_critico_p(prem):
        if prem <= 4: return attr['p_nc1']
        elif prem <= 10: return attr['p_nc2']
        elif prem <= 19: return attr['p_nc3']
        elif prem <= 30: return attr['p_nc4']
        elif prem <= 45: return attr['p_nc5']
        else: return attr['p_nc6']
    
    # Fator de Textura (simplificado pela Argila g/kg)
    def fator_textura(argila):
        if argila > 600: return attr['fator_m_argiloso']
        elif argila > 350: return attr['fator_argiloso']
        elif argila > 150: return attr['fator_medio']
        else: return attr['fator_arenoso']

    # Aplicação da lógica de Fósforo
    # (Exemplo simplificado da subtração da "gordura" da exportação)
    exp_p = attr['prod_esperada'] * attr['p_export_sc']
    df['NC_P'] = df['P-REM'].apply(nivel_critico_p)
    df['FATOR_T'] = df['ARGILA'].apply(fator_textura)
    
    # Se P solo > NC, subtrai a diferença da exportação
    df['DIF_P'] = df['P'] - df['NC_P']
    df['RECO_P2O5'] = np.where(df['DIF_P'] > 0, 
                                exp_p - (df['DIF_P'] * df['FATOR_T']), 
                                exp_p + (abs(df['DIF_P']) * df['FATOR_T']))
    
    return df

# --- 2. INTERFACE DA ABA DE ATRIBUTOS ---
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
        p_nc1 = st.number_input("0 a 4 (P-Rem)", value=8.0)
        p_nc2 = st.number_input("4.1 a 10 (P-Rem)", value=10.0)
        p_nc3 = st.number_input("10.1 a 19 (P-Rem)", value=12.0)
        p_nc4 = st.number_input("19.1 a 30 (P-Rem)", value=15.0)
        
        st.write("**Fator Textura (kg P p/ elevar 1mg)**")
        f_m_arg = st.number_input("M. Argiloso", value=10.0)
        f_arg = st.number_input("Argiloso", value=8.0)
        
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
        g_fator = st.number_input("Fator Gesso (Argila * X)", value=15.0)
        g_max = st.number_input("Dose Máxima Gesso", value=900.0)
        g_min = st.number_input("Dose Mínima Gesso", value=400.0)
        g_preco = st.number_input("Preço Gesso (R$/ton)", value=400.0)
        
        st.write("---")
        prod_exp = st.number_input("Produtividade Esperada (sc/ha)", value=80.0)

    # Dicionário de Atributos para os cálculos
    return {
        "gesso_fator": g_fator, "gesso_min": g_min, "gesso_max": g_max,
        "p_nc1": p_nc1, "p_nc2": p_nc2, "p_nc3": p_nc3, "p_nc4": p_nc4,
        "fator_m_argiloso": f_m_arg, "fator_argiloso": f_arg,
        "p_export_sc": p_export, "prod_esperada": prod_exp
    }
