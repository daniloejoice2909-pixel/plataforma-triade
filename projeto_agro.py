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

# --- 1. CONFIGURAÇÃO E PERSISTÊNCIA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# Inicialização de Estado (Evita perda de dados ao atualizar)
if 'cadastros' not in st.session_state:
    st.session_state['cadastros'] = {
        "Produtores": ["Gilson Berneck", "AgroMoreira"],
        "Fazendas": ["Brasnorte", "Santa Fé"],
        "Talhoes": ["T1", "T2", "Pivo Central"]
    }
if 'fert_ok' not in st.session_state: st.session_state['fert_ok'] = False
if 'vrt_ok' not in st.session_state: st.session_state['vrt_ok'] = False
if 'df_proc' not in st.session_state: st.session_state['df_proc'] = None

# --- 2. ESTILO PREMIUM (OPEN SANS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 13px; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #fff; padding: 15px; border-radius: 8px; 
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-top: 4px solid #1e3d59; 
        text-align: center; margin-bottom: 10px;
    }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1e3d59; }
    .arg-tecnico { 
        font-size: 11px; color: #333; background: #eef5f8; padding: 10px; 
        border-radius: 5px; border-left: 5px solid #27ae60; margin-top: 5px; 
    }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; height: 3.5em; background-color: #1e3d59; color: white; border:none; }
    .stButton>button:hover { background-color: #2c567a; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INTERFACE DINÂMICA (HIERARQUIA + INPUTS +/-) ---
def gerenciar_hierarquia(label, chave):
    lista = st.session_state['cadastros'][chave]
    selecao = st.sidebar.selectbox(label, lista + ["+ Adicionar Novo"])
    if selecao == "+ Adicionar Novo":
        novo = st.sidebar.text_input(f"Nome do Novo {label}")
        if st.sidebar.button(f"💾 Salvar {label}") and novo:
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
        prod_alvo = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_pre = st.number_input("R$/Ton Calcário", value=190.0, step=1.0)
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0); c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0); c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1); c_mgo = st.number_input("MgO %", value=9.0, step=0.1)

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
        "meta": {"prod": prod, "faz": faz, "tal": tal, "alvo": prod_alvo},
        "calc": {"pre": c_pre, "prnt": c_prnt, "res": c_res, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg},
        "fosf": {"pre": p_pre, "nc": nc, "f_arg": f_arg, "teor": p_teor, "exp": p_exp},
        "pot": {"pre": k_pre, "target": k_t, "exp": k_e, "teor": k_teor},
        "gesso": {"pre": g_pre, "fator": g_f, "min": g_mi, "max": g_ma}
    }

