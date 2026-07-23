"""
pages/cedears.py — Análisis de CEDEARs: valor implícito vs precio ARS.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core
import cedear_mapper

BG_DARK = "#0f1117"
BG_CARD = "#1e2130"
COLOR_VERDE   = "#00c896"
COLOR_ROJO    = "#f74f4f"
COLOR_AZUL    = "#4f8ef7"
COLOR_NARANJA = "#f7a34f"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _badge_estado(estado: str) -> str:
    if "Barato" in estado:
        return f'<span style="background:{COLOR_VERDE};color:#000;padding:2px 8px;border-radius:4px;font-size:12px">{estado}</span>'
    if "Caro" in estado:
        return f'<span style="background:{COLOR_ROJO};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{estado}</span>'
    return f'<span style="background:#555;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{estado}</span>'

def _grafico_diferencia(df: pd.DataFrame) -> go.Figure:
    df_ok = df.dropna(subset=["Diferencia (%)"]).copy()
    df_ok = df_ok.sort_values("Diferencia (%)")
    colors = [COLOR_VERDE if v < 0 else COLOR_ROJO for v in df_ok["Diferencia (%)"]]
    fig = go.Figure(go.Bar(
        x=df_ok["Ticker"],
        y=df_ok["Diferencia (%)"],
        marker_color=colors,
        text=df_ok["Diferencia (%)"].apply(lambda v: f"{v:+.1f}%"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Diferencia: %{y:+.1f}%<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#888")
    fig.update_layout(
        title="Diferencia % Precio CEDEAR vs Valor Implícito",
        yaxis_title="Diferencia (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=380
    )
    return fig

def _grafico_comparacion(df: pd.DataFrame) -> go.Figure:
    df_ok = df.dropna(subset=["Valor implícito (ARS)", "Precio CEDEAR (ARS)"]).copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Valor implícito (ARS)", x=df_ok["Ticker"],
        y=df_ok["Valor implícito (ARS)"], marker_color=COLOR_AZUL,
        hovertemplate="<b>%{x}</b><br>Implícito: $%{y:,.0f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        name="Precio CEDEAR (ARS)", x=df_ok["Ticker"],
        y=df_ok["Precio CEDEAR (ARS)"], marker_color=COLOR_NARANJA,
        hovertemplate="<b>%{x}</b><br>Precio: $%{y:,.0f}<extra></extra>"
    ))
    fig.update_layout(
        barmode="group",
        title="Precio CEDEAR vs Valor Implícito (ARS)",
        yaxis_title="Precio (ARS)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=380
    )
    return fig

# ── RENDER PRINCIPAL ──────────────────────────────────────────────────────────
def render():
    st.title("🇦🇷 Análisis de CEDEARs")
    st.markdown("Compará el precio de mercado de cada CEDEAR contra su valor implícito calculado con el dólar CCL.")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")

        # CCL
        st.markdown("**Dólar CCL**")
        usar_ccl_auto = st.checkbox("Obtener CCL automáticamente", value=True)
        if usar_ccl_auto:
            with st.spinner("Obteniendo CCL..."):
                ccl = core.obtener_dolar_ccl()
            st.success(f"CCL: **${ccl:,.0f}**")
        else:
            ccl = st.number_input("CCL manual (ARS/USD)", min_value=100.0,
                                  max_value=10000.0, value=1200.0, step=10.0)

        # CSV de ratios
        st.markdown("**Ratios CEDEAR**")
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        csv_path = os.path.join(data_dir, "ratios_cedear.csv")
        if os.path.exists(csv_path):
            ratios = core.cargar_ratios_cedear(csv_path)
            st.success(f"✅ {len(ratios)} ratios cargados desde CSV")
        else:
            st.warning("⚠️ No se encontró ratios_cedear.csv en data/")
            uploaded = st.file_uploader("Subir ratios_cedear.csv", type="csv")
            if uploaded:
                import io
                df_up = pd.read_csv(io.BytesIO(uploaded.read()))
                df_up.to_csv(csv_path, index=False)
                ratios = core.cargar_ratios_cedear(csv_path)
                st.success(f"✅ {len(ratios)} ratios cargados")
            else:
                ratios = {}

        # Tickers a analizar
        st.markdown("**Tickers a analizar**")
        # Fuente de tickers
        fuente_ced = st.radio(
            "Fuente de tickers",
            ["📝 Ingresar manualmente", "💼 Desde Mi Cartera"],
            index=0, key="ced_fuente"
        )

        tickers_input = ""
        if fuente_ced == "💼 Desde Mi Cartera":
            try:
                import cartera_db as cdb
                df_carteras = cdb.listar_carteras()
                if not df_carteras.empty:
                    opciones = {f"{r['nombre']} ({r['moneda_base']})": r['id']
                                for _, r in df_carteras.iterrows()}
                    opciones["🔀 Todas las carteras"] = -1
                    sel_c = st.selectbox("Cartera", list(opciones.keys()), key="ced_cart_sel")
                    cid   = opciones[sel_c]
                    if cid == -1:
                        tickers_set = set()
                        for _, r in df_carteras.iterrows():
                            dp = cdb.listar_posiciones(r['id'])
                            if not dp.empty:
                                # Solo CEDEARs (es_cedear=1) o todos
                                tickers_set.update(dp["ticker"].tolist())
                        tickers_input = ", ".join(list(tickers_set))
                    else:
                        dp = cdb.listar_posiciones(cid)
                        if not dp.empty:
                            tickers_input = ", ".join(dp["ticker"].tolist())
                    if tickers_input:
                        st.success(f"✅ Tickers: {tickers_input}")
                else:
                    st.warning("Sin carteras creadas")
            except Exception as e:
                st.warning(f"Error: {e}")

        if fuente_ced == "📝 Ingresar manualmente" or not tickers_input:
            tickers_input = st.text_area(
                "Tickers (separados por coma)",
                value=tickers_input or "YPFD, BMA, GGAL, PAMP, TECO2, CEPU, BBAR, EDN, IRSA",
                height=100
            )
        analizar = st.button("▶️ Analizar CEDEARs", type="primary", use_container_width=True)

    if not analizar:
        # Panel informativo
        st.info("👈 Configurá los parámetros y presioná **Analizar CEDEARs**.")

        st.markdown("---")
        st.markdown("### 📖 ¿Cómo se calcula el valor implícito?")
        st.latex(r"\text{Valor implícito (ARS)} = \frac{\text{Precio USD}}{\text{Ratio CEDEAR}} \times \text{CCL}")
        st.markdown("""
        - **Precio USD**: precio actual del activo subyacente en NYSE/NASDAQ
        - **Ratio CEDEAR**: cantidad de CEDEARs que equivalen a 1 acción subyacente (fuente: BYMA)
        - **CCL**: dólar contado con liquidación (tipo de cambio implícito)

        Si el **precio de mercado ARS < valor implícito** → el CEDEAR está **Barato** (oportunidad)
        Si el **precio de mercado ARS > valor implícito** → el CEDEAR está **Caro** (sobrevaluado)
        """)

        st.markdown("---")
        st.markdown("### ⚠️ Equivalencias corregidas")
        st.markdown("""
        | Ticker BYMA | Empresa | ADR NYSE | Nota |
        |-------------|---------|----------|------|
        | BYMA | Bolsas y Mercados Argentinos | ❌ Sin ADR | No confundir con BMA |
        | BMA | Banco Macro | ✅ BMA | Empresa distinta a BYMA |
        | YPFD | YPF SA | ✅ YPF | |
        | PAMP | Pampa Energía | ✅ PAM | |
        | TECO2 | Telecom Argentina | ✅ TEO | |
        | ALUA | Aluar Aluminio | ❌ Sin ADR | Solo BCBA |
        """)
        return

    # ── Análisis ──────────────────────────────────────────────────────────────
    tickers_raw = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    if not ratios:
        st.error("❌ No hay ratios CEDEAR cargados. Subí el archivo ratios_cedear.csv.")
        return

    resultados = []
    prog = st.progress(0)
    status = st.empty()

    for i, t in enumerate(tickers_raw):
        status.text(f"Analizando {t}...")
        try:
            res = core.analizar_cedear(t, ccl)
            resultados.append(res)
        except Exception as e:
            resultados.append({
                "Ticker": t, "Nombre": "—", "Tipo": cedear_mapper.clasificar_ticker(t),
                "Precio USD": None, "Ratio CEDEAR": core.get_ratio_cedear(t),
                "Dólar CCL": ccl, "Valor implícito (ARS)": None,
                "Precio CEDEAR (ARS)": None, "Diferencia (%)": None,
                "Estado": "⚪ Sin datos"
            })
        prog.progress((i+1)/len(tickers_raw))

    prog.empty()
    status.empty()

    df = pd.DataFrame(resultados)

    # ── Métricas resumen ──────────────────────────────────────────────────────
    st.markdown("---")
    n_baratos = (df["Estado"].str.contains("Barato")).sum()
    n_caros   = (df["Estado"].str.contains("Caro")).sum()
    n_sin     = (df["Estado"].str.contains("Sin datos")).sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💱 Dólar CCL", f"${ccl:,.0f}")
    c2.metric("🟢 Baratos",   n_baratos)
    c3.metric("🔴 Caros",     n_caros)
    c4.metric("⚪ Sin datos", n_sin)

    # ── Tabla principal ───────────────────────────────────────────────────────
    st.markdown("### 📋 Resultados")

    def color_estado(val):
        if "Barato" in str(val): return "color: #00c896; font-weight: bold"
        if "Caro"   in str(val): return "color: #f74f4f; font-weight: bold"
        return "color: #888"

    def color_dif(val):
        try:
            v = float(val)
            return f"color: {'#00c896' if v < 0 else '#f74f4f'}; font-weight: bold"
        except Exception:
            return ""

    cols_mostrar = ["Ticker","Nombre","Tipo","Precio USD","Ratio CEDEAR",
                    "Valor implícito (ARS)","Precio CEDEAR (ARS)","Diferencia (%)","Estado"]
    df_show = df[cols_mostrar].copy()

    st.dataframe(
        df_show.style
            .map(color_estado, subset=["Estado"])
            .map(color_dif,    subset=["Diferencia (%)"])
            .format({
                "Precio USD":             lambda v: f"${v:,.2f}" if v else "—",
                "Ratio CEDEAR":           lambda v: f"{v}" if v else "—",
                "Valor implícito (ARS)":  lambda v: f"${v:,.2f}" if v else "—",
                "Precio CEDEAR (ARS)":    lambda v: f"${v:,.2f}" if v else "—",
                "Diferencia (%)":         lambda v: f"{v:+.1f}%" if v else "—",
            }),
        use_container_width=True, hide_index=True
    )

    # ── Gráficos ──────────────────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["📊 Diferencia %", "💰 Precio vs Implícito"])
    with tab1:
        if df["Diferencia (%)"].notna().any():
            st.plotly_chart(_grafico_diferencia(df), use_container_width=True)
        else:
            st.info("No hay datos suficientes para graficar.")
    with tab2:
        if df["Valor implícito (ARS)"].notna().any():
            st.plotly_chart(_grafico_comparacion(df), use_container_width=True)
        else:
            st.info("No hay datos suficientes para graficar.")

    # ── Detalle por ticker ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔍 Detalle por ticker")
    ticker_sel = st.selectbox("Seleccioná un ticker", df["Ticker"].tolist())
    row = df[df["Ticker"] == ticker_sel].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Precio USD",            f"${row['Precio USD']:,.2f}"           if row['Precio USD']           else "—")
    c2.metric("Valor implícito (ARS)", f"${row['Valor implícito (ARS)']:,.2f}" if row['Valor implícito (ARS)'] else "—")
    c3.metric("Precio CEDEAR (ARS)",   f"${row['Precio CEDEAR (ARS)']:,.2f}"  if row['Precio CEDEAR (ARS)']  else "—",
              delta=f"{row['Diferencia (%)']:+.1f}%" if row['Diferencia (%)'] else None)

    st.markdown(f"**Estado:** {row['Estado']}  |  **Tipo:** {row['Tipo']}  |  **Ratio:** {row['Ratio CEDEAR']}")
    st.caption(f"Fórmula: ${row['Precio USD'] or '?'} ÷ {row['Ratio CEDEAR'] or '?'} × ${ccl:,.0f} CCL = ${row['Valor implícito (ARS)'] or '?'} ARS")

    # ── Exportar ──────────────────────────────────────────────────────────────
    st.markdown("---")
    from io import BytesIO
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Analisis CEDEAR", index=False)
    st.download_button(
        "⬇️ Descargar Excel",
        data=buf.getvalue(),
        file_name=f"cedears_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )