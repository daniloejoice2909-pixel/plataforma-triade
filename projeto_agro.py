import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import Rbf
from shapely.geometry import Point, shape
from fpdf import FPDF
import json
import io
import zipfile

# --- 1. CONFIGURAÇÃO E ESTADO ---
st.set_page_config(page_title="Tríade Agro V43 (Final)", layout="wide", page_icon="🌱")

# Persistência de Dados (Não perder cadastros)
if 'cadastros' not in st.session_state:
    st.session_state['cadastros'] = {
        "Produtores": ["Gilson Berneck", "AgroMoreira"],
        "Fazendas": ["Brasnorte", "Santa Fé", "Gleba Azul"],
        "Talhoes": ["T1", "T2", "Pivo 05"]
    }
# Estados de Processamento
if 'fert_ok' not in st.session_state: st.session_state['fert_ok'] = False
if 'vrt_ok' not in st.session_state: st.session_state['vrt_ok'] = False
if 'df_proc' not in st.session_state: st.session_state['df_proc'] = None

# --- 2. CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #ffffff; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #2e7d32; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: center; margin-bottom: 10px;
    }
    .kpi-val { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; height: 3.5em; background-color: #1e3d59; color: white; border: none; }
    .stButton>button:hover { background-color: #2c567a; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INTERFACE DINÂMICA (REGRA DE PERSISTÊNCIA) ---
def gerenciar_cadastro(label, chave):
    lista = st.session_state['cadastros'][chave]
    selecao = st.sidebar.selectbox(label, lista + ["+ Adicionar Novo"])
    
    if selecao == "+ Adicionar Novo":
        novo = st.sidebar.text_input(f"Nome do Novo {label}")
        if st.sidebar.button(f"💾 Salvar {label}") and novo:
            st.session_state['cadastros'][chave].append(novo)
            st.rerun() # Recarrega a página para atualizar a lista
        return novo if novo else lista[0]
    return selecao

def configurar_sidebar():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### 📍 Gestão de Clientes")
    
    prod = gerenciar_cadastro("Produtor", "Produtores")
    faz = gerenciar_cadastro("Fazenda", "Fazendas")
    tal = gerenciar_cadastro("Talhão", "Talhoes")

    st.sidebar.divider()
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        meta = st.number_input("Meta (sc/ha)", value=80.0, step=1.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_pre = st.number_input("R$/Ton Calcário", value=190.0, step=1.0)
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0); c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1); c_mgo = st.number_input("MgO %", value=9.0, step=0.1)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0); c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)

    with st.sidebar.expander("🧪 Fósforo"):
        p_pre = st.number_input("R$/Ton P", value=2200.0, step=10.0)
        nc = [st.number_input(f"NC {f}", v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        f_arg = [st.number_input(f, v, step=0.1) for f, v in zip(["M.Arg", "Arg", "Med", "Are"], [10.0, 8.0, 4.0, 2.0])]
        p_teor = st.number_input("Teor P %", value=21.0, step=0.1); p_exp = st.number_input("Exp P (kg/sc)", value=0.8, step=0.01)

    with st.sidebar.expander("🍌 Potássio"):
        k_pre = st.number_input("R$/Ton K", value=2800.0, step=10.0)
        k_t = st.number_input("Alvo K % CTC", value=3.2, step=0.1); k_e = st.number_input("Exp K (kg/sc)", value=1.2, step=0.01)
        k_teor = st.number_input("Teor K %", value=60.0, step=0.1)

    with st.sidebar.expander("📦 Gesso"):
        g_pre = st.number_input("R$/Ton Gesso", value=400.0, step=1.0)
        g_f = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_mi = st.number_input("Mín kg/ha", value=400.0, step=10.0); g_ma = st.number_input("Máx kg/ha", value=900.0, step=10.0)

    return {
        "meta": {"prod": prod, "faz": faz, "tal": tal, "alvo": meta},
        "calc": {"pre": c_pre, "prnt": c_prnt, "res": c_res, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg},
        "fosf": {"pre": p_pre, "nc": nc, "f_arg": f_arg, "teor": p_teor, "exp": p_exp},
        "pot": {"pre": k_pre, "target": k_t, "exp": k_e, "teor": k_teor},
        "gesso": {"pre": g_pre, "fator": g_f, "min": g_mi, "max": g_ma}
    }

# --- 4. MOTOR LÓGICO V43 (MAPEAMENTO + CÁLCULOS TOTAIS) ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace('ç','c').str.replace('ã','a').str.replace('%','')
    
    # Mapeamento Inteligente
    de_para = {
        'ph': ['ph', 'ph_h2o', 'ph agua'],
        'argila': ['argila', 'clay', 'argila_total'],
        'ca_p': ['ca', 'calcio', 'ca_cmolc'],
        'mg_p': ['mg', 'magnesio', 'mg_cmolc'],
        'k_p': ['k', 'potassio', 'k_cmolc'],
        'al_p': ['al', 'aluminio', 'acidez'],
        'prem': ['p_rem', 'prem', 'p-rem'],
        'p_mehl': ['p', 'fosforo', 'p_mehlich', 'fosforo_mehlich'],
        'v_p': ['v', 'sat_bases', 'v_sat'],
        'ctc': ['t', 'ctc_total', 'ctc', 'ctc_ph7']
    }
    
    for padrao, variantes in de_para.items():
        for v in variantes:
            if v in df.columns:
                df[padrao] = df[v]
                break
    
    # Validação Básica
    if 'argila' not in df.columns:
        return df, ["ATENÇÃO: Coluna 'Argila' não encontrada. Cálculos de Gesso afetados."]

    # CÁLCULOS
    # Gesso
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])
    
    # Calagem
    if 'ca_p' in df.columns and 'ctc' in df.columns:
        nc_ca = ((p['calc']['t_ca'] - df['ca_p']) * df['ctc'] / 100).clip(lower=0)
        nc_mg = ((p['calc']['t_mg'] - df['mg_p']) * df['ctc'] / 100).clip(lower=0)
        df['rec_calcario'] = (np.maximum((nc_ca*5600000/(p['calc']['cao']*p['calc']['prnt']+0.1)), 
                                         (nc_mg*4000000/(p['calc']['mgo']*p['calc']['prnt']+0.1))) + p['calc']['res']).round(2)
    
    # Potássio
    if 'k_p' in df.columns and 'ctc' in df.columns:
        k_elev = ((p['pot']['target'] - df['k_p']).clip(lower=0) * df['ctc'] / 100 * 391)
        df['rec_potassio'] = (k_elev + (p['meta']['alvo'] * p['pot']['exp'])) * 100 / p['pot']['teor']
    
    # Fósforo (Obrigatório na VRT)
    if 'prem' in df.columns and 'p_mehl' in df.columns:
        def calc_p(row):
            idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
            f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
            p_nec = (p['fosf']['nc'][idx] - row['p_mehl']) * p['fosf']['f_arg'][f_idx]
            return (max(p_nec, 0) + (p['meta']['alvo'] * p['fosf']['exp'])) * 100 / p['fosf']['teor']
        df['rec_fosforo'] = df.apply(calc_p, axis=1)
    
    return df, None