# --- 4. MOTOR LÓGICO V43 (MAPEAMENTO INTELIGENTE) ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    # Normalização de nomes (evita KeyError)
    df.columns = df.columns.str.strip().str.lower().str.replace('ç', 'c').str.replace('ã', 'a').str.replace('%', '')
    
    # Dicionário de Sinônimos (De -> Para Padrão)
    de_para = {
        'ph': ['ph_h2o', 'ph agua', 'ph'],
        'argila': ['argila_total', 'clay', 'argila'],
        'ca_p': ['ca', 'calcio', 'ca_cmolc'],
        'mg_p': ['mg', 'magnesio', 'mg_cmolc'],
        'k_p': ['k', 'potassio', 'k_cmolc'],
        'al_p': ['al', 'aluminio', 'acidez'],
        'prem': ['p_rem', 'prem', 'p-rem'],
        'p_mehl': ['p', 'fosforo', 'p_mehlich'],
        'v_p': ['v', 'sat_bases', 'v_sat'],
        'ctc': ['t', 'ctc_total', 'ctc']
    }
    
    # Aplica mapeamento
    for padrao, variantes in de_para.items():
        for v in variantes:
            if v in df.columns:
                df[padrao] = df[v]
                break
    
    # Validação de Dados Essenciais
    missing = [c for c in ['argila', 'ctc', 'ca_p', 'mg_p'] if c not in df.columns]
    if missing:
        return df, f"Erro: Colunas faltando {missing}"

    # CÁLCULOS
    # Gesso: Argila % x 15
    df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])
    
    # Calagem: Maior Ca/Mg + Reserva
    nc_ca = ((p['calc']['t_ca'] - df.get('ca_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    nc_mg = ((p['calc']['t_mg'] - df.get('mg_p', 0)) * df.get('ctc', 0) / 100).clip(lower=0)
    df['rec_calcario'] = (np.maximum((nc_ca*5600000/(p['calc']['cao']*p['calc']['prnt']+0.1)), 
                                     (nc_mg*4000000/(p['calc']['mgo']*p['calc']['prnt']+0.1))) + p['calc']['res']).round(2)
    
    # Potássio: Elevação 3.2% + Exp
    k_elev = ((p['pot']['target'] - df.get('k_p', 0)).clip(lower=0) * df.get('ctc', 0) / 100 * 391)
    df['rec_potassio'] = (k_elev + (p['meta']['alvo'] * p['pot']['exp'])) * 100 / p['pot']['teor']
    
    # Fósforo: NC + Exp
    if 'prem' in df.columns and 'p_mehl' in df.columns:
        def calc_p(row):
            idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
            f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
            p_nec = (p['fosf']['nc'][idx] - row['p_mehl']) * p['fosf']['f_arg'][f_idx]
            return (max(p_nec, 0) + (p['meta']['alvo'] * p['fosf']['exp'])) * 100 / p['fosf']['teor']
        df['rec_fosforo'] = df.apply(calc_p, axis=1)
    else:
        df['rec_fosforo'] = 0 # Fallback seguro

    return df, None

# --- 5. GEOPROCESSAMENTO (SATÉLITE + 1:1 + BUFFER) ---
def plot_satelite_v43(df, col, title, poly=None):
    if col not in df.columns: return None # Validação silenciosa

    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    
    # Buffer de 8% para preenchimento total
    bx, by = (x.max()-x.min())*0.08, (y.max()-y.min())*0.08
    xi = np.linspace(x.min()-bx, x.max()+bx, 150) # Grid Denso
    yi = np.linspace(y.min()-by, y.max()+by, 150)
    xi, yi = np.meshgrid(xi, yi)
    
    # Krigagem Segura
    try:
        rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    except: return None
    
    # Clipping
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    # MAPBOX SATÉLITE
    fig = go.Figure()
    fig.add_trace(go.Densitymapbox(
        lat=yi.flatten(), lon=xi.flatten(), z=zi.flatten(),
        radius=10, opacity=0.60, colorscale='RdYlBu_r', showscale=True, # Opacidade 0.60
        colorbar=dict(title=dict(text="Dose/Teor", font=dict(color='white')), tickfont=dict(color='white'))
    ))
    
    # Contorno Preto (Validação)
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scattermapbox(lat=cy, lon=cx, mode='lines', line=dict(color='black', width=4), name='Limite'))

    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]}],
            center=dict(lat=y.mean(), lon=x.mean()), zoom=13
        ),
        title=dict(text=f"<b>{title}</b>", font=dict(size=14)),
        height=550, margin=dict(l=0,r=0,t=40,b=0)
    )
    return fig

# --- APP PRINCIPAL ---
sb = configurar_interface()
st.title(f"🌱 Tríade Agro: {sb['meta']['prod']} | {sb['meta']['faz']} - {sb['meta']['tal']}")

c1, c2 = st.columns(2)
f_csv = c1.file_uploader("1. Planilha (CSV)", type="csv")
f_geo = c2.file_uploader("2. Contorno (GeoJSON)", type="geojson")

