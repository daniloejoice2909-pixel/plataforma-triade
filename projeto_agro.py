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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- INICIALIZAÇÃO DE ESTADO (PERSISTÊNCIA) ---
if 'cadastros' not in st.session_state:
    st.session_state['cadastros'] = {
        "Produtores": ["Gilson Berneck", "AgroMoreira"],
        "Fazendas": ["Brasnorte", "Santa Fé"],
        "Talhoes": ["T1", "T2", "Pivo Central"]
    }
if 'fert_ok' not in st.session_state: st.session_state['fert_ok'] = False
if 'vrt_ok' not in st.session_state: st.session_state['vrt_ok'] = False
if 'df_proc' not in st.session_state: st.session_state['df_proc'] = None

# --- CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 13px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { background: #fff; padding: 15px; border-radius: 8px; border-top: 4px solid #1e3d59; text-align: center; margin-bottom: 10px;}
    .kpi-value { font-size: 18px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { font-size: 11px; color: #333; background: #eef5f8; padding: 10px; border-radius: 5px; border-left: 5px solid #27ae60; margin-top: 5px;}
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; height: 3em; background-color: #1e3d59; color: white; border: none; }
    .stButton>button:hover { background-color: #2c567a; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- CAMADA 1: SIDEBAR COM HIERARQUIA DINÂMICA ---
def gerenciar_hierarquia(tipo, chave):
    lista = st.session_state['cadastros'][chave]
    selecao = st.sidebar.selectbox(tipo, lista + ["+ Adicionar Novo"])
    if selecao == "+ Adicionar Novo":
        novo = st.sidebar.text_input(f"Nome do Novo {tipo}")
        if st.sidebar.button(f"💾 Salvar {tipo}") and novo:
            st.session_state['cadastros'][chave].append(novo)
            st.rerun()
        return novo if novo else lista[0]
    return selecao

def configurar_interface():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### 📍 Gestão de Clientes")
    
    prod = gerenciar_hierarquia("Produtor", "Produtores")
    faz = gerenciar_hierarquia("Fazenda", "Fazendas")
    tal = gerenciar_hierarquia("Talhão", "Talhoes")

    st.sidebar.divider()
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        meta = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_pre = st.number_input("R$/Ton Calcário", value=190.0, step=1.0)
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0); c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1); c_mgo = st.number_input("MgO %", value=9.0, step=0.1)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0); c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)

    with st.sidebar.expander("🧪 Fósforo"):
        p_pre = st.number_input("R$/Ton P", value=2000.0, step=10.0)
        nc = [st.number_input(f"NC {f}", v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        f_arg = [st.number_input(f, v, step=0.1) for f, v in zip(["M.Arg", "Arg", "Med", "Are"], [10.0, 8.0, 4.0, 2.0])]
        p_teor = st.number_input("Teor Adubo P %", value=21.0, step=0.1); p_exp = st.number_input("Exp P (kg/sc)", value=0.8, step=0.01)

    with st.sidebar.expander("🍌 Potássio"):
        k_pre = st.number_input("R$/Ton K", value=2800.0, step=10.0)
        k_t = st.number_input("Alvo K % CTC", value=3.2, step=0.1); k_e = st.number_input("Exp K (kg/sc)", value=1.2, step=0.01)
        k_teor = st.number_input("Teor Adubo K %", value=60.0, step=0.1)

    with st.sidebar.expander("📦 Gesso"):
        g_pre = st.number_input("R$/Ton Gesso", value=400.0, step=1.0)
        g_f = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_mi = st.number_input("Mín kg/ha", value=400.0, step=10.0); g_ma = st.number_input("Máx kg/ha", value=900.0, step=10.0)

    return {
        "meta": {"produtor": prod, "fazenda": faz, "talhao": tal, "alvo": meta},
        "calc": {"pre": c_pre, "prnt": c_prnt, "res": c_res, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg},
        "fosf": {"pre": p_pre, "nc": nc, "f_arg": f_arg, "teor": p_teor, "exp": p_exp},
        "pot": {"pre": k_pre, "target": k_t, "exp": k_e, "teor": k_teor},
        "gesso": {"pre": g_pre, "fator": g_f, "min": g_mi, "max": g_ma}
    }

# --- CAMADA 2: MOTOR LÓGICO V43 ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()
    mapping = {'p mehl': 'p_mehl', 'p-rem': 'prem', 'ca%': 'ca_p', 'mg%': 'mg_p', 'k%': 'k_p', 'al%': 'al_p', 'v%': 'v_p'}
    df = df.rename(columns=mapping)
    
    # Gesso
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])
    
    # Calagem
    nc_ca = ((p['calc']['t_ca'] - df.get('ca_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    nc_mg = ((p['calc']['t_mg'] - df.get('mg_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['rec_calcario'] = (np.maximum((nc_ca*5600000/(p['calc']['cao']*p['calc']['prnt']+0.1)), 
                                     (nc_mg*4000000/(p['calc']['mgo']*p['calc']['prnt']+0.1))) + p['calc']['res']).round(2)
    
    # Potássio (Elevação + Exportação)
    k_elev = ((p['pot']['target'] - df.get('k_p', 0)).clip(lower=0) * df.get('ctc', 0) / 100 * 391)
    df['rec_potassio'] = (k_elev + (p['meta']['alvo'] * p['pot']['exp'])) * 100 / p['pot']['teor']
    
    # Fósforo (NC + Exportação)
    def calc_p(row):
        idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
        f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
        p_nec = (p['fosf']['nc'][idx] - row['p_mehl']) * p['fosf']['f_arg'][f_idx]
        return (max(p_nec, 0) + (p['meta']['alvo'] * p['fosf']['exp'])) * 100 / p['fosf']['teor']
    df['rec_fosforo'] = df.apply(calc_p, axis=1)
    
    return df

# --- CAMADA 3: GEOPROCESSAMENTO COM SATÉLITE REAL ---
def plot_satelite(df, col, title, poly=None):
    # Buffer de 8% para preenchimento total
    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    bx, by = (x.max()-x.min())*0.08, (y.max()-y.min())*0.08
    
    # Grid denso (150x150)
    xi = np.linspace(x.min()-bx, x.max()+bx, 150)
    yi = np.linspace(y.min()-by, y.max()+by, 150)
    xi, yi = np.meshgrid(xi, yi)
    rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    
    # Clipping com Shapely
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    # Camada de Satélite (Esri World Imagery)
    fig = go.Figure()
    
    # Mapa de Calor (Translucido sobre satélite)
    fig.add_trace(go.Densitymapbox(
        lat=yi.flatten(), lon=xi.flatten(), z=zi.flatten(),
        radius=10, opacity=0.65, colorscale='RdYlBu_r', showscale=True,
        colorbar=dict(title=dict(text="Valor", font=dict(color='white')), tickfont=dict(color='white'))
    ))
    
    # Contorno Preto
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scattermapbox(
            lat=cy, lon=cx, mode='lines', 
            line=dict(color='black', width=3), name='Contorno'
        ))

    # Configuração Mapbox
    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            layers=[{
                "below": 'traces',
                "sourcetype": "raster",
                "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]
            }],
            center=dict(lat=y.mean(), lon=x.mean()),
            zoom=13
        ),
        title=dict(text=f"<b>{title}</b>", font=dict(size=16)),
        height=550, margin=dict(l=0,r=0,t=40,b=0)
    )
    return fig