# --- 5. GEOPROCESSAMENTO (SATÉLITE + BUFFER 100% + MAPBOX) ---
def plot_satelite_v43(df, col, title, poly=None):
    if col not in df.columns: return None

    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    
    # --- REGRA DO BUFFER 10% (Preenchimento Total) ---
    bx = (x.max() - x.min()) * 0.10
    by = (y.max() - y.min()) * 0.10
    xi = np.linspace(x.min() - bx, x.max() + bx, 150)
    yi = np.linspace(y.min() - by, y.max() + by, 150)
    xi, yi = np.meshgrid(xi, yi)
    
    try:
        rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    except: return None
    
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    # PLOTAGEM
    fig = go.Figure()
    
    # Heatmap Jet Suave
    fig.add_trace(go.Densitymapbox(
        lat=yi.flatten(), lon=xi.flatten(), z=zi.flatten(),
        radius=10, opacity=0.60, colorscale='Jet', showscale=True,
        colorbar=dict(title=dict(text="Valor", font=dict(color='white')), tickfont=dict(color='white'))
    ))
    
    # Contorno
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scattermapbox(lat=cy, lon=cx, mode='lines', line=dict(color='black', width=3), name='Talhão'))

    # Configuração Mapbox
    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]}],
            center=dict(lat=y.mean(), lon=x.mean()), zoom=13.5
        ),
        title=dict(text=f"<b>{title}</b>", font=dict(size=14)),
        height=500, margin=dict(l=0,r=0,t=40,b=0)
    )
    return fig

