import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64

# --- 1. CONFIGURAÇÃO DE BACKEND (VACINA ANTI-TRAVAMENTO) ---
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

import folium
from streamlit_folium import st_folium

# ==============================================================================
# 2. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Tríade VRT", layout="wide")
st.title("🚜 Tríade VRT - Motor de Recomendação")

# ==============================================================================
# 3. FUNÇÕES UTILITÁRIAS
# ==============================================================================
def limpar_e_padronizar_dados(df):
    df_novo = df.copy()
    df_novo.columns = [c.lower().strip() for c in df_novo.columns]
    
    sinonimos = {
        'latitude': ['latitude', 'lat', 'y', 'lat_wgs84'],
        'longitude': ['longitude', 'long', 'lon', 'x', 'lon_wgs84'],
        'Ca': ['ca', 'calcio', 'cálcio', 'ca_cmolc'],
        'Mg': ['mg', 'magnesio', 'magnésio', 'mg_cmolc'],
        'K':  ['k', 'potassio', 'potássio', 'k_mg'],
        'P':  ['p mehl', 'p_mehl', 'pmehlich', 'fosforo', 'fósforo', 'p'], 
        'P_Rem': ['prem', 'p_rem', 'p-rem', 'fosforo_remanescente', 'prem.'],
        'Argila': ['argila', 'clay', 'argila_total'],
        'CTC': ['ctc', 't', 'ctc_ph7']
    }
    
    mapa_final = {}
    for col_real in df_novo.columns:
        for padrao, lista in sinonimos.items():
            if col_real in lista:
                mapa_final[col_real] = padrao
                break
    
    if mapa_final:
        df_novo = df_novo.rename(columns=mapa_final)

    cols_numericas = ['Ca', 'Mg', 'K', 'P', 'P_Rem', 'Argila', 'CTC', 'latitude', 'longitude']
    for col in cols_numericas:
        if col in df_novo.columns:
            if df_novo[col].dtype == 'object':
                df_novo[col] = df_novo[col].astype(str).str.replace(',', '.')
            df_novo[col] = pd.to_numeric(df_novo[col], errors='coerce').fillna(0)

    return df_novo

def calcular_recomendacao(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt_val, p_exp, p_teor_val, k_alvo_val, k_exp, k_teor_val, g_fat, g_min, g_max, nc_vals):
    dfr = df.copy()
    
    # --- CALAGEM ---
    if all(c in dfr.columns for c in ['Ca','Mg','CTC']):
        meta_ca = dfr['CTC'] * (ca_alvo / 100.0)
        meta_mg = dfr['CTC'] * (mg_alvo / 100.0)
        def_ca = (meta_ca - dfr['Ca']).clip(lower=0)
        def_mg = (meta_mg - dfr['Mg']).clip(lower=0)
        ap_ca = max((cao * 10 / 560.0) * (prnt_val / 100.0), 0.001)
        ap_mg = max((mgo * 10 / 403.0) * (prnt_val / 100.0), 0.001)
        dfr['Dose_Calcario'] = np.maximum(def_ca/ap_ca, def_mg/ap_mg).round(2)
    else:
        dfr['Dose_Calcario'] = 0.0

    # --- FÓSFORO (TABELA FIXA) ---
    if 'P_Rem' in dfr.columns and 'P' in dfr.columns:
        
        # Definição das condições (Faixas de P-rem)
        condicoes = [
            (dfr['P_Rem'] <= 4.0),                          # Faixa 1
            (dfr['P_Rem'] > 4.0) & (dfr['P_Rem'] <= 10.0),  # Faixa 2
            (dfr['P_Rem'] > 10.0) & (dfr['P_Rem'] <= 19.0), # Faixa 3
            (dfr['P_Rem'] > 19.0) & (dfr['P_Rem'] <= 30.0), # Faixa 4
            (dfr['P_Rem'] > 30.0)                           # Faixa 5
        ]
        
        # Valores correspondentes a cada faixa (vindos da Sidebar)
        valores_nc = [
            nc_vals['nc_1'], 
            nc_vals['nc_2'], 
            nc_vals['nc_3'], 
            nc_vals['nc_4'], 
            nc_vals['nc_5']
        ]
        
        # Aplica a lógica
        nc = np.select(condicoes, valores_nc, default=nc_vals['nc_5'])
        
        # Fator Tampão
        fct = (56.5 * dfr['P_Rem']**-0.52).clip(4, 40)
        
        # Auditoria e Cálculo
        dfr['NC_Tabular'] = nc
        dfr['FCT_Calculado'] = fct.round(2)
        
        dose_const = np.where(nc > dfr['P'], (nc - dfr['P']) * fct, 0)
        dose_manu = prod * p_exp
        total_p = dose_const + dose_manu
        dfr['Dose_P2O5_Kg'] = (total_p / (p_teor_val/100.0)) if p_teor_val > 0 else 0
        dfr['Dose_P2O5_Kg'] = dfr['Dose_P2O5_Kg'].round(0)
    else:
        dfr['Dose_P2O5_Kg'] = 0.0

    # --- POTÁSSIO ---
    if 'K' in dfr.columns and 'CTC' in dfr.columns:
        k_meta = dfr['CTC'] * (k_alvo_val/100.0)
        k_vals = dfr['K'].copy()
        if k_vals.mean() > 10: k_vals = k_vals / 391.0 
        dose_k_const = (k_meta - k_vals).clip(lower=0) * 940.0
        dose_k_manu = prod * k_exp
        total_k = dose_k_const + dose_k_manu
        dfr['Dose_K2O_Kg'] = (total_k / (k_teor_val/100.0)) if k_teor_val > 0 else 0
    else:
        dfr['Dose_K2O_Kg'] = 0.0

    # --- GESSO ---
    if 'Argila' in dfr.columns:
        dfr['Dose_Gesso_Kg'] = (dfr['Argila'] * g_fat).clip(lower=g_min, upper=g_max)
    else:
        dfr['Dose_Gesso_Kg'] = 0.0

    return dfr

