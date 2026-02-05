import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Tríade VRT", layout="wide")
st.title("🚜 Tríade VRT - Motor de Recomendação")

# ==============================================================================
# FUNÇÃO AUXILIAR: PADRONIZAR NOMES DE COLUNAS (CORREÇÃO DO ERRO)
# ==============================================================================
def padronizar_coordenadas(df):
    """
    Tenta encontrar colunas de latitude/longitude com nomes variados
    e renomeia para o padrão 'lat' e 'lon'.
    """
    df_novo = df.copy()
    colunas_originais = [c.lower().strip() for c in df_novo.columns]
    mapa_renomeacao = {}

    # Procura variações de Latitude
    for col in df_novo.columns:
        c_low = col.lower().strip()
        if c_low in ['latitude', 'lat', 'y', 'lat_wgs84']:
            mapa_renomeacao[col] = 'lat'
        elif c_low in ['longitude', 'long', 'lon', 'x', 'lon_wgs84']:
            mapa_renomeacao[col] = 'lon'
            
    # Aplica a renomeação
    if mapa_renomeacao:
        df_novo = df_novo.rename(columns=mapa_renomeacao)
        
    return df_novo

# ==============================================================================
# 1. SIDEBAR: UPLOAD E CONFIGURAÇÕES
# ==============================================================================
with st.sidebar:
    st.header("📂 Entrada de Dados")
    
    # --- A. UPLOAD DO ARQUIVO ---
    uploaded_file = st.file_uploader("Carregar Malha Interpolada (.csv)", type=["csv"])
    
    df_input = None

    # Lógica de Carregamento + BLINDAGEM DE ERRO
    if uploaded_file is not None:
        try:
            df_raw = pd.read_csv(uploaded_file)
            df_input = padronizar_coordenadas(df_raw) # <--- AQUI A MÁGICA
            st.success(f"Arquivo carregado! {len(df_input)} pontos.")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            st.stop()
            
    elif 'df_interpolado' in st.session_state:
        # Recupera da memória e também padroniza
        df_raw = st.session_state['df_interpolado']
        df_input = padronizar_coordenadas(df_raw)
        st.info("Usando dados da memória (Aba Interpolação).")
    else:
        st.warning("⚠️ Por favor, faça o upload do CSV acima para começar.")
        st.stop()

    # Validação Final: Se depois de tudo não tiver 'lat'/'lon', avisa o usuário
    if 'lat' not in df_input.columns or 'lon' not in df_input.columns:
        st.error("❌ Erro Crítico: Não encontrei colunas de coordenadas.")
        st.write("O sistema procurou por: lat, latitude, y / lon, longitude, x.")
        st.write("Colunas encontradas no seu arquivo:", list(df_input.columns))
        st.stop()

    st.markdown("---")
    st.header("⚙️ Parâmetros Agronômicos")
    
    # --- B. CONFIGURAÇÕES DOS NUTRIENTES ---
    
    # 1. Cultura e Produtividade
    with st.expander("🌱 1. Cultura & Produtividade", expanded=True):
        produtividade_alvo = st.number_input("Meta de Produtividade (sc/ha):", value=80.0, step=1.0)

    # 2. Calagem
    with st.expander("⚪ 2. Calagem (Balanço de Bases)", expanded=False):
        alvo_ca = st.number_input("Alvo Ca (% CTC):", value=60.0, step=1.0)
        alvo_mg = st.number_input("Alvo Mg (% CTC):", value=18.0, step=1.0)
        teor_cao = st.number_input("Teor CaO Calcário (%):", value=38.0, step=0.5)
        teor_mgo = st.number_input("Teor MgO Calcário (%):", value=12.0, step=0.5)
        prnt = st.number_input("PRNT (%):", value=85.0, step=1.0)

    # 3. Fósforo
    with st.expander("🔴 3. Fósforo (5ª Aprox)", expanded=False):
        p_export = st.number_input("Exportação P (kg/sc):", value=0.8, step=0.1)
        p_teor = st.number_input("Teor P2O5 Adubo (%):", value=52.0, step=1.0)
        # Parâmetros ocultos (regressão)
        nc_a, nc_b = 8.8, 0.76
        fct_a, fct_b = 56.5, -0.52

    # 4. Potássio
    with st.expander("🟣 4. Potássio (K)", expanded=False):
        k_alvo_ctc = st.number_input("K Alvo CTC (%):", value=3.0, step=0.1)
        k_export = st.number_input("Exportação K (kg/sc):", value=1.2, step=0.1)
        k_teor = st.number_input("Teor K2O Adubo (%):", value=60.0, step=1.0)

    # 5. Gesso
    with st.expander("⚪ 5. Gesso Agrícola", expanded=False):
        gesso_fator = st.number_input("Fator x Argila:", value=50.0, step=5.0)
        gesso_min = st.number_input("Dose Mínima (kg/ha):", value=0.0, step=100.0)
        gesso_max = st.number_input("Dose Máxima (kg/ha):", value=2000.0, step=100.0)

