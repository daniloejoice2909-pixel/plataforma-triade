import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==============================================================================
# 1. MOTOR DE CÁLCULO (Ajustado: Dose Cheia + Coluna de Alerta)
# ==============================================================================
@st.cache_data(show_spinner=False, persist=True)
def processar_malha_vrt(df, params):
    dfr = df.copy()

    # --- A. CALAGEM (Equilíbrio de Bases sem Redução de Dose) ---
    cols_calagem = ['Ca', 'Mg', 'CTC']
    if all(col in dfr.columns for col in cols_calagem):
        
        # 1. Alvos em Cmol
        ca_alvo_cmol = dfr['CTC'] * (params['calagem_alvo_ca'] / 100.0)
        mg_alvo_cmol = dfr['CTC'] * (params['calagem_alvo_mg'] / 100.0)
        
        # 2. Déficits (Zerando negativos)
        deficit_ca = (ca_alvo_cmol - dfr['Ca']).clip(lower=0)
        deficit_mg = (mg_alvo_cmol - dfr['Mg']).clip(lower=0)

        # 3. Aporte por Tonelada (Baseado no Calcário Escolhido)
        # 1 Ton fornece X cmol de Ca e Y cmol de Mg
        aporte_ca_por_ton = (params['calagem_cao'] * 10 / 560.0) * (params['calagem_prnt'] / 100.0)
        aporte_mg_por_ton = (params['calagem_mgo'] * 10 / 403.0) * (params['calagem_prnt'] / 100.0)

        # Evitar divisão por zero
        aporte_ca_por_ton = max(aporte_ca_por_ton, 0.001)
        aporte_mg_por_ton = max(aporte_mg_por_ton, 0.001)

        # 4. Calcular Doses Individuais
        dose_pelo_ca = deficit_ca / aporte_ca_por_ton
        dose_pelo_mg = deficit_mg / aporte_mg_por_ton
        
        # 5. REGRA DO MAIOR: Atende o limitante, sem reduzir.
        dfr['Dose_Calcario_Ton'] = np.maximum(dose_pelo_ca, dose_pelo_mg)
        dfr['Dose_Calcario_Ton'] = dfr['Dose_Calcario_Ton'].round(2)

        # 6. CÁLCULO DE PROJEÇÃO (Para gerar o Alerta)
        # Como ficará o solo após aplicar essa dose?
        ca_final = dfr['Ca'] + (dfr['Dose_Calcario_Ton'] * aporte_ca_por_ton)
        mg_final = dfr['Mg'] + (dfr['Dose_Calcario_Ton'] * aporte_mg_por_ton)
        
        # Evitar div por zero
        mg_final = mg_final.replace(0, 0.01)
        dfr['Ratio_Final'] = ca_final / mg_final
        
        # 7. CRIAR AVISO VISUAL (String para o Tooltip)
        # Inicialmente vazio
        dfr['Alerta_Ratio'] = "✅ Equilibrado"
        
        # Se relação < 2 (Muito Magnésio ou Pouco Cálcio relativo)
        dfr.loc[dfr['Ratio_Final'] < 2.0, 'Alerta_Ratio'] = "⚠️ Excesso Mg (Relação < 2)"
        
        # Se relação > 4 (Muito Cálcio ou Pouco Magnésio relativo)
        dfr.loc[dfr['Ratio_Final'] > 4.0, 'Alerta_Ratio'] = "⚠️ Falta Mg (Relação > 4)"
        
    else:
        dfr['Dose_Calcario_Ton'] = 0.0
        dfr['Alerta_Ratio'] = "Sem dados Ca/Mg"
        dfr['Ratio_Final'] = 0.0

    # --- B, C, D (Gesso, Fósforo, Potássio mantidos iguais...) ---
    # (Resumi aqui para focar na mudança da Calagem, mas o código original dos outros nutrientes continua aqui)
    # ... [Inserir lógica de Gesso, Fósforo e K aqui igual ao script anterior] ...
    
    # REPLICANDO LÓGICA DE FOSFORO/POTASSIO/GESSO PARA O CONTEXTO (Simplificado p/ resposta)
    if 'Argila' in dfr.columns:
        dfr['Dose_Gesso_Kg'] = (dfr['Argila'] * params['gesso_fator']).clip(params['gesso_min'], params['gesso_max'])
    
    if 'P_Rem' in dfr.columns and 'P' in dfr.columns:
        nc = (params['phos_nc_intercept'] + params['phos_nc_slope'] * dfr['P_Rem']).clip(8,60)
        fct = (params['phos_fct_a'] * dfr['P_Rem']**params['phos_fct_b']).clip(4,40)
        dose_p = np.where((nc - dfr['P']) > 0, (nc - dfr['P'])*fct, 0)
        total_p = dose_p + (params['produtividade_alvo'] * params['phos_exportacao'])
        dfr['Dose_Fosforo_Kg'] = total_p / (params['phos_teor_adubo']/100) if params['phos_teor_adubo'] > 0 else 0

    if 'K' in dfr.columns and 'CTC' in dfr.columns:
        k_alvo = dfr['CTC'] * (params['potassio_alvo_ctc']/100)
        dose_k_const = ((k_alvo - (dfr['K']/391)).clip(0)) * 940
        total_k = dose_k_const + (params['produtividade_alvo'] * params['potassio_exportacao'])
        dfr['Dose_Potassio_Kg'] = total_k / (params['potassio_teor_adubo']/100) if params['potassio_teor_adubo'] > 0 else 0

    return dfr