if f_csv:
    # Processamento Único (Blindagem contra travamento)
    if st.session_state['df_proc'] is None:
        processed_df, error_msg = motor_v43(pd.read_csv(f_csv), sb)
        if error_msg: st.error(error_msg)
        else: st.session_state['df_proc'] = processed_df
    
    df_res = st.session_state['df_proc']
    
    if df_res is not None:
        poly_obj = shape(json.load(f_geo)['features'][0]['geometry']) if f_geo else None
        tabs = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT", "📥 Exportar"])

        with tabs[0]: # FERTILIDADE COMPLETA
            if st.button("🚀 PROCESSAR FERTILIDADE"): st.session_state['fert_ok'] = True
            if st.session_state['fert_ok']:
                attrs = [('ph', 'pH'), ('argila', 'Argila %'), ('v_p', 'V%'), ('prem', 'P-rem'), 
                         ('ca_p', 'Cálcio'), ('mg_p', 'Magnésio'), ('k_p', 'Potássio'), ('al_p', 'Alumínio')]
                for c, l in attrs:
                    if c in df_res.columns:
                        c_m, c_i = st.columns([3, 1])
                        fig = plot_satelite_v43(df_res, c, l, poly_obj)
                        if fig:
                            c_m.plotly_chart(fig, use_container_width=True)
                            v = df_res[c].dropna(); c_i.info(f"**{l}**\nMéd: {v.mean():.2f}\nMín: {v.min():.2f}")
                    else: st.warning(f"Dado ausente: {l}")

        with tabs[1]: # VRT COMPLETA
            if st.button("🗺️ PROCESSAR VRT"): st.session_state['vrt_ok'] = True
            if st.session_state['vrt_ok']:
                vrt_list = [('rec_calcario', 'Calcário', sb['calc']['pre'], "Equilíbrio Ca/Mg"), 
                            ('rec_fosforo', 'Fosfatado', sb['fosf']['pre'], "NC P-rem + Exp"), 
                            ('rec_potassio', 'Potássico', sb['pot']['pre'], "Alvo 3.2% + Exp"), 
                            ('rec_gesso', 'Gesso', sb['gesso']['pre'], "Argila% x 15")]
                for c, l, pr, arg in vrt_list:
                    if c in df_res.columns:
                        c_m, c_i = st.columns([3, 1])
                        fig = plot_satelite_v43(df_res, c, f"VRT {l}", poly_obj)
                        if fig:
                            c_m.plotly_chart(fig, use_container_width=True)
                            v = df_res[c].dropna(); custo = (v.mean()/1000)*pr
                            c_i.markdown(f"<div class='kpi-card'><small>Custo Médio</small><br><span class='kpi-value'>R$ {custo:.2f}/ha</span></div>", unsafe_allow_html=True)
                            c_i.markdown(f"<div class='arg-tecnico'>{arg}</div>", unsafe_allow_html=True)

        with tabs[2]: # EXPORTAÇÃO
            st.subheader("Central de Downloads")
            c_p, c_z = st.columns(2)
            
            # PDF Seguro (Bytes)
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
            pdf.cell(0, 10, f"TRÍADE AGRO - {sb['meta']['prod']}", ln=True, align='C')
            pdf.ln(10); pdf.set_font("Helvetica", '', 12)
            pdf.cell(0, 10, "Relatório processado via Protocolo V43.", ln=True)
            pdf_bytes = bytes(pdf.output()) 
            c_p.download_button("📄 PDF Relatório", data=pdf_bytes, file_name="Relatorio.pdf", mime="application/pdf")
            
            # ZIP com Pastas Reais
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as z:
                for m in ["JOHN_DEERE", "TRIMBLE", "HORSCH", "CASE", "STARA"]:
                    z.writestr(f"{m}/VRT_{sb['meta']['tal']}.csv", df_res.to_csv(index=False))
            c_z.download_button("📦 ZIP Monitores", data=buf.getvalue(), file_name="VRT_Monitores.zip", mime="application/zip")
