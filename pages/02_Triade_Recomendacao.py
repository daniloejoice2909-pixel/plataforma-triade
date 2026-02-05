import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==============================================================================
# 1. MOTOR DE CÁLCULO (Backend Blindado com Cache)
# ==============================================================================
@st.cache_data(show_spinner=False, persist=True)
def processar_malha_vrt(df, params):
    dfr = df.copy()

    # --- A. CALAGEM (Equilíbrio de Bases + Alertas) ---
    cols_calagem = ['Ca', 'Mg', 'CTC']
    if all(col in dfr.columns for col in cols_calagem):
        
        # 1. Alvos em Cmol
        ca_alvo_cmol = dfr['CTC'] * (params['calagem_alvo_ca'] / 100.0)
        mg_alvo_cmol = dfr['CTC'] * (params['calagem_alvo_mg'] / 100.0)
        
        # 2. Déficits (Zerando negativos)
        deficit_ca = (ca_alvo_cmol - dfr['Ca']).clip(lower=0)
        deficit_mg = (mg_alvo_cmol - dfr['Mg']).clip(lower=0)

        # 3. Aporte por Tonelada (Baseado no Calcário Escolhido)
        # Fatores: 560 mg Ca/kg e 403 mg Mg/kg são constantes estequiométricas aproximadas
        aporte_ca_por_ton = (params['calagem_cao'] * 10 / 560.0) * (params['calagem_prnt'] / 100.0)
        aporte_mg_por_ton = (params['calagem_mgo'] * 10 / 403.0) * (params['calagem_prnt'] / 100.0)

        # Evitar divisão por zero e erros matemáticos
        aporte_ca_por_ton = max(aporte_ca_por_ton, 0.001)
        aporte_mg_por_ton = max(aporte_mg_por_ton, 0.001)

        # 4. Calcular Doses Individuais
        dose_pelo_ca = deficit_ca / aporte_ca_por_ton
        dose_pelo_mg = deficit_mg / aporte_mg_por_ton
        
        # 5. REGRA DO MAIOR: Atende o limitante, sem reduzir dose (Sua regra de negócio)
        dfr['Dose_Calcario_Ton'] = np.maximum(dose_pelo_ca, dose_pelo_mg)
        dfr['Dose_Calcario_Ton'] = dfr['Dose_Calcario_Ton'].round(2)

        # 6. CÁLCULO DE PROJEÇÃO (Para gerar o Alerta de Desequilíbrio)
        # Como ficaria o solo após aplicar essa dose?
        ca_final = dfr['Ca'] + (dfr['Dose_Calcario_Ton'] * aporte_ca_por_ton)
        mg_final = dfr['Mg'] + (dfr['Dose_Calcario_Ton'] * aporte_mg_por_ton)
        
        # Evitar div por zero
        mg_final = mg_final.replace(0, 0.01)
        dfr['Ratio_Final'] = ca_final / mg_final
        
        # 7. CRIAR AVISO VISUAL
        dfr['Alerta_Ratio'] = "✅ Equilibrado"
        
        # Se relação < 2 (Muito Magnésio ou Pouco Cálcio relativo)
        dfr.loc[dfr['Ratio_Final'] < 2.0, 'Alerta_Ratio'] = "⚠️ Risco: Excesso Mg (Ca/Mg < 2)"
        
        # Se relação > 4 (Muito Cálcio ou Pouco Magnésio relativo)
        dfr.loc[dfr['Ratio_Final'] > 4.0, 'Alerta_Ratio'] = "⚠️ Risco: Falta Mg (Ca/Mg > 4)"
        
    else:
        dfr['Dose_Calcario_Ton'] = 0.0
        dfr['Alerta_Ratio'] = "Sem dados Ca/Mg"
        dfr['Ratio_Final'] = 0.0

    # --- B. GESSO ---
    if 'Argila' in dfr.columns:
        dfr['Dose_Gesso_Kg'] = (dfr['Argila'] * params['gesso_fator']).clip(params['gesso_min'], params['gesso
