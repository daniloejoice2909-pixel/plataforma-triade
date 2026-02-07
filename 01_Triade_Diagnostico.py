import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64

# --- 1. CONFIGURAÇÃO DE BACKEND (A VACINA ANTI-TRAVAMENTO) ---
import matplotlib
matplotlib.use('Agg') # Força modo não-interativo (Essencial para Web)
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

from pykrige.ok import OrdinaryKriging
import folium
from streamlit_folium import st_folium

# Importando utils (Mantendo a compatibilidade)
from utils_v43 import (
    configurar_pagina, 
    renderizar_cabecalho_sidebar, 
    carregar_dados_blindado, 
    validar_colunas
)

# ==============================================================================
# 2. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
configurar_pagina("Diagnóstico de Solo | Tríade")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Diagnóstico de Fertilidade")

# Inicialização de Estado
if 'dados_processados' not in st.session_state:
    st.session_state['dados_processados'] = None
if 'geojson_data' not in st.session_state:
    st.session_state['geojson_data'] = None

# ==============================================================================
# 3. SIDEBAR: CAMADA DE CONFIGURAÇÃO E INPUTS BLINDADOS
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.header("1. Arquivos de Entrada")
file_csv = st.sidebar.file_uploader("📂 Tabela (.csv)", type=["csv"])
file_geojson = st.sidebar.file_uploader("🌍 Contorno (.geojson)", type=["geojson", "json"])

st.sidebar.markdown("---")
st.sidebar.header("2. Parâmetros Agronômicos")

# --- BLOCO 1: CALAGEM ---
with st.sidebar.expander("🪨 Configuração de Calagem", expanded=False):
    c_cal1, c_cal2 = st.columns(2)
    with c_cal1:
        prnt = st.number_input("PRNT (%)", value=80.0, step=1.0, min_value=0.0, max_value=1000.0)
        teor_cao = st.number_input("Teor CaO (%)", value=38.0, step=0.1, min_value=0.0, max_value=100.0)
        alvo_ca = st.number_input("Alvo Ca (%)", value=60.0, step=1.0, min_value=0.0, max_value=100.0)
    with c_cal2:
        reserva = st.number_input("Reserva", value=0.0, step=0.1, min_value=0.0, max_value=100.0)
        teor_mgo = st.number_input("Teor MgO (%)", value=12.0, step=0.1, min_value=0.0, max_value=100.0)
        alvo_mg = st.number_input("Alvo Mg (%)", value=18.0, step=1.0, min_value=0.0, max_value=100.0)
    
    preco_calcario = st.number_input("Preço Calcário (R$/Ton)", value=190.0, step=5.0, min_value=0.0, max_value=10000.0)

# --- BLOCO 2: FÓSFORO ---
with st.sidebar.expander("🔥 Configuração de Fósforo", expanded=False):
    st.markdown("**Faixas de P-rem:**")
    cp1, cp2 = st.columns(2)
    with cp1:
        prem_f1 = st.number_input("Faixa 1 (0-X)", value=4.0, step=1.0)
        prem_f2 = st.number_input("Faixa 2 (X-Y)", value=10.0, step=1.0)
        prem_f3 = st.number_input("Faixa 3 (Y-Z)", value=19.0, step=1.0)
    with cp2:
        prem_f4 = st.number_input("Faixa 4 (Z-W)", value=30.0, step=1.0)
        prem_f5 = st.number_input("Faixa 5 (W-K)", value=45.0, step=1.0)
        prem_f6 = st.number_input("Faixa 6 (K-60)", value=60.0, step=1.0)
    
    st.markdown("---")
    teor_p2o5 = st.number_input("Teor P2O5 Adubo (%)", value=50.0, step=1.0, min_value=0.0, max_value=100.0)
    export_p = st.number_input("Exportação P (kg/sc)", value=0.8, step=0.1, min_value=0.0, max_value=100.0)
    preco_p = st.number_input("Preço Fósforo (R$/Ton)", value=2000.0, step=10.0, min_value=0.0, max_value=20000.0)

# --- BLOCO 3: POTÁSSIO ---
with st.sidebar.expander("🍌 Configuração de Potássio", expanded=False):
    alvo_k = st.number_input("Alvo K (%)", value=3.2, step=0.1, min_value=0.0, max_value=100.0)
    teor_k2o = st.number_input("Teor K2O Adubo (%)", value=60.0, step=1.0, min_value=0.0, max_value=100.0)
    export_k = st.number_input("Exportação K (kg/sc)", value=1.2, step=0.1, min_value=0.0, max_value=100.0)
    preco_k = st.number_input("Preço Potássio (R$/Ton)", value=2800.0, step=10.0, min_value=0.0, max_value=20000.0)

