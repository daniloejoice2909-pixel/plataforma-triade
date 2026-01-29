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
    import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import os

def exibir_aba_mapas_fertilidade(df, contorno_geojson):
    st.markdown("### 🗺️ Mapas de Fertilidade (Zonas de Manejo)")
    
    # Caminho do Logo para a Marca d'Água
    logo_path = "LogoTriadeagro.png.png"
    logo_base64 = ""
    if os.path.exists(logo_path):
        import base64
        with open(logo_path, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode()

    # Selecionar apenas colunas de dados (E até Y)
    colunas_dados = [c for c in df.columns if c not in ['LATITUDE', 'LONGITUDE', 'CAMPO', 'PONTO']]

    for col in colunas_dados:
        # Se a coluna for toda zero ou vazia, ocultamos
        if df[col].dropna().sum() == 0:
            continue

        st.markdown(f"#### Atributo: {col}")
        
        # Estatísticas para o rodapé reduzido
        v_min, v_max, v_med = df[col].min(), df[col].max(), df[col].mean()

        # Criando o Mapa de Contorno (Zonamento 100% preenchido)
        fig = go.Figure(go.Histogram2dContour(
            x = df['LONGITUDE'],
            y = df['LATITUDE'],
            z = df[col],
            colorscale='coolwarm',
            ncontours=6, # 6 Zonas de Manejo
            line_width=0,
            hovertemplate="Valor: %{z}<extra></extra>"
        ))

        # Configuração da Identidade Visual (Logo Apagado)
        if logo_base64:
            fig.add_layout_image(
                dict(
                    source=f"data:image/png;base64,{logo_base64}",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, # Centralizado
                    sizex=0.4, sizey=0.4, # Tamanho discreto
                    xanchor="center", yanchor="middle",
                    opacity=0.15, # Tom apagado para não atrapalhar
                    layer="above"
                )
            )

        # Ajustes de Layout e Legendas Reduzidas
        fig.update_layout(
            width=900, height=600,
            margin={"r":10,"t":10,"l":10,"b":10},
            coloraxis_showscale=True,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            coloraxis_colorbar=dict(
                thickness=12,
                title="",
                tickfont=dict(size=9, color="white")
            )
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # Rodapé Técnico em Tamanho Reduzido
        st.markdown(
            f"""<div style='text-align: center; font-size: 11px; color: #CCCCCC; margin-bottom: 20px;'>
            MÍN: {v_min:.2f} | MÉD: {v_med:.2f} | MÁX: {v_max:.2f}
            </div>""", unsafe_allow_html=True
        )
        import streamlit as st
import pandas as pd
import numpy as np

def exibir_aba_recomendacoes(df, attr):
    st.markdown("## 💰 Recomendações Técnicas e Custos por Zona")
    
    # --- 1. CÁLCULOS TÉCNICOS (LOGICA DANILO) ---
    
    # GESSO
    df['Dose_Gesso'] = df['ARGILA'] * attr['gesso_fator']
    df['Dose_Gesso'] = df['Dose_Gesso'].clip(lower=attr['gesso_min'], upper=attr['gesso_max'])
    
    # POTÁSSIO (K)
    # 1.2 kg/sc * Produtividade + Elevação para 3.2% da CTC
    exp_k = attr['prod_esperada'] * attr['k_export_sc']
    # Simplificação da necessidade de elevação (K_necessario = (K_desejado% - K_atual%) * CTC)
    df['Elevacao_K'] = ((attr['k_perc_ctc'] - df['K%']).clip(lower=0) / 100) * df['CTC'] * 391 * 2 
    df['Dose_K2O'] = exp_k + df['Elevacao_K']
    
    # FÓSFORO (P)
    def calcular_p(row):
        # Define Nível Crítico (NC) baseado no P-REM
        prem = row['P-REM']
        if prem <= 4: nc = attr['p_nc1']
        elif prem <= 10: nc = attr['p_nc2']
        elif prem <= 19: nc = attr['p_nc3']
        elif prem <= 30: nc = attr['p_nc4']
        elif prem <= 45: nc = attr['p_nc5']
        else: nc = attr['p_nc6']
        
        export_p = attr['prod_esperada'] * attr['p_export_sc']
        fator_t = 8 # Padrão argiloso (editável nos atributos)
        
        dif_p = row['P'] - nc
        # Se P solo > NC (Gordura), subtrai da exportação. Se <, soma correção.
        return export_p - (dif_p * fator_t)

    df['Dose_P2O5'] = df.apply(calcular_p, axis=1).clip(lower=0)

    # CALCÁRIO (Maior dose entre elevar Ca ou Mg)
    nec_ca = ((attr['ca_ctc_des'] - df['CA%']).clip(lower=0) / 100) * df['CTC']
    nec_mg = ((attr['mg_ctc_des'] - df['MG%']).clip(lower=0) / 100) * df['CTC']
    df['Dose_Calcario'] = np.maximum(nec_ca, nec_mg) * (100 / attr['ca_prnt']) * 1000 # kg/ha

    # --- 2. CÁLCULO DE CUSTOS (R$/ha) ---
    df['Custo_Gesso'] = (df['Dose_Gesso'] / 1000) * attr['gesso_preco']
    df['Custo_P'] = (df['Dose_P2O5'] / (attr['p_adubo_perc']/100) / 1000) * attr['p_preco']
    df['Custo_K'] = (df['Dose_K2O'] / (attr['k_adubo_perc']/100) / 1000) * attr['k_preco']
    df['Custo_Calcario'] = (df['Dose_Calcario'] / 1000) * attr['ca_preco']
    
    df['Custo_Total_HA'] = df['Custo_Gesso'] + df['Custo_P'] + df['Custo_K'] + df['Custo_Calcario']

    # --- 3. EXIBIÇÃO POR ZONAS DE CUSTO ---
    df['Zona_Investimento'] = pd.qcut(df['Custo_Total_HA'], 6, labels=["Muito Baixo", "Baixo", "Médio-Baixo", "Médio-Alto", "Alto", "Crítico"])
    
    resumo_zonas = df.groupby('Zona_Investimento', observed=True).agg({
        'Dose_Gesso': 'mean',
        'Dose_P2O5': 'mean',
        'Dose_K2O': 'mean',
        'Dose_Calcario': 'mean',
        'Custo_Total_HA': 'mean'
    }).reset_index()

    st.table(resumo_zonas.style.format(precision=2))

    st.info("💡 Os custos acima são baseados nos preços editados na aba de Atributos.")
    # --- LOGICA DE CARREGAMENTO ---
        if st.button("🚀 INICIAR ANÁLISE ESTRATÉGICA"):
            if up_excel:
                # Carrega os dados para a sessão
                st.session_state.dados_excel = pd.read_excel(up_excel)
                # Se houver geojson, pode carregar aqui também futuramente
                st.session_state.pagina = "plataforma"
                st.rerun()
            else:
                st.warning("CARREGUE A PLANILHA PARA CONTINUAR")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# PÁGINA 3: PLATAFORMA INTEGRADA (ABAS)
# ==========================================
elif st.session_state.pagina == "plataforma":
    # Ajuste visual para ambiente de análise (escuro e técnico)
    st.markdown("""
        <style>
        [data-testid="stAppViewContainer"] { background-image: none !important; background-color: #0e1117 !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            background-color: rgba(255,255,255,0.05);
            border-radius: 4px;
            color: #FFD700 !important;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    # Definição das Abas (Adicionada Aba Satélite conforme solicitado)
    aba_attr, aba_ferti, aba_reco, aba_satelite = st.tabs([
        "⚙️ ATRIBUTOS", 
        "🗺️ MAPAS FERTILIDADE", 
        "💰 RECOMENDAÇÕES",
        "🛰️ MONITORAMENTO SATÉLITE"
    ])

    # 1. ABA DE ATRIBUTOS
    with aba_attr:
        # Chama a função que você colou e captura as variáveis editadas
        atributos_editados = exibir_aba_atributos()

    # 2. ABA DE MAPAS DE FERTILIDADE
    with aba_ferti:
        if "dados_excel" in st.session_state:
            # Chama sua função de mapas (Histogram2dContour com marca d'água)
            exibir_aba_mapas_fertilidade(st.session_state.dados_excel, None)
        else:
            st.warning("⚠️ Planilha não encontrada.")

    # 3. ABA DE RECOMENDAÇÕES
    with aba_reco:
        if "dados_excel" in st.session_state:
            # Executa os cálculos de Gesso, P, K e Calcário com os atributos da aba 1
            exibir_aba_recomendacoes(st.session_state.dados_excel, atributos_editados)

    # 4. ABA DE SATÉLITE (Painel de Configuração Sentinel Hub)
    with aba_satelite:
        st.subheader("🛰️ Conexão Sentinel Hub")
        st.markdown("---")
        st.write("Insira suas credenciais para monitoramento de índices de biomassa (NDVI/EVI).")
        
        col_sat1, col_sat2 = st.columns(2)
        with col_sat1:
            st.text_input("CLIENT ID", type="password", help="Chave gerada no dashboard do Sentinel Hub")
        with col_sat2:
            st.text_input("CLIENT SECRET", type="password")
            
        st.info("ℹ️ Esta aba permitirá a integração direta com imagens de satélite para monitoramento em tempo real.")
        if st.button("TESTAR CONEXÃO SATÉLITE"):
            st.toast("Aguardando configuração de API...")