# ==============================================================================
# 2. INTERFACE
# ==============================================================================
# ... (Sidebar mantém igual ao anterior) ...

# ==============================================================================
# 3. VISUALIZAÇÃO COM "BALÃOZINHO" (TOOLTIP)
# ==============================================================================

if st.session_state.get('vrt_processado'):
    dfr = st.session_state['df_vrt_final']
    
    tab1, tab2, tab3, tab4 = st.tabs(["Calagem (Ca/Mg)", "Fósforo", "Potássio", "Gesso"])
    
    # Função Especial para o Mapa de Calcário com Alerta
    def plotar_mapa_calcario(dados):
        dados_vis = dados.iloc[::5, :].copy() # Downsample visual
        
        # Define cor do hover baseada no problema
        # Vamos criar uma coluna de cor para o texto se quiser, mas o texto já ajuda
        
        fig = go.Figure(go.Scattermapbox(
            lat=dados_vis['lat'], lon=dados_vis['lon'],
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=6, 
                color=dados_vis['Dose_Calcario_Ton'],
                colorscale="Reds", 
                opacity=1.0, 
                showscale=True,
                colorbar=dict(title="Ton/ha")
            ),
            # AQUI ESTÁ A MÁGICA DO BALÃOZINHO
            customdata=np.stack((
                dados_vis['Dose_Calcario_Ton'], 
                dados_vis['Ratio_Final'], 
                dados_vis['Alerta_Ratio']
            ), axis=-1),
            hovertemplate=(
                "<b>Dose: %{customdata[0]:.2f} ton/ha</b><br>" +
                "Relação Final: %{customdata[1]:.2f}<br>" +
                "%{customdata[2]}<extra></extra>" # Mostra o Alerta
            )
        ))
        
        fig.update_layout(
            mapbox_style="satellite", mapbox_accesstoken="SEU_TOKEN",
            title="Recomendação Calcário (Balanço de Bases)", margin={"r":0,"t":30,"l":0,"b":0}, height=450
        )
        return fig

    with tab1:
        # Lógica de aviso global
        total_pontos = len(dfr)
        pontos_com_problema = len(dfr[dfr['Alerta_Ratio'] != "✅ Equilibrado"])
        percentual_problema = (pontos_com_problema / total_pontos) * 100
        
        if percentual_problema > 15:
            st.warning(
                f"⚠️ Atenção: O calcário selecionado causará desequilíbrio na relação Ca/Mg "
                f"em {percentual_problema:.1f}% da área. Verifique se o teor de MgO está adequado."
            )
        else:
            st.success(f"✅ O calcário selecionado mantém o equilíbrio em {100-percentual_problema:.1f}% da área.")

        st.plotly_chart(plotar_mapa_calcario(dfr), key="map_calc_warning")
    
    # As outras abas usam plotagem padrão...
    # ...
