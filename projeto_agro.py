import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
import base64
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Tríade Agro Estratégica v43", layout="wide", page_icon="🌱")

# --- CSS CUSTOMIZADO (UX PREMIUM TRÍADE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }
    .stApp { background-color: #f4f7f6; }
    .kpi-card {
        background-color: #ffffff; padding: 25px; border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center;
        border-bottom: 4px solid #1e3d59;
    }
    .kpi-value { font-size: 32px; font-weight: 700; color: #1e3d59; margin-bottom: 5px; }
    .kpi-label { font-size: 14px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 1px; }
    .section-header { color: #1e3d59; border-left: 5px solid #1e3d59; padding-left: 15px; margin-top: 25px; }
    </style>
    """, unsafe_allow_html=True)

# --- GERADOR DE RELATÓRIO PDF (PADRÃO A4 / 2cm MARGENS) ---
class TriadePDF(FPDF):
    def header(self):
        try: self.image("LogoTriadeagro.png.png", 10, 8, 40)
        except: pass
        self.ln(20)

def gerar_pdf_v43(df_res, produtor, area_total):
    pdf = TriadePDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"Relatório Técnico: {produtor}", ln=True)
    pdf.set_font("helvetica", "", 12)
    pdf.multi_cell(0, 7, "Metodologia: Rooting profundo e reducao de aluminio via gessagem e calagem atomica.")
    pdf.ln(10)
    # Tabela de Resultados
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(20, 8, "ID", 1); pdf.cell(40, 8, "Calcario (t/ha)", 1); pdf.cell(40, 8, "Gesso (kg/ha)", 1); pdf.ln()
    pdf.set_font("helvetica", "", 10)
    for _, row in df_res.iterrows():
        pdf.cell(20, 8, str(row['id']), 1); pdf.cell(40, 8, str(row['REC_CALCARIO']), 1); pdf.cell(40, 8, str(row['REC_GESSO']), 1); pdf.ln()
    return pdf.output()

# --- MOTOR AGRONÔMICO (REGRAS DE OURO TRÍADE) ---
def motor_calculo_v43(df