# ==============================================================================
# 2. MOTOR DE CÁLCULO
# ==============================================================================
def calcular_recomendacao_completa(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt_val, 
                                  p_exp, p_teor_val, k_alvo_val, k_exp, k_teor_val,
                                  g_fat, g_min, g_max):
    dfr = df.copy()
    
    # --- A. CALAGEM ---
    if all(c in dfr.columns for c in ['Ca','Mg','CTC']):
        meta_ca = dfr['CTC'] * (ca_alvo / 100)
        meta_mg = dfr['CTC'] * (mg_alvo / 100)
        
        def_ca = (meta_ca - dfr['Ca']).clip(lower=0)
        def_mg = (meta_mg - dfr['Mg']).clip(lower=0)
        
        ap_ca = max((cao * 10 / 560) * (prnt_val / 100), 0.001)
        ap_mg = max((mgo * 10 / 403) * (prnt_val / 100), 0.001)
        
        dose_ca = def_ca / ap_ca
        dose_mg = def_mg / ap_mg
        
        dfr['Dose_Calcario'] = np.maximum(dose_ca, dose_mg).round(2)
        
        # Alerta Ratio
        ca_fim = dfr['Ca'] + (dfr['Dose_Calcario'] * ap_ca)
        mg_fim = dfr['Mg'] + (dfr['Dose_Calcario'] * ap_mg)
        ratio = ca_fim / mg_fim.replace(0, 0.01)
        
        dfr['Status_Calagem'] = 'OK'
        dfr.loc[ratio < 2, 'Status_Calagem'] = '⚠️ Risco: Excesso Mg'
        dfr.loc[ratio > 4, 'Status_Calagem'] = '⚠️ Risco: Falta Mg'
    else:
        dfr['Dose_Calcario'] = 0.0
        dfr['Status_Calagem'] = 'S/ Dados'

    # --- B. FÓSFORO ---
    if 'P_Rem' in dfr.columns and 'P' in dfr.columns:
        nc = (8.8 + 0.76 * dfr['P_Rem']).clip(8, 60)
        fct = (56.5 * dfr['P_Rem']**-0.52).clip(4, 40)
        dose_const = np.where(nc > dfr['P'], (nc - dfr['P']) * fct, 0)
        dose_manu = prod * p_exp
        total_p = dose_const + dose_manu
        dfr['Dose_P2O5_Kg'] = (total_p / (p_teor_val/100)) if p_teor_val > 0 else 0
    else:
        dfr['Dose_P2O5_Kg'] = 0.0

    # --- C. POTÁSSIO ---
    if 'K' in dfr.columns and 'CTC' in dfr.columns:
        k_meta = dfr['CTC'] * (k_alvo_val/100)
        k_atual = dfr['K'] / 391
        dose_k_const = (k_meta - k_atual).clip(lower=0) * 940
        dose_k_manu = prod * k_exp
        total_k = dose_k_const + dose_k_manu
        dfr['Dose_K2O_Kg'] = (total_k / (k_teor_val/100)) if k_teor_val > 0 else 0
    else:
        dfr['Dose_K2O_Kg'] = 0.0

    # --- D. GESSO ---
    if 'Argila' in dfr.columns:
        dfr['Dose_Gesso_Kg'] = (dfr['Argila'] * g_fat).clip(lower=g_min, upper=g_max)
    else:
        dfr['Dose_Gesso_Kg'] = 0.0

    return dfr

