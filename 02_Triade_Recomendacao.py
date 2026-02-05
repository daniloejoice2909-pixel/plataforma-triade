import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64

# --- BLINDAGEM ANTI-TRAVAMENTO (V59) ---
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

import folium
from streamlit_folium import st_folium

# Importando ferramentas compartilhadas
from utils_v43 import configurar_pagina, renderizar_cabecalho_sidebar, carregar_dados_blindado

# ==============================================================================
# 1. CONFIGURAÇÃO
# ==============================================================================
configurar_pagina("Motor de Recomendação v43")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Motor de Recomendação VRT (Protocolo v43)")

if 'geojson_rec' not in st.session_state:
    st.session_state['geojson_rec'] = None

# ==============================================================================
# 2. MOTOR LÓGICO (PROTOCOLOS AGRONÔMICOS)
# ==============================================================================

def calcular_calagem(df, v_alvo, prnt, cao_teor):
    """
    Protocolo: Elevação da Saturação por Bases (V%).
    """
    # Identificar colunas
    col_v = next((c for c in df.columns if c in ['v%', 'v']), None)
    col_ctc = next((c for c in df.columns if c in ['ctc', 't_cec', 't']), None)
    
    if col_v and col_ctc:
        # Fórmula: NC (ton/ha) = (V2 - V1) * CTC / (10 * PRNT)
        df['NC_ton'] = (df[col_ctc] * (v_alvo - df[col_v])) / (10 * prnt) * 100
        
        # Ajuste: Se NC < 0, dose = 0
        df['NC_ton'] = df['NC_ton'].apply(lambda x: x if x > 0 else 0)
        
        # Conversão para kg/ha
        df['Dose_Calcario_kg'] = df['NC_ton'] * 1000
        return True, df
    return False, df

def calcular_fosforo(df, prod_alvo, fator_exp, teor_p_adubo):
    """
    Protocolo v43: Reposição baseada na Exportação.
    P_Rec = (Produtividade * Fator_Exp) / (Teor_Adubo/100)
    """
    # Exportação (kg de P2O5 por ha)
    exportacao_p2o5 = prod_alvo * fator_exp
    
    # Quantidade de Adubo comercial
    dose_adubo = exportacao_p2o5 / (teor_p_adubo / 100)
    
    df['Dose_Fosforo_kg'] = dose_adubo
    return True, df

def calcular_potassio(df, k_alvo_pct, prod_alvo, fator_exp, teor_k_adubo):
    """
    Protocolo v43:
    1. Correção para atingir % da CTC (ex: 3.2%)
    2. Reposição da Exportação (1.2 kg/sc)
    """
    col_k = next((c for c in df.columns if c in ['k', 'potassio']), None) # em cmolc/dm3 ou mmol
    col_ctc = next((c for c in df.columns if c in ['ctc', 't_cec']), None)
    
    if col_k and col_ctc:
        # --- PARTE 1: CORREÇÃO (Saturação de K na CTC) ---
        # K Ideal (cmolc) = CTC * (Alvo% / 100)
        k_ideal = df[col_ctc] * (k_alvo_pct / 100)
        
        # Déficit K (cmolc) = K Ideal - K Atual
        # Assumindo K da planilha em cmolc/dm3. Se estiver em mg/dm3, precisaria converter.
        # Vamos assumir cmolc padrão.
        deficit_k = k_ideal - df[col_k]
        deficit_k = deficit_k.apply(lambda x: x if x > 0 else 0)
        
        # Converter Déficit cmolc para kg/ha de K2O
        # Fator: 1 cmolc K = 942 kg K2O/ha (aproximação agronômica padrão para camada 20cm)
        dose_k2o_correcao = deficit_k * 942 
        
        # --- PARTE 2: EXPORTAÇÃO ---
        dose_k2o_exportacao = prod_alvo * fator_exp
        
        # --- TOTAL ---
        dose_k2o_total = dose_k2o_correcao + dose_k2o_exportacao
        
        # Converter para Produto Comercial (ex: KCl 60%)
        df['Dose_Potassio_kg'] = dose_k2o_total / (teor_k_adubo / 100)
        return True, df
        
    return False, df

