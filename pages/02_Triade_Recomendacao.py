import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

def renderizar_curvas_calibracao():
    st.markdown("### 🛠️ Validação Visual das Regressões")
    st.info("Este gráfico simula o comportamento da 5ª Aproximação suavizada (Regressão) para toda a faixa de P-rem.")

    # 1. Gerar dados simulados (P-rem de 1 a 70 com passo de 0.5)
    x_prem = np.linspace(1, 70, 140)

    # 2. Aplicar as Equações (Coeficientes Padrão)
    # Nível Crítico (NC): Alvo de P a atingir
    y_nc = 8.8 + (0.76 * x_prem)
    y_nc = np.clip(y_nc, 8.0, 60.0) # Travas de segurança agronômica

    # Fator Capacidade Tampão (FCT): Kg P2O5 para subir 1 ppm
    y_fct = 56.5 * (x_prem ** -0.52)
    y_fct = np.clip(y_fct, 5.0, 40.0) # Travas de segurança

    # 3. Criar o Gráfico com Eixo Duplo (Dual Axis)
    fig = go.Figure()

    # Linha 1: Nível Crítico (Sobe com P-rem)
    fig.add_trace(go.Scatter(
        x=x_prem, 
        y=y_nc,
        name="Nível Crítico (Alvo mg/dm³)",
        line=dict(color='green', width=3),
        yaxis="y1"
    ))

    # Linha 2: Fator Tampão (Desce com P-rem)
    fig.add_trace(go.Scatter(
        x=x_prem, 
        y=y_fct,
        name="Fator Tampão (kg P2O5/ppm)",
        line=dict(color='red', width=3, dash='dot'),
        yaxis="y2" # Eixo secundário
    ))

    # 4. Layout Otimizado (Seguindo seus protocolos de interface)
    fig.update_layout(
        title="Dinâmica do Fósforo: P-rem vs. Alvo vs. Tampão",
        xaxis_title="Teor de P-rem (mg/L)",
        yaxis=dict(
            title="Nível Crítico (mg/dm³)",
            titlefont=dict(color="green"),
            tickfont=dict(color="green")
        ),
        yaxis2=dict(
            title="Fator Tampão (FCT)",
            titlefont=dict(color="red"),
            tickfont=dict(color="red"),
            overlaying="y",
            side="right"
        ),
        legend=dict(x=0.01, y=0.99),
        hovermode="x unified",
        margin=dict(l=20, r=20, t=50, b=20),
        height=450
    )

    # Renderização com Key única para não conflitar com outros gráficos
    st.plotly_chart(fig, use_container_width=True, key="chart_validacao_fosforo")

# --- Para testar, basta chamar a função dentro do seu app ---
# renderizar_curvas_calibracao()
