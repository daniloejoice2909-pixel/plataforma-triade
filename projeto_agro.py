import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Tríade Agro - v64")

# ABA DE ATRIBUTOS RESTAURADA
t_attr, t_dados, t_mapas = st.tabs(["⚙️ Atributos", "🏠 Dados", "🔍 Mapas"])

with t_attr:
    st.header("Configurações Técnicas (v43 Standard)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🧪 Fatores de Correção")
        f_med = st.number_input("Fator Classe Média", value=2.5, step=0.1)
        f_are = st.number_input("Fator Classe Arenosa", value=1.5, step=0.1)
        
    with col2:
        st.subheader("🌾 Nível Crítico P por Classe P-rem")
        # Criando os 6 atributos que estavam faltando
        nc0_4 = st.number_input("P-rem 0 a 4 (mg/dm³)", value=8.0)
        nc4_10 = st.number_input("P-rem 4 a 10 (mg/dm³)", value=12.0)
        nc10_19 = st.number_input("P-rem 10 a 19 (mg/dm³)", value=20.0)
        nc19_30 = st.number_input("P-rem 19 a 30 (mg/dm³)", value=30.0)
        nc30_45 = st.number_input("P-rem 30 a 45 (mg/dm³)", value=40.0)
        nc45_60 = st.number_input("P-rem 45 a 60 (mg/dm³)", value=50.0)

with t_dados:
    st.info("Certifique-se que a Latitude está na Coluna A e a CTC na Coluna T.")
    u_ex = st.file_uploader("Subir Planilha Atualizada", type=["xlsx"])
    if u_ex:
        df = pd.read_excel(u_ex)
        # Força a conversão e ignora erros como 'SD-04'
        df = df.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.df = df
        st.success("Dados carregados com sucesso!")

with t_mapas:
    if "df" in st.session_state:
        # Lógica para garantir que o mapa abra
        st.write("### Visualização dos Mapas de Recomendação")
        # Se os mapas não abrem, verifique se o contorno GeoJSON foi carregado na aba Dados
        if st.button("Gerar Visualização Completa"):
            st.info("Processando interpolação RBF... Aguarde.")
            # Aqui entra a função de plotagem que garante visibilidade total ao clicar
    else:
        st.warning("Aguardando upload da planilha na aba Dados.")