# ==============================================================================
# 4. MOTOR VISUAL DO APP 1
# ==============================================================================
st.divider()
    
    # Seletor de Mapa
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        atributo = st.selectbox("Selecione o mapa:", cols_ver)
        df_plot = df_final.dropna(subset=[atributo])
        
        if not df_plot.empty:
            try:
                # Gera Imagem
                img_buffer, bounds, intervals = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'])
                
                # Mapa Folium
                centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                
                # Overlay da Imagem
                img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                folium.raster_layers.ImageOverlay(
                    image=f"data:image/png;base64,{img_b64}",
                    bounds=bounds, opacity=0.85
                ).add_to(m)
                
                # Contorno Preto
                folium.GeoJson(
                    st.session_state['geojson_data'],
                    style_function=lambda x: {'color': 'black', 'weight': 3, 'fillOpacity': 0}
                ).add_to(m)
                
                # Legenda Simples
                legend_html = f"""
                <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; background: white; padding: 10px; border: 2px solid black; border-radius: 5px;">
                <b>{atributo}</b><br>
                <span style="color:#d73027">■</span> Baixo ({intervals[0]:.1f} - {intervals[1]:.1f})<br>
                <span style="color:#fee08b">■</span> Médio ({intervals[2]:.1f})<br>
                <span style="color:#1a9850">■</span> Alto ({intervals[4]:.1f} - {intervals[5]:.1f})
                </div>
                """
                m.get_root().html.add_child(folium.Element(legend_html))
                
                st_folium(m, height=500, use_container_width=True)
                
            except Exception as e:
                st.error(f"Erro visual: {e}")

# ==============================================================================
# 5. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("📂 Arquivos de Entrada")
    uploaded_csv = st.file_uploader("1. Malha Interpolada (.csv)", type=["csv"])
    uploaded_geojson = st.file_uploader("2. Contorno (.geojson)", type=["geojson", "json"])
    
    df_input = None
    geojson_data = None

    if uploaded_csv and uploaded_geojson:
        try:
            try: df_raw = pd.read_csv(uploaded_csv, sep=None, engine='python')
            except: df_raw = pd.read_csv(uploaded_csv)
            df_input = limpar_e_padronizar_dados(df_raw)
            geojson_data = json.load(uploaded_geojson)
            st.success(f"Dados prontos! {len(df_input)} pontos.")
        except Exception as e:
            st.error(f"Erro: {e}")
            st.stop()
    else:
        st.warning("Faça upload do CSV e do GeoJSON.")
        st.stop()

    st.markdown("---")
    st.header("⚙️ Parâmetros")
    
    with st.expander("🌱 1. Cultura & Produtividade", expanded=True):
        produtividade_alvo = st.number_input("Meta (sc/ha):", value=75.0)

    with st.expander("⚪ 2. Calagem", expanded=False):
        alvo_ca = st.number_input("Alvo Ca (% CTC):", value=55.0)
        alvo_mg = st.number_input("Alvo Mg (% CTC):", value=15.0)
        teor_cao = st.number_input("CaO Calcário (%):", value=38.0)
        teor_mgo = st.number_input("MgO Calcário (%):", value=12.0)
        prnt = st.number_input("PRNT (%):", value=85.0)

    with st.expander("🔴 3. Fósforo (Tabela Fixa)", expanded=True):
        p_export = st.number_input("Exportação P (kg/sc):", value=0.8)
        p_teor = st.number_input("Teor P2O5 (%):", value=52.0)
        
        st.markdown("##### 🎯 Níveis Críticos (mg/dm³) por Faixa de P-rem")
        c1, c2 = st.columns(2)
        with c1:
            nc_1 = st.number_input("0 - 4", value=5.5)
            nc_2 = st.number_input("4,1 - 10", value=8.0)
            nc_3 = st.number_input("10,1 - 19", value=12.0)
        with c2:
            nc_4 = st.number_input("19,1 - 30", value=15.0)
            nc_5 = st.number_input("> 30", value=20.0)
            
        nc_vals = {'nc_1': nc_1, 'nc_2': nc_2, 'nc_3': nc_3, 'nc_4': nc_4, 'nc_5': nc_5}

    with st.expander("🟣 4. Potássio", expanded=False):
        k_alvo_ctc = st.number_input("K Alvo CTC (%):", value=3.0)
        k_export = st.number_input("Exportação K (kg/sc):", value=1.2)
        k_teor = st.number_input("Teor K2O (%):", value=60.0)

    with st.expander("⚪ 5. Gesso", expanded=False):
        gesso_fator = st.number_input("Fator x Argila:", value=50.0)
        gesso_min = st.number_input("Min (kg/ha):", value=0.0)
        gesso_max = st.number_input("Max (kg/ha):", value=2000.0)

# ==============================================================================
# 6. EXECUÇÃO
# ==============================================================================
if st.button("🚀 Calcular e Gerar Mapas", type="primary"):
    with st.spinner("Aplicando Tabela Fixa de Fósforo..."):
        res = calcular_recomendacao(
            df_input, produtividade_alvo, alvo_ca, alvo_mg, teor_cao, teor_mgo, prnt,
            p_export, p_teor, k_alvo_ctc, k_export, k_teor, gesso_fator, gesso_min, gesso_max, nc_vals
        )
        st.session_state['vrt_final'] = res
        st.rerun()

if 'vrt_final' in st.session_state:
    df_show = st.session_state['vrt_final']
    st.markdown("---")
    
    t1, t2, t3, t4 = st.tabs(["⚪ Calcário", "🔴 Fósforo", "🟣 Potássio", "🔵 Gesso"])
    
    with t1:
        st.metric("Dose Média", f"{df_show['Dose_Calcario'].mean():.2f} ton/ha")
        mapa = gerar_mapa_app1(df_show, 'Dose_Calcario', "Calcário (ton/ha)", geojson_data)
        if mapa: st_folium(mapa, height=500, use_container_width=True)

    with t2:
        st.metric("Dose Média", f"{df_show['Dose_P2O5_Kg'].mean():.0f} kg/ha")
        
        st.info("Validação: Confira se o NC_Tabular bate com os valores que você definiu.")
        cols_final = [c for c in ['P_Rem', 'P', 'NC_Tabular', 'FCT_Calculado', 'Dose_P2O5_Kg'] if c in df_show.columns]
        st.dataframe(df_show[cols_final].head(50), height=200)

        mapa = gerar_mapa_app1(df_show, 'Dose_P2O5_Kg', "Fósforo (kg/ha)", geojson_data)
        if mapa: st_folium(mapa, height=500, use_container_width=True)

    with t3:
        st.metric("Dose Média", f"{df_show['Dose_K2O_Kg'].mean():.0f} kg/ha")
        mapa = gerar_mapa_app1(df_show, 'Dose_K2O_Kg', "Potássio (kg/ha)", geojson_data)
        if mapa: st_folium(mapa, height=500, use_container_width=True)

    with t4:
        st.metric("Dose Média", f"{df_show['Dose_Gesso_Kg'].mean():.0f} kg/ha")
        mapa = gerar_mapa_app1(df_show, 'Dose_Gesso_Kg', "Gesso (kg/ha)", geojson_data)
        if mapa: st_folium(mapa, height=500, use_container_width=True)

    st.markdown("---")
    csv = df_show.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Baixar CSV Final (Monitor)", csv, "recomendacao_vrt.csv", "text/csv", type='primary')
