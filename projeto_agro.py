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

# --- 1. CONFIGURAÇÃO E ESTADO GLOBAL ---
st.set_page_config(page_title="Tríade Agro V43 (Gold)", layout="wide", page_icon="🌱")

# Inicialização de Variáveis de Sessão (Persistência)
if 'cadastros' not in st.session_state:
    st.session_state['cadastros'] = {
        "Produtores": ["Gilson Berneck", "AgroMoreira", "Tríade Demo"],
        "Fazendas": ["Brasnorte", "Santa Fé", "Gleba A"],
        "Talhoes": ["T1", "T2", "Pivo 03"]
    }
if 'fert_ok' not in st.session_state: st.session_state['fert_ok'] = False
if 'vrt_ok' not in st.session_state: st.session_state['vrt_ok'] = False
if 'df_proc' not in st.session_state: st.session_state['df_proc'] = None

# --- 2. ESTILO VISUAL PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card { 
        background: #ffffff; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #2e7d32; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center; margin-bottom: 10px;
    }
    .kpi-val { font-size: 22px; font-weight: 700; color: #1e3d59; }
    .kpi-lbl { font-size: 12px; color: #666; text-transform: uppercase; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; height: 3.5em; background-color: #1e3d59; color: white; border: none; }
    .stButton>button:hover { background-color: #2c567a; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INTERFACE DINÂMICA (HIERARQUIA + PARÂMETROS) ---
def gerenciar_cadastro(tipo, chave):
    lista = st.session_state['cadastros'][chave]
    selecao = st.sidebar.selectbox(tipo, lista + ["+ Adicionar Novo"])
    if selecao == "+ Adicionar Novo":
        novo = st.sidebar.text_input(f"Nome do Novo {tipo}")
        if st.sidebar.button(f"💾 Salvar {tipo}") and novo:
            st.session_state['cadastros'][chave].append(novo)
            st.rerun()
        return novo if novo else lista[0]
    return selecao

def configurar_sidebar():
    st.sidebar.image("LogoTriadeagro.png.png", use_container_width=True)
    st.sidebar.markdown("### 📍 Gestão do Cliente")
    
    prod = gerenciar_cadastro("Produtor", "Produtores")
    faz = gerenciar_cadastro("Fazenda", "Fazendas")
    tal = gerenciar_cadastro("Talhão", "Talhoes")

    st.sidebar.divider()
    with st.sidebar.expander("🌍 Produtividade Alvo", expanded=True):
        meta = st.number_input("Meta (sc/ha)", value=80.0, step=1.0, min_value=0.0)

    with st.sidebar.expander("🪨 Calagem"):
        c_pr = st.number_input("R$/Ton Calcário", value=190.0, step=1.0)
        c_prnt = st.number_input("PRNT %", value=80.0, step=1.0); c_res = st.number_input("Reserva (kg/ha)", value=0.0, step=10.0)
        c_cao = st.number_input("CaO %", value=36.0, step=0.1); c_mgo = st.number_input("MgO %", value=9.0, step=0.1)
        c_t_ca = st.number_input("Alvo Ca %", value=60.0, step=1.0); c_t_mg = st.number_input("Alvo Mg %", value=18.0, step=1.0)

    with st.sidebar.expander("🧪 Fósforo"):
        p_pr = st.number_input("R$/Ton MAP/Super", value=2200.0, step=10.0)
        nc = [st.number_input(f"NC {f}", v, step=0.1) for f, v in zip(["0-4","4-10","10-19","19-30","30-45","45-60"], [8.0, 10.0, 12.0, 15.0, 18.0, 22.0])]
        f_arg = [st.number_input(f, v, step=0.1) for f, v in zip(["M.Arg", "Arg", "Med", "Are"], [10.0, 8.0, 4.0, 2.0])]
        p_t = st.number_input("Teor P %", value=21.0, step=0.1); p_e = st.number_input("Exp P (kg/sc)", value=0.8, step=0.01)

    with st.sidebar.expander("🍌 Potássio"):
        k_pr = st.number_input("R$/Ton KCl", value=2800.0, step=10.0)
        k_t = st.number_input("Alvo K % CTC", value=3.2, step=0.1); k_e = st.number_input("Exp K (kg/sc)", value=1.2, step=0.01)
        k_teor = st.number_input("Teor K %", value=60.0, step=0.1)

    with st.sidebar.expander("📦 Gesso"):
        g_pr = st.number_input("R$/Ton Gesso", value=400.0, step=1.0)
        g_f = st.number_input("Fator Gesso", value=15.0, step=0.1)
        g_mi = st.number_input("Mín kg/ha", value=400.0, step=10.0); g_ma = st.number_input("Máx kg/ha", value=900.0, step=10.0)

    return {
        "meta": {"prod": prod, "faz": faz, "tal": tal, "alvo": meta},
        "calc": {"pr": c_pr, "prnt": c_prnt, "res": c_res, "cao": c_cao, "mgo": c_mgo, "t_ca": c_t_ca, "t_mg": c_t_mg},
        "fosf": {"pr": p_pr, "nc": nc, "f_arg": f_arg, "teor": p_t, "exp": p_e},
        "pot": {"pr": k_pr, "target": k_t, "exp": k_e, "teor": k_teor},
        "gesso": {"pr": g_pr, "fator": g_f, "min": g_mi, "max": g_ma}
    }

# --- 4. MOTOR LÓGICO V43 (MAPEAMENTO INTELIGENTE + BLINDAGEM KEYERROR) ---
def motor_v43(df_raw, p):
    df = df_raw.copy()
    # Normalização de nomes (Remove acentos, espaços, maiúsculas)
    df.columns = df.columns.str.strip().str.lower().str.replace('ç','c').str.replace('ã','a').str.replace('%','')
    
    # Dicionário de Sinônimos (De -> Para Padrão Interno)
    de_para = {
        'ph': ['ph_h2o', 'ph agua', 'ph'],
        'argila': ['argila_total', 'clay', 'argila'],
        'ca_p': ['ca', 'calcio', 'ca_cmolc'],
        'mg_p': ['mg', 'magnesio', 'mg_cmolc'],
        'k_p': ['k', 'potassio', 'k_cmolc'],
        'al_p': ['al', 'aluminio', 'acidez'],
        'prem': ['p_rem', 'prem', 'p-rem'],
        'p_mehl': ['p', 'fosforo', 'p_mehlich', 'fosforo_mehlich'],
        'v_p': ['v', 'sat_bases', 'v_sat'],
        'ctc': ['t', 'ctc_total', 'ctc', 'ctc_ph7']
    }
    
    # Aplicação do Mapeamento
    for padrao, variantes in de_para.items():
        for v in variantes:
            if v in df.columns:
                df[padrao] = df[v]
                break
    
    # Verificação de colunas mínimas para cálculo
    erros = []
    if 'argila' not in df.columns: erros.append("Falta coluna de Argila")
    if 'ca_p' not in df.columns: erros.append("Falta coluna de Cálcio")
    
    # CÁLCULOS VRT
    # Gesso (Argila * Fator)
    if 'argila' in df.columns:
        df['rec_gesso'] = (df['argila'] * p['gesso']['fator']).clip(p['gesso']['min'], p['gesso']['max'])
    
    # Calagem (Max Ca/Mg + Reserva)
    if 'ca_p' in df.columns and 'ctc' in df.columns:
        nc_ca = ((p['calc']['t_ca'] - df['ca_p']) * df['ctc'] / 100).clip(lower=0)
        nc_mg = ((p['calc']['t_mg'] - df['mg_p']) * df['ctc'] / 100).clip(lower=0)
        df['rec_calcario'] = (np.maximum((nc_ca*5600000/(p['calc']['cao']*p['calc']['prnt']+0.1)), 
                                         (nc_mg*4000000/(p['calc']['mgo']*p['calc']['prnt']+0.1))) + p['calc']['res']).round(2)
    
    # Potássio (Elevação 3.2% + Exp)
    if 'k_p' in df.columns and 'ctc' in df.columns:
        k_elev = ((p['pot']['target'] - df['k_p']).clip(lower=0) * df['ctc'] / 100 * 391)
        df['rec_potassio'] = (k_elev + (p['meta']['alvo'] * p['pot']['exp'])) * 100 / p['pot']['teor']
    
    # Fósforo (NC P-rem + Exp)
    if 'prem' in df.columns and 'p_mehl' in df.columns:
        def calc_p(row):
            idx = 0 if row['prem']<=4 else 1 if row['prem']<=10 else 2 if row['prem']<=19 else 3 if row['prem']<=30 else 4 if row['prem']<=45 else 5
            f_idx = 0 if row['argila']>60 else 1 if row['argila']>35 else 2 if row['argila']>15 else 3
            p_nec = (p['fosf']['nc'][idx] - row['p_mehl']) * p['fosf']['f_arg'][f_idx]
            return (max(p_nec, 0) + (p['meta']['alvo'] * p['fosf']['exp'])) * 100 / p['fosf']['teor']
        df['rec_fosforo'] = df.apply(calc_p, axis=1)
    
    return df, erros

# --- 5. GEOPROCESSAMENTO "INCERES STYLE" (SATÉLITE + SUAVIZAÇÃO) ---
def plot_satelite_v43(df, col, title, poly=None):
    # Validação Pré-Renderização (Argumento 13)
    if col not in df.columns:
        return None 

    x, y, z = df['longitude'].values, df['latitude'].values, df[col].values
    
    # Buffer de 8% para preenchimento total da área
    bx, by = (x.max()-x.min())*0.08, (y.max()-y.min())*0.08
    xi = np.linspace(x.min()-bx, x.max()+bx, 150) # Grid Denso
    yi = np.linspace(y.min()-by, y.max()+by, 150)
    xi, yi = np.meshgrid(xi, yi)
    
    try:
        rbf = Rbf(x, y, z, function='linear'); zi = rbf(xi, yi)
    except: return None
    
    # Clipping com Shapely
    if poly:
        for i in range(len(xi)):
            for j in range(len(yi)):
                if not poly.contains(Point(xi[i,j], yi[i,j])): zi[i,j] = np.nan

    # PLOTAGEM (Mapbox para Satélite Real)
    fig = go.Figure()
    
    # Camada de Calor (Heatmap suave)
    fig.add_trace(go.Densitymapbox(
        lat=yi.flatten(), lon=xi.flatten(), z=zi.flatten(),
        radius=10, opacity=0.65, # Opacidade 0.65 para ver o solo
        colorscale='Jet', # Paleta Agronômica
        showscale=True, colorbar=dict(title=dict(text="Unid.", font=dict(color='white')), tickfont=dict(color='white'))
    ))
    
    # Contorno GeoJSON (Linha Preta)
    if poly:
        cx, cy = zip(*list(poly.exterior.coords))
        fig.add_trace(go.Scattermapbox(lat=cy, lon=cx, mode='lines', line=dict(color='black', width=3), name='Contorno'))

    # Configuração do Mapa (Satélite ESRI)
    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            layers=[{
                "below": 'traces', "sourcetype": "raster",
                "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]
            }],
            center=dict(lat=y.mean(), lon=x.mean()), zoom=13.5
        ),
        title=dict(text=f"<b>{title}</b>", font=dict(size=16)),
        height=550, margin=dict(l=0,r=0,t=40,b=0)
    )
    return fig

# --- APP PRINCIPAL ---
sb = configurar_interface()
st.title(f"🌱 Plataforma Tríade Agro: {sb['meta']['prod']} - {sb['meta']['faz']}")

c_up1, c_up2 = st.columns(2)
f_csv = c_up1.file_uploader("1. Carregar Planilha (CSV)", type="csv")
f_geo = c_up2.file_uploader("2. Carregar Contorno (GeoJSON)", type="geojson")

if f_csv:
    # Processamento Único (Evita re-run desnecessário)
    if st.session_state['df_proc'] is None:
        df_proc, alertas = motor_v43(pd.read_csv(f_csv), sb)
        if alertas:
            for a in alertas: st.warning(a)
        st.session_state['df_proc'] = df_proc
    
    df_res = st.session_state['df_proc']
    poly_obj = shape(json.load(f_geo)['features'][0]['geometry']) if f_geo else None

    tabs = st.tabs(["📊 Fertilidade", "🗺️ Recomendações VRT", "📥 Exportar"])

    with tabs[0]: # ABA FERTILIDADE COMPLETA
        if st.button("🚀 GERAR MAPAS DE FERTILIDADE"): st.session_state['fert_ok'] = True
        
        if st.session_state['fert_ok']:
            # Lista completa conforme Argumento 10
            cols = [('ph', 'pH'), ('argila', 'Argila (%)'), ('v_p', 'V%'), ('prem', 'P-rem'), 
                    ('ca_p', 'Cálcio'), ('mg_p', 'Magnésio'), ('k_p', 'Potássio'), ('al_p', 'Alumínio')]
            
            for c, l in cols:
                if c in df_res.columns:
                    c_m, c_i = st.columns([3, 1])
                    fig = plot_satelite_v43(df_res, c, l, poly_obj)
                    if fig:
                        c_m.plotly_chart(fig, use_container_width=True)
                        v = df_res[c].dropna()
                        c_i.markdown(f"<div class='kpi-card'><span class='kpi-lbl'>MÉDIA</span><br><span class='kpi-val'>{v.mean():.2f}</span></div>", unsafe_allow_html=True)
                        c_i.info(f"Mín: {v.min():.2f}\nMáx: {v.max():.2f}")
                else:
                    st.warning(f"Dado de {l} ausente na planilha.")

    with tabs[1]: # ABA VRT COM FÓSFORO E VALIDAÇÃO
        if st.button("🗺️ PROCESSAR VRT"): st.session_state['vrt_ok'] = True
        
        if st.session_state['vrt_ok']:
            vrt_list = [('rec_calcario', 'Calcário', sb['calc']['pr']), 
                        ('rec_fosforo', 'Fosfatado', sb['fosf']['pr']), 
                        ('rec_potassio', 'Potássico', sb['pot']['pr']), 
                        ('rec_gesso', 'Gesso', sb['gesso']['pr'])]
            
            for c, l, pr in vrt_list:
                if c in df_res.columns:
                    c_m, c_i = st.columns([3, 1])
                    fig = plot_satelite_v43(df_res, c, f"Recomendação {l}", poly_obj)
                    if fig:
                        c_m.plotly_chart(fig, use_container_width=True)
                        v = df_res[c].dropna()
                        custo = (v.mean() / 1000) * pr
                        c_i.markdown(f"<div class='kpi-card'><span class='kpi-lbl'>CUSTO MÉDIO / HA</span><br><span class='kpi-val'>R$ {custo:.2f}</span></div>", unsafe_allow_html=True)
                else:
                    st.error(f"Não foi possível calcular VRT de {l}. Verifique os dados de entrada.")

    with tabs[2]: # EXPORTAÇÃO BLINDADA
        st.subheader("Gerar Arquivos para Campo")
        btn_pdf, btn_zip = st.columns(2)
        
        # PDF
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, f"RELATORIO TRIADE - {sb['meta']['prod']}", ln=True, align='C')
        pdf.ln(10); pdf.set_font("Helvetica", '', 12)
        pdf.cell(0, 10, f"Fazenda: {sb['meta']['faz']} | Talhao: {sb['meta']['tal']}", ln=True)
        pdf.cell(0, 10, "Relatório processado seguindo o Protocolo V43.", ln=True)
        pdf_bytes = bytes(pdf.output()) 
        btn_pdf.download_button("📄 Baixar PDF", data=pdf_bytes, file_name="Relatorio.pdf", mime="application/pdf")
        
        # ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for m in ["JOHN_DEERE", "TRIMBLE", "HORSCH", "CASE", "STARA"]:
                z.writestr(f"{m}/Prescricao_{sb['meta']['tal']}.csv", df_res.to_csv(index=False))
        btn_zip.download_button("📦 Baixar ZIP", data=buf.getvalue(), file_name="Triade_VRT.zip", mime="application/zip")
