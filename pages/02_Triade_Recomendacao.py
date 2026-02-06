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
        condicoes = [
            (dfr['P_Rem'] <= 4.0),
            (dfr['P_Rem'] > 4.0) & (dfr['P_Rem'] <= 10.0),
            (dfr['P_Rem'] > 10.0) & (dfr['P_Rem'] <= 19.0),
            (dfr['P_Rem'] > 19.0) & (dfr['P_Rem'] <= 30.0),
            (dfr['P_Rem'] > 30.0)
        ]
        valores_nc = [nc_vals['nc_1'], nc_vals['nc_2'], nc_vals['nc_3'], nc_vals['nc_4'], nc_vals['nc_5']]
        nc = np.select(condicoes, valores_nc, default=nc_vals['nc_5'])
        fct = (56.5 * dfr['P_Rem']**-0.52).clip(4, 40)
        
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
# 4. MOTOR VISUAL DO APP 1 (CORRIGIDO: RECORTE EXATO + 6 CORES)
# ==============================================================================
def gerar_mapa_app1(df, atributo, titulo, geojson_data):
    try:
        pivot = df.pivot_table(index='latitude', columns='longitude', values=atributo)
    except:
        return None

    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values
    
    # --- DEFINIÇÃO DA PALETA DE 6 CORES (VERMELHO -> AZUL) ---
    # Cores Hexadecimais para:
    # 1. Muito Baixo (Vermelho)
    # 2. Baixo (Laranja)
    # 3. Médio (Amarelo)
    # 4. Bom (Verde Claro)
    # 5. Muito Bom (Verde Escuro)
    # 6. Alto (Azul)
    cores_personalizadas = ['#D7191C', '#FDAE61', '#FFFFBF', '#A6D96A', '#1A9641', '#2C7BB6']
    cmap = mcolors.ListedColormap(cores_personalizadas)
    
    # Define os intervalos baseados nos dados (6 faixas)
    z_min, z_max = np.nanmin(Z), np.nanmax(Z)
    if z_min == z_max: z_max += 0.001
    
    # BoundaryNorm força as cores a serem discretas (faixas) e não gradiente
    bounds = np.linspace(z_min, z_max, 7) # 7 limites para criar 6 faixas
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # Criação da Figura
    plt.close('all') 
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_axis_off()
    
    # Desenho do Contourf (Preenchimento)
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both', alpha=1.0)
    
    # --- RECORTE EXATO PELO GEOJSON ---
    if geojson_data:
        try:
            # Extrai as coordenadas do polígono externo
            # O geojson geralmente é FeatureCollection -> Feature -> Geometry -> Coordinates
            # Coordinates[0] é o anel externo
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
            
            # Cria o "Caminho de Recorte" (Cookie Cutter)
            poly_path = MplPath(coords)
            
            # Cria o Patch invisível que servirá de molde
            patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', linewidth=0)
            ax.add_patch(patch)
            
            # Aplica o recorte a todas as camadas do mapa
            for col in cf.collections: 
                col.set_clip_path(patch)
        except Exception as e:
            print(f"Erro no recorte: {e}")

    # Ajuste dos limites para não sobrar espaço branco
    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    
    # Salva a imagem transparente em memória
    img_data = BytesIO()
    plt.savefig(img_data, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=150)
    plt.close(fig)
    img_data.seek(0)
    
    # Montagem no Folium
    centro = [Y.mean(), X.mean()]
    m = folium.Map(location=centro, zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    
    img_b64 = base64.b64encode(img_data.getvalue()).decode()
    
    # Sobrepõe a imagem gerada
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{img_b64}",
        bounds=[[Y.min(), X.min()], [Y.max(), X.max()]], 
        opacity=0.85
    ).add_to(m)
    
    # Desenha o Contorno Preto (Para garantir que a borda fique perfeita)
    if geojson_data:
        folium.GeoJson(
            geojson_data, 
            style_function=lambda x: {'color': 'black', 'weight': 3, 'fillOpacity': 0}
        ).add_to(m)
    
    # Legenda HTML Personalizada (Com as 6 cores)
    legend_html = f"""
    <div style="position: fixed; bottom: 30px; right: 30px; z-index:9999; background: white; padding: 10px; border: 2px solid black; border-radius: 5px; font-family: sans-serif;">
    <b>{titulo}</b><br>
    <span style='color:{cores_personalizadas[5]}'>■</span> Muito Alto ({bounds[5]:.1f} - {bounds[6]:.1f})<br>
    <span style='color:{cores_personalizadas[4]}'>■</span> Alto ({bounds[4]:.1f} - {bounds[5]:.1f})<br>
    <span style='color:{cores_personalizadas[3]}'>■</span> Bom ({bounds[3]:.1f} - {bounds[4]:.1f})<br>
    <span style='color:{cores_personalizadas[2]}'>■</span> Médio ({bounds[2]:.1f} - {bounds[3]:.1f})<br>
    <span style='color:{cores_personalizadas[1]}'>■</span> Baixo ({bounds[1]:.1f} - {bounds[2]:.1f})<br>
    <span style='color:{cores_personalizadas[0]}'>■</span> M. Baixo ({bounds[0]:.1f} - {bounds[1]:.1f})
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

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
        
        st.markdown("##### 🎯 Níveis Críticos (mg/dm³) por Classe")
        c1, c2 = st.columns(2)
        with c1:
            nc_1 = st.number_input("0 a 4 (Muito Arg.)", value=5.5