# --- BLOCO 4: GESSO ---
with st.sidebar.expander("⚪ Configuração de Gesso", expanded=False):
    fator_gesso = st.number_input("Fator Gesso", value=50.0, step=1.0, min_value=0.0, max_value=500.0)
    dose_min_gesso = st.number_input("Dose Mínima (kg/ha)", value=400.0, step=50.0, min_value=0.0, max_value=10000.0)
    dose_max_gesso = st.number_input("Dose Máxima (kg/ha)", value=2000.0, step=50.0, min_value=0.0, max_value=10000.0)
    preco_gesso = st.number_input("Preço Gesso (R$/Ton)", value=400.0, step=10.0, min_value=0.0, max_value=5000.0)

# --- BLOCO 5: PRODUTIVIDADE ---
with st.sidebar.expander("🌽 Meta de Produtividade", expanded=True):
    prod_alvo = st.number_input("Produtividade Alvo (sc/ha)", value=80.0, step=1.0, min_value=0.0, max_value=300.0)

# ==============================================================================
# 4. KRIGAGEM OTIMIZADA (V58 - LEVE)
# ==============================================================================
@st.cache_data(show_spinner="⚙️ Calculando Geoestatística...")
def processar_matrizes_interpolacao(df_input, geojson_data, resolucao_grid=150):
    df = df_input.copy() 
    cols_proibidas = ['id', 'ponto', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y', 'data', 'hora', 'campo', 'fazenda', 'profundidade', 'zona', 'talhao']
    cols_validas = []
    
    # Limpeza Rápida
    for col in df.columns:
        if col.lower() in cols_proibidas: continue
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if df[col].notna().sum() > 5: cols_validas.append(col)
        except: pass 

    # Grid Inteligente
    x_min, x_max = df['longitude'].min(), df['longitude'].max()
    y_min, y_max = df['latitude'].min(), df['latitude'].max()
    buffer = 0.003 
    
    grid_x = np.linspace(x_min - buffer, x_max + buffer, resolucao_grid)
    grid_y = np.linspace(y_min - buffer, y_max + buffer, resolucao_grid)
    
    xx, yy = np.meshgrid(grid_x, grid_y)
    df_result = pd.DataFrame({'latitude': yy.flatten(), 'longitude': xx.flatten()})

    # Interpolação
    for col in cols_validas:
        try:
            dados = df[['longitude', 'latitude', col]].dropna()
            if len(dados) < 5: continue

            OK = OrdinaryKriging(
                dados['longitude'], dados['latitude'], dados[col], 
                variogram_model='linear', verbose=False, enable_plotting=False
            )
            z, _ = OK.execute('grid', grid_x, grid_y)
            df_result[col] = z.flatten()
        except: pass

    return df_result.dropna(subset=cols_validas, how='all')

# ==============================================================================
# 5. GERAÇÃO DE IMAGEM (MATPLOTLIB SEGURO - COM JET)
# ==============================================================================
def gerar_imagem_overlay(df_plot, atributo, geojson_data):
    # 1. Prepara Dados
    pivot = df_plot.pivot(index='latitude', columns='longitude', values=atributo)
    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values    
    
    # 2. Configura Cores (JET Padrão Agronômico)
    # Criando 8 níveis discretos baseados na escala Jet
    cmap = plt.get_cmap('jet', 8) 
    bounds = np.linspace(np.nanmin(Z), np.nanmax(Z), 9) # 9 limites para 8 intervalos
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # 3. Gera Figura (MODO AGG)
    plt.close('all') 
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_axis_off()
    
    # 4. Desenha (Contourf Sólido)
    # alpha=1.0 para opacidade total, cores vivas
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both', alpha=1.0)
    
    # 5. Aplica Recorte (Clipping)
    try:
        coords = geojson_data['features'][0]['geometry']['coordinates'][0]
        poly_path = MplPath(coords)
        patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', edgecolor='black', linewidth=2)
        ax.add_patch(patch)
        
        if hasattr(cf, 'collections'):
            for col in cf.collections: col.set_clip_path(patch)
        else:
            cf.set_clip_path(patch)
    except Exception as e:
        # Silencioso ou Log
        pass

    # 6. Finaliza
    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    
    img_data = BytesIO()
    plt.savefig(img_data, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=100)
    plt.close(fig)
    img_data.seek(0)
    
    return img_data, [[Y.min(), X.min()], [Y.max(), X.max()]], bounds

# ==============================================================================
# 6. LÓGICA DE PROCESSAMENTO
# ==============================================================================
if file_csv and file_geojson:
    df_raw = carregar_dados_blindado(file_csv)
    df_raw.columns = [c.strip().lower() for c in df_raw.columns]
    
    try:
        file_geojson.seek(0)
        geojson_data = json.load(file_geojson)
        st.session_state['geojson_data'] = geojson_data
    except Exception as e:
        st.error(f"Erro ao ler GeoJSON: {e}")
        st.stop()

    # Mapeamento de Colunas
    c1, c2 = st.columns(2)
    cols = list(df_raw.columns)
    idx_lat = cols.index('latitude') if 'latitude' in cols else 0
    idx_lon = cols.index('longitude') if 'longitude' in cols else 1
    
    with c1: lat_col = st.selectbox("Coluna Latitude:", cols, index=idx_lat)
    with c2: lon_col = st.selectbox("Coluna Longitude:", cols, index=idx_lon)
    
    df_raw = df_raw.rename(columns={lat_col: 'latitude', lon_col: 'longitude'})

    # Botão de Gatilho (Processamento Pesado)
    if st.button("🚀 Processar Mapas de Solo", type="primary"):
        with st.status("Processando dados...", expanded=True) as status:
            st.write("Verificando integridade...")
            
            st.write("Calculando Geoestatística (Krigagem)...")
            # Validação Try/Except no bloco pesado
            try:
                df_krig = processar_matrizes_interpolacao(df_raw, geojson_data)
                st.session_state['dados_processados'] = df_krig
                status.update(label="Processamento Concluído!", state="complete", expanded=False)
            except Exception as e:
                st.error(f"Erro na Krigagem: {e}")
                status.update(label="Erro no Processamento", state="error")
                st.stop()
        st.rerun()

# ==============================================================================
# 7. VISUALIZAÇÃO E EXPORTAÇÃO
# ==============================================================================
if st.session_state['dados_processados'] is not None:
    df_final = st.session_state['dados_processados'].copy()
    
    st.divider()
    st.subheader("💾 Exportação de Dados")
    
    col_down1, col_down2 = st.columns(2)
    
    # Exportação CSV Otimizado
    csv_data = df_final.to_csv(index=False).encode('utf-8')
    col_down1.download_button(
        label="Baixar CSV Otimizado (.csv)",
        data=csv_data,
        file_name="dados_processados_solo.csv",
        mime="text/csv"
    )

    # Exportação Parquet (Preferencial se bibliotecas disponíveis)
    try:
        parquet_buffer = BytesIO()
        df_final.to_parquet(parquet_buffer, index=False)
        parquet_buffer.seek(0)
        col_down2.download_button(
            label="Baixar Parquet (.parquet)",
            data=parquet_buffer,
            file_name="dados_processados_solo.parquet",
            mime="application/octet-stream",
            type="primary"
        )
    except Exception as e:
        col_down2.warning("Biblioteca pyarrow/fastparquet não encontrada para Parquet.")
    
    st.divider()
    
    # Seletor de Mapa
    cols_ver = [c for c in df_final.columns if c not in ['latitude', 'longitude']]
    
    if cols_ver:
        st.subheader("🗺️ Visualização de Diagnóstico")
        atributo = st.selectbox("Selecione o atributo para visualizar:", cols_ver)
        
        # Botão para Gerar Mapas (Evita renderização automática pesada)
        if st.button(f"Gerar Mapa de {atributo}"):
            df_plot = df_final.dropna(subset=[atributo])
            
            if not df_plot.empty:
                try:
                    # Gera Imagem com JET
                    img_buffer, bounds, intervals = gerar_imagem_overlay(df_plot, atributo, st.session_state['geojson_data'])
                    
                    # Mapa Folium (Base Google Satellite)
                    centro = [df_plot['latitude'].mean(), df_plot['longitude'].mean()]
                    m = folium.Map(
                        location=centro, 
                        zoom_start=14, 
                        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                        attr='Google Satellite'
                    )
                    
                    # Overlay da Imagem (Opacidade Alta na Imagem)
                    img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                    folium.raster_layers.ImageOverlay(
                        image=f"data:image/png;base64,{img_b64}",
                        bounds=bounds, 
                        opacity=0.9, # Leve transparência apenas para ver relevo se necessário, mas próximo de 1.0
                        interactive=True
                    ).add_to(m)
                    
                    # Contorno Preto (Separação Física)
                    folium.GeoJson(
                        st.session_state['geojson_data'],
                        style_function=lambda x: {'color': 'black', 'weight': 3, 'fillOpacity': 0}
                    ).add_to(m)
                    
                    # Legenda (HTML/CSS Injetado)
                    min_val, max_val = intervals[0], intervals[-1]
                    legend_html = f"""
                    <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; 
                                background: white; padding: 10px; border: 2px solid black; border-radius: 5px; font-family: sans-serif;">
                    <b>{atributo} (Escala Jet)</b><br>
                    Mín: {min_val:.2f} <br>
                    Máx: {max_val:.2f} <br>
                    <div style="background: linear-gradient(to right, #000080, #0000ff, #00ffff, #ffff00, #ff0000, #800000); height: 10px; width: 100px;"></div>
                    </div>
                    """
                    m.get_root().html.add_child(folium.Element(legend_html))
                    
                    # Box Informativo Estatístico
                    st.info(f"📊 Estatísticas ({atributo}): Mín: {df_plot[atributo].min():.2f} | Média: {df_plot[atributo].mean():.2f} | Máx: {df_plot[atributo].max():.2f}")
                    
                    st_folium(m, height=500, use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Erro visual: {e}")
            else:
                st.warning("Dados insuficientes para este atributo.")
