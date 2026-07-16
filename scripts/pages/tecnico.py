"""
pages/tecnico.py — Reporte técnico completo por ticker en Streamlit.
Muestra: RSI + divergencias, cruces MA, Squeeze + ADX, Order Blocks,
estadísticas históricas y señal combinada con score 0-100.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tecnico
import core

# ── Paleta ────────────────────────────────────────────────────────────────────
BG_DARK      = "#0f1117"
BG_CARD      = "#1e2130"
COLOR_VERDE  = "#00c896"
COLOR_ROJO   = "#f74f4f"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA= "#f7a34f"
COLOR_GRIS   = "#6b7280"

# ── Helpers visuales ──────────────────────────────────────────────────────────
def _badge(texto: str, color: str) -> str:
    return (f'<span style="background:{color};color:#fff;padding:3px 10px;'
            f'border-radius:12px;font-size:13px;font-weight:600">{texto}</span>')

def _semaforo_score(score: int) -> tuple[str, str]:
    if score >= 65: return COLOR_VERDE,  "🟢 COMPRAR"
    if score >= 45: return COLOR_NARANJA, "🟡 NEUTRAL"
    return COLOR_ROJO, "🔴 VENDER"

def _color_rsi(rsi: float) -> str:
    if rsi <= 30: return COLOR_VERDE
    if rsi >= 70: return COLOR_ROJO
    return COLOR_NARANJA

def _gauge_score(score: int) -> go.Figure:
    """Gauge circular para el score técnico."""
    color, _ = _semaforo_score(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Score Técnico", "font": {"color": "white", "size": 14}},
        number={"font": {"color": color, "size": 36}},
        gauge={
            "axis":      {"range": [0, 100], "tickcolor": "white"},
            "bar":       {"color": color},
            "bgcolor":   BG_CARD,
            "bordercolor": "white",
            "steps": [
                {"range": [0,  45], "color": "#2d1b1b"},
                {"range": [45, 65], "color": "#2d2a1b"},
                {"range": [65, 100],"color": "#1b2d1b"},
            ],
            "threshold": {
                "line":  {"color": "white", "width": 2},
                "thickness": 0.75,
                "value": score
            }
        }
    ))
    fig.update_layout(
        height=220, margin=dict(t=30, b=10, l=20, r=20),
        paper_bgcolor=BG_CARD, font=dict(color="white")
    )
    return fig

def _grafico_rsi(rsi_serie: pd.Series, ticker: str) -> go.Figure:
    """Gráfico de RSI con zonas coloreadas."""
    fig = go.Figure()
    x = rsi_serie.index

    # Zona sobrecompra
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(247,79,79,0.1)",
                  line_width=0, annotation_text="Sobrecompra")
    # Zona sobreventa
    fig.add_hrect(y0=0, y1=30, fillcolor="rgba(0,200,150,0.1)",
                  line_width=0, annotation_text="Sobreventa")
    # Líneas de referencia
    fig.add_hline(y=70, line_dash="dash", line_color=COLOR_ROJO,   line_width=1)
    fig.add_hline(y=50, line_dash="dot",  line_color=COLOR_GRIS,   line_width=1)
    fig.add_hline(y=30, line_dash="dash", line_color=COLOR_VERDE,  line_width=1)

    # RSI
    fig.add_trace(go.Scatter(
        x=x, y=rsi_serie.values,
        mode="lines", name="RSI (14)",
        line=dict(color=COLOR_AZUL, width=2),
        hovertemplate="RSI: %{y:.1f}<extra></extra>"
    ))

    fig.update_layout(
        title=f"RSI (14) — {ticker}",
        yaxis=dict(range=[0, 100], title="RSI"),
        xaxis_title="Fecha",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=300,
        margin=dict(t=40, b=20, l=40, r=20),
        showlegend=False
    )
    return fig

def _grafico_ma(df_close: pd.Series, ma9: float, ma21: float,
                cruces: list, ticker: str) -> go.Figure:
    """Precio con MA9, MA21 y marcadores de cruces."""
    import pandas as pd
    close = df_close.tail(252)  # último año
    ma9_s  = close.rolling(9).mean()
    ma21_s = close.rolling(21).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=close.index, y=close.values,
        mode="lines", name="Precio",
        line=dict(color="#888", width=1),
        hovertemplate="$%{y:.2f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=ma9_s.index, y=ma9_s.values,
        mode="lines", name="MA 9",
        line=dict(color=COLOR_NARANJA, width=1.5),
        hovertemplate="MA9: $%{y:.2f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=ma21_s.index, y=ma21_s.values,
        mode="lines", name="MA 21",
        line=dict(color=COLOR_AZUL, width=1.5),
        hovertemplate="MA21: $%{y:.2f}<extra></extra>"
    ))

    # Marcar cruces del último año
    for c in cruces:
        try:
            fecha = pd.to_datetime(c.fecha)
            if fecha >= close.index[0]:
                color  = COLOR_VERDE if c.tipo == "golden" else COLOR_ROJO
                symbol = "triangle-up" if c.tipo == "golden" else "triangle-down"
                label  = "GC ↑" if c.tipo == "golden" else "DC ↓"
                precio_cruce = c.precio_en_cruce
                fig.add_trace(go.Scatter(
                    x=[fecha], y=[precio_cruce],
                    mode="markers+text",
                    marker=dict(size=12, color=color, symbol=symbol),
                    text=[label], textposition="top center",
                    textfont=dict(color=color, size=10),
                    name=label,
                    hovertemplate=f"<b>{label}</b><br>Fecha: {c.fecha}<br>Precio: ${precio_cruce:.2f}<extra></extra>",
                    showlegend=False
                ))
        except Exception:
            pass

    fig.update_layout(
        title=f"Precio + MA 9/21 — {ticker} (último año)",
        yaxis_title="Precio (USD)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=350,
        margin=dict(t=40, b=20, l=40, r=20),
        legend=dict(bgcolor=BG_CARD)
    )
    return fig

def _grafico_squeeze_momentum(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Histograma de momentum del Squeeze."""
    try:
        res_sqz = tecnico.calcular_squeeze_adx(df)
        # Recalcular serie completa de momentum para graficar
        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        length = 20
        highest = high.rolling(length).max()
        lowest  = low.rolling(length).min()
        mid     = (highest + lowest) / 2 + close.rolling(length).mean()
        mid     = mid / 2
        src     = close - mid
        # Regresión lineal rolling simplificada
        mom = src.rolling(length).apply(
            lambda x: np.polyval(np.polyfit(range(len(x)), x, 1), len(x)-1)
            if len(x) == length else np.nan, raw=True
        ).tail(120)

        colors = []
        for i, v in enumerate(mom.values):
            prev = mom.values[i-1] if i > 0 else v
            if v > 0:
                colors.append(COLOR_VERDE if v > prev else "#006644")
            else:
                colors.append(COLOR_ROJO if v < prev else "#660000")

        fig = go.Figure(go.Bar(
            x=mom.index, y=mom.values,
            marker_color=colors,
            hovertemplate="Momentum: %{y:.3f}<extra></extra>"
        ))
        fig.add_hline(y=0, line_color="white", line_width=1)
        fig.update_layout(
            title=f"Squeeze Momentum — {ticker}",
            yaxis_title="Momentum",
            plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
            font=dict(color="white"), height=280,
            margin=dict(t=40, b=20, l=40, r=20),
            showlegend=False
        )
        return fig
    except Exception:
        return None

