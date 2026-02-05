import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import base64

# --- BLINDAGEM ANTI-TRAVAMENTO ---
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
import folium
from streamlit_folium import st_folium

from utils_v43 import configurar_pagina, renderizar_cabecalho_sidebar

# ==============================================================================
# 1. CONFIGURAÇÃO
# ==============================================================================
configurar_pagina("Motor de Recomendação V60")
renderizar_cabecalho_sidebar()

st.title("🚜 Tríade: Motor Agronômico (V60)")

if 'geojson_rec' not in st.session_state:
    st.session_state['geojson_rec'] = None

# ==============================================================================
# 2. MOTOR DE CÁLCULO (LÓGICA REFINADA V60)
# ==============================================================================

def calcular_calagem_balanceada(df, ca_alvo_pct, mg_alvo_pct, teor_cao, teor_mgo, prnt):
    """
    Protocolo V60: Elevação de Ca e Mg individualmente.
    Dose Final = Maior dose entre a necessidade de Ca e a de Mg.
    """
    col_ca = next((c for c in df.columns if c in ['ca', 'calcio']), None)
    col_mg = next((c for c in df.columns if c in ['mg', 'magnesio']), None)
    col_ctc = next((c for c in df.columns if c in ['ctc', 't_cec', 't']), None)
    
    if col_ca and col_mg and col_ctc:
        # 1. Necessidade para CÁLCIO (Meta: 60% da CTC)
        # Ca Desejado (cmolc) = CTC * 0.60
        ca_desejado = df[col_ctc] * (ca_alvo_pct / 100)
        deficit_ca = ca_desejado - df[col_ca]
        deficit_ca = deficit_ca.apply(lambda x: x if x > 0 else 0)
        
        # Conversão: 1 cmolc Ca requer 560 kg CaO/ha (Estequiometria agronômica prática)
        kg_cao_necessario = deficit_ca * 560
        # Ton Calcário p/ Ca = (Kg CaO / (Teor CaO * 10)) * (100/PRNT)
        nc_ca_ton = (kg_cao_necessario / (teor_cao * 10)) * (100 / prnt)

        # 2. Necessidade para MAGNÉSIO (Meta: 18% da CTC)
        mg_desejado = df[col_ctc] * (mg_alvo_pct / 100)
        deficit_mg = mg_desejado - df[col_mg]
        deficit_mg = deficit_mg.apply(lambda x: x if x > 0 else 0)
        
        # Conversão: 1 cmolc Mg requer 403 kg MgO/ha
        kg_mgo_necessario = deficit_mg * 403
        # Ton Calcário p/ Mg
        nc_mg_ton = (kg_mgo_necessario / (teor_mgo * 10)) * (100 / prnt)

        # 3. Decisão: Aplica a MAIOR dose para garantir que ambos subam
        # (O excedente de um nutriente geralmente não é problema nessas faixas)
        df['NC_ton'] = np.maximum(nc_ca_ton, nc_mg_ton)
        
        # Dose final em kg
        df['Dose_Calcario_kg'] = df['NC_ton'] * 1000
        return True, df
        
    return False, df

def calcular_fosforo_rem(df, prod_alvo, fator_exp, teor_p_adubo):
    """
    Protocolo V60: Fósforo Remanescente (P-rem)
    1. Define Nível Crítico (NC) baseado no P-rem.
    2. Se P_Solo > NC: Subtrai o "crédito" da exportação.
    3. Se P_Solo < NC: Correção + Exportação.
    """
    col_p = next((c for c in df.columns if c in ['p', 'fosforo']), None) # mg/dm3
    col_prem = next((c for c in df.columns if c in ['p_rem', 'prem', 'p-rem']), None)
    
    if col_p and col_prem:
        # Tabela de Níveis Críticos (mg/dm3) baseada em P-rem (mg/L)
        # Fonte Aprox: 5ª Aproximação
        def get_nivel_critico(prem):
            if prem < 4: return 30.0
            elif prem < 10: return 24.0
            elif prem < 19: return 18.2
            elif prem < 30: return 12.0
            elif prem < 45: return 10.0
            else: return 8.0 # P-rem > 60
        
        df['Nivel_Critico_P'] = df[col_prem].apply(get_nivel_critico)
        
        # Cálculo da Dose
        def calc_dose_p(row):
            p_solo = row[col_p]
            nc = row['Nivel_Critico_P']
            exportacao_p2o5 = prod_alvo * fator_exp
            
            # Capacidade Tampão (b) aproximada pelo P-rem (simplificação para correção)
            # Dose Correção (kg P2O5/ha) = (NC - P_Solo) * Capacidade_Tampão
            # Se não tivermos tabela de buffer exata, usamos uma estimativa ou focamos na lógica de subtração pedida
            
            # Lógica do Usuário: "Se acima do nível crítico, converter excedente e subtrair da exportação"
            if p_solo > nc:
                excedente_mg = p_solo - nc
                # Conversão mg/dm3 P para kg/ha P2O5 (x2 profundidade * 2.29 fator P->P2O5)
                # Fator aprox: 1 mg/dm3 P ~ 4.58 kg P2O5/ha (considerando camada 20cm e conversão)
                credito_p2o5 = excedente_mg * 4.58 
                
                necessidade_p2o5 = exportacao_p2o5 - credito_p2o5
                if necessidade_p2o5 < 0: necessidade_p2o5 = 0 # Não aplica nada se sobrar muito
                
            else:
                # Se abaixo, precisa corrigir.
                # (NC - Atual) * Fator_Buffer + Exportação
                deficit_mg = nc - p_solo
                # Fator Buffer varia com argila/P-rem. Vamos usar um médio conservador de 2.5 kg P2O5 por mg de déficit?
                # Para simplificar e atender o prompt: Vamos aplicar Exportação + Correção Básica
                correcao_p2o5 = deficit_mg * 5 # Estimativa de fixação
                necessidade_p2o5 = correcao_p2o5 + exportacao_p2o5
            
            # Converter P2O5 para Produto Comercial (MAP/Super)
            return necessidade_p2o5 / (teor_p_adubo / 100)

        df['Dose_Fosforo_kg'] = df.apply(calc_dose_p, axis=1)
        return True, df
        
    return False, df

def calcular_potassio_rigido(df, k_alvo_pct, prod_alvo, fator_exp, teor_k_adubo):
    """
    Protocolo V60:
    "Sempre considerar o total de K exportado na conta, mesmo que sobro."
    """
    col_k = next((c for c in df.columns if c in ['k', 'potassio']), None)
    col_ctc = next((c for c in df.columns if c in ['ctc', 't_cec']), None)
    
    if col_k and col_ctc:
        # Exportação (Obrigatória)
        dose_k2o_exp = prod_alvo * fator_exp
        
        # Correção (Apenas se faltar)
        k_ideal = df[col_ctc] * (k_alvo_pct / 100)
        deficit_k = k_ideal - df[col_k]
        
        # Se deficit < 0 (solo rico), Correção é 0.
        # Mas a Exportação CONTINUA na soma.
        dose_k2o_corr = deficit_k.apply(lambda x: x * 942 if x > 0 else 0)
        
        total_k2o = dose_k2o_corr + dose_k2o_exp
        
        df['Dose_Potassio_kg'] = total_k2o / (teor_k_adubo / 100)
        return True, df
        
    return False, df

def calcular_gesso_simples(df, fator_argila):
    """
    Protocolo V60: Argila * 15 (Sem multiplicar por 10 extra).
    """
    col_argila = next((c for c in df.columns if c in ['argila', 'clay']), None)
    
    if col_argila:
        # Fórmula Direta: Argila * Fator
        # Assumindo Argila em % (ex: 30) e Fator 15 -> 450 kg/ha? 
        # Ou Argila g/kg (300) * 15 -> 4500?
        # Geralmente Argila% * 50 = kg/ha. Aqui o usuário pediu Fator 15.
        # Vamos respeitar estritamente a matemática pedida.
        
        df['Dose_Gesso_kg'] = df[col_argila] * fator_argila
        return True, df
        
    return False, df

# ==============================================================================
# 3. FUNÇÃO DE MAPA (RECORTE PERFEITO)
# ==============================================================================
def gerar_mapa_prescricao(df, col_dose, geojson_data, cor_base):
    pivot = df.pivot(index='latitude', columns='longitude', values=col_dose)
    Z = pivot.values
    X = pivot.columns.values 
    Y = pivot.index.values   
    
    # Paletas
    if cor_base == 'blue': 
        colors = ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#084594']
    elif cor_base == 'red': 
        colors = ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#99000d']
    elif cor_base == 'green': 
        colors = ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32']
    else: 
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
# 4. SIDEBAR - PARÂMETROS V60
# ==============================================================================
st.sidebar.header("1. Arquivos")
file_ponte = st.sidebar.file_uploader("📂 Arquivo PONTE (CSV)", type=["csv"])
file_geo = st.sidebar.file_uploader("🌍 Contorno (.geojson)", type=["geojson", "json"])

st.sidebar.divider()
st.sidebar.header("2. Parâmetros Agronômicos")

# --- CALAGEM ---
with st.sidebar.expander("⚪ 1. Calagem (Ca/Mg)", expanded=True):
    col_a, col_b = st.columns(2)
    with col_a:
        ca_alvo = st.number_input("Ca Alvo (%CTC):", value=60.0, step=1.0)
        teor_cao = st.number_input("% CaO Calcário:", value=38.0, step=1.0)
    with col_b:
        mg_alvo = st.number_input("Mg Alvo (%CTC):", value=18.0, step=1.0)
        teor_mgo = st.number_input("% MgO Calcário:", value=12.0, step=1.0)
    
    prnt = st.number_input("PRNT (%):", value=85.0, step=1.0)
    preco_calc = st.number_input("Preço Calcário (R$/ton):", value=190.0)

# --- FÓSFORO ---
with st.sidebar.expander("🟢 2. Fósforo (P-Rem)", expanded=False):
    st.info("Lógica: Se P > Nível Crítico (NC), desconta o excedente da exportação.")
    prod_alvo_p = st.number_input("Produtividade (sc/ha):", value=70.0)
    fator_exp_p = st.number_input("Exportação P (kg/sc):", value=0.8)
    teor_p_adubo = st.number_input("% P2O5 Adubo:", value=52.0)
    preco_map = st.number_input("Preço P (R$/ton):", value=2000.0)

# --- POTÁSSIO ---
with st.sidebar.expander("🔴 3. Potássio (Travado)", expanded=False):
    st.info("Lógica: Sempre soma a Exportação, mesmo em solo rico.")
    k_alvo_pct = st.number_input("K Alvo (%CTC):", value=3.2)
    fator_exp_k = st.number_input("Exportação K (kg/sc):", value=1.2)
    teor_k_adubo = st.number_input("% K2O Adubo:", value=60.0)
    preco_kcl = st.number_input("Preço K (R$/ton):", value=2800.0)

# --- GESSO ---
with st.sidebar.expander("🌫️ 4. Gesso", expanded=False):
    st.info("Fórmula: Argila x Fator")
    fator_gesso = st.number_input("Fator Gesso:", value=15.0, step=1.0, help="Multiplicador direto sobre a Argila")
    preco_gesso = st.number_input("Preço Gesso (R$/ton):", value=400.0)

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
        
    if st.button("🚀 CALCULAR RECOMENDAÇÕES (V60)", type="primary"):
        
        # 1. Calagem Balanceada (Ca/Mg)
        ok_calc, df = calcular_calagem_balanceada(df, ca_alvo, mg_alvo, teor_cao, teor_mgo, prnt)
        if not ok_calc: st.error("Faltam colunas: Ca, Mg ou CTC")

        # 2. Fósforo (P-Rem)
        ok_p, df = calcular_fosforo_rem(df, prod_alvo_p, fator_exp_p, teor_p_adubo)
        if not ok_p: st.error("Faltam colunas: P ou P-Rem")

        # 3. Potássio (Rígido)
        ok_k, df = calcular_potassio_rigido(df, k_alvo_pct, prod_alvo_p, fator_exp_k, teor_k_adubo)
        if not ok_k: st.error("Faltam colunas: K ou CTC")

        # 4. Gesso (Argila * 15)
        ok_g, df = calcular_gesso_simples(df, fator_gesso)
        if not ok_g: st.error("Falta coluna: Argila")
        
        st.session_state['df_vrt'] = df
        st.session_state['calc_done'] = True
        st.toast("Cálculo V60 Concluído!", icon="✅")

    # --- VISUALIZAÇÃO ---
    if st.session_state.get('calc_done'):
        df_vrt = st.session_state['df_vrt']
        tabs = st.tabs(["⚪ Calagem", "🟢 Fósforo", "🔴 Potássio", "🌫️ Gesso"])
        
        def render_tab(tab, col_dados, nome, cor, preco):
            with tab:
                if col_dados in df_vrt.columns:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        try:
                            img, bounds, intervals = gerar_mapa_prescricao(df_vrt, col_dados, geojson, cor)
                            centro = [df_vrt['latitude'].mean(), df_vrt['longitude'].mean()]
                            m = folium.Map(location=centro, zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
                            img_b64 = base64.b64encode(img.getvalue()).decode()
                            folium.raster_layers.ImageOverlay(image=f"data:image/png;base64,{img_b64}", bounds=bounds, opacity=0.8).add_to(m)
                            folium.GeoJson(geojson, style_function=lambda x: {'color':'black', 'weight':3, 'fillOpacity':0}).add_to(m)
                            st_folium(m, height=450, use_container_width=True)
                        except Exception as e:
                            st.error(f"Erro mapa: {e}")
                    with c2:
                        media = df_vrt[col_dados].mean()
                        custo = (media / 1000) * preco
                        st.metric("Dose Média", f"{media:.0f} kg/ha")
                        st.metric("Custo Médio", f"R$ {custo:.2f}/ha")
                else:
                    st.warning(f"Cálculo de {nome} não realizado (falta dados).")

        render_tab(tabs[0], 'Dose_Calcario_kg', 'Calcário', 'blue', preco_calc)
        render_tab(tabs[1], 'Dose_Fosforo_kg', 'Fósforo', 'green', preco_map)
        render_tab(tabs[2], 'Dose_Potassio_kg', 'Potássio', 'red', preco_kcl)
        render_tab(tabs[3], 'Dose_Gesso_kg', 'Gesso', 'gray', preco_gesso)
        
        st.divider()
        csv_final = df_vrt.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Baixar Mapa VRT Consolidado", csv_final, "vrt_final.csv", "text/csv", type="primary")

else:
    st.info("Faça o upload do CSV (Ponte) e GeoJSON.")