# --- APP PRINCIPAL ---
sb = configurar_interface()
st.title(f"🌱 Tríade Agro: {sb['meta']['prod']} | {sb['meta']['faz']} - {sb['meta']['tal']}")

c_up1, c_up2 = st.columns(2)
f_csv = c_up1.file_uploader("1. Planilha Solo (CSV)", type="csv")
f_geo = c_up2.file_uploader("2. Contorno (GeoJSON)", type="geojson")

if f_csv:
    if st.session_state['df_proc'] is None:
        df_proc, msg = motor_v43(pd.read_csv(f_csv), sb)
        if msg: 
            for m in msg: st.warning(m)
        st.session_state['df_proc'] = df_proc
    
    df_res = st.session_state['df_proc']
    poly_obj = shape(json.load(f_geo)['features'][0]['geometry']) if f_geo else None

    tabs = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT", "📥 Exportar"])

    with tabs[0]: # FERTILIDADE (COMPLETA)
        if st.button("🚀 GERAR MAPAS DE FERTILIDADE"): st.session_state['fert_ok'] = True
        
        if st.session_state['fert_ok']:
            # Lista completa conforme REGRA 2
            cols = [
                ('ph', 'pH'), ('argila', 'Argila (%)'), ('v_p', 'V%'), ('prem', 'P-rem'),
                ('ca_p', 'Cálcio'), ('mg_p', 'Magnésio'), ('k_p', 'Potássio'), ('al_p', 'Alumínio')
            ]
            for c, l in cols:
                if c in df_res.columns:
                    c_m, c_i = st.columns([3, 1])
                    fig = plot_satelite_v43(df_res, c, l, poly_obj)
                    if fig:
                        c_m.plotly_chart(fig, use_container_width=True)
                        v = df_res[c].dropna()
                        c_i.markdown(f"<div class='kpi-card'><span class='kpi-val'>Méd: {v.mean():.2f}</span></div>", unsafe_allow_html=True)
                        c_i.info(f"Mín: {v.min():.2f}\nMáx: {v.max():.2f}")
                else:
                    st.warning(f"Dado ausente: {l}")

    with tabs[1]: # VRT (COM FÓSFORO)
        if st.button("🗺️ PROCESSAR VRT"): st.session_state['vrt_ok'] = True
        
        if st.session_state['vrt_ok']:
            vrt_list = [
                ('rec_calcario', 'Calcário', sb['calc']['pre'], "Equilíbrio Ca/Mg"),
                ('rec_fosforo', 'Fosfatado', sb['fosf']['pre'], "NC P-rem + Exp"), # FÓSFORO INCLUÍDO
                ('rec_potassio', 'Potássico', sb['pot']['pre'], "Alvo 3.2% + Exp"),
                ('rec_gesso', 'Gesso', sb['gesso']['pre'], "Argila% x 15")
            ]
            for c, l, pr, arg in vrt_list:
                if c in df_res.columns:
                    c_m, c_i = st.columns([3, 1])
                    fig = plot_satelite_v43(df_res, c, f"Recomendação {l}", poly_obj)
                    if fig:
                        c_m.plotly_chart(fig, use_container_width=True)
                        v = df_res[c].dropna(); custo = (v.mean()/1000)*pr
                        c_i.markdown(f"<div class='kpi-card'><span class='kpi-lbl'>CUSTO MÉDIO</span><br><span class='kpi-val'>R$ {custo:.2f}</span></div>", unsafe_allow_html=True)
                        c_i.markdown(f"<div class='arg-tecnico'>{arg}</div>", unsafe_allow_html=True)
                else:
                    st.error(f"Impossível calcular {l}. Verifique os dados.")

    with tabs[2]: # EXPORTAÇÃO
        st.subheader("Central de Downloads")
        c_p, c_z = st.columns(2)
        
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, f"RELATORIO TRIADE - {sb['meta']['prod']}", ln=True, align='C')
        pdf_bytes = bytes(pdf.output()) 
        c_p.download_button("📄 Baixar PDF", data=pdf_bytes, file_name="Relatorio.pdf", mime="application/pdf")
        
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for m in ["JOHN_DEERE", "TRIMBLE", "HORSCH", "CASE", "STARA"]:
                z.writestr(f"{m}/VRT_{sb['meta']['tal']}.csv", df_res.to_csv(index=False))
        c_z.download_button("📦 Baixar ZIP", data=buf.getvalue(), file_name="Triade_VRT.zip", mime="application/zip")
