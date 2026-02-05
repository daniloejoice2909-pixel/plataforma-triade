import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==============================================================================
# 1. MOTOR DE CÁLCULO (Backend Blindado com Cache)
# ==============================================================================
@st.cache_data(show_spinner=False, persist=True)
def processar_malha_vrt(df, params):
    # Cria uma cópia para não alterar os dados originais
    dfr = df.copy()

    # --- A. CALAGEM (Equilíbrio de Bases + Alertas) ---
    cols_calagem = ['Ca', 'Mg', 'CTC']
    if all(col in dfr.columns for col in cols_calagem):
        
        # 1. Alvos em Cmol (Quantidade total desejada no solo)
        ca_alvo_cmol = dfr['CTC'] * (params['calagem_alvo_ca'] / 100.0)
        mg_alvo_cmol = dfr['CTC'] * (params['calagem_alvo_mg'] / 100.0)
        
        # 2. Déficits (O quanto falta para atingir o alvo, zerando negativos)
        deficit_ca = (ca_alvo_cmol - dfr['Ca']).clip(lower=0)
        deficit_mg = (mg_alvo_cmol - dfr['Mg']).clip(lower=0)

        # 3. Aporte por Tonelada (Baseado no Calcário Escolhido na Sidebar)
        # Fatores constantes: 560 mg Ca/kg e 403 mg Mg/kg
        aporte_ca_por_ton = (params['calagem_cao'] * 10 / 560.0) * (params['calagem_prnt'] / 100.0)
        aporte_mg_por_ton = (params['calagem_mgo'] * 10 / 403.0) * (params['calagem_prnt'] / 100.0)

        # Evitar divisão por zero (segurança matemática)
        aporte_ca_por_ton = max(aporte_ca_por_ton, 0.001)
        aporte_mg_por_ton = max(aporte_mg_por_ton, 0.001)

        # 4. Calcular Doses Individuais
        dose_pelo_ca = deficit_ca / aporte_ca_por_ton
        dose_pelo_mg = deficit_mg / aporte_mg_por_ton
        
        # 5. REGRA DO MAIOR: Aplica-se a dose necessária para corrigir o limitante
        dfr['Dose_Calcario_Ton'] = np.maximum(dose_pelo_ca, dose_pelo_mg)
        dfr['Dose_Calcario_Ton'] = dfr['Dose_Calcario_Ton'].round(2)

        # 6. CÁLCULO DE PROJEÇÃO (Simulação do solo após aplicação)
        ca_final = dfr['Ca'] + (dfr['Dose_Calcario_Ton'] * aporte_ca_por_ton)
        mg_final = dfr['Mg'] + (dfr['Dose_Calcario_Ton'] * aporte_mg_por_ton)
        
        # Evitar divisão por zero na relação
        mg_final = mg_final.replace(0, 0.01)
        dfr['Ratio_Final'] = ca_final / mg_final
        
        # 7. CRIAR AVISO VISUAL (Coluna de texto para o balãozinho)
        dfr['Alerta_Ratio'] = "✅ Equilibrado"
        
        # Se relação < 2 (Risco de excesso de Magnésio)
        dfr.loc[dfr['Ratio_Final'] < 2.0, 'Alerta_Ratio'] = "⚠️ Risco: Excesso Mg (Ca/Mg < 2)"
        
        # Se relação > 4 (Risco de falta de Magnésio)
        dfr.loc[dfr['Ratio_Final'] > 4.0, 'Alerta_Ratio'] = "⚠️ Risco: Falta Mg (Ca/Mg > 4)"
        
    else:
        # Se não tiver colunas de solo, zera a recomendação
        dfr['Dose_Calcario_Ton'] = 0.0
        dfr['Alerta_Ratio'] = "Sem dados Ca/Mg"
        dfr['Ratio_Final'] = 0.0

    # --- B. GESSO ---
    if 'Argila' in dfr.columns:
        dfr['Dose_Gesso_Kg'] = (dfr['Argila'] * params['gesso_fator']).clip(params['gesso_min'], params['gesso_max'])
    else:
        dfr['Dose_Gesso_Kg'] = 0.0
    
    # --- C. FÓSFORO (5ª APROX - REGRESSÃO) ---
    if 'P_Rem' in dfr.columns and 'P' in dfr.columns:
        # Nível Crítico (NC) e Fator Capacidade Tampão (FCT) via Regressão
        nc = (params['phos_nc_intercept'] + params['phos_nc_slope'] * dfr['P_Rem']).clip(8, 60)
        fct = (params['phos_fct_a'] * dfr['P_Rem']**params['phos_fct_b']).clip(4, 40)
        
        # Dose Construção + Manutenção
        dose_construcao = np.where((nc - dfr['P']) > 0, (nc - dfr['P']) * fct, 0)
        dose_manutencao = params['produtividade_alvo'] * params['phos_exportacao']
        total_p = dose_construcao + dose_manutencao
        
        # Converter para produto comercial (ex: MAP)
        teor = params['phos_teor_adubo'] / 100.0
        dfr['Dose_Fosforo_Kg'] = total_p / teor if teor > 0 else 0
    else:
        dfr['Dose_Fosforo_Kg'] = 0.0

    # --- D. POTÁSSIO (Ligado à Produtividade) ---
    if 'K' in dfr.columns and 'CTC' in dfr.columns:
        # K Alvo na CTC
        k_alvo = dfr['CTC'] * (params['potassio_alvo_ctc'] / 100.0)
        k_atual = dfr['K'] / 391.0 # Convertendo mg para cmol
        
        # Dose Construção + Manutenção (Exportação)
        dose_k_const = ((k_alvo - k_atual).clip(0)) * 940.0 # Fator de conversão cmol K -> kg K2O
        dose_k_manut = params['produtividade_alvo'] * params['potassio_exportacao']
        total_k = dose_k_const + dose_k_manut
        
        # Converter para produto comercial (ex: KCl)
        teor_k = params['potassio_teor_adubo'] / 100.0
        dfr['Dose_Potassio_Kg'] = total_k / teor_k if teor_k > 0 else 0
    else:
        dfr['Dose_Potassio_Kg'] = 0.0

    return dfr

