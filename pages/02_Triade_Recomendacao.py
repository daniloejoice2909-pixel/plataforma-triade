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

# --- FUNÇÃO DE LEITURA BLINDADA ---
def carregar_csv_seguro(file):
    try:
        # Tentativa 1: Padrão (Vírgula + UTF-8)
        file.seek(0)
        return pd.read_csv(file)
    except:
        try:
            # Tentativa 2: Excel Brasileiro (Ponto-e-vírgula + Latin-1)
            file.seek(0)
            return pd.read_csv(file, sep=';', encoding='latin-1')
        except:
            try:
                # Tentativa 3: Motor Python (Mais lento, mas detecta tudo)
                file.seek(0)
                return pd.read_csv(file, sep=None, engine='python')
            except Exception as e:
                st.error(f"Não foi possível ler o CSV. Erro: {e}")
                return None

def clean_data(df):
    if df is None: return None
    df = df.copy()
    
    # Remove espaços e joga tudo pra minúsculo
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # Mapa de Sinônimos
    mapa = {
        'lat': ['latitude','lat','y','lat_wgs84'], 
        'lon': ['longitude','long','lon','x','lon_wgs84'],
        'Ca': ['ca','calcio','cálcio','ca_cmolc'], 
        'Mg': ['mg','magnesio','magnésio','mg_cmolc'], 
        'K': ['k','potassio','potássio','k_mg'],
        'P': ['p','fosforo','fósforo','p_mehl','pmehlich'], 
        'Prem': ['prem','p_rem','p-rem','fosforo_remanescente'],
        'Argila': ['argila','clay','argila_total'], 
        'CTC': ['ctc','t','ctc_ph7']
    }
    
    renomear = {}
    for col in df.columns:
        for k, v in mapa.items():
            # Verifica igualdade exata ou se contém o nome
            if col in v or any(x == col for x in v):
                renomear[col] = k
                break
    
    if renomear: df = df.rename(columns=renomear)
    
    # Validação Crítica
    if 'lat' not in df.columns or 'lon' not in df.columns:
        st.error(f"❌ Erro: Não encontrei colunas de Coordenadas. Colunas disponíveis: {list(df.columns)}")
        return None

    # Conversão Numérica Forçada
    cols = ['Ca','Mg','K','P','Prem','Argila','CTC','lat','lon']
    for c in cols:
        if c in df.columns:
            # Troca vírgula por ponto se for string (Brasil)
            if df[c].dtype == 'object': 
                df[c] = df[c].astype(str).str.replace(',', '.', regex=False)
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
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
    
    if geojson_data:
        try:
            # Tenta pegar coordenadas do primeiro poligono
            geom = geojson_data['features'][0]['geometry']
            coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
            patch = PathPatch(MplPath(coords), transform=ax.transData, facecolor='none', linewidth=0)
            ax.add_patch(patch)
            for c in cf.collections: c.set_clip_path(patch)
        except: pass
    
    ax.set_xlim(X.min(), X.max()); ax.set_ylim(Y.min(), Y.max())
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=100)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode(), bounds, [Y.min(), X.min(), Y.max(), X.max()]