# --- APP PRINCIPAL ---
sb = configurar_interface()
st.title(f"🌱 Tríade Agro: {sb['meta']['produtor']} | {sb['meta']['fazenda']}")

col_up1, col_up2 = st.columns(2)
f_csv = col_up1.file_uploader("1. Planilha Solo (CSV)", type="csv")
f_geo = col_up2.file_uploader("2. Contorno (GeoJSON)", type="geojson")

if f_csv:
    # Processamento Único
    if st.session_state['df_proc'] is None:
        st.session_state['df_proc'] = motor_v43(pd.read_csv(f_csv), sb)
    
    df_res = st.session_state['df_proc']
    poly_obj = shape(json.load(f_geo)['features'][0]['geometry']) if f_geo else None

    tabs = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT", "📥 Exportar"])

    with tabs[0]: # ABA FERTILIDADE COMPLETA
        if st.button("🚀 GERAR MAPAS DE FERTILIDADE"): st.session_state['fert_ok'] = True
        
        if st.session_state['fert_ok']:
            # Lista completa de atributos conforme Protocolo V43
            attrs = [('ph', 'pH'), ('argila', 'Argila (%)'), ('v_p', 'V%'), ('prem', 'P-rem'), 
                     ('ca_p', 'Cálcio (cmol)'), ('mg_p', 'Magnésio (cmol)'), ('k_p', 'Potássio (cmol)'), ('al_p', 'Alumínio')]
            
            for col, label in attrs:
                if col in df_res.columns:
                    c_map, c_info = st.columns([3, 1])
                    c_map.plotly_chart(plot_satelite(df_res, col, label, poly_obj), use_container_width=True)
                    v = df_res[col].dropna()
                    c_info.info(f"**Estatísticas {label}**\nMín: {v.min():.2f}\nMáx: {v.max():.2f}\nMéd: {v.mean():.2f}")

    with tabs[1]: # ABA VRT (COM FÓSFORO)
        if st.button("🗺️ PROCESSAR RECOMENDAÇÕES VRT"): st.session_state['vrt_ok'] = True
        
        if st.session_state['vrt_ok']:
            vrt_list = [('rec_calcario', 'Calcário', sb['calc']['pre'], "Equilíbrio Ca/Mg"), 
                        ('rec_fosforo', 'Fosfatado', sb['fosf']['pre'], "NC P-rem + Exp"), 
                        ('rec_potassio', 'Potássico', sb['pot']['pre'], "Alvo 3.2% + Exp"), 
                        ('rec_gesso', 'Gesso', sb['gesso']['pre'], "Argila% x 15")]
            
            for col, label, preco, arg in vrt_list:
                c_map, c_info = st.columns([3, 1])
                c_map.plotly_chart(plot_satelite(df_res, col, f"Recomendação {label}", poly_obj), use_container_width=True)
                v = df_res[col].dropna()
                custo = (v.mean() / 1000) * preco
                c_info.markdown(f"<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo:.2f}/ha</span></div>", unsafe_allow_html=True)
                c_info.markdown(f"<div class='arg-tecnico'><b>Protocolo:</b> {arg}</div>", unsafe_allow_html=True)

    with tabs[2]: # EXPORTAÇÃO
        st.subheader("Central de Downloads")
        c1, c2 = st.columns(2)
        
        # PDF CORRIGIDO (BYTES)
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, f"RELATORIO TRIADE - {sb['meta']['produtor'].upper()}", ln=True, align='C')
        pdf.set_font("Helvetica", '', 12); pdf.ln(10)
        pdf.cell(0, 10, f"Fazenda: {sb['meta']['fazenda']} | Talhao: {sb['meta']['talhao']}", ln=True)
        pdf_bytes = bytes(pdf.output()) # Conversão crucial para evitar StreamlitAPIException
        c1.download_button("📄 Baixar Relatório PDF", data=pdf_bytes, file_name=f"Relatorio_{sb['meta']['talhao']}.pdf", mime="application/pdf")
        
        # ZIP COM PASTAS
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for m in ["JOHN_DEERE", "TRIMBLE", "HORSCH", "CASE", "STARA"]:
                z.writestr(f"{m}/Rx_VRT_{sb['meta']['talhao']}.csv", df_res.to_csv(index=False))
        c2.download_button("📦 Exportar ZIP Monitores", data=buf.getvalue(), file_name="Triade_Export.zip", mime="application/zip")
