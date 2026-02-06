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
    df = df.rename(columns=renomear)
    cols = ['Ca','Mg','K','P','Prem','Argila','CTC','lat','lon']
    for c in cols:
        if c in df.columns:
            if df[c].dtype == 'object': df[c] = df[c].str.replace(',','.').astype(float)
            else: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df

def calc_vrt(df, prod, ca_alvo, mg_alvo, cao, mgo, prnt, p_exp, p_teor, k_alvo, k_exp, k_teor, g_fat, g_min, g_max, nc_vals):
    d = df.copy()
    # Calagem
    if all(x in d.columns for x in ['Ca','Mg','CTC']):
        nc_ca, nc_mg = d['CTC']*(ca_alvo/100), d['CTC']*(mg_alvo/100)
        d['Dose_Calcario'] = np.maximum((nc_ca - d['Ca'])/max((cao*10/560)*(prnt/100),0.001), (nc_mg - d['Mg'])/max((mgo*10/403)*(prnt/100),0.001)).clip(0).round(2)
    else: d['Dose_Calcario'] = 0.0
    
    # Fosforo (Tabela Fixa)
    if 'Prem' in d.columns and 'P' in d.columns:
        c = [(d['Prem']<=4), (d['Prem']<=10), (d['Prem']<=19), (d['Prem']<=30), (d['Prem']>30)]
        v = [nc_vals['n1'], nc_vals['n2'], nc_vals['n3'], nc_vals['n4'], nc_vals['n5']]
        nc = np.select(c, v, default=nc_vals['n5'])
        fct = (56.5 * d['Prem']**-0.52).clip(4,40)
        d['NC_Tabular'] = nc
        d['Dose_P2O5_Kg'] = (((np.where(nc>d['P'],(nc-d['P'])*fct,0)) + (prod*p_exp)) / (p_teor/100)).round(0)
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

def plot_map(df, col, title, geojson):
    try: p = df.pivot_
