import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚑 Modo de Diagnóstico")

# 1. Verifica se o arquivo interpolado existe na memória
if 'df_interpolado' in st.session_state:
    df = st.session_state['df_interpolado']
    st.success(f"Arquivo carregado com sucesso! Linhas: {len(df)}")
    st.dataframe(df.head()) # Mostra só as 5 primeiras linhas
else:
    st.error("Nenhum arquivo interpolado encontrado. Volte para a aba de Interpolação.")

# 2. Teste de Botão (Se clicar e funcionar, o Streamlit não está travado)
if st.button("Teste de Vida"):
    st.info("O sistema está respondendo!")
