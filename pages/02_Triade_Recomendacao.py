import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Tríade VRT", layout="wide")
st.title("🚜 Tríade VRT - Motor de Recomendação")

# ==============================================================================
# 0. TRADUTOR DE COLUNAS (CALIBRADO PARA SUA IMAGEM)
# ==============================================================================
def padronizar_colunas_universal(df):
    """
    Renomeia as colunas do CSV do usuário para os nomes que o Python entende.
    Baseado na imagem enviada: 'P mehl' -> 'P', 'prem' -> 'P_Rem'
    """
    df_novo = df.copy()
    
    # Mapa de tradução (Chave = Nome no Código : Valor = Lista de nomes no seu CSV)
    sinonimos = {
        'lat': ['latitude', 'lat', 'y'],
        'lon': ['longitude', 'long', 'lon', 'x'],
        
        # Nutrientes (Conforme sua imagem)
        'Ca': ['ca', 'calcio'],        # Pega a coluna "Ca"
        'Mg': ['mg', 'magnesio'],      # Pega a coluna "Mg"
        'K':  ['k', 'potassio'],       # Pega a coluna "K"
        
        # Fósforo: O Código precisa do 'P' (Mehlich)
        'P':  ['p mehl', 'p_mehl', 'pmehlich', 'fosforo'], 
        
        # P-Rem: O Código precisa do 'P_Rem'
        'P_Rem': ['prem', 'p_rem', 'p-rem', 'prem.'],
        
        # Outros
        'Argila': ['argila', 'clay'],
        'CTC': ['ctc', 't']
    }

    # Varredura
    mapa_final = {}
    colunas_originais = list(df_novo.columns)
    
    for col_real in colunas_originais:
        c_clean = col_real.lower().strip() # Transforma "P mehl " em "p mehl"
        
        for padrao_codigo, lista_possibilidades in sinonimos.items():
            if c_clean in lista_possibilidades:
                mapa_final[col_real] = padrao_codigo
                break
    
    # Aplica a renomeação
    if mapa_final:
        df_novo = df_novo.rename(columns=mapa_final)
    
    return df_novo

# ==============================================================================
# 1. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("📂 Entrada de Dados")
    uploaded_file = st.file_uploader("Carregar Malha Interpolada (.csv)", type=["csv"])
    
    df_input = None

    if uploaded_file is not None:
        try:
            df_raw = pd.read_csv(uploaded_file)
            # APLICA A TRADUÇÃO
            df_input = padronizar_colunas_universal(df_raw)
            st.success(f"Arquivo carregado! {len(df_input)} pontos.")
        except Exception as e:
            st.error(f"Erro leitura: {e}")
            st.stop()
    elif 'df_interpolado' in st.session_state:
        df_raw = st.session_state['df_interpolado']
        df_input = padronizar_colunas_universal(df_raw)
        st.info("Usando dados da memória.")
    else:
        st.warning("⚠️ Faça upload do CSV.")
        st.stop()

    # --- DIAGNÓSTICO VISUAL (PARA CONFERÊNCIA) ---
    with st.expander("🕵️ Conferência de Colunas"):
        cols_usadas = df_input.columns.tolist()
        
        # Verifica se achou os principais
        check = {
            'P (Mehlich)': 'P' in cols_usadas,
            'P-rem': 'P_Rem' in cols_usadas,
            'Cálcio': 'Ca' in cols_usadas,
            'Potássio': 'K' in cols_usadas,
            'Argila': 'Argila' in cols_usadas
        }
        
        for k, v in check.items():
            if v: st.write(f"✅ {k}: OK")
            else: st.write(f"❌ {k}: Não achado (Dose será 0)")

    st.markdown("---")
    st.header("⚙️ Parâmetros")
    
    # 1. Cultura
    with st.expander("🌱 1. Cultura & Produtividade", expanded=True):
        produtividade_alvo = st.number_input("Meta (sc/ha):", value=80.0)

    # 2. Calagem
    with st.expander("⚪ 2. Calagem", expanded=False):
        alvo_ca = st.number_input("Alvo Ca (% CTC):", value=60.0)
        alvo_mg = st.number_input("Alvo Mg (% CTC):", value=18.0)
        teor_cao = st.number_input("CaO Calcário (%):", value=38.0)
        teor_mgo = st.number_input("MgO Calcário (%):", value=12.0)
        prnt = st.number_input("PRNT (%):", value=85.0)

    # 3. Fósforo
    with st.expander("🔴 3. Fósforo", expanded=False):
        p_export = st.number_input("Exportação P (kg/sc):", value=0.8)
        p_teor = st.number_input("Teor P2O5 (%):", value=52.0)
        nc_a, nc_b = 8.8, 0.76
        fct_a, fct_b = 56.5, -0.52

    # 4. Potássio
    with st.expander("🟣 4. Potássio", expanded=False):
        k_alvo_ctc = st.number_input("K Alvo CTC (%):", value=3.0)
        k_export = st.number_input("Exportação K (kg/sc):", value=1.2)
        k_teor = st.number_input("Teor K2O (%):", value=60.0)

    # 5. Gesso
    with st.expander("⚪ 5. Gesso", expanded=False):
        gesso_fator = st.number_input("Fator x Argila:", value=50.0)
        gesso_min = st.number_input("Min (kg/ha):", value=0.0)
        gesso_max = st.number_input("Max (kg/ha):", value=2000.0)

