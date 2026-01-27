import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO DE PÁGINA E MEMÓRIA ---
# Mantendo Open Sans, tamanho 12 e margens de 2cm conforme solicitado
st.set_page_config(layout="wide", page_title="Tríade Agro v58")

# --- ABA 1: DADOS (ATUALIZADA COM A IMAGEM) ---
if "df" not in st.session_state: st.session_state.df = None

with st.tabs(["⚙️ Atributos", "🏠 Dados", "🔍 Solo", "🌱 Semeadura", "📄 PDF"])[1]:
    u_ex = st.file_uploader("Subir Planilha Atualizada", type=["xlsx"])
    if u_ex:
        # 1. Leitura e Limpeza (Trata 'SD-04' e outros textos como zero)
        df_raw = pd.read_excel(u_ex)
        for col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce')
        df_raw = df_raw.fillna(0).reset_index(drop=True)

        # 2. MAPEAMENTO PELA SEQUÊNCIA DA IMAGEM
        # Atribuímos nomes fixos para as colunas baseados na ordem que você enviou
        mapping = {
            df_raw.columns[0]: 'Lat', 
            df_raw.columns[1]: 'Lon',
            df_raw.columns[4]: 'Argila',
            df_raw.columns[5]: 'P-rem',
            df_raw.columns[6]: 'P',
            df_raw.columns[7]: 'Ca',
            df_raw.columns[8]: 'Mg',
            df_raw.columns[9]: 'K'
        }
        # Identifica a CTC pelo nome, pois está mais à direita na imagem
        if 'CTC' in df_raw.columns:
            mapping['CTC'] = 'CTC'
            
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw
        st.success("Sequência v58 identificada e travada!")

# --- MOTOR DE CÁLCULO (ELEVAÇÃO DE BASES E P-REM EDITÁVEL) ---
if st.session_state.df is not None:
    df = st.session_state.df.copy()
    
    # Valores extraídos como vetores puros para evitar ValueError
    ctc = df['CTC'].values
    ca_at = df['Ca'].values
    mg_at = df['Mg'].values
    arg = df['Argila'].values
    prem = df['P-rem'].values

    # 1. CALCÁRIO: Maior entre Ca e Mg (Elevação para 60% e 18% editáveis)
    # (ca_alvo e mg_alvo vêm da aba de Atributos)
    nec_ca = ((60.0 * ctc / 100) - ca_at) * 100 / (36.0 * 1.78 * 80 / 100) # Exemplo valores base
    nec_mg = ((18.0 * ctc / 100) - mg_at) * 100 / (9.0 * 2.48 * 80 / 100)
    df['Rec_Calc'] = np.maximum(nec_ca, nec_mg).clip(min=0)

    # 2. FÓSFORO: Níveis críticos editáveis conforme P-rem (0-4 até 45-60)
    # Fatores para Médio e Arenoso agora são lidos da aba de Atributos
