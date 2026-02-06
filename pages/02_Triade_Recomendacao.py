import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
import folium
from streamlit_folium import st_folium

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Tríade VRT", layout="wide")
st.title("🚜 Tríade VRT - Motor de Recomendação")

# ==============================================================================
# 1. FUNÇÕES DE LIMPEZA
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

# ==============================================================================
# 2. MOTOR DE CÁLCULO (COM TABELA FIXA)
# ==============================================================================
def calcular_recomendacao(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt_val, p_exp, p_teor_val, k_alvo_val, k_exp, k_teor_val, g_fat, g_min, g_max, nc_vals):
    dfr = df.copy()
    
    # CALAGEM
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

    # FÓSFORO (LÓGICA DE TABELA FIXA)
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

    # POTÁSSIO
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

    # GESSO
    if 'Argila' in dfr.columns:
        dfr['Dose_Gesso_Kg'] = (dfr['Argila'] * g_fat).clip(lower=g_min, upper=g_max)
    else:
        dfr['Dose_Gesso_Kg'] = 0.0

    return dfr

# ==============================================================================
# 3. MOTOR VISUAL APP 1
# ==============================================================================
def gerar_mapa_app1(df, atributo, titulo, geojson_data):
    try:
        pivot = df.pivot_table(index='latitude', columns='longitude', values=atributo)
    except:
        return None

    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values   
    
    # PALETA 6 CORES: Vermelho -> Laranja -> Amarelo -> Verde Claro -> Verde Escuro -> Azul
    cores_personalizadas = ['#D7191C', '#FDAE61', '#FFFFBF', '#A6D96A', '#1A9641', '#2C7BB6']
    cmap = mcolors.ListedColormap(cores_personalizadas)
    
    z_min, z_max = np.nanmin(Z), np.nanmax(Z)
    if z_min == z_max: z_max += 0.001
    bounds = np.linspace(z_min, z_max, 7)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    plt.close('all') 
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_axis_off()
    
    # Desenho Sólido
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both', alpha=1.0)
    
    # Recorte Exato
    if geojson_data:
        try:
            coords = geojson_data['features'][0]['geometry']['coordinates'][0]
            poly_path = MplPath(coords)
            patch = PathPatch(poly_path, transform=ax.transData, facecolor='none', linewidth=0)
            ax.add_patch(patch)
            for col in cf.collections: col.set_clip_path(patch)
        except: pass

    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    
    img_data = BytesIO()
    plt.savefig(img_data, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=150)
    plt.close(fig)
    img_data.seek(0)
    
    centro = [Y.mean(), X.mean()]
    m = folium.Map(location=
