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

st.set_page_config(page_title="Triade VRT", layout="wide")
st.title("🚜 Triade VRT - Motor de Recomendacao")

# --- FUNÇÃO AUXILIAR PARA CORRIGIR GEOJSON ---
def extrair_coordenadas_seguras(geojson_data):
    """Tenta extrair as coordenadas do polígono de qualquer formato GeoJSON."""
    try:
        # Caso 1: FeatureCollection (Padrão QGIS/GIS)
        if geojson_data.get('type') == 'FeatureCollection':
            features = geojson_data.get('features', [])
            if not features: return None
            geometry = features[0].get('geometry', {})
        
        # Caso 2: Feature isolada
        elif geojson_data.get('type') == 'Feature':
            geometry = geojson_data.get('geometry', {})
            
        # Caso 3: Geometria direta
        elif geojson_data.get('type') in ['Polygon', 'MultiPolygon']:
            geometry = geojson_data
        else:
            return None

        # Extrai coordenadas do anel externo
        coords = geometry.get('coordinates', [])
        if not coords: return None
        
        # Se for MultiPolygon, pega o primeiro polígono
        if geometry.get('type') == 'MultiPolygon':
            return coords[0][0] 
        # Se for Polygon simples
        else:
            return coords[0]
            
    except Exception as e:
        print(f"Erro ao ler GeoJSON: {e}")
        return None

def clean_data(df):
    df = df.copy()
    df.columns = [c.lower().strip() for c in df.columns]
    mapa = {
        'lat': ['latitude','lat','y'], 'lon': ['longitude','long','lon','x'],
        'Ca': ['ca','calcio'], 'Mg': ['mg','magnesio'], 'K': ['k','potassio'],
        'P': ['p','fosforo','p_mehl'], 'Prem': ['prem','p_rem','p-rem'],
        'Argila': ['argila','clay'], 'CTC': ['ctc','t']
    }
    renomear = {}
    for col in df.columns:
        for k, v in mapa.items():
            if any(x in col for x in v):
                renomear[col] = k
                break
    if renomear: df = df.rename(columns=renomear)
    cols = ['Ca','Mg','K','P','Prem','Argila','CTC','lat','lon']
    for c in cols:
        if c in df.columns:
            if df[c].dtype == 'object': df[c] = df[c].str.replace(',','.').astype(float)
            else: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df

@st.cache_data(show_spinner=False)
def calc_vrt(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt, p_exp, p_teor, k_alvo, k_exp, k_teor, g_fat, g_min, g_max, nc_vals):
    d = df.copy()
    # Calagem
    if all(x in d.columns for x in ['Ca','Mg','CTC']):
        nc_ca, nc_mg = d['CTC']*(ca_alvo/100), d['CTC']*(mg_alvo/100)
        fat_ca = max((cao*10/560)*(prnt/100),0.001)
        fat_mg = max((mgo*10/403)*(prnt/100),0.001)
        d['Dose_Calcario'] = np.maximum((nc_ca - d['Ca'])/fat_ca, (nc_mg - d['Mg'])/fat_mg).clip(0).round(2)
    else: d['Dose_Calcario'] = 0.0
    
    # Fosforo
    if 'Prem' in d.columns and 'P' in d.columns:
        c = [(d['Prem']<=4), (d['Prem']<=10), (d['Prem']<=19), (d['Prem']<=30), (d['Prem']>30)]
        v = [nc_vals['n1'], nc_vals['n2'], nc_vals['n3'], nc_vals['n4'], nc_vals['n5']]
        nc = np.select(c, v, default=nc_vals['n5'])
        fct = (56.5 * d['Prem']**-0.52).clip(4,40)
        d['NC_Tabular'] = nc
        dose = np.where(nc>d['P'],(nc-d['P'])*fct,0)
        d['Dose_P2O5_Kg'] = ((dose + (prod*p_exp)) / (p_teor/100)).round(0)
    else: d['Dose_P2O5_Kg'] = 0.0

    # Potassio
    if 'K' in d.columns and 'CTC' in d.columns:
        kval = d['K']/391 if d['K'].mean() > 10 else d['K']
        dk = ((d['CTC']*(k_alvo/100) - kval).clip(0)*940) + (prod*k_exp)
        d['Dose_K2O_Kg'] = (dk / (k_teor/100)).round(0)
    else: d['Dose_K2O_Kg'] = 0.0

    # Gesso
    if 'Argila' in d.columns:
        d['Dose_Gesso_Kg'] = (d['Argila']*g_fat).clip(g_min, g_max)
    else: d['Dose_Gesso_Kg'] = 0.0
    return d

