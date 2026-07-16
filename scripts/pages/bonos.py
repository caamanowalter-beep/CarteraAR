"""
pages/bonos.py — Bonos soberanos argentinos y Obligaciones Negociables.
Muestra precios, TIR, duration y tipos de cambio (CCL, MEP, Oficial, Blue).
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import market_info as mi

BG_DARK      = "#0f1117"
BG_CARD      = "#1e2130"
COLOR_VERDE  = "#00c896"
COLOR_ROJO   = "#f74f4f"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA= "#f7a34f"
COLOR_GRIS   = "#6b7280"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _card_tc(nombre: str, valor: float | None, color: str, descripcion: str):
    val_str = f"${valor:,.2f}" if valor else "—"
    st.markdown(
        f'<div style="background:{BG_CARD};padding:14px 16px;border-radius:10px;'
        f'border-left:4px solid {color};margin-bottom:8px">'
        f'<div style="color:#aaa;font-size:11px">{nombre}</div>'
        f'<div style="color:{color};font-size:26px;font-weight:700">{val_str}</div>'
        f'<div style="color:#888;font-size:11px">{descripcion}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

def _grafico_tir(df: pd.DataFrame, titulo: str) -> go.Figure | None:
    df_ok = df.dropna(subset=["TIR"]).copy()
    if df_ok.empty:
        return None
    df_ok = df_ok.sort_values("TIR", ascending=False).head(15)
    colors = [COLOR_VERDE if m == "USD" else COLOR_AZUL
              for m in df_ok.get("Moneda", ["USD"] * len(df_ok))]
    fig = go.Figure(go.Bar(
        x=df_ok["Ticker"], y=df_ok["TIR"],
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df_ok["TIR"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>TIR: %{y:.2f}%<extra></extra>"
    ))
    fig.update_layout(
        title=titulo,
        yaxis_title="TIR (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=340,
        showlegend=False
    )
    return fig

# ── RENDER PRINCIPAL ──────────────────────────────────────────────────────────
def render():
    st.title("🏦 Bonos y Obligaciones Negociables")
    st.markdown("Tipos de cambio, bonos soberanos argentinos y ONs corporativas.")

    # ── Tipos de cambio ───────────────────────────────────────────────────────
    st.markdown("## 💱 Tipos de cambio")
    with st.spinner("Obteniendo tipos de cambio..."):
        tc = mi.obtener_tipos_cambio()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card_tc("CCL", tc.get("CCL"), COLOR_AZUL,
                 "Contado con liquidación")
    with c2:
        _card_tc("MEP", tc.get("MEP"), COLOR_VERDE,
                 "Dólar bolsa (MEP)")
    with c3:
        _card_tc("Oficial", tc.get("Oficial"), COLOR_NARANJA,
                 "Tipo de cambio oficial")
    with c4:
        _card_tc("Blue", tc.get("Blue"), COLOR_ROJO,
                 "Dólar informal")
    with c5:
        _card_tc("Cripto", tc.get("Cripto"), COLOR_GRIS,
                 "Dólar cripto (USDT)")

    # Brecha CCL vs Oficial
    if tc.get("CCL") and tc.get("Oficial"):
        brecha = (tc["CCL"] - tc["Oficial"]) / tc["Oficial"] * 100
        color_brecha = COLOR_ROJO if brecha > 30 else COLOR_NARANJA if brecha > 15 else COLOR_VERDE
        st.markdown(
            f'<div style="background:{BG_CARD};padding:10px 16px;border-radius:8px;'
            f'margin-top:8px;display:inline-block">'
            f'<span style="color:#aaa">Brecha CCL/Oficial: </span>'
            f'<span style="color:{color_brecha};font-weight:700;font-size:18px">'
            f'{brecha:+.1f}%</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── Tabs bonos y ON ───────────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["📊 Bonos Soberanos", "🏢 Obligaciones Negociables"])

    with tab1:
        st.markdown("### 📊 Bonos Soberanos Argentinos")
        st.caption("Fuentes: ArgentinaDatos · BYMA Open Data")

        with st.spinner("Obteniendo datos de bonos..."):
            df_bonos = mi.obtener_bonos_argentina()

        if df_bonos.empty:
            st.warning("No se pudieron obtener datos de bonos.")
        else:
            # Filtros
            c1, c2 = st.columns(2)
            moneda_fil = c1.multiselect(
                "Moneda", ["USD", "ARS"],
                default=["USD", "ARS"],
                key="fil_moneda_bonos"
            )
            tipo_fil = c2.multiselect(
                "Tipo",
                df_bonos["Tipo"].unique().tolist(),
                default=df_bonos["Tipo"].unique().tolist(),
                key="fil_tipo_bonos"
            )

            df_fil = df_bonos[
                df_bonos["Moneda"].isin(moneda_fil) &
                df_bonos["Tipo"].isin(tipo_fil)
            ].copy()

            # Tabla
            cols_show = [c for c in ["Ticker","Nombre","Precio","TIR","Duration","Moneda","Tipo","Fuente"]
                         if c in df_fil.columns]

            def color_tir(val):
                try:
                    v = float(val)
                    if v > 15:  return "color: #00c896; font-weight: bold"
                    if v > 8:   return "color: #f7a34f"
                    return "color: #f74f4f"
                except Exception:
                    return ""

            fmt = {}
            if "Precio"   in df_fil.columns: fmt["Precio"]   = lambda v: f"${v:,.2f}" if pd.notna(v) else "—"
            if "TIR"      in df_fil.columns: fmt["TIR"]      = lambda v: f"{v:.2f}%"  if pd.notna(v) else "—"
            if "Duration" in df_fil.columns: fmt["Duration"] = lambda v: f"{v:.2f}"   if pd.notna(v) else "—"

            st.dataframe(
                df_fil[cols_show].style
                    .map(color_tir, subset=["TIR"] if "TIR" in cols_show else [])
                    .format(fmt),
                use_container_width=True, hide_index=True
            )

            # Gráfico TIR
            fig = _grafico_tir(df_fil, "TIR por bono (verde=USD, azul=ARS)")
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            # Nota informativa
            st.info(
                "ℹ️ **Cómo interpretar la TIR**: "
                "Mayor TIR = mayor rendimiento pero también mayor riesgo. "
                "Los bonos USD Ley NY (GD) suelen tener menor riesgo legal que los Ley Arg (AL). "
                "Los bonos CER ajustan por inflación."
            )

    with tab2:
        st.markdown("### 🏢 Obligaciones Negociables Corporativas")
        st.caption("Fuente: BYMA Open Data")

        with st.spinner("Obteniendo ONs..."):
            df_on = mi.obtener_on_argentina()

        if df_on.empty:
            st.warning("No se pudieron obtener datos de ONs.")
        else:
            # Filtro por moneda
            moneda_on = st.multiselect(
                "Moneda", ["USD", "ARS"],
                default=["USD", "ARS"],
                key="fil_moneda_on"
            )
            df_on_fil = df_on[df_on["Moneda"].isin(moneda_on)].copy()

            cols_on = [c for c in ["Ticker","Emisor","Precio","TIR","Duration",
                                    "Moneda","Vencimiento","Tipo"]
                       if c in df_on_fil.columns]

            fmt_on = {}
            if "Precio"   in df_on_fil.columns: fmt_on["Precio"]   = lambda v: f"${v:,.2f}" if pd.notna(v) else "—"
            if "TIR"      in df_on_fil.columns: fmt_on["TIR"]      = lambda v: f"{v:.2f}%"  if pd.notna(v) else "—"
            if "Duration" in df_on_fil.columns: fmt_on["Duration"] = lambda v: f"{v:.2f}"   if pd.notna(v) else "—"

            def color_tir_on(val):
                try:
                    v = float(val)
                    if v > 10: return "color: #00c896; font-weight: bold"
                    if v > 6:  return "color: #f7a34f"
                    return "color: #aaa"
                except Exception:
                    return ""

            st.dataframe(
                df_on_fil[cols_on].style
                    .map(color_tir_on, subset=["TIR"] if "TIR" in cols_on else [])
                    .format(fmt_on),
                use_container_width=True, hide_index=True
            )

            fig_on = _grafico_tir(df_on_fil, "TIR por ON corporativa")
            if fig_on:
                st.plotly_chart(fig_on, use_container_width=True)

            st.info(
                "ℹ️ **Sobre las ONs**: Son deuda corporativa emitida por empresas argentinas. "
                "Generalmente ofrecen mayor TIR que los bonos soberanos del mismo plazo "
                "a cambio de mayor riesgo crediticio. "
                "Las ONs USD son una alternativa para dolarizar cartera dentro del sistema."
            )

    # ── Comparativa CCL vs MEP ────────────────────────────────────────────────
    if tc.get("CCL") and tc.get("MEP"):
        st.markdown("---")
        st.markdown("### 📊 CCL vs MEP — ¿Cuál usar?")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            **MEP (Dólar Bolsa)** — ${tc['MEP']:,.2f}
            - Operación 100% legal dentro del sistema financiero
            - Se opera comprando un bono en ARS y vendiéndolo en USD
            - Liquidación en 24-48hs
            - Sin límite de monto (con restricciones de parking)
            - Ideal para: dolarizar ahorros, comprar CEDEARs
            """)
        with col2:
            st.markdown(f"""
            **CCL (Contado con Liqui)** — ${tc['CCL']:,.2f}
            - Operación legal para empresas y personas
            - Se opera con acciones/bonos que cotizan en el exterior
            - Permite sacar divisas al exterior
            - Diferencia con MEP: {((tc['CCL']-tc['MEP'])/tc['MEP']*100):+.1f}%
            - Ideal para: transferir fondos al exterior, inversores sofisticados
            """)