# ==============================================================================
# 2. CÁLCULO
# ==============================================================================
def calcular(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt_val, p_exp, p_teor_val, k_alvo_val, k_exp, k_teor_val, g_fat, g_min, g_max):
    dfr = df.copy()
    
    # CALAGEM
    if all(c in dfr.columns for c in ['Ca','Mg','CTC']):
        meta_ca, meta_mg = dfr['CTC']*(ca_alvo/100), dfr['CTC']*(mg_alvo/100)
        def_ca, def_mg = (meta_ca - dfr['Ca']).clip(0), (meta_mg - dfr['Mg']).clip(0)
        ap_ca, ap_mg = max((cao*10/560)*(prnt_val/100), 0.001), max((mgo*10/403)*(prnt_val/100), 0.001)
        dfr['Dose_Calcario'] = np.maximum(def_ca/ap_ca, def_mg/ap_mg).round(2)
        
        ca_f = dfr['Ca'] + (dfr['Dose_Calcario']*ap_ca)
        mg_f = dfr['Mg'] + (dfr['Dose_Calcario']*ap_mg)
        ratio = ca_f / mg_f.replace(0, 0.01)
        dfr['Status_Calagem'] = 'OK'
        dfr.loc[ratio < 2, 'Status_Calagem'] = '⚠️ Risco: Excesso Mg'
        dfr.loc[ratio > 4, 'Status_Calagem'] = '⚠️ Risco: Falta Mg'
    else:
        dfr['Dose_Calcario'] = 0.0
        dfr['Status_Calagem'] = 'S/ Dados'

    # FOSFORO (5ª Aprox: Usa 'P' (Mehlich) e 'P_Rem' (Prem))
    if 'P_Rem' in dfr.columns and 'P' in dfr.columns:
        # Garante numérico
        dfr['P'] = pd.to_numeric(dfr['P'], errors='coerce').fillna(0)
        dfr['P_Rem'] = pd.to_numeric(dfr['P_Rem'], errors='coerce').fillna(10) # Default seguro
        
        nc = (8.8 + 0.76*dfr['P_Rem']).clip(8,60)
        fct = (56.5 * dfr['P_Rem']**-0.52).clip(4,40)
        dose_p = np.where(nc > dfr['P'], (nc-dfr['P'])*fct, 0) + (prod*p_exp)
        dfr['Dose_P2O5_Kg'] = (dose_p / (p_teor_val/100)) if p_teor_val > 0 else 0
    else:
        dfr['Dose_P2O5_Kg'] = 0.0

    # POTASSIO
    if 'K' in dfr.columns and 'CTC' in dfr.columns:
        k_meta = dfr['CTC']*(k_alvo_val/100)
        # Conversão Inteligente: Se K > 10, assume mg/dm3 e converte pra cmol
        k_vals = pd.to_numeric(dfr['K'], errors='coerce').fillna(0)
        if k_vals.mean() > 10:
            k_vals = k_vals / 391.0
            
        dose_k = (k_meta - k_vals).clip(0)*940 + (prod*k_exp)
        dfr['Dose_K2O_Kg'] = (dose_k / (k_teor_val/100)) if k_teor_val > 0 else 0
    else:
        dfr['Dose_K2O_Kg'] = 0.0

    # GESSO
    if 'Argila' in dfr.columns:
        dfr['Dose_Gesso_Kg'] = (dfr['Argila']*g_fat).clip(g_min, g_max)
    else:
        dfr['Dose_Gesso_Kg'] = 0.0

    return dfr

# ==============================================================================
# 3. EXECUÇÃO
# ==============================================================================
if st.button("🚀 Processar Recomendação VRT", type="primary"):
    with st.spinner("Calculando..."):
        try:
            res = calcular(df_input, produtividade_alvo, alvo_ca, alvo_mg, teor_cao, teor_mgo, prnt,
                           p_export, p_teor, k_alvo_ctc, k_export, k_teor, gesso_fator, gesso_min, gesso_max)
            st.session_state['vrt_final'] = res
            st.success("Sucesso! O sistema identificou 'P mehl' e 'prem' corretamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

# ==============================================================================
# 4. MAPAS (PONTOS MAIORES)
# ==============================================================================
if 'vrt_final' in st.session_state:
    df_show = st.session_state['vrt_final']
    st.markdown("---")
    
    if df_show.empty:
        st.error("Erro: Tabela vazia.")
    else:
        t1, t2, t3, t4 = st.tabs(["⚪ Calcário", "🔴 Fósforo", "🟣 Potássio", "🔵 Gesso"])
        
        def mapa(d, col, tit, cor):
            amostra = d.sample(n=min(800, len(d)), random_state=42)
            fig = go.Figure(go.Scattermapbox(
                lat=amostra['lat'], lon=amostra['lon'],
                mode='markers',
                marker=go.scattermapbox.Marker(
                    size=10, 
                    color=amostra[col], colorscale=cor, showscale=True, opacity=0.9
                ),
                text=amostra[col].round(1),
                hovertemplate=f"<b>{tit}: %{{text}}</b><extra></extra>"
            ))
            fig.update_layout(
                mapbox_style="open-street-map", title=f"{tit} (Amostra Rápida)",
                margin={"r":0,"t":30,"l":0,"b":0}, height=450
            )
            return fig

        with t1:
            st.metric("Média", f"{df_show['Dose_Calcario'].mean():.2f} ton")
            if 'Status_Calagem' in df_show.columns:
                 stats = df_show['Status_Calagem'].astype(str)
                 ruins = len(stats[stats.str.contains("⚠️")])
                 if ruins > 0: st.warning(f"⚠️ {ruins} pontos com desequilíbrio.")
            st.plotly_chart(mapa(df_show, 'Dose_Calcario', "Calcário", "Reds"), use_container_width=True)

        with t2:
            st.metric("Média", f"{df_show['Dose_P2O5_Kg'].mean():.0f} kg")
            st.plotly_chart(mapa(df_show, 'Dose_P2O5_Kg', "Fósforo", "Viridis"), use_container_width=True)

        with t3:
            st.metric("Média", f"{df_show['Dose_K2O_Kg'].mean():.0f} kg")
            st.plotly_chart(mapa(df_show, 'Dose_K2O_Kg', "Potássio", "Plasma"), use_container_width=True)

        with t4:
            st.metric("Média", f"{df_show['Dose_Gesso_Kg'].mean():.0f} kg")
            st.plotly_chart(mapa(df_show, 'Dose_Gesso_Kg', "Gesso", "Blues"), use_container_width=True)

        st.markdown("---")
        csv = df_show.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Baixar CSV Completo", csv, "recomendacao_vrt.csv", "text/csv", type='primary')