# ── Secciones del reporte ─────────────────────────────────────────────────────

def _seccion_rsi(res: tecnico.ResultadoTecnico, df: pd.DataFrame):
    st.markdown("### 📉 RSI — Índice de Fuerza Relativa")
    rsi = res.rsi
    c1, c2, c3, c4 = st.columns(4)
    color_rsi = _color_rsi(rsi.valor_actual)
    c1.markdown(
        f'<div style="background:{BG_CARD};padding:12px;border-radius:8px;text-align:center">'
        f'<div style="color:#aaa;font-size:12px">RSI actual</div>'
        f'<div style="color:{color_rsi};font-size:28px;font-weight:700">{rsi.valor_actual:.1f}</div>'
        f'<div style="color:{color_rsi};font-size:12px">{rsi.zona.upper()}</div>'
        f'</div>', unsafe_allow_html=True
    )
    c2.metric("Períodos en zona", rsi.periodos_en_zona)
    c3.metric("Divergencia", rsi.divergencia.upper() if rsi.divergencia else "—")
    c4.metric("% rebote tras sobreventa", f"{rsi.pct_rebote_tras_sobreventa:.1f}%")

    st.plotly_chart(_grafico_rsi(rsi.serie.tail(252), res.ticker),
                    use_container_width=True)

    with st.expander("📊 Estadísticas históricas RSI"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Tiempo en zonas extremas**")
            st.dataframe(pd.DataFrame({
                "Zona":                ["Sobreventa (RSI<30)", "Sobrecompra (RSI>70)"],
                "% del tiempo":        [f"{rsi.pct_tiempo_sobreventa:.1f}%",
                                        f"{rsi.pct_tiempo_sobrecompra:.1f}%"],
                "Duración media":      [f"{rsi.duracion_media_sobreventa:.1f} barras",
                                        f"{rsi.duracion_media_sobrecompra:.1f} barras"],
            }), hide_index=True, use_container_width=True)
        with col2:
            st.markdown("**Efectividad histórica**")
            st.dataframe(pd.DataFrame({
                "Señal":               ["RSI<30 → rebote >5% en 20d",
                                        "RSI>70 → caída >5% en 20d"],
                "% de veces correcto": [f"{rsi.pct_rebote_tras_sobreventa:.1f}%",
                                        f"{rsi.pct_caida_tras_sobrecompra:.1f}%"],
            }), hide_index=True, use_container_width=True)


def _seccion_ma(res: tecnico.ResultadoTecnico, df: pd.DataFrame):
    st.markdown("### 📈 Medias Móviles MA 9 / MA 21")
    ma = res.ma
    c1, c2, c3, c4 = st.columns(4)
    tend_color = COLOR_VERDE if ma.tendencia == "alcista" else COLOR_ROJO
    c1.markdown(
        f'<div style="background:{BG_CARD};padding:12px;border-radius:8px;text-align:center">'
        f'<div style="color:#aaa;font-size:12px">Tendencia</div>'
        f'<div style="color:{tend_color};font-size:22px;font-weight:700">'
        f'{"↑ ALCISTA" if ma.tendencia == "alcista" else "↓ BAJISTA"}</div>'
        f'</div>', unsafe_allow_html=True
    )
    c2.metric("MA 9 actual",  f"${ma.ma9_actual:,.2f}")
    c3.metric("MA 21 actual", f"${ma.ma21_actual:,.2f}")
    c4.metric("Barras desde último cruce", ma.barras_desde_cruce)

    # Gráfico precio + MAs
    close_s = df["Close"].squeeze() if isinstance(df["Close"], pd.DataFrame) else df["Close"]
    st.plotly_chart(
        _grafico_ma(close_s, ma.ma9_actual, ma.ma21_actual,
                    ma.cruces_historicos, res.ticker),
        use_container_width=True
    )

    # Estadísticas de cruces
    st.markdown("#### 📊 Estadísticas históricas de cruces")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**🟢 Golden Cross** ({ma.total_golden_cross} históricos)")
        if ma.total_golden_cross > 0:
            st.dataframe(pd.DataFrame({
                "Horizonte": ["10 días", "20 días", "30 días", "60 días"],
                "Retorno promedio": [
                    f"{ma.golden_cross_retorno_10d_prom:+.1f}%" if ma.golden_cross_retorno_10d_prom else "—",
                    f"{ma.golden_cross_retorno_20d_prom:+.1f}%" if ma.golden_cross_retorno_20d_prom else "—",
                    f"{ma.golden_cross_retorno_30d_prom:+.1f}%" if ma.golden_cross_retorno_30d_prom else "—",
                    f"{ma.golden_cross_retorno_60d_prom:+.1f}%" if ma.golden_cross_retorno_60d_prom else "—",
                ]
            }), hide_index=True, use_container_width=True)
    with c2:
        st.markdown(f"**🔴 Death Cross** ({ma.total_death_cross} históricos)")
        if ma.total_death_cross > 0:
            st.dataframe(pd.DataFrame({
                "Horizonte": ["10 días", "20 días", "30 días", "60 días"],
                "Retorno promedio": [
                    f"{ma.death_cross_retorno_10d_prom:+.1f}%" if ma.death_cross_retorno_10d_prom else "—",
                    f"{ma.death_cross_retorno_20d_prom:+.1f}%" if ma.death_cross_retorno_20d_prom else "—",
                    f"{ma.death_cross_retorno_30d_prom:+.1f}%" if ma.death_cross_retorno_30d_prom else "—",
                    f"{ma.death_cross_retorno_60d_prom:+.1f}%" if ma.death_cross_retorno_60d_prom else "—",
                ]
            }), hide_index=True, use_container_width=True)

    # Historial de cruces
    with st.expander("📋 Historial de cruces (últimos 10)"):
        df_cruces = tecnico.cruces_tabla(res)
        if not df_cruces.empty:
            st.dataframe(df_cruces, hide_index=True, use_container_width=True)
        else:
            st.info("Sin cruces detectados en el período analizado.")


def _seccion_squeeze_adx(res: tecnico.ResultadoTecnico, df: pd.DataFrame):
    st.markdown("### 🔥 Squeeze Momentum + ADX")
    sqz = res.squeeze

    c1, c2, c3, c4, c5 = st.columns(5)
    sqz_color = COLOR_NARANJA if sqz.squeeze_activo else COLOR_GRIS
    c1.markdown(
        f'<div style="background:{BG_CARD};padding:12px;border-radius:8px;text-align:center">'
        f'<div style="color:#aaa;font-size:12px">Squeeze</div>'
        f'<div style="color:{sqz_color};font-size:18px;font-weight:700">'
        f'{"🔴 ACTIVO" if sqz.squeeze_activo else "✅ INACTIVO"}</div>'
        f'<div style="color:{sqz_color};font-size:11px">{sqz.nivel_compresion.upper()}</div>'
        f'</div>', unsafe_allow_html=True
    )
    mom_color = COLOR_VERDE if sqz.momentum_valor > 0 else COLOR_ROJO
    c2.markdown(
        f'<div style="background:{BG_CARD};padding:12px;border-radius:8px;text-align:center">'
        f'<div style="color:#aaa;font-size:12px">Momentum</div>'
        f'<div style="color:{mom_color};font-size:20px;font-weight:700">{sqz.momentum_valor:+.3f}</div>'
        f'<div style="color:{mom_color};font-size:11px">{"↑ SUBIENDO" if sqz.momentum_direccion == "subiendo" else "↓ BAJANDO"}</div>'
        f'</div>', unsafe_allow_html=True
    )
    adx_color = COLOR_VERDE if sqz.adx_valor >= 25 else COLOR_NARANJA
    c3.metric("ADX", f"{sqz.adx_valor:.1f}", sqz.adx_fuerza.upper())
    c4.metric("DI+", f"{sqz.di_plus:.1f}")
    c5.metric("DI−", f"{sqz.di_minus:.1f}")

    # Dirección ADX
    dir_color = COLOR_VERDE if sqz.direccion_adx == "alcista" else COLOR_ROJO
    st.markdown(
        f'Dirección ADX: {_badge(sqz.direccion_adx.upper(), dir_color)} &nbsp;&nbsp; '
        f'% tiempo en squeeze: **{sqz.pct_tiempo_squeeze:.1f}%** &nbsp;&nbsp; '
        f'Retorno promedio post-squeeze: **{sqz.retorno_post_squeeze_prom:+.1f}%**',
        unsafe_allow_html=True
    )

    # Gráfico momentum
    fig_mom = _grafico_squeeze_momentum(df, res.ticker)
    if fig_mom:
        st.plotly_chart(fig_mom, use_container_width=True)

    if sqz.squeeze_activo:
        if sqz.momentum_valor > 0 and sqz.momentum_direccion == "subiendo":
            st.success("⚡ Squeeze activo con momentum positivo y subiendo → posible expansión alcista inminente")
        elif sqz.momentum_valor < 0:
            st.warning("⚠️ Squeeze activo con momentum negativo → posible expansión bajista")
        else:
            st.info("ℹ️ Squeeze activo — esperar confirmación de dirección del momentum")


def _seccion_order_blocks(res: tecnico.ResultadoTecnico):
    st.markdown("### 🧱 Order Blocks — Soportes y Resistencias")
    ob = res.order_blocks

    # Posición del precio
    pos_color = {
        "en soporte":     COLOR_VERDE,
        "en resistencia": COLOR_ROJO,
        "zona neutral":   COLOR_NARANJA,
    }.get(ob.precio_actual_vs_ob, COLOR_GRIS)

    st.markdown(
        f'Precio actual **${res.precio_actual:,.2f}** → '
        f'{_badge(ob.precio_actual_vs_ob.upper(), pos_color)}',
        unsafe_allow_html=True
    )
    st.markdown("")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🟢 Soportes activos")
        if ob.soportes:
            df_sop = tecnico.order_blocks_tabla(res)
            df_sop = df_sop[df_sop["Tipo"].str.contains("Soporte")]
            if not df_sop.empty:
                st.dataframe(df_sop.drop(columns=["Tipo"]),
                             hide_index=True, use_container_width=True)
        else:
            st.info("Sin soportes activos detectados")

        if ob.ob_soporte_mas_cercano:
            s = ob.ob_soporte_mas_cercano
            st.metric("Soporte más cercano",
                      f"${s.precio_btm:,.2f} – ${s.precio_top:,.2f}",
                      f"{s.distancia_pct:+.1f}% del precio actual")

    with c2:
        st.markdown("#### 🔴 Resistencias activas")
        if ob.resistencias:
            df_res = tecnico.order_blocks_tabla(res)
            df_res = df_res[df_res["Tipo"].str.contains("Resistencia")]
            if not df_res.empty:
                st.dataframe(df_res.drop(columns=["Tipo"]),
                             hide_index=True, use_container_width=True)
        else:
            st.info("Sin resistencias activas detectadas")

        if ob.ob_resistencia_mas_cercana:
            r = ob.ob_resistencia_mas_cercana
            st.metric("Resistencia más cercana",
                      f"${r.precio_btm:,.2f} – ${r.precio_top:,.2f}",
                      f"{r.distancia_pct:+.1f}% del precio actual")

    st.caption(
        f"% respeto histórico soportes: **{ob.pct_respeto_soporte:.1f}%** | "
        f"% respeto histórico resistencias: **{ob.pct_respeto_resistencia:.1f}%**"
    )


def _seccion_score(res: tecnico.ResultadoTecnico):
    st.markdown("### 🎯 Señal Combinada")
    color, señal = _semaforo_score(res.score)

    c1, c2 = st.columns([1, 2])
    with c1:
        st.plotly_chart(_gauge_score(res.score), use_container_width=True)
    with c2:
        st.markdown(
            f'<div style="background:{BG_CARD};padding:20px;border-radius:10px;'
            f'border-left:4px solid {color};margin-top:20px">'
            f'<div style="color:{color};font-size:28px;font-weight:700">{señal}</div>'
            f'<div style="color:#ccc;font-size:14px;margin-top:8px">{res.resumen}</div>'
            f'</div>', unsafe_allow_html=True
        )
        st.markdown("")
        # Desglose del score
        st.markdown("**Desglose del score:**")
        comp = res.componentes_score
        total = sum(comp.values())
        for nombre, pts in comp.items():
            max_pts = 25
            pct = pts / max_pts
            bar_color = COLOR_VERDE if pct >= 0.6 else (COLOR_NARANJA if pct >= 0.4 else COLOR_ROJO)
            st.markdown(
                f'<div style="display:flex;align-items:center;margin:4px 0">'
                f'<div style="width:120px;color:#aaa;font-size:12px">{nombre}</div>'
                f'<div style="flex:1;background:#333;border-radius:4px;height:12px;margin:0 8px">'
                f'<div style="width:{pct*100:.0f}%;background:{bar_color};height:12px;border-radius:4px"></div>'
                f'</div>'
                f'<div style="width:50px;color:white;font-size:12px;text-align:right">{pts}/{max_pts}</div>'
                f'</div>',
                unsafe_allow_html=True
            )


# ── RENDER PRINCIPAL ──────────────────────────────────────────────────────────
def render():
    st.title("📈 Análisis Técnico")
    st.markdown("Reporte técnico completo: RSI, Medias Móviles, Squeeze Momentum, ADX y Order Blocks.")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")
        ticker_input = st.text_input(
            "Ticker a analizar",
            value="AAPL",
            placeholder="ej: AAPL, MSFT, MELI"
        ).upper().strip()
        periodo = st.selectbox(
            "Período de datos",
            ["1y", "2y", "3y", "5y"],
            index=1
        )
        intervalo = st.selectbox(
            "Intervalo",
            ["1d", "1wk"],
            index=0,
            help="Diario recomendado para análisis técnico"
        )
        analizar = st.button("▶️ Analizar", type="primary", use_container_width=True)

        st.markdown("---")
        st.markdown("**Comparar múltiples tickers**")
        tickers_multi = st.text_area(
            "Tickers (uno por línea o separados por coma)",
            placeholder="AAPL\nMSFT\nMELI",
            height=100
        )
        comparar = st.button("📊 Comparar", use_container_width=True)

    # ── Modo comparación ──────────────────────────────────────────────────────
    if comparar and tickers_multi:
        tickers_lista = [t.strip().upper()
                         for t in tickers_multi.replace(",", "\n").split("\n")
                         if t.strip()]
        if len(tickers_lista) < 2:
            st.warning("Ingresá al menos 2 tickers para comparar.")
            return

        st.markdown("## 📊 Comparación de señales técnicas")
        resultados = []
        prog = st.progress(0)
        for i, t in enumerate(tickers_lista):
            try:
                df = core.descargar_precios((t,), anios=2)
                if df.empty or len(df) < 50:
                    continue
                df_t = df.copy()
                if isinstance(df_t.columns, pd.MultiIndex):
                    df_t.columns = df_t.columns.droplevel(1)
                # Necesitamos OHLCV completo
                df_full = yf.download(t, period="2y", interval="1d",
                                      progress=False, auto_adjust=True)
                if isinstance(df_full.columns, pd.MultiIndex):
                    df_full.columns = df_full.columns.droplevel(1)
                if df_full.empty or len(df_full) < 50:
                    continue
                res = tecnico.analizar(df_full, t)
                resultados.append(tecnico.resumen_tabla(res))
            except Exception as e:
                st.warning(f"⚠️ Error con {t}: {e}")
            prog.progress((i+1)/len(tickers_lista))
        prog.empty()

        if resultados:
            df_comp = pd.DataFrame(resultados)
            cols_show = ["Ticker", "Precio", "Score", "Señal", "RSI", "RSI Zona",
                         "RSI Divergencia", "Tendencia MA", "Barras desde cruce",
                         "Squeeze", "Compresión", "ADX", "ADX Fuerza",
                         "Soporte cercano", "Resistencia cercana"]
            cols_ok = [c for c in cols_show if c in df_comp.columns]

            def color_señal(val):
                if "COMPRAR" in str(val): return "color: #00c896; font-weight: bold"
                if "VENDER"  in str(val): return "color: #f74f4f; font-weight: bold"
                return "color: #f7a34f"

            def color_score(val):
                try:
                    v = int(val)
                    if v >= 65: return "background-color: #1b2d1b; color: #00c896"
                    if v >= 45: return "background-color: #2d2a1b; color: #f7a34f"
                    return "background-color: #2d1b1b; color: #f74f4f"
                except Exception:
                    return ""

            st.dataframe(
                df_comp[cols_ok].style
                    .applymap(color_señal, subset=["Señal"])
                    .applymap(color_score, subset=["Score"]),
                use_container_width=True, hide_index=True
            )
        return

    # ── Modo análisis individual ──────────────────────────────────────────────
    if not analizar:
        st.info("👈 Ingresá un ticker en el panel izquierdo y presioná **Analizar**.")

        st.markdown("---")
        st.markdown("## ¿Qué analiza este módulo?")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **📉 RSI (14)**
            - Valor actual y zona (sobreventa/neutral/sobrecompra)
            - Divergencias alcistas y bajistas
            - Estadística histórica: % de rebotes tras sobreventa

            **📈 Medias Móviles MA 9/21**
            - Tendencia actual y barras desde el último cruce
            - Historial de Golden Cross y Death Cross
            - Retorno promedio a 10/20/30/60 días post-cruce
            """)
        with col2:
            st.markdown("""
            **🔥 Squeeze Momentum + ADX**
            - Detección de compresión de volatilidad (BB vs KC)
            - Momentum lineal: dirección y aceleración
            - ADX: fuerza de tendencia con DI+ y DI−

            **🧱 Order Blocks**
            - Zonas de soporte y resistencia institucional
            - Fuerza volumétrica bull/bear por zona
            - Distancia % al precio actual
            """)
        return

    # ── Descarga y análisis ───────────────────────────────────────────────────
    with st.spinner(f"📥 Descargando datos de {ticker_input}..."):
        try:
            df = yf.download(ticker_input, period=periodo,
                             interval=intervalo, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
        except Exception as e:
            st.error(f"❌ Error al descargar {ticker_input}: {e}")
            return

    if df.empty or len(df) < 50:
        st.error(f"❌ Datos insuficientes para {ticker_input}. "
                 f"Verificá el ticker y la conexión.")
        return

    with st.spinner("🔍 Calculando indicadores técnicos..."):
        try:
            res = tecnico.analizar(df, ticker_input)
        except Exception as e:
            st.error(f"❌ Error en análisis técnico: {e}")
            return

    # ── Header del ticker ─────────────────────────────────────────────────────
    color_s, señal_s = _semaforo_score(res.score)
    st.markdown(
        f'<div style="background:{BG_CARD};padding:16px 20px;border-radius:10px;'
        f'border-left:5px solid {color_s};margin-bottom:20px">'
        f'<span style="font-size:22px;font-weight:700;color:white">{ticker_input}</span>'
        f'&nbsp;&nbsp;'
        f'<span style="font-size:18px;color:#aaa">${res.precio_actual:,.2f}</span>'
        f'&nbsp;&nbsp;&nbsp;'
        f'<span style="background:{color_s};color:#fff;padding:4px 14px;'
        f'border-radius:12px;font-size:14px;font-weight:600">{señal_s} — {res.score}/100</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    # ── Tabs de contenido ─────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 Señal combinada",
        "📉 RSI",
        "📈 MA 9/21",
        "🔥 Squeeze + ADX",
        "🧱 Order Blocks"
    ])

    with tab1:
        _seccion_score(res)

    with tab2:
        _seccion_rsi(res, df)

    with tab3:
        _seccion_ma(res, df)

    with tab4:
        _seccion_squeeze_adx(res, df)

    with tab5:
        _seccion_order_blocks(res)