def calcular_gesso(df, fator_argila, dose_min, dose_max):
    """
    Protocolo v43: NG = Argila * Fator.
    Travas de segurança: Mínimo e Máximo.
    """
    col_argila = next((c for c in df.columns if c in ['argila', 'clay']), None)
    
    if col_argila:
        # Cálculo da Necessidade
        # Se Argila estiver em % (ex: 40), Fator 50 -> 2000 kg/ha
        # Se Argila estiver em g/kg (ex: 400), Fator 5 -> 2000 kg/ha
        # Assumindo Argila em % padrão (0-100)
        df['NG_kg'] = df[col_argila] * fator_argila * 10 # *10 é ajuste comum se fator for 5
        
        # Se o fator v43 mencionado for "15", pode ser um cálculo específico direto
        # Vamos usar a lógica direta: NG = Argila * Fator
        df['Dose_Gesso_kg'] = df[col_argila] * fator_argila
        
        # Travas (Clamping)
        # Se calculado < min, aplica 0 (não compensa entrar) ou aplica min?
        # Agronomicamente: Se precisa, aplica pelo menos o mínimo operacional.
        # Se calculado > 0 e < min, vira min.
        def aplicar_travas(val):
            if val <= 0: return 0
            if val < dose_min: return dose_min
            if val > dose_max: return dose_max
            return val
            
        df['Dose_Gesso_kg'] = df['Dose_Gesso_kg'].apply(aplicar_travas)
        return True, df
        
    return False, df

# ==============================================================================
# 3. VISUALIZAÇÃO (RECORTE PERFEITO)
# ==============================================================================
def gerar_mapa_prescricao(df, col_dose, geojson_data, cor_base):
    pivot = df.pivot(index='latitude', columns='longitude', values=col_dose)
    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values   
    
    # Paletas Monocromáticas
    if cor_base == 'blue': # Calcário
        colors = ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#084594']
    elif cor_base == 'red': # Potássio
        colors = ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#99000d']
    elif cor_base == 'green': # Fósforo
        colors = ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32']
    else: # Gesso (Cinza/Branco)
        colors = ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#252525']

    cmap = mcolors.ListedColormap(colors)
    
    if np.nanmax(Z) == 0:
        bounds = np.linspace(0, 1, 8)
    else:
        bounds = np.linspace(np.nanmin(Z), np.nanmax(Z), 8)
        
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    plt.close('all')
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_axis_off()
    
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both')
    
    try:
        coords = geojson_data['features'][0]['geometry']['coordinates'][0]
        poly_path = MplPath(coords)
        patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', edgecolor='black', linewidth=2)
        ax.add_patch(patch)
        if hasattr(cf, 'collections'):
            for c in cf.collections: c.set_clip_path(patch)
        else:
            cf.set_clip_path(patch)
    except: pass

    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    
    img_data = BytesIO()
    plt.savefig(img_data, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=100)
    plt.close(fig)
    img_data.seek(0)
    
    return img_data, [[Y.min(), X.min()], [Y.max(), X.max()]], bounds

# ==============================================================================
# 4. SIDEBAR V43 (INTERFACE BLINDADA)
# ==============================================================================
st.sidebar.header("1. Arquivos")
file_ponte = st.sidebar.file_uploader("📂 Arquivo PONTE (CSV)", type=["csv"])
file_geo = st.sidebar.file_uploader("🌍 Contorno (.geojson)", type=["geojson", "json"])

st.sidebar.divider()
st.sidebar.header("2. Parâmetros v43")

# --- BLOCO 1: CALAGEM ---
with st.sidebar.expander("⚪ 1. Calagem", expanded=True):
    v_alvo = st.number_input("V% Alvo:", value=60.0, step=1.0, min_value=0.0, max_value=100.0)
    prnt = st.number_input("PRNT (%):", value=85.0, step=1.0)
    preco_calc = st.number_input("Preço Calcário (R$/ton):", value=190.0, step=10.0)

# --- BLOCO 2: FÓSFORO ---
with st.sidebar.expander("🟢 2. Fósforo", expanded=False):
    prod_alvo_p = st.number_input("Produtividade Alvo (sc/ha):", value=70.0, step=1.0, key='prod_p')
    fator_exp_p = st.number_input("Fator Exportação (kg/sc):", value=0.8, step=0.1)
    teor_p_adubo = st.number_input("Teor P do Adubo (%):", value=52.0, step=1.0, help="Ex: MAP = 52%")
    preco_map = st.number_input("Preço Fósforo (R$/ton):", value=2000.0, step=50.0)

# --- BLOCO 3: POTÁSSIO ---
with st.sidebar.expander("🔴 3. Potássio", expanded=False):
    k_alvo_pct = st.number_input("Alvo K na CTC (%):", value=3.2, step=0.1)
    fator_exp_k = st.number_input("Fator Exportação K (kg/sc):", value=1.2, step=0.1)
    teor_k_adubo = st.number_input("Teor K do Adubo (%):", value=60.0, step=1.0, help="Ex: KCl = 60%")
    preco_kcl = st.number_input("Preço Potássio (R$/ton):", value=2800.0, step=50.0)