def renderizar_mapa(b64, bounds_vals, limits, titulo, geojson_data):
    if not b64: return None
    colors = ['#D7191C', '#FDAE61', '#FFFFBF', '#A6D96A', '#1A9641', '#2C7BB6']
    ymin, xmin, ymax, xmax = limits
    m = folium.Map([(ymin+ymax)/2, (xmin+xmax)/2], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{b64}", bounds=[[ymin, xmin], [ymax, xmax]], opacity=0.85).add_to(m)
    if geojson_data: folium.GeoJson(geojson_data, style_function=lambda x:{'color':'black','weight':2,'fillOpacity':0}).add_to(m)
    
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
    f_csv = st.file_uploader("1. CSV Interpolado", type=["csv"])
    f_geo = st.file_uploader("2. GeoJSON", type=["geojson","json"])
    df_in, geo_data = None, None
    
    if f_csv:
        raw = carregar_csv_seguro(f_csv)
        if raw is not None:
            df_in = clean_data(raw)
            if df_in is not None: st.success(f"CSV OK: {len(df_in)} pts")
    
    if f_geo:
        try: geo_data = json.load(f_geo)
        except: st.error("GeoJSON Inválido")

    st.markdown("---")
    with st.expander("🌱 1. Cultura", True): prod = st.number_input("Meta (sc/ha)", value=75.0)
    with st.expander("⚪ 2. Calagem"):
        ca_alvo = st.number_input("Alvo Ca%", value=60.0)
        mg_alvo = st.number_input("Alvo Mg%", value=18.0)
        cao = st.number_input("CaO%", value=36.0)
        mgo = st.number_input("MgO%", value=9.0)
        prnt = st.number_input("PRNT%", value=80.0)
    with st.expander("🔴 3. Fósforo (Tabela Fixa)", True):
        p_exp = st.number_input("Exp P (kg/sc)", value=0.8)
        p_teor = st.number_input("Teor P2O5%", value=21.0)
        c1, c2 = st.columns(2)
        n1 = c1.number_input("0-4", value=5.5)
        n2 = c1.number_input("4-10", value=7.5)
        n3 = c1.number_input("10-19", value=11.5)
        n4 = c2.number_input("19-30", value=15.0)
        n5 = c2.number_input(">30", value=20.0)
        nc_vals = {'n1':n1, 'n2':n2, 'n3':n3, 'n4':n4, 'n5':n5}
    with st.expander("🟣 4. Potassio"):
        k_alvo = st.number_input("K Alvo CTC%", value=3.5)
        k_exp = st.number_input("Exp K (kg/sc)", value=1.2)
        k_teor = st.number_input("Teor K2O%", value=60.0)
    with st.expander("⚪ 5. Gesso"):
        g_fat = st.number_input("Fator x Arg", value=15.0)
        g_min = st.number_input("Min kg/ha", value=500.0)
        g_max = st.number_input("Max kg/ha", value=1000.0)

if st.button("🚀 Gerar Mapas", type="primary"):
    if df_in is not None and geo_data is not None:
        st.session_state['res'] = calc_vrt(df_in, prod, ca_alvo, mg_alvo, cao, mgo, prnt, p_exp, p_teor, k_alvo, k_exp, k_teor, g_fat, g_min, g_max, nc_vals)
        st.rerun()
    else: st.warning("Arquivos incompletos")

if 'res' in st.session_state:
    df = st.session_state['res']
    st.markdown("---")
    geo_str = json.dumps(geo_data) if geo_data else ""
    t1, t2, t3, t4 = st.tabs(["⚪ Calcario", "🔴 Fosforo", "🟣 Potassio", "🔵 Gesso"])
    
    with t1:
        st.metric("Media", f"{df['Dose_Calcario'].mean():.2f} ton")
        b64, bnds, lims = gerar_imagem_base64(df, 'Dose_Calcario', geo_str)
        m = renderizar_mapa(b64, bnds, lims, 'Calcario (ton)', geo_data)
        if m: st_folium(m, height=500, use_container_width=True)
    with t2:
        st.metric("Media", f"{df['Dose_P2O5_Kg'].mean():.0f} kg")
        st.dataframe(df[['Prem','P','NC_Tabular','Dose_P2O5_Kg']].head(50), height=150)
        b64, bnds, lims = gerar_imagem_base64(df, 'Dose_P2O5_Kg', geo_str)
        m = renderizar_mapa(b64, bnds, lims, 'Fosforo (kg)', geo_data)
        if m: st_folium(m, height=500, use_container_width=True)
    with t3:
        st.metric("Media", f"{df['Dose_K2O_Kg'].mean():.0f} kg")
        b64, bnds, lims = gerar_imagem_base64(df, 'Dose_K2O_Kg', geo_str)
        m = renderizar_mapa(b64, bnds, lims, 'Potassio (kg)', geo_data)
        if m: st_folium(m, height=500, use_container_width=True)
    with t4:
        st.metric("Media", f"{df['Dose_Gesso_Kg'].mean():.0f} kg")
        b64, bnds, lims = gerar_imagem_base64(df, 'Dose_Gesso_Kg', geo_str)
        m = renderizar_mapa(b64, bnds, lims, 'Gesso (kg)', geo_data)
        if m: st_folium(m, height=500, use_container_width=True)
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Baixar CSV", csv, "vrt_final.csv", "text/csv")