@st.cache_data(show_spinner=False)
def gerar_imagem_base64(df, col, geojson_str):
    # Recupera o GeoJSON
    geojson_data = json.loads(geojson_str) if geojson_str else None
    
    try: pivot = df.pivot_table(index='lat', columns='lon', values=col)
    except: return None, None, None
    
    Z, X, Y = pivot.values, pivot.columns.values, pivot.index.values
    
    colors = ['#D7191C', '#FDAE61', '#FFFFBF', '#A6D96A', '#1A9641', '#2C7BB6']
    cmap = mcolors.ListedColormap(colors)
    zmin, zmax = np.nanmin(Z), np.nanmax(Z)
    if zmin == zmax: zmax += 0.01
    bounds = np.linspace(zmin, zmax, 7)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    plt.close('all')
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_axis_off()
    cf = ax.contourf(X, Y, Z, levels=bounds, cmap=cmap, norm=norm, extend='both')
    
    # --- RECORTE SEGURO ---
    if geojson_data:
        coords = extrair_coordenadas_seguras(geojson_data)
        if coords:
            try:
                patch = PathPatch(MplPath(coords), transform=ax.transData, facecolor='none', linewidth=0)
                ax.add_patch(patch)
                for c in cf.collections: c.set_clip_path(patch)
            except Exception as e:
                pass # Se falhar o recorte, desenha quadrado normal
    
    ax.set_xlim(X.min(), X.max())
    ax.set_ylim(Y.min(), Y.max())
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=100)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.getvalue()).decode()
    
    return b64, bounds, [Y.min(), X.min(), Y.max(), X.max()]

def renderizar_mapa(b64, bounds_vals, limits, titulo, geojson_data):
    if not b64: return None
    colors = ['#D7191C', '#FDAE61', '#FFFFBF', '#A6D96A', '#1A9641', '#2C7BB6']
    ymin, xmin, ymax, xmax = limits
    
    m = folium.Map([(ymin+ymax)/2, (xmin+xmax)/2], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{b64}",
        bounds=[[ymin, xmin], [ymax, xmax]],
        opacity=0.85
    ).add_to(m)
    
    if geojson_data:
        folium.GeoJson(geojson_data, style_function=lambda x:{'color':'black','weight':2,'fillOpacity':0}).add_to(m)
    
    leg = f"""<div style="position:fixed; bottom:30px; right:30px; z-index:9999; background:white; padding:10px; border:2px solid black;">
    <b>{titulo}</b><br>
    <span style='color:{colors[5]}'>■</span> > {bounds_vals[5]:.0f}<br>
    <span style='color:{colors[4]}'>■</span> {bounds_vals[4]:.0f} - {bounds_vals[5]:.0f}<br>
    <span style='color:{colors[3]}'>■</span> {bounds_vals[3]:.0f} - {bounds_vals[4]:.0f}<br>
    <span style='color:{colors[2]}'>■</span> {bounds_vals[2]:.0f} - {bounds_vals[3]:.0f}<br>
    <span style='color:{colors[1]}'>■</span> {bounds_vals[1]:.0f} - {bounds_vals[2]:.0f}<br>
    <span style='color:{colors[0]}'>■</span> < {bounds_vals[1]:.0f}
    </div>"""
    m.get_root().html.add_child(folium.Element(leg))
    return m

with st.sidebar:
    st.header("📂 Arquivos")
    f_csv = st.file_uploader("1. Malha (.csv)", type=["csv"])
    f_geo = st.file_uploader("2. Contorno (.geojson)", type=["geojson","json"])
    df_in, geo_data = None, None
    
    if f_csv:
        try: df_in = clean_data(pd.read_csv(f_csv))
        except: st.error("Erro no CSV")
    
    if f_geo:
        try: geo_data = json.load(f_geo)
        except: st.error("Erro no GeoJSON")

    if df_in is