# ==============================================================================
# 3. INTERFACE DE EXECUÇÃO
# ==============================================================================

if st.button("🚀 Processar Recomendação VRT", type="primary"):
    with st.spinner("Calculando..."):
        try:
            df_result = calcular_recomendacao_completa(
                df_input, produtividade_alvo,
                alvo_ca, alvo_mg, teor_cao, teor_mgo, prnt,
                p_export, p_teor,
                k_alvo_ctc, k_export, k_teor,
                gesso_fator, gesso_min, gesso_max
            )
            st.session_state['vrt_final'] = df_result
            st.success("Sucesso! Atualizando mapas...")
            st.rerun()
        except Exception as e:
            st.error(f"Erro no cálculo: {e}")

# ==============================================================================
# 4. VISUALIZAÇÃO
# ==============================================================================
if 'vrt_final' in st.session_state:
    df_show = st.session_state['vrt_final']
    
    st.markdown("---")
    st.header("🗺️ Mapas Gerados")
    
    if df_show.empty:
        st.error("Erro: Tabela vazia.")
    else:
        t1, t2, t3, t4 = st.tabs(["⚪ Calcário", "🔴 Fósforo", "🟣 Potássio", "🔵 Gesso"])
        
        # Função Mapa Leve
        def mapa_leve(dados, col, tit, cor):
            # Garante que usamos 'lat' e 'lon' que agora existem certeza
            amostra = dados.sample(n=min(500, len(dados)), random_state=42)
            
            fig = go.Figure(go.Scattermapbox(
                lat=amostra['lat'], lon=amostra['lon'],
                mode='markers',
                marker=go.scattermapbox.Marker(
                    size=8, color=amostra[col], colorscale=cor, showscale=True, opacity=0.9
                ),
                text=amostra[col].round(1),
                hovertemplate=f"<b>{tit}: %{{text}}</b><extra></extra>"
            ))
            fig.update_layout(
                mapbox_style="open-street-map", 
                title=f"{tit} (Amostra Rápida)",
                margin={"r":0,"t":30,"l":0,"b":0}, height=450
            )
            return fig

        with t1:
            st.metric("Média Calcário", f"{df_show['Dose_Calcario'].mean():.2f} ton/ha")
            if 'Status_Calagem' in df_show.columns:
                ruins = len(df_show[df_show['Status_Calagem'].astype(str).str.contains("⚠️")])
                if ruins > 0: st.warning(f"⚠️ {ruins} pontos com risco de desequilíbrio.")
            st.plotly_chart(mapa_leve(df_show, 'Dose_Calcario', "Calcário", "Reds"), use_container_width=True)

        with t2:
            st.metric("Média Fósforo", f"{df_show['Dose_P2O5_Kg'].mean():.0f} kg/ha")
            st.plotly_chart(mapa_leve(df_show, 'Dose_P2O5_Kg', "Fósforo", "Viridis"), use_container_width=True)

        with t3:
            st.metric("Média Potássio", f"{df_show['Dose_K2O_Kg'].mean():.0f} kg/ha")
            st.plotly_chart(mapa_leve(df_show, 'Dose_K2O_Kg', "Potássio", "Plasma"), use_container_width=True)
            
        with t4:
            st.metric("Média Gesso", f"{df_show['Dose_Gesso_Kg'].mean():.0f} kg/ha")
            st.plotly_chart(mapa_leve(df_show, 'Dose_Gesso_Kg', "Gesso", "Blues"), use_container_width=True)

        st.markdown("---")
        csv = df_show.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Baixar CSV Completo", csv, "recomendacao_vrt.csv", "text/csv", type='primary')