# --- BLOCO 4: GESSO ---
with st.sidebar.expander("🌫️ 4. Gesso", expanded=False):
    fator_gesso = st.number_input("Fator x Argila:", value=50.0, step=5.0)
    gesso_min = st.number_input("Dose Mínima (kg/ha):", value=400.0, step=50.0)
    gesso_max = st.number_input("Dose Máxima (kg/ha):", value=2000.0, step=100.0)
    preco_gesso = st.number_input("Preço Gesso (R$/ton):", value=400.0, step=10.0)

# ==============================================================================
# 5. PROCESSAMENTO
# ==============================================================================
if file_ponte and file_geo:
    df = pd.read_csv(file_ponte)
    df.columns = [c.strip().lower() for c in df.columns]
    
    try:
        geojson = json.load(file_geo)
        st.session_state['geojson_rec'] = geojson
    except:
        st.error("GeoJSON inválido.")
        st.stop()
        
    # --- GATILHO DE CÁLCULO (Evita processamento automático pesado) ---
    if st.button("🚀 PROCESSAR RECOMENDAÇÕES (VRT)", type="primary"):
        
        # 1. Calagem
        ok_calc, df = calcular_calagem(df, v_alvo, prnt, 40) # 40% CaO padrão estimativo
        
        # 2. Fósforo
        ok_p, df = calcular_fosforo(df, prod_alvo_p, fator_exp_p, teor_p_adubo)
        
        # 3. Potássio
        ok_k, df = calcular_potassio(df, k_alvo_pct, prod_alvo_p, fator_exp_k, teor_k_adubo)
        
        # 4. Gesso
        ok_g, df = calcular_gesso(df, fator_gesso, gesso_min, gesso_max)
        
        st.session_state['df_vrt'] = df
        st.session_state['calc_done'] = True
        st.toast("Cálculos VRT Concluídos!", icon="🚜")

    # --- EXIBIÇÃO ---
    if st.session_state.get('calc_done'):
        df_vrt = st.session_state['df_vrt']
        
        tabs = st.tabs(["⚪ Calagem", "🟢 Fósforo", "🔴 Potássio", "🌫️ Gesso"])
        
        # Função Auxiliar de Renderização
        def render_tab(tab, col_dados, nome, cor_mapa, preco):
            with tab:
                c1, c2 = st.columns([3, 1])
                with c1:
                    try:
                        img, bounds, intervals = gerar_mapa_prescricao(df_vrt, col_dados, geojson, cor_mapa)
                        centro = [df_vrt['latitude'].mean(), df_vrt['longitude'].mean()]
                        m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                        
                        img_b64 = base64.b64encode(img.getvalue()).decode()
                        folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{img_b64}", bounds=bounds, opacity=0.8).add_to(m)
                        folium.GeoJson(geojson, style_function=lambda x: {'color':'black', 'weight':3, 'fillOpacity':0}).add_to(m)
                        
                        # Legenda Dinâmica
                        legend_html = f"""
                        <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; background: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
                        <b>{nome} (kg/ha)</b><br>
                        Max: {intervals[-1]:.0f}<br>
                        Min: {intervals[0]:.0f}
                        </div>
                        """
                        m.get_root().html.add_child(folium.Element(legend_html))
                        st_folium(m, height=450, use_container_width=True)
                    except Exception as e:
                        st.error(f"Erro mapa: {e}")
                
                with c2:
                    media = df_vrt[col_dados].mean()
                    total_ton = (media * len(df_vrt) * 0.04) / 1000 # Estimativa Ton Total
                    custo_ha = (media / 1000) * preco
                    
                    st.metric("Dose Média", f"{media:.0f} kg/ha")
                    st.metric("Custo Médio", f"R$ {custo_ha:.2f}/ha")
                    st.metric("Total Estimado", f"{total_ton:.1f} Ton")

        # Renderizar Abas
        render_tab(tabs[0], 'Dose_Calcario_kg', 'Calcário', 'blue', preco_calc)
        render_tab(tabs[1], 'Dose_Fosforo_kg', 'Fósforo', 'green', preco_map)
        render_tab(tabs[2], 'Dose_Potassio_kg', 'Potássio', 'red', preco_kcl)
        render_tab(tabs[3], 'Dose_Gesso_kg', 'Gesso', 'gray', preco_gesso)

        # --- EXPORTAÇÃO FINAL ---
        st.divider()
        st.subheader("💾 Exportar Arquivos")
        
        csv_final = df_vrt.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Baixar CSV Consolidado (Todas as Prescrições)", csv_final, "prescricao_triade_vrt.csv", "text/csv", type="primary")

else:
    st.info("Aguardando upload dos arquivos do App 1.")
