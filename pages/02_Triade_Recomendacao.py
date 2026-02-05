import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Título
st.title("🚜 Tríade VRT - Motor de Recomendação")

# --- 1. VERIFICAÇÃO DE DADOS ---
if 'df_interpolado' not in st.session_state:
    st.warning("⚠️ Volte para a aba 'Interpolação' e gere a malha primeiro.")
    st.stop()

df_input = st.session_state['df_interpolado']

# --- 2. SIDEBAR (CONFIGURAÇÕES) ---
with st.sidebar:
    st.header("⚙️ Parâmetros")
    
    with st.expander("1. Cultura & Produtividade", expanded=True):
        produtividade_alvo = st.number_input("Meta (sc/ha):", value=80.0)

    with st.expander("2. Calagem (Ca/Mg)", expanded=False):
        alvo_ca = st.number_input("Alvo Ca (%):", value=60.0)
        alvo_mg = st.number_input("Alvo Mg (%):", value=18.0)
        teor_cao = st.number_input("Teor CaO (%):", value=38.0)
        teor_mgo = st.number_input("Teor MgO (%):", value=12.0)
        prnt = st.number_input("PRNT (%):", value=85.0)

    with st.expander("3. Fósforo (5ª Aprox)", expanded=False):
        p_export = st.number_input("Exportação P (kg/sc):", value=0.8)
        p_teor = st.number_input("Teor P2O5 Adubo (%):", value=52.0)

    with st.expander("4. Potássio", expanded=False):
        k_alvo_ctc = st.number_input("K Alvo CTC (%):", value=3.0)
        k_export = st.number_input("Exportação K (kg/sc):", value=1.2)
        k_teor = st.number_input("Teor K2O Adubo (%):", value=60.0)

# --- 3. MOTOR DE CÁLCULO (FUNÇÃO PURA) ---
def calcular_recomendacao(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt_val, p_exp, p_teor_val, k_alvo_val, k_exp, k_teor_val):
    dfr = df.copy()
    
    # --- CALAGEM ---
    if all(c in dfr.columns for c in ['Ca','Mg','CTC']):
        # Alvos em Cmol
        meta_ca = dfr['CTC'] * (ca_alvo / 100)
        meta_mg = dfr['CTC'] * (mg_alvo / 100)
        
        # Déficits
        def_ca = (meta_ca - dfr['Ca']).clip(lower=0)
        def_mg = (meta_mg - dfr['Mg']).clip(lower=0)
        
        # Aporte por Tonelada
        ap_ca = (cao * 10 / 560) * (prnt_val / 100)
        ap_mg = (mgo * 10 / 403) * (prnt_val / 100)
        
        # Doses
        dose_ca = def_ca / max(ap_ca, 0.001)
        dose_mg = def_mg / max(ap_mg, 0.001)
        
        # Regra do Maior
        dfr['Dose_Calcario'] = np.maximum(dose_ca, dose_mg).round(2)
        
        # Alerta
        ca_fim = dfr['Ca'] + (dfr['Dose_Calcario'] * ap_ca)
        mg_fim = dfr['Mg'] + (dfr['Dose_Calcario'] * ap_mg)
        ratio = ca_fim / mg_fim.replace(0, 0.01)
        
        dfr['Status'] = 'OK'
        dfr.loc[ratio < 2, 'Status'] = '⚠️ Excesso Mg'
        dfr.loc[ratio > 4, 'Status'] = '⚠️ Falta Mg'
    else:
        dfr['Dose_Calcario'] = 0.0

    # --- FÓSFORO (Regressão) ---
    if 'P_Rem' in dfr.columns and 'P' in dfr.columns:
        nc = (8.8 + 0.76 * dfr['P_Rem']).clip(8, 60)
        fct = (56.5 * dfr['P_Rem']**-0.52).clip(4, 40)
        dose_const = np.where(nc > dfr['P'], (nc - dfr['P']) * fct, 0)
        dose_manu = prod * p_exp
        dfr['Dose_P2O5'] = (dose_const + dose_manu) / (p_teor_val/100)
    else:
        dfr['Dose_P2O5'] = 0.0

    # --- POTÁSSIO ---
    if 'K' in dfr.columns and 'CTC' in dfr.columns:
        k_meta = dfr['CTC'] * (k_alvo_val/100)
        k_atual = dfr['K'] / 391
        dose_k_const = (k_meta - k_atual).clip(lower=0) * 940
        dose_k_manu = prod * k_exp
        dfr['Dose_K2O'] = (dose_k_const + dose_k_manu) / (k_teor_val/100)
    else:
        dfr['Dose_K2O'] = 0.0

    return dfr

# --- 4. EXECUÇÃO ---
if st.button("🚀 Calcular VRT", type="primary"):
    with st.spinner("Processando..."):
        # Executa cálculo
        resultado = calcular_recomendacao(
            df_input, produtividade_alvo, 
            alvo_ca, alvo_mg, teor_cao, teor_mgo, prnt,
            p_export, p_teor,
            k_alvo_ctc, k_export, k_teor
        )
        
        # Salva na sessão
        st.session_state['vrt_final'] = resultado
        st.success("Cálculo Finalizado!")

# --- 5. VISUALIZAÇÃO (SÓ EXECUTA SE TIVER DADOS) ---
if 'vrt_final' in st.session_state:
    df_show = st.session_state['vrt_final']
    
    # ABAS
    t1, t2, t3 = st.tabs(["Calcário", "Fósforo", "Potássio"])
    
    # --- FUNÇÃO DE MAPA SUPER LEVE ---
    def mapa_leve(dados, col, tit, cor):
        # PEGA NO MÁXIMO 500 PONTOS P/ NÃO TRAVAR
        amostra = dados.sample(n=min(500, len(dados)), random_state=1)
        
        fig = go.Figure(go.Scattermapbox(
            lat=amostra['lat'], lon=amostra['lon'],
            mode='markers',
            marker=go.scattermapbox.Marker(size=9, color=amostra[col], colorscale=cor, showscale=True),
            text=amostra[col].round(1)
        ))
        fig.update_layout(
            mapbox_style="open-street-map", 
            title=f"{tit} (Amostra Rápida)",
            height=400, margin={"r":0,"t":40,"l":0,"b":0}
        )
        return fig

    with t1:
        st.metric("Média", f"{df_show['Dose_Calcario'].mean():.2f} ton")
        st.plotly_chart(mapa_leve(df_show, 'Dose_Calcario', "Calcário", "Reds"), use_container_width=True)
        
        # Aviso de Ratio (Sem travar mapa)
        ruins = len(df_show[df_show['Status'] != 'OK'])
        if ruins > 0:
            st.warning(f"⚠️ {ruins} pontos com desequilíbrio Ca/Mg previsto.")

    with t2:
        st.metric("Média", f"{df_show['Dose_P2O5'].mean():.0f} kg")
        st.plotly_chart(mapa_leve(df_show, 'Dose_P2O5', "Fósforo", "Viridis"), use_container_width=True)

    with t3:
        st.metric("Média", f"{df_show['Dose_K2O'].mean():.0f} kg")
        st.plotly_chart(mapa_leve(df_show, 'Dose_K2O', "Potássio", "Plasma"), use_container_width=True)

    # DOWNLOAD (AQUI VAI O ARQUIVO COMPLETO)
    st.markdown("---")
    csv = df_show.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Baixar CSV Completo (Todos os pontos)", csv, "vrt_final.csv", "text/csv")