# ==============================================================================
# 2. VISUALIZAÇÃO OTIMIZADA (ANTI-TRAVAMENTO)
# ==============================================================================
# Este bloco deve ficar na parte inferior do seu código, após o botão de processamento

if st.session_state.get('vrt_processado'):
    # Recupera o DataFrame COMPLETO da memória
    df_completo = st.session_state['df_vrt_final']
    
    st.markdown("---")
    st.markdown("### 🗺️ Mapas de Recomendação VRT")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Calagem (Ca/Mg)", "Fósforo", "Potássio", "Gesso"])
    
    # --- FUNÇÃO DE PLOTAGEM INTELIGENTE ---
    def plotar_mapa_otimizado(dados_full, coluna_z, titulo, cor, is_calcario=False):
        """
        Plota no máximo 1500 pontos para visualização leve.
        """
        # 1. Downsampling Seguro (Evita travar o navegador)
        if len(dados_full) > 1500:
            dados_vis = dados_full.sample(n=1500, random_state=42)
        else:
            dados_vis = dados_full.copy()
            
        # 2. Configuração do Tooltip (Balãozinho)
        if is_calcario:
            # Empilha os dados para o hover do calcário (Dose + Risco)
            custom_data = np.stack((
                dados_vis[coluna_z], 
                dados_vis['Ratio_Final'], 
                dados_vis['Alerta_Ratio']
            ), axis=-1)
            
            hover_template = (
                "<b>Dose: %{customdata[0]:.2f} ton/ha</b><br>" +
                "Relação Ca/Mg Final: %{customdata[1]:.2f}<br>" +
                "%{customdata[2]}<extra></extra>"
            )
        else:
            # Tooltip simples para outros nutrientes
            custom_data = dados_vis[coluna_z]
            hover_template = "<b>Dose: %{customdata:.0f} kg/ha</b><extra></extra>"

        # 3. Gráfico Otimizado (WebGL)
        fig = go.Figure(go.Scattermapbox(
            lat=dados_vis['lat'], lon=dados_vis['lon'],
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=8, # Tamanho ajustado para visualização amostral
                color=dados_vis[coluna_z],
                colorscale=cor, 
                opacity=0.9, 
                showscale=True,
                colorbar=dict(title="Dose")
            ),
            customdata=custom_data,
            hovertemplate=hover_template
        ))
        
        fig.update_layout(
            mapbox_style="open-street-map", # Mapa leve e gratuito (sem token)
            title=f"{titulo} (Visualização Rápida)", 
            margin={"r":0,"t":40,"l":0,"b":0}, 
            height=500
        )
        return fig

    # --- ABA 1: CALAGEM COM ALERTA ---
    with tab1:
        # Verifica se há alertas na base COMPLETA
        if 'Alerta_Ratio' in df_completo.columns:
            # Conta quantos pontos têm o ícone de alerta ⚠️
            pontos_ruins = len(df_completo[df_completo['Alerta_Ratio'].astype(str).str.contains("⚠️")])
            pct_ruim = (pontos_ruins / len(df_completo)) * 100
            
            if pct_ruim > 15:
                st.warning(f"⚠️ Atenção: {pct_ruim:.1f}% da área ficará com desequilíbrio Ca/Mg (Relação <2 ou >4).")
            elif pct_ruim > 0:
                st.info(f"ℹ️ Nota: {pct_ruim:.1f}% da área apresenta leve desequilíbrio na relação Ca/Mg.")
            else:
                st.success("✅ Relação Ca/Mg equilibrada em toda a área.")

        st.plotly_chart(
            plotar_mapa_otimizado(df_completo, 'Dose_Calcario_Ton', "Calcário", "Reds", is_calcario=True),
            use_container_width=True
        )

    # --- ABA 2: FÓSFORO ---
    with tab2:
        media_p = df_completo['Dose_Fosforo_Kg'].mean()
        st.metric("Média da Aplicação", f"{media_p:.0f} kg/ha")
        st.plotly_chart(
            plotar_mapa_otimizado(df_completo, 'Dose_Fosforo_Kg', "Fósforo (P2O5)", "Viridis"),
            use_container_width=True
        )

    # --- ABA 3: POTÁSSIO ---
    with tab3:
        media_k = df_completo['Dose_Potassio_Kg'].mean()
        st.metric("Média da Aplicação", f"{media_k:.0f} kg/ha")
        st.plotly_chart(
            plotar_mapa_otimizado(df_completo, 'Dose_Potassio_Kg', "Potássio (K2O)", "Plasma"),
            use_container_width=True
        )
        
    # --- ABA 4: GESSO ---
    with tab4:
        media_g = df_completo['Dose_Gesso_Kg'].mean()
        st.metric("Média da Aplicação", f"{media_g:.0f} kg/ha")
        st.plotly_chart(
            plotar_mapa_otimizado(df_completo, 'Dose_Gesso_Kg', "Gesso", "Blues"),
            use_container_width=True
        )

    # --- BOTÃO DE EXPORTAÇÃO (IMPORTANTE) ---
    st.markdown("---")
    st.info("💡 A visualização acima mostra apenas uma amostra para não travar o sistema. O botão abaixo baixa o arquivo com 100% dos dados para o GPS.")
    
    # Gera CSV com 100% dos dados
    csv = df_completo.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="💾 BAIXAR ARQUIVO FINAL COMPLETO (.CSV)",
        data=csv,
        file_name='recomendacao_triade_vrt_final.csv',
        mime='text/csv',
        type='primary'
    )
