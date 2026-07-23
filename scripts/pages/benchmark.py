"""
pages/benchmark.py — Comparación de la cartera vs benchmarks.
Compara el rendimiento de tu cartera contra SPY, QQQ, Merval y otros índices.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartera_db
import core

try:
    import auth as _auth
    AUTH_OK = True
except Exception:
    AUTH_OK = False

def _get_user_id():
    if AUTH_OK and _auth.esta_logueado():
        return _auth.get_user_id()
    return None

BG_DARK      = "#0f1117"
BG_CARD      = "#1e2130"
COLOR_VERDE  = "#00c896"
COLOR_ROJO   = "#f74f4f"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA= "#f7a34f"
COLOR_GRIS   = "#6b7280"

# ── Benchmarks disponibles ────────────────────────────────────────────────────
BENCHMARKS = {
    "SPY — S&P 500":          {"ticker": "SPY",   "color": COLOR_AZUL,   "tipo": "ETF"},
    "QQQ — NASDAQ-100":       {"ticker": "QQQ",   "color": COLOR_NARANJA,"tipo": "ETF"},
    "DIA — Dow Jones":        {"ticker": "DIA",   "color": "#9b59b6",    "tipo": "ETF"},
    "IWM — Russell 2000":     {"ticker": "IWM",   "color": "#1abc9c",    "tipo": "ETF"},
    "GLD — Oro":              {"ticker": "GLD",   "color": "#f1c40f",    "tipo": "Commodity"},
    "YPFD — YPF (BYMA)":      {"ticker": "YPFD.BA","color": "#e74c3c",   "tipo": "Argentina"},
    "GGAL — Galicia (BYMA)":  {"ticker": "GGAL.BA","color": "#2ecc71",   "tipo": "Argentina"},
    "BMA — Macro (BYMA)":     {"ticker": "BMA.BA", "color": "#3498db",   "tipo": "Argentina"},
}

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def descargar_benchmark(ticker: str, fecha_inicio: str, fecha_fin: str) -> pd.Series:
    """Descarga precios históricos de un benchmark y retorna retornos acumulados."""
    try:
        df = yf.download(ticker, start=fecha_inicio, end=fecha_fin,
                        interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return pd.Series(dtype=float)
        close = df["Close"].squeeze()
        # Retorno acumulado desde el inicio (base 100)
        retorno = (close / close.iloc[0] - 1) * 100
        return retorno
    except Exception:
        return pd.Series(dtype=float)

def calcular_retorno_cartera(df_hist: pd.DataFrame) -> pd.Series:
    """
    Calcula el retorno acumulado de la cartera desde el primer snapshot.
    Base: valor del primer día = 0%
    """
    if df_hist.empty or "valor_usd" not in df_hist.columns:
        return pd.Series(dtype=float)
    df = df_hist.set_index("fecha")["valor_usd"].dropna()
    if df.empty or float(df.iloc[0]) == 0:
        return pd.Series(dtype=float)
    retorno = (df / float(df.iloc[0]) - 1) * 100
    return retorno

def calcular_metricas(retornos: pd.Series, nombre: str) -> dict:
    """Calcula métricas de rendimiento de una serie de retornos acumulados."""
    if retornos.empty:
        return {"nombre": nombre, "retorno_total": None, "volatilidad": None,
                "max_drawdown": None, "sharpe": None}
    ret_diarios = retornos.diff().dropna() / 100
    ret_total   = float(retornos.iloc[-1])
    vol_anual   = float(ret_diarios.std() * np.sqrt(252) * 100) if len(ret_diarios) > 1 else None
    sharpe      = float(ret_total / vol_anual) if vol_anual and vol_anual > 0 else None

    # Max drawdown
    cum = (1 + retornos / 100)
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max * 100
    max_dd = float(drawdown.min()) if not drawdown.empty else None

    return {
        "nombre":        nombre,
        "retorno_total": round(ret_total, 2),
        "volatilidad":   round(vol_anual, 2) if vol_anual else None,
        "max_drawdown":  round(max_dd, 2) if max_dd else None,
        "sharpe":        round(sharpe, 2) if sharpe else None,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ═══════════════════════════════════════════════════════════════════════════════

def _grafico_comparacion(retornos_dict: dict) -> go.Figure:
    """Gráfico de retorno acumulado normalizado (base 0%)."""
    fig = go.Figure()
    colors = [COLOR_VERDE, COLOR_AZUL, COLOR_NARANJA, COLOR_ROJO,
              "#9b59b6", "#1abc9c", "#f1c40f", "#e74c3c", "#3498db"]

    for i, (nombre, serie) in enumerate(retornos_dict.items()):
        if serie is None or (hasattr(serie, 'empty') and serie.empty):
            continue
        color = colors[i % len(colors)]
        es_cartera = "Cartera" in nombre or "Mi " in nombre

        fig.add_trace(go.Scatter(
            x=serie.index, y=serie.values,
            mode="lines", name=nombre,
            line=dict(
                color=color,
                width=3 if es_cartera else 1.5,
                dash="solid" if es_cartera else "dot"
            ),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br>%{{y:+.2f}}%<extra></extra>"
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="#555", line_width=1)
    fig.update_layout(
        title="Retorno acumulado vs Benchmarks (base 0%)",
        xaxis_title="Fecha",
        yaxis_title="Retorno acumulado (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=450,
        legend=dict(bgcolor=BG_CARD),
        hovermode="x unified"
    )
    return fig

def _grafico_metricas(metricas_list: list) -> go.Figure:
    """Gráfico de barras comparando retorno total."""
    nombres  = [m["nombre"] for m in metricas_list if m.get("retorno_total") is not None]
    retornos = [m["retorno_total"] for m in metricas_list if m.get("retorno_total") is not None]
    colors   = [COLOR_VERDE if r >= 0 else COLOR_ROJO for r in retornos]

    fig = go.Figure(go.Bar(
        x=nombres, y=retornos,
        marker_color=colors,
        text=[f"{r:+.1f}%" for r in retornos],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Retorno: %{y:+.2f}%<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#888")
    fig.update_layout(
        title="Retorno total del período",
        yaxis_title="Retorno (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=350,
        showlegend=False
    )
    return fig

# ═══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def render():
    st.title("🏆 Comparación vs Benchmark")
    st.markdown("Compará el rendimiento de tu cartera contra índices y ETFs de referencia.")

    uid = _get_user_id()
    df_carteras = cartera_db.listar_carteras(usuario_id=uid)

    if df_carteras.empty:
        st.info("👈 Creá una cartera en **💼 Mi Cartera** para comparar.")
        return

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")

        opciones = {f"{r['nombre']} ({r['moneda_base']})": r['id']
                    for _, r in df_carteras.iterrows()}
        sel = st.selectbox("Cartera a comparar", list(opciones.keys()),
                           key="bench_cart_sel")
        cartera_id = opciones[sel]
        nombre_cartera = sel.split(" (")[0]

        st.markdown("**Benchmarks a comparar:**")
        bench_sel = st.multiselect(
            "Seleccioná benchmarks",
            list(BENCHMARKS.keys()),
            default=["SPY — S&P 500", "QQQ — NASDAQ-100"],
            key="bench_sel"
        )

        periodo = st.selectbox("Período", ["1 mes", "3 meses", "6 meses", "1 año"], index=3)
        dias_map = {"1 mes": 30, "3 meses": 90, "6 meses": 180, "1 año": 365}
        dias = dias_map[periodo]

        fecha_fin   = date.today()
        fecha_inicio = fecha_fin - timedelta(days=dias)

        analizar = st.button("▶️ Comparar", type="primary", use_container_width=True)

    if not analizar:
        st.info("👈 Seleccioná tu cartera y los benchmarks, luego presioná **Comparar**.")
        st.markdown("---")
        st.markdown("## Benchmarks disponibles")
        rows = []
        for nombre, meta in BENCHMARKS.items():
            rows.append({
                "Benchmark": nombre,
                "Ticker":    meta["ticker"],
                "Tipo":      meta["tipo"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.info(
            "ℹ️ **Nota**: La comparación usa el historial de snapshots de tu cartera. "
            "Cuantos más snapshots tengas guardados, más precisa será la comparación. "
            "Guardá snapshots diarios desde **📈 Historial P&L**."
        )
        return

    # ── Obtener historial de la cartera ───────────────────────────────────────
    try:
        # Importar funciones de historial de forma robusta
        import importlib, sys
        # Intentar import directo
        try:
            from pages.historial import listar_historial, init_historial_db
        except ImportError:
            # Fallback: definir funciones inline
            def init_historial_db():
                pass
            def listar_historial(cid, dias=365):
                from datetime import date, timedelta
                desde = (date.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
                try:
                    return cartera_db._read_sql(
                        "SELECT * FROM historial_pnl WHERE cartera_id=? AND fecha>=? ORDER BY fecha",
                        [cid, desde]
                    )
                except Exception:
                    return __import__('pandas').DataFrame()

        init_historial_db()
        df_hist = listar_historial(cartera_id, dias)
    except Exception as e:
        st.error(f"❌ Error al obtener historial: {e}")
        return

    if df_hist.empty:
        st.warning(
            f"⚠️ Sin historial para **{nombre_cartera}**. "
            "Guardá snapshots diarios en **📈 Historial P&L** para poder comparar."
        )
        return

    # ── Calcular retornos ─────────────────────────────────────────────────────
    retorno_cartera = calcular_retorno_cartera(df_hist)

    if retorno_cartera.empty:
        st.error("❌ No se pudo calcular el retorno de la cartera.")
        return

    fecha_inicio_real = retorno_cartera.index[0]
    fecha_fin_real    = retorno_cartera.index[-1]

    # Descargar benchmarks
    retornos_dict = {f"🏦 {nombre_cartera}": retorno_cartera}

    with st.spinner("📥 Descargando datos de benchmarks..."):
        for bench_nombre in bench_sel:
            meta = BENCHMARKS[bench_nombre]
            serie = descargar_benchmark(
                meta["ticker"],
                str(fecha_inicio_real),
                str(fecha_fin_real)
            )
            if not serie.empty:
                retornos_dict[bench_nombre] = serie
            else:
                st.warning(f"⚠️ Sin datos para {bench_nombre}")

    # ── Métricas ──────────────────────────────────────────────────────────────
    st.markdown(f"### 📊 Período: {fecha_inicio_real} → {fecha_fin_real}")

    metricas_list = []
    for nombre, serie in retornos_dict.items():
        metricas_list.append(calcular_metricas(serie, nombre))

    # Cards de retorno total
    n_cols = min(len(metricas_list), 4)
    cols = st.columns(n_cols)
    for i, m in enumerate(metricas_list[:n_cols]):
        with cols[i % n_cols]:
            ret = m.get("retorno_total")
            color = COLOR_VERDE if ret and ret >= 0 else COLOR_ROJO
            es_cartera = "🏦" in m["nombre"]
            st.markdown(
                f'<div style="background:{BG_CARD};padding:12px;border-radius:8px;'
                f'border-left:4px solid {color};margin-bottom:8px">'
                f'<div style="color:#aaa;font-size:11px">{"⭐ " if es_cartera else ""}{m["nombre"][:25]}</div>'
                f'<div style="color:{color};font-size:22px;font-weight:700">'
                f'{ret:+.2f}%</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown("---")

    # ── Gráficos ──────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📈 Retorno acumulado", "📊 Comparativa", "📋 Métricas detalle"])

    with tab1:
        st.plotly_chart(_grafico_comparacion(retornos_dict), use_container_width=True)
        st.caption(
            "La línea sólida gruesa es tu cartera. Las líneas punteadas son los benchmarks. "
            "Base 0% = valor al inicio del período."
        )

    with tab2:
        st.plotly_chart(_grafico_metricas(metricas_list), use_container_width=True)

    with tab3:
        df_metricas = pd.DataFrame(metricas_list)
        df_metricas.columns = ["Instrumento", "Retorno total %",
                                "Volatilidad anual %", "Max Drawdown %", "Sharpe ratio"]

        def color_retorno(val):
            try:
                v = float(val)
                return f"color: {'#00c896' if v >= 0 else '#f74f4f'}; font-weight: bold"
            except Exception:
                return ""

        st.dataframe(
            df_metricas.style
                .map(color_retorno, subset=["Retorno total %", "Max Drawdown %"])
                .format({
                    "Retorno total %":    lambda v: f"{v:+.2f}%" if v else "—",
                    "Volatilidad anual %": lambda v: f"{v:.2f}%" if v else "—",
                    "Max Drawdown %":     lambda v: f"{v:.2f}%" if v else "—",
                    "Sharpe ratio":       lambda v: f"{v:.2f}" if v else "—",
                }),
            use_container_width=True, hide_index=True
        )

        st.markdown("---")
        st.markdown("### 📖 Glosario de métricas")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Retorno total %**: Ganancia o pérdida acumulada en el período.

            **Volatilidad anual %**: Desviación estándar de los retornos diarios,
            anualizada. Mayor volatilidad = mayor riesgo.
            """)
        with col2:
            st.markdown("""
            **Max Drawdown %**: Caída máxima desde un pico hasta un valle.
            Indica el peor momento de pérdida.

            **Sharpe ratio**: Retorno ajustado por riesgo.
            Mayor = mejor relación riesgo/retorno.
            """)

        # Conclusión automática
        st.markdown("---")
        st.markdown("### 🎯 Conclusión del período")
        ret_cartera = next((m["retorno_total"] for m in metricas_list
                           if "🏦" in m["nombre"]), None)
        if ret_cartera is not None:
            mejor_bench = max(
                [m for m in metricas_list if "🏦" not in m["nombre"] and m.get("retorno_total")],
                key=lambda x: x["retorno_total"] or -999,
                default=None
            )
            if mejor_bench and mejor_bench.get("retorno_total") is not None:
                diff = ret_cartera - mejor_bench["retorno_total"]
                if diff > 0:
                    st.success(
                        f"✅ Tu cartera **superó** al mejor benchmark ({mejor_bench['nombre']}) "
                        f"por **{diff:+.2f}%** en el período."
                    )
                elif diff > -5:
                    st.info(
                        f"🟡 Tu cartera estuvo **cerca** del mejor benchmark ({mejor_bench['nombre']}), "
                        f"con una diferencia de **{diff:.2f}%**."
                    )
                else:
                    st.warning(
                        f"⚠️ Tu cartera **quedó por debajo** del mejor benchmark ({mejor_bench['nombre']}) "
                        f"por **{abs(diff):.2f}%**. Considerá revisar la composición."
                    )