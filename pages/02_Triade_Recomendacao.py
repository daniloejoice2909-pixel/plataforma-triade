import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64
import folium
from streamlit_folium import st_folium

# Configuração do Matplotlib para não travar o servidor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA (Deve ser o primeiro comando Streamlit)
# ==============================================================================
st.set_page_config(page_title="Tríade VRT", layout="wide")
st.title("🚜 Tríade VRT - Motor de Recomendação")

# ==============================================================================
# 2. FUNÇÕES DE LIMPEZA
# ==============================================================================
def limpar_dados(df):
    """Limpa e padroniza as colunas do CSV."""
    df_novo = df.copy()
    df_novo.columns = [c.lower().strip() for c in df_novo.columns]
    
    # Dicionário de sinônimos para encontrar colunas automaticamente
    mapa_colunas = {
        'latitude': ['latitude', 'lat', 'y', 'lat_wgs84'],
        'longitude': ['longitude', 'long', 'lon', 'x', 'lon_wgs84'],
        'Ca': ['ca', 'calcio', 'cálcio', 'ca_cmolc'],
        'Mg': ['mg', 'magnesio', 'magnésio', 'mg_cmolc'],
        'K':  ['k', 'potassio', 'potássio', 'k_mg'],
        'P':  ['p', 'fosforo', 'fósforo', 'p_mehl', 'pmehlich'], 
        'P_Rem': ['prem', 'p_rem', 'p-rem', 'fosforo_remanescente'],
        'Argila': ['argila', 'clay', 'argila_total'],
        'CTC': ['ctc', 't', 'ctc_ph7']
    }
    
    renomear = {}
    for col_real in df_novo.columns:
        for padrao, lista in mapa_colunas.items():
            if col_real in lista:
                renomear[col_real] = padrao
                break
            # Tenta encontrar substring (ex: "Argila %")
            for item in lista:
                if item == col_real:
                    renomear[col_real] = padrao
                    break
    
    if renomear:
        df_novo = df_novo.rename(columns=renomear)

    # Converte para números
    cols_check = ['Ca', 'Mg', 'K', 'P', 'P_Rem', 'Argila', 'CTC', 'latitude', 'longitude']
    for c in cols_check:
        if c in df_novo.columns:
            if df_novo[c].dtype == 'object':
                df_novo[c] = df_novo[c].astype(str).str.replace(',', '.')
            df_novo[c] = pd.to_numeric(df_novo[c], errors='coerce').fillna(0)

    return df_novo

# ==============================================================================
# 3. CÁLCULO VRT (COM TABELA FIXA)
# ==============================================================================
def calcular_vrt(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt, p_exp, p_teor, k_alvo, k_exp, k_teor, g_fat, g_min, g_max, nc_vals):
    d = df.copy()
    
    # --- CALAGEM ---
    if all(x in d.columns for x in ['Ca', 'Mg', 'CTC']):
        nc_ca = d['CTC'] * (ca_alvo / 100.0)
        nc_mg = d['CTC'] * (mg_alvo / 100.0)
        
        # Evita divisão por zero
        fator_ca = max((cao * 10 / 560.0) * (prnt / 100.0), 0.001)
        fator_mg = max((mgo * 10 / 403.0) * (prnt / 100.0), 0.001)
        
        d['Dose_Calcario'] = np.maximum(
            (nc_ca - d['Ca']) / fator_ca,
            (nc_mg - d['Mg']) / fator_mg
        ).clip(lower=0).round(2)
    else:
        d['Dose_Calcario'] = 0.0

    # --- FÓSFORO (Lógica de Tabela Fixa) ---
    if 'P_Rem' in d.columns and 'P' in d.columns:
        # Define as condições baseadas no P-rem
        condicoes = [
            (d['P_Rem'] <= 4.0),                          # 0 a 4
            (d['P_Rem'] > 4.0) & (d['P_Rem'] <= 10.0),    # 4 a 10
            (d['P_Rem'] > 10.0) & (d['P_Rem'] <= 19.0),   # 10 a 19
            (d['P_Rem'] > 19.0) & (d['P_Rem'] <= 30.0),   # 19 a 30
            (d['P_Rem'] > 30.0)                           # > 30
        ]
        
        # Pega os valores da Sidebar
        valores = [nc_vals['n1'], nc_vals['n2'], nc_vals['n3'], nc_vals['n4'], nc_vals['n5']]
        
        # Aplica a tabela
        nc = np.select(condicoes, valores, default=nc_vals['n5'])
        
        # Fator Tampão (Física do solo)
        fct = (56.5 * d['P_Rem']**-0.52).clip(4, 40)
        
        d['NC_Tab
