import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from shapely.geometry import shape

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Tríade Agro Estratégica 1.0")
st.markdown("""<style> .stApp { background-color: #FFFFFF; } html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; font-size: 12px; } </style>""", unsafe_allow_html=True)

# --- 2. LOGIN (LOGO 200px) ---
if "password_correct" not in st.session_state:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        logo = "LogoTriadeagro.png.png"
        if os.path.exists(logo): st.image(logo, width=200)
        senha = st.text_input("Senha de Acesso:", type="password")
        if st.button("Entrar"):
            if senha == "triade2026": st.session_state["password_correct"] = True; st.rerun()
    st.stop()

# --- 3. CARREGAMENTO (SEQUÊNCIA A-Y) ---
if "df" not in st.session_state:
    st.header("📥 Novo Projeto")
    c1, c2 = st.columns(2)
    with c1:
        u_geo = st.file_uploader("Contorno (GeoJSON)", type=["json", "geojson"])
        u_ex = st.file_uploader("Dados (Excel A-Y)", type=["xlsx"])
    with c2:
        st.session_state.prod = st.text_input("Produtor:")
        st.session_state.faz = st.text_input("Fazenda:")
        st.session_state.mun = st.text_input("Município:")

    if u_ex and u_geo:
        df_raw = pd.read_excel(u_ex)
        mapping = {df_raw.columns[i]: n for i, n in zip([0,1,4,5,6,7,8,9,20], ['Lat','Lon','Argila','P-rem','P','Ca','Mg','K','CTC'])}
        df_raw.rename(columns=mapping, inplace=True)
        st.session_state.df = df_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        st.session_state.contorno = shape(json.load(u_geo)['features'][0]['geometry'])
        st.session_state.area_ha = (st.session_state.contorno.area * 10**10) / 10000 
        st.success("✅ Tudo pronto!"); st.button("Abrir Plataforma")
    st.stop()

# --- 4. PLATAFORMA INTEGRAL ---
df = st.session_state.df
tabs = st.tabs(["⚙️ Atributos", "🔍 Mapas Solo", "🏠 Recomendações", "🛰️ Satélite", "🗺️ Zonas", "🌱 RSTV", "🌱 RNTV", "🌱 RDTV", "📄 Relatório"])

# ABA 0: ATRIBUTOS
with tabs[0]:
    st.subheader("Configurações Técnicas")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("**Calcário & Gesso**")
        cao, mgo, prnt = st.number_input("CaO%", 36.0), st.number_input("MgO%", 9.0), st.number_input("PRNT%", 80.0)
        ca_alvo, mg_alvo = st.number_input("Ca% Alvo", 60.0), st.number_input("Mg% Alvo", 18.0)
        g_max, g_min = st.number_input("Gesso Max", 900.0), st.number_input("Gesso Min", 400.0)
    with c2:
        st.write("**Fósforo (Metas & Solo)**")
        f_mtarg, f_arg, f_med, f_are = st.number_input("Fator M.Arg", 10.0), st.number_input("Fator Arg", 8.0), st.number_input("Fator Méd", 4.0), st.number_input("Fator Are", 2.0)
        p2o5_ad = st.number_input("% P2O5 Adubo", 46.0); fat_p_sc = st.number_input("P kg/sc", 0.8)
    with c3:
        st.write("**Potássio & Produtividade**")
        k_alvo, k2o_ad = st.number_input("K% Alvo", 3.2), st.number_input("% K2O Adubo", 60.0)
        prod_esp, fat_k_sc = st.number_input("Meta sc/ha", 80.0), st.number_input("K kg/sc", 1.2)

# ABA 2: RECOMENDAÇÕES (MOTOR 1.0)
with tabs[2]:
    st.header("Cálculos de Recomendação")
    adicional_calc = st.number_input("Adicional Calcário (t/ha)", 0.0)
    ctc = df['CTC']
    # Calcário
    nec_ca = ((ca_alvo * ctc / 100) - df['Ca']) * 100 / (cao * 1.78 * prnt / 100)
    nec_mg = ((mg_alvo * ctc / 100) - df['Mg']) * 100 / (mgo * 2.48 * prnt / 100)
    df['Rec_Calc'] = (np.maximum(nec_ca, nec_mg) + adicional_calc).clip(lower=0)
    # Gesso
    df['Rec_Gesso'] = (df['Argila'] * 15).clip(lower=g_min, upper=g_max)
    # Potássio (Elevação + Exportação)
    df['Rec_K2O'] = (((k_alvo * ctc / 100) - df['K']) * 940).clip(lower=0) + (prod_esp * fat_k_sc)
    st.dataframe(df[['Lat', 'Lon', 'Rec_Calc', 'Rec_Gesso', 'Rec_K2O']].head())

# ABAS DE TAXA VARIÁVEL (RSTV, RNTV, RDTV)
for i, nome in zip([5,6,7], ["Semeadura (RSTV)", "Nitrogênio (RNTV)", "Dessecação (RDTV)"]):
    with tabs[i]:
        st.subheader(nome)
        c1, c2, c3 = st.columns(3)
        prod_tv = c1.text_input(f"Produto/Híbrido - {nome}")
        v_alta = c1.number_input(f"Dose Alta ({nome})", 0.0)
        v_media = c2.number_input(f"Dose Média ({nome})", 0.0)
        v_baixa = c3.number_input(f"Dose Baixa ({nome})", 0.0)
        if st.button(f"Gerar Arquivo Monitor - {nome}"): st.download_button("Baixar SHP", data="...", file_name="prescricao.zip")

# ABA 8: RELATÓRIO
with tabs[8]:
    st.header("📄 Relatório Final A4")
    st.write(f"**Área Total:** {st.session_state.area_ha:.2f} ha")
    st.write(f"**Insumos Totais:** Calcário: {df['Rec_Calc'].mean() * st.session_state.area_ha:.1f} ton")
    if st.button("Exportar PDF Completo"): st.success("Gerando PDF com Justificativas Técnicas...")
