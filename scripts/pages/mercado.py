"""
pages/mercado.py — Información de mercado por ticker.
Noticias, consenso de analistas, ratings, próximos eventos y métricas ETF.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import market_info as mi
import cartera_db

# Traducción completa con deep-translator (pip install deep-translator)
try:
    from deep_translator import GoogleTranslator
    _TRADUCTOR_DISPONIBLE = True
except ImportError:
    _TRADUCTOR_DISPONIBLE = False

BG_DARK      = "#0f1117"
BG_CARD      = "#1e2130"
COLOR_VERDE  = "#00c896"
COLOR_ROJO   = "#f74f4f"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA= "#f7a34f"
COLOR_GRIS   = "#6b7280"

# ── Traducciones inglés → español ─────────────────────────────────────────────
_TRADUCCIONES = {
    "strong_buy": "Compra fuerte", "strongBuy": "Compra fuerte",
    "strong buy": "Compra fuerte", "buy": "Comprar", "Buy": "Comprar",
    "overweight": "Sobreponderar", "Overweight": "Sobreponderar",
    "outperform": "Superar mercado", "Outperform": "Superar mercado",
    "hold": "Mantener", "Hold": "Mantener",
    "neutral": "Neutral", "Neutral": "Neutral",
    "equal_weight": "Neutral", "market_perform": "En línea con mercado",
    "underperform": "Bajo mercado", "Underperform": "Bajo mercado",
    "underweight": "Subponderar", "Underweight": "Subponderar",
    "sell": "Vender", "Sell": "Vender",
    "strong_sell": "Venta fuerte",
    "Upgrade": "Mejora de rating", "Downgrade": "Baja de rating",
    "Maintain": "Mantiene rating", "Initiated": "Inicio de cobertura",
    "Reiterated": "Reitera rating", "Resumed": "Retoma cobertura",
    "Suspended": "Suspende cobertura",
}

def _es(texto) -> str:
    """Traduce un valor al español si existe traducción."""
    if texto is None:
        return "—"
    s = str(texto).strip()
    return _TRADUCCIONES.get(s, s)

def _fmt_monto(v) -> str:
    """Formatea montos grandes en formato legible."""
    if v is None:
        return "—"
    try:
        v = float(v)
        if abs(v) >= 1e12: return f"${v/1e12:.1f}T"
        if abs(v) >= 1e9:  return f"${v/1e9:.1f}B"
        if abs(v) >= 1e6:  return f"${v/1e6:.1f}M"
        return f"${v:,.0f}"
    except Exception:
        return "—"

@st.cache_data(ttl=86400, show_spinner=False)
def _traducir_texto(texto: str) -> str:
    """
    Traduce texto del inglés al español.
    Usa deep-translator (Google Translate) si está disponible,
    sino aplica traducción parcial por diccionario.
    """
    if not texto or not texto.strip():
        return texto

    # Método 1: deep-translator (traducción completa)
    if _TRADUCTOR_DISPONIBLE:
        try:
            traducido = GoogleTranslator(source="auto", target="es").translate(texto[:500])
            if traducido:
                return traducido
        except Exception:
            pass

    # Método 2: diccionario de términos financieros (fallback)
    terminos = {
        "earnings": "resultados", "Earnings": "Resultados",
        "revenue": "ingresos", "Revenue": "Ingresos",
        "profit": "ganancia", "Profit": "Ganancia",
        "quarterly": "trimestral", "Quarterly": "Trimestral",
        "forecast": "pronóstico", "Forecast": "Pronóstico",
        "guidance": "perspectivas", "Guidance": "Perspectivas",
        "dividend": "dividendo", "Dividend": "Dividendo",
        "buyback": "recompra de acciones",
        "merger": "fusión", "Merger": "Fusión",
        "acquisition": "adquisición", "Acquisition": "Adquisición",
        "growth": "crecimiento", "Growth": "Crecimiento",
        "decline": "caída", "Decline": "Caída",
        "surge": "suba", "Surge": "Suba",
        "beat": "superó expectativas", "Beat": "Superó expectativas",
        "miss": "no alcanzó expectativas",
        "outlook": "perspectiva", "Outlook": "Perspectiva",
        "upgrade": "mejora de rating", "Upgrade": "Mejora de rating",
        "downgrade": "baja de rating", "Downgrade": "Baja de rating",
        "price target": "precio objetivo", "Price Target": "Precio objetivo",
        "analyst": "analista", "Analyst": "Analista",
        "report": "reporte", "Report": "Reporte",
        "results": "resultados", "Results": "Resultados",
        "raises": "eleva", "Raises": "Eleva",
        "cuts": "recorta", "Cuts": "Recorta",
        "beats": "supera", "Beats": "Supera",
        "Q1": "T1", "Q2": "T2", "Q3": "T3", "Q4": "T4",
        "shares": "acciones", "Shares": "Acciones",
        "stock": "acción", "Stock": "Acción",
        "market": "mercado", "Market": "Mercado",
        "investors": "inversores", "Investors": "Inversores",
        "CEO": "CEO", "CFO": "CFO",
        "layoffs": "despidos", "Layoffs": "Despidos",
        "lawsuit": "demanda", "Lawsuit": "Demanda",
        "record": "récord", "Record": "Récord",
        "billion": "mil millones", "Billion": "Mil millones",
        "million": "millones", "Million": "Millones",
    }
    resultado = texto
    for en, es in terminos.items():
        resultado = resultado.replace(en, es)
    return resultado

def _traducir_titulo(titulo: str) -> str:
    """Alias para compatibilidad."""
    return _traducir_texto(titulo)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _badge(texto: str, color: str) -> str:
    return (f'<span style="background:{color};color:#fff;padding:3px 10px;'
            f'border-radius:12px;font-size:12px;font-weight:600">{texto}</span>')

def _color_recomendacion(rec: str) -> str:
    r = rec.lower()
    if any(x in r for x in ["compra fuerte","strong","outperform","sobreponderar"]):
        return COLOR_VERDE
    if any(x in r for x in ["comprar","buy"]):
        return "#4ade80"
    if any(x in r for x in ["mantener","hold","neutral","línea"]):
        return COLOR_NARANJA
    if any(x in r for x in ["vender","sell","subponderar","under"]):
        return COLOR_ROJO
    return COLOR_GRIS

def _color_upside(upside: float | None) -> str:
    if upside is None: return COLOR_GRIS
    if upside >= 20:   return COLOR_VERDE
    if upside >= 5:    return COLOR_AZUL
    if upside >= 0:    return COLOR_NARANJA
    return COLOR_ROJO

def _card_analista(ticker: str, info: mi.InfoMercado):
    """Card compacta de consenso de analistas."""
    rec   = _es(info.recomendacion_consenso) if info.recomendacion_consenso else "—"
    color = _color_recomendacion(rec)
    upside = info.upside_potencial

    st.markdown(
        f'<div style="background:{BG_CARD};padding:14px 16px;border-radius:10px;'
        f'border-left:4px solid {color};margin-bottom:10px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<div>'
        f'<span style="font-size:16px;font-weight:700;color:white">{ticker}</span>'
        f'&nbsp;&nbsp;'
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:10px;font-size:12px">{rec}</span>'
        f'</div>'
        f'<div style="text-align:right">'
        f'<div style="color:#aaa;font-size:11px">Precio objetivo</div>'
        f'<div style="color:white;font-size:16px;font-weight:600">'
        f'${info.precio_objetivo_consenso:,.2f}</div>'
        f'</div>'
        f'</div>'
        f'<div style="display:flex;gap:20px;margin-top:8px">'
        f'<div><span style="color:#aaa;font-size:11px">Precio actual</span>'
        f'<br><span style="color:white;font-size:14px">${info.precio_actual:,.2f}</span></div>'
        f'<div><span style="color:#aaa;font-size:11px">Upside</span>'
        f'<br><span style="color:{_color_upside(upside)};font-size:14px;font-weight:600">'
        f'{upside:+.1f}%</span></div>'
        f'<div><span style="color:#aaa;font-size:11px">Analistas</span>'
        f'<br><span style="color:white;font-size:14px">{info.num_analistas or "—"}</span></div>'
        f'<div><span style="color:#aaa;font-size:11px">Próx. earnings</span>'
        f'<br><span style="color:white;font-size:14px">{info.proximo_earnings or "—"}</span></div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

def _grafico_upside(info_dict: dict) -> go.Figure:
    """Gráfico de barras con upside por ticker."""
    datos = [
        (t, i.upside_potencial, _color_upside(i.upside_potencial))
        for t, i in info_dict.items()
        if not i.es_etf and i.upside_potencial is not None
    ]
    if not datos:
        return None
    datos.sort(key=lambda x: x[1], reverse=True)
    tickers = [d[0] for d in datos]
    upsides = [d[1] for d in datos]
    colors  = [d[2] for d in datos]

    fig = go.Figure(go.Bar(
        x=tickers, y=upsides,
        marker_color=colors,
        text=[f"{u:+.1f}%" for u in upsides],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Upside: %{y:+.1f}%<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#888")
    fig.update_layout(
        title="Upside potencial vs precio objetivo de analistas",
        yaxis_title="Upside (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=320,
        margin=dict(t=40, b=20, l=40, r=20),
        showlegend=False
    )
    return fig

def _grafico_etf_retornos(info_dict: dict) -> go.Figure | None:
    """Gráfico comparativo de retornos de ETFs."""
    etfs = {t: i for t, i in info_dict.items() if i.es_etf and i.etf}
    if not etfs:
        return None

    fig = go.Figure()
    horizontes = ["Ret. YTD", "Ret. 3Y", "Ret. 5Y"]
    attrs      = ["retorno_ytd", "retorno_3y", "retorno_5y"]
    colors_bar = [COLOR_AZUL, COLOR_VERDE, COLOR_NARANJA]

    def _norm_ret_grafico(v):
        """Normaliza retorno para el gráfico."""
        if v is None: return None
        v = float(v)
        return v * 100 if abs(v) < 5 else v

    for attr, label, color in zip(attrs, horizontes, colors_bar):
        vals    = []
        tickers = []
        for t, info in etfs.items():
            v = getattr(info.etf, attr, None)
            v_norm = _norm_ret_grafico(v)
            if v_norm is not None:
                vals.append(round(v_norm, 2))
                tickers.append(t)
        if vals:
            fig.add_trace(go.Bar(
                name=label, x=tickers, y=vals,
                marker_color=color,
                hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:+.1f}}%<extra></extra>"
            ))

    fig.add_hline(y=0, line_dash="dash", line_color="#888")
    fig.update_layout(
        barmode="group",
        title="Retornos históricos de ETFs",
        yaxis_title="Retorno (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=340,
        margin=dict(t=40, b=20, l=40, r=20),
        legend=dict(bgcolor=BG_CARD)
    )
    return fig


# ── Secciones ─────────────────────────────────────────────────────────────────

def _seccion_eventos(info_dict: dict):
    """Próximos eventos ordenados por fecha."""
    eventos = []
    for ticker, info in info_dict.items():
        for ev in info.proximos_eventos:
            if ev.fecha and ev.fecha != "—":
                eventos.append((ticker, ev))

    if not eventos:
        st.info("Sin eventos próximos detectados.")
        return

    # Filtrar solo eventos futuros o del mes actual (no históricos)
    from datetime import datetime, timedelta
    hoy = datetime.now()
    hace_30_dias = hoy - timedelta(days=30)

    eventos_filtrados = []
    for ticker, ev in eventos:
        try:
            fecha_ev = datetime.strptime(ev.fecha, "%d/%m/%Y")
            # Solo incluir si es futuro o de los últimos 30 días
            if fecha_ev >= hace_30_dias:
                eventos_filtrados.append((ticker, ev))
        except Exception:
            # Si no se puede parsear la fecha, incluir igual
            eventos_filtrados.append((ticker, ev))

    if not eventos_filtrados:
        st.info("Sin eventos próximos. Los dividendos históricos se omiten.")
        return

    # Ordenar por fecha
    def _sort_key(item):
        try:
            return datetime.strptime(item[1].fecha, "%d/%m/%Y")
        except Exception:
            return item[1].fecha

    eventos_filtrados.sort(key=_sort_key)
    eventos = eventos_filtrados

    for ticker, ev in eventos:
        es_earnings = "earnings" in ev.tipo.lower()
        color  = COLOR_VERDE if es_earnings else COLOR_NARANJA
        icono  = "📊" if es_earnings else "💰"
        tipo_s = "Resultados" if es_earnings else "Dividendo"

        st.markdown(
            f'<div style="background:{BG_CARD};padding:10px 14px;border-radius:8px;'
            f'border-left:3px solid {color};margin-bottom:6px;'
            f'display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<span style="color:white;font-weight:700">{icono} {ticker}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:{color};font-size:12px">{tipo_s}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:#aaa;font-size:12px">{ev.descripcion}</span>'
            f'</div>'
            f'<div style="color:white;font-size:13px;font-weight:600">{ev.fecha}</div>'
            f'</div>',
            unsafe_allow_html=True
        )


def _seccion_analistas(info_dict: dict):
    """Consenso de analistas con cards y gráfico de upside."""
    acciones = {t: i for t, i in info_dict.items()
                if not i.es_etf and i.precio_objetivo_consenso}

    if not acciones:
        st.info("Sin datos de analistas disponibles.")
        return

    # Gráfico upside
    fig = _grafico_upside(info_dict)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    # Cards por ticker
    st.markdown("#### Detalle por ticker")
    cols = st.columns(min(len(acciones), 2))
    for i, (ticker, info) in enumerate(acciones.items()):
        with cols[i % 2]:
            _card_analista(ticker, info)

    # Tabla resumen
    with st.expander("📋 Tabla completa de consenso"):
        rows = []
        for ticker, info in acciones.items():
            rows.append({
                "Ticker":              ticker,
                "Precio actual":       f"${info.precio_actual:,.2f}" if info.precio_actual else "—",
                "Precio obj.":         f"${info.precio_objetivo_consenso:,.2f}" if info.precio_objetivo_consenso else "—",
                "Precio obj. alto":    f"${info.precio_objetivo_alto:,.2f}" if info.precio_objetivo_alto else "—",
                "Precio obj. bajo":    f"${info.precio_objetivo_bajo:,.2f}" if info.precio_objetivo_bajo else "—",
                "Upside %":            f"{info.upside_potencial:+.1f}%" if info.upside_potencial else "—",
                "Recomendación":       _es(info.recomendacion_consenso) if info.recomendacion_consenso else "—",
                "N° analistas":        info.num_analistas or "—",
                "Próx. earnings":      info.proximo_earnings or "—",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


@st.fragment
def _seccion_ratings(info_dict: dict, ticker_sel: str = None):
    """Ratings detallados de analistas por ticker.
    @st.fragment: solo esta sección se recarga al cambiar el selectbox.
    """
    acciones = {t: i for t, i in info_dict.items()
                if not i.es_etf and i.ratings}

    if not acciones:
        st.info("Sin ratings de analistas disponibles.")
        return

    # Con @st.fragment el selectbox no causa rerun de toda la página
    ticker_sel = st.selectbox(
        "🔍 Seleccioná ticker",
        list(acciones.keys()),
        key="_sel_ratings_fragment"
    )
    info = acciones[ticker_sel]

    # Resumen consenso
    rec   = _es(info.recomendacion_consenso) if info.recomendacion_consenso else "—"
    color = _color_recomendacion(rec)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f'<div style="background:{BG_CARD};padding:12px;border-radius:8px;text-align:center">'
        f'<div style="color:#aaa;font-size:11px">Consenso</div>'
        f'<div style="color:{color};font-size:16px;font-weight:700">{rec}</div>'
        f'</div>', unsafe_allow_html=True
    )
    c2.metric("Precio objetivo", f"${info.precio_objetivo_consenso:,.2f}" if info.precio_objetivo_consenso else "—")
    c3.metric("Upside", f"{info.upside_potencial:+.1f}%" if info.upside_potencial else "—")
    c4.metric("N° analistas", info.num_analistas or "—")

    st.markdown("")

    # Tabla de ratings
    if info.ratings:
        rows = []
        for r in info.ratings:
            accion_es = _es(r.accion)
            upside_r  = None
            if info.precio_actual and r.precio_objetivo:
                try:
                    upside_r = (r.precio_objetivo - info.precio_actual) / info.precio_actual * 100
                except Exception:
                    pass

            # Color de fondo según acción
            ac_lower = accion_es.lower()
            if any(x in ac_lower for x in ["compra","mejora","superar","sobreponderar","inicio"]):
                bg_color = "#1b2d1b"
            elif any(x in ac_lower for x in ["mantiene","neutral","mantener","línea","reitera"]):
                bg_color = "#2d2a1b"
            elif any(x in ac_lower for x in ["vender","baja","subponderar","suspende"]):
                bg_color = "#2d1b1b"
            else:
                bg_color = BG_CARD

            rows.append({
                "Firma":           r.firma,
                "Acción":          accion_es,
                "Precio objetivo": f"${r.precio_objetivo:,.2f}" if r.precio_objetivo else "—",
                "Upside":          f"{upside_r:+.1f}%" if upside_r else "—",
                "Fecha":           r.fecha,
                "_bg":             bg_color
            })

        df_r = pd.DataFrame(rows)

        # Ocultar columnas vacías (Precio objetivo y Upside si todos son "—")
        cols_mostrar = ["Firma", "Acción", "Fecha"]
        tiene_precio = any(r.precio_objetivo for r in info.ratings)
        if tiene_precio:
            cols_mostrar = ["Firma", "Acción", "Precio objetivo", "Upside", "Fecha"]

        def color_accion(val):
            v = str(val).lower()
            if any(x in v for x in ["compra","mejora","superar","sobreponderar","inicio"]):
                return "color: #00c896; font-weight: bold"
            if any(x in v for x in ["vender","baja","subponderar","suspende"]):
                return "color: #f74f4f; font-weight: bold"
            return "color: #f7a34f"

        st.dataframe(
            df_r[cols_mostrar].style.map(color_accion, subset=["Acción"]),
            hide_index=True, use_container_width=True
        )

        if not tiene_precio:
            st.caption(
                "ℹ️ El precio objetivo individual por firma no está disponible en fuentes gratuitas. "
                "El **precio objetivo consenso** (promedio de todos los analistas) se muestra arriba."
            )
    else:
        st.info(f"Sin ratings detallados para {ticker_sel}.")


@st.fragment
def _seccion_noticias(info_dict: dict, ticker_sel: str = None):
    """Noticias recientes con traducción completa o parcial al español.
    @st.fragment: solo esta sección se recarga al cambiar el selectbox.
    """
    acciones_n = [t for t, i in info_dict.items() if not i.es_etf]
    if not acciones_n:
        acciones_n = list(info_dict.keys())

    # Con @st.fragment el selectbox no causa rerun de toda la página
    ticker_sel = st.selectbox(
        "🔍 Seleccioná ticker",
        acciones_n,
        key="_sel_noticias_fragment"
    )
    info = info_dict[ticker_sel]

    if not info.noticias:
        st.info(f"Sin noticias disponibles para {ticker_sel}.")
        return

    # Indicador de estado de traducción
    if _TRADUCTOR_DISPONIBLE:
        st.success("✅ Traducción completa al español activa (Google Translate)")
    else:
        st.info(
            "ℹ️ Traducción parcial activa. "
            "Para traducción completa ejecutá: `pip install deep-translator`"
        )

    for n in info.noticias:
        titulo_es  = _traducir_texto(n.titulo)
        resumen_es = _traducir_texto(n.resumen) if n.resumen else ""

        st.markdown(
            f'<div style="background:{BG_CARD};padding:14px 16px;border-radius:10px;'
            f'margin-bottom:8px">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
            f'<div style="flex:1;margin-right:12px">'
            f'<div style="color:white;font-size:14px;font-weight:600;line-height:1.4">'
            f'{titulo_es}</div>'
            f'{"<div style=\"color:#aaa;font-size:12px;margin-top:6px;line-height:1.4\">" + resumen_es + "</div>" if resumen_es else ""}'
            f'</div>'
            f'<div style="text-align:right;min-width:120px">'
            f'<div style="color:#aaa;font-size:11px">{n.fuente}</div>'
            f'<div style="color:#aaa;font-size:11px">{n.fecha}</div>'
            f'{"<a href=\"" + n.url + "\" target=\"_blank\" style=\"color:" + COLOR_AZUL + ";font-size:11px\">Ver nota →</a>" if n.url else ""}'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )


def _seccion_etfs(info_dict: dict):
    """Métricas detalladas de ETFs."""
    etfs = {t: i for t, i in info_dict.items() if i.es_etf and i.etf}

    if not etfs:
        st.info("No hay ETFs en la lista analizada.")
        return

    # Gráfico retornos
    fig = _grafico_etf_retornos(info_dict)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    # Cards por ETF
    for ticker, info in etfs.items():
        e = info.etf
        beta_color = (COLOR_VERDE if e.beta_3y and e.beta_3y < 0.7
                      else COLOR_NARANJA if e.beta_3y and e.beta_3y < 1.1
                      else COLOR_ROJO)
        riesgo_color = {
            "Defensivo": COLOR_VERDE,
            "Moderado":  COLOR_NARANJA,
            "Agresivo":  COLOR_ROJO,
        }.get(e.clasificacion_riesgo, COLOR_GRIS)

        with st.expander(f"📊 {ticker} — {info.nombre or e.indice_seguido}"):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("AUM", _fmt_monto(e.aum_usd) if e.aum_usd else "—")
            c2.metric("Yield anual", f"{e.yield_anual*100:.2f}%" if e.yield_anual else "—")
            # yfinance devuelve ytdReturn ya en % (ej: 20.19 = 20.19%), no multiplicar x100
            def _fmt_ret(v):
                if v is None: return "—"
                # Si el valor es > 1, ya viene en % (ej: 20.19)
                # Si es < 1, viene como decimal (ej: 0.2019) → multiplicar x100
                pct = v if abs(v) > 1 else v * 100
                return f"{pct:+.1f}%"
            c3.metric("Ret. YTD",    _fmt_ret(e.retorno_ytd))
            c4.metric("Ret. 3Y",     _fmt_ret(e.retorno_3y))
            c5.metric("Beta 3Y",     f"{e.beta_3y:.2f}" if e.beta_3y else "—")

            st.markdown(
                f'Índice: **{e.indice_seguido}** &nbsp;|&nbsp; '
                f'Categoría: **{e.categoria}** &nbsp;|&nbsp; '
                f'Riesgo: {_badge(e.clasificacion_riesgo, riesgo_color)} &nbsp;|&nbsp; '
                f'Rol: **{e.rol_en_cartera}**',
                unsafe_allow_html=True
            )

            # Top holdings
            if e.top_holdings:
                st.markdown("**Top Holdings:**")
                df_h = pd.DataFrame(e.top_holdings)
                if "peso" in df_h.columns:
                    df_h["peso"] = df_h["peso"].apply(lambda x: f"{x:.2f}%")
                df_h = df_h.rename(columns={
                    "ticker": "Ticker", "nombre": "Nombre", "peso": "Peso %"
                })
                st.dataframe(df_h, hide_index=True, use_container_width=True)


# ── RENDER PRINCIPAL ──────────────────────────────────────────────────────────
def render():
    st.title("📰 Información de Mercado")
    st.markdown("Noticias, consenso de analistas, ratings, próximos eventos y métricas de ETFs.")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")

        # Opción: usar cartera guardada o ingresar tickers
        fuente = st.radio(
            "Fuente de tickers",
            ["📝 Ingresar manualmente", "💼 Usar Mi Cartera"],
            index=0
        )

        if fuente == "💼 Usar Mi Cartera":
            try:
                df_carteras = cartera_db.listar_carteras()
                if df_carteras.empty:
                    st.warning("No hay carteras creadas.")
                    tickers_lista = []
                else:
                    opciones = {f"{r['nombre']} ({r['moneda_base']})": r['id']
                                for _, r in df_carteras.iterrows()}
                    opciones["🔀 Todas"] = -1
                    sel = st.selectbox("Cartera", list(opciones.keys()), key="merc_cart_sel")
                    cid = opciones[sel]
                    if cid == -1:
                        tickers_set = set()
                        for _, r in df_carteras.iterrows():
                            dp = cartera_db.listar_posiciones(r['id'])
                            if not dp.empty:
                                tickers_set.update(dp["ticker"].tolist())
                        tickers_lista = list(tickers_set)
                    else:
                        dp = cartera_db.listar_posiciones(cid)
                        tickers_lista = dp["ticker"].tolist() if not dp.empty else []
                    if tickers_lista:
                        st.success(f"✅ {len(tickers_lista)} tickers")
                        st.caption(", ".join(tickers_lista))
            except Exception as e:
                st.warning(f"Error: {e}")
                tickers_lista = []
        else:
            tickers_input = st.text_area(
                "Tickers (separados por coma)",
                value="META, MSFT, MELI, QQQ, XLP",
                height=80
            )
            tickers_lista = [t.strip().upper()
                             for t in tickers_input.split(",") if t.strip()]

        max_noticias = st.slider("Noticias por ticker", 3, 15, 6)
        incluir_ratings = st.checkbox("Incluir ratings de analistas", value=True)
        analizar = st.button("▶️ Obtener información", type="primary",
                             use_container_width=True)

    if not analizar:
        st.info("👈 Configurá los tickers y presioná **Obtener información**.")

        st.markdown("---")
        st.markdown("## ¿Qué información se obtiene?")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **📅 Próximos eventos**
            - Fecha de resultados (earnings) con EPS estimado
            - Fecha ex-dividendo con monto por acción
            - Ordenados cronológicamente

            **🏦 Consenso de analistas**
            - Precio objetivo (consenso, alto y bajo)
            - Upside potencial vs precio actual
            - Recomendación: Compra fuerte / Comprar / Mantener / Vender
            - Número de analistas cubriendo el ticker
            """)
        with col2:
            st.markdown("""
            **📋 Ratings detallados**
            - Historial de upgrades y downgrades por firma
            - Precio objetivo individual por analista
            - Upside calculado por cada rating

            **📰 Noticias recientes**
            - Últimas noticias de Yahoo Finance
            - Traducción parcial automática al español
            - Link directo a la nota original

            **📊 Métricas de ETFs**
            - AUM, yield, retornos 1/3/5 años, beta
            - Top holdings con pesos
            - Clasificación: Defensivo / Moderado / Agresivo
            """)
        return

    if not tickers_lista:
        st.error("❌ Ingresá al menos un ticker.")
        return

    # Clave de caché única por combinación de tickers
    cache_key = f"mercado_info_{'_'.join(sorted(tickers_lista))}"

    # ── Obtener información (o usar caché) ────────────────────────────────────
    if analizar or cache_key not in st.session_state:
        with st.spinner(f"📡 Obteniendo información de {len(tickers_lista)} tickers..."):
            prog    = st.progress(0)
            info_dict = {}
            for i, ticker in enumerate(tickers_lista):
                try:
                    info_dict[ticker] = mi.obtener_info_mercado(
                        ticker,
                        max_noticias=max_noticias,
                        incluir_ratings=incluir_ratings
                    )
                except Exception as e:
                    st.warning(f"⚠️ Error con {ticker}: {e}")
                prog.progress((i+1)/len(tickers_lista))
            prog.empty()
        # Guardar en session_state para que persista al cambiar de tab
        st.session_state[cache_key] = info_dict
    else:
        # Usar datos cacheados — no recarga al cambiar de tab
        info_dict = st.session_state[cache_key]

    if not info_dict:
        st.error("❌ No se pudo obtener información. Verificá la conexión.")
        return

    # Guardar en session_state para que persista al cambiar de tab
    st.session_state[cache_key] = info_dict
    st.success(f"✅ Información obtenida para {len(info_dict)} tickers")

    # ── Selector de ticker para Ratings y Noticias ──────────────────────────
    acciones_lista = [t for t, i in info_dict.items() if not i.es_etf]
    # El ticker_global se pasa como parámetro a las funciones que lo necesitan
    # Se inicializa en session_state y se actualiza via on_change
    if "_ticker_sel_val" not in st.session_state or        st.session_state.get("_ticker_sel_val") not in acciones_lista:
        st.session_state["_ticker_sel_val"] = acciones_lista[0] if acciones_lista else None
    ticker_global = st.session_state.get("_ticker_sel_val")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Próximos eventos",
        "🏦 Analistas",
        "📋 Ratings",
        "📰 Noticias",
        "📊 ETFs"
    ])

    with tab1:
        _seccion_eventos(info_dict)

    with tab2:
        _seccion_analistas(info_dict)

    with tab3:
        _seccion_ratings(info_dict, ticker_global)

    with tab4:
        _seccion_noticias(info_dict, ticker_global)

    with tab5:
        _seccion_etfs(info_dict)