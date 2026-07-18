"""
pages/rotacion.py — Señal de rotación completa por ticker.
Combina Markowitz + RSI + Squeeze + ADX + Order Blocks
para generar una recomendación accionable por cada posición.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartera_db
import core
import tecnico

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

# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE SEÑAL COMBINADA
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_señal_rotacion(
    ticker: str,
    peso_actual: float,
    peso_optimo_sharpe: float,
    peso_optimo_minvar: float,
    df_ohlcv: pd.DataFrame = None
) -> dict:
    """
    Calcula la señal de rotación combinando 4 fuentes:
      1. Markowitz (30 pts) — peso actual vs óptimo
      2. RSI (25 pts)       — zona y divergencias
      3. Squeeze+ADX (25 pts) — momentum y fuerza de tendencia
      4. Order Blocks (20 pts) — soporte/resistencia institucional

    Retorna dict con score, señal, componentes y resumen.
    """
    resultado = {
        "ticker":             ticker,
        "peso_actual":        round(peso_actual * 100, 2),
        "peso_optimo_sharpe": round(peso_optimo_sharpe * 100, 2),
        "peso_optimo_minvar": round(peso_optimo_minvar * 100, 2),
        "score":              50,
        "señal":              "🟡 MANTENER",
        "color":              COLOR_NARANJA,
        "componentes":        {},
        "detalle":            {},
        "resumen":            "Sin datos técnicos disponibles",
        "accion_sugerida":    "Mantener posición actual",
    }

    # ── 1. MARKOWITZ (30 pts) ─────────────────────────────────────────────────
    diff_sharpe = peso_optimo_sharpe - peso_actual
    diff_minvar = peso_optimo_minvar - peso_actual

    score_mk = 15  # base neutral
    if diff_sharpe > 0.08:
        score_mk = 28   # muy subponderado → fuerte señal de sumar
    elif diff_sharpe > 0.04:
        score_mk = 22   # subponderado → sumar
    elif diff_sharpe > 0.01:
        score_mk = 17   # levemente subponderado
    elif diff_sharpe < -0.08:
        score_mk = 2    # muy sobreponderado → reducir
    elif diff_sharpe < -0.04:
        score_mk = 6    # sobreponderado → reducir
    elif diff_sharpe < -0.01:
        score_mk = 11   # levemente sobreponderado

    resultado["componentes"]["Markowitz"] = score_mk
    resultado["detalle"]["markowitz"] = {
        "peso_actual_%":        round(peso_actual * 100, 2),
        "peso_optimo_sharpe_%": round(peso_optimo_sharpe * 100, 2),
        "peso_optimo_minvar_%": round(peso_optimo_minvar * 100, 2),
        "diferencia_%":         round(diff_sharpe * 100, 2),
        "señal":                "SUMAR" if diff_sharpe > 0.04 else
                                "REDUCIR" if diff_sharpe < -0.04 else "MANTENER"
    }

    # ── 2-4. ANÁLISIS TÉCNICO ─────────────────────────────────────────────────
    score_rsi, score_sqz, score_ob = 12, 12, 10  # valores neutrales por defecto

    if df_ohlcv is not None and len(df_ohlcv) >= 50:
        try:
            res_tec = tecnico.analizar(df_ohlcv, ticker)

            # ── RSI (25 pts) ──────────────────────────────────────────────────
            rsi = res_tec.rsi
            if rsi.zona == "sobreventa":
                score_rsi = 22
                if rsi.divergencia == "bullish":
                    score_rsi = 25
            elif rsi.zona == "neutral":
                score_rsi = 13
                if rsi.divergencia == "bullish":
                    score_rsi = 17
                elif rsi.divergencia == "bearish":
                    score_rsi = 8
            elif rsi.zona == "sobrecompra":
                score_rsi = 4
                if rsi.divergencia == "bearish":
                    score_rsi = 2

            resultado["detalle"]["rsi"] = {
                "valor":          rsi.valor_actual,
                "zona":           rsi.zona,
                "divergencia":    rsi.divergencia or "—",
                "periodos_zona":  rsi.periodos_en_zona,
                "pct_rebote_hist": rsi.pct_rebote_tras_sobreventa,
            }

            # ── Squeeze + ADX (25 pts) ────────────────────────────────────────
            sqz = res_tec.squeeze
            score_sqz = 12
            if sqz.squeeze_activo:
                if sqz.momentum_valor > 0 and sqz.momentum_direccion == "subiendo":
                    score_sqz = 22   # squeeze liberando al alza
                elif sqz.momentum_valor > 0:
                    score_sqz = 17
                elif sqz.momentum_valor < 0:
                    score_sqz = 6    # squeeze con momentum negativo
            else:
                if sqz.momentum_valor > 0 and sqz.momentum_direccion == "subiendo":
                    score_sqz = 18
                elif sqz.momentum_valor < 0:
                    score_sqz = 8

            # Bonus/penalidad por ADX
            if sqz.adx_fuerza in ("fuerte", "muy fuerte"):
                if sqz.direccion_adx == "alcista":
                    score_sqz = min(25, score_sqz + 3)
                else:
                    score_sqz = max(0, score_sqz - 3)

            resultado["detalle"]["squeeze_adx"] = {
                "squeeze_activo":    sqz.squeeze_activo,
                "nivel_compresion":  sqz.nivel_compresion,
                "momentum":          round(sqz.momentum_valor, 4),
                "momentum_dir":      sqz.momentum_direccion,
                "adx":               sqz.adx_valor,
                "adx_fuerza":        sqz.adx_fuerza,
                "direccion_adx":     sqz.direccion_adx,
            }

            # ── Order Blocks (20 pts) ─────────────────────────────────────────
            ob = res_tec.order_blocks
            score_ob = 10
            if ob.precio_actual_vs_ob == "en soporte":
                score_ob = 18
            elif ob.precio_actual_vs_ob == "en resistencia":
                score_ob = 3
            elif ob.ob_soporte_mas_cercano:
                dist = abs(ob.ob_soporte_mas_cercano.distancia_pct)
                if dist < 2:
                    score_ob = 15
                elif dist < 5:
                    score_ob = 12

            resultado["detalle"]["order_blocks"] = {
                "posicion":          ob.precio_actual_vs_ob,
                "soporte_cercano":   f"${ob.ob_soporte_mas_cercano.precio_btm:.2f}–${ob.ob_soporte_mas_cercano.precio_top:.2f}"
                                     if ob.ob_soporte_mas_cercano else "—",
                "resistencia_cercana": f"${ob.ob_resistencia_mas_cercana.precio_btm:.2f}–${ob.ob_resistencia_mas_cercana.precio_top:.2f}"
                                       if ob.ob_resistencia_mas_cercana else "—",
                "dist_soporte_%":    round(ob.ob_soporte_mas_cercano.distancia_pct, 2)
                                     if ob.ob_soporte_mas_cercano else None,
            }

            # Tendencia MA
            ma = res_tec.ma
            resultado["detalle"]["ma"] = {
                "tendencia":         ma.tendencia,
                "barras_cruce":      ma.barras_desde_cruce,
                "ultimo_cruce":      ma.ultimo_cruce.tipo if ma.ultimo_cruce else "—",
                "gc_ret60d_hist":    ma.golden_cross_retorno_60d_prom,
            }

        except Exception as e:
            resultado["detalle"]["error_tecnico"] = str(e)

    resultado["componentes"]["RSI"]         = score_rsi
    resultado["componentes"]["Squeeze+ADX"] = score_sqz
    resultado["componentes"]["Order Blocks"]= score_ob

    # ── Score total y señal ───────────────────────────────────────────────────
    score_total = score_mk + score_rsi + score_sqz + score_ob
    resultado["score"] = score_total

    # Señal basada en score Y en Markowitz
    mk_señal = resultado["detalle"].get("markowitz", {}).get("señal", "MANTENER")

    if score_total >= 70 and mk_señal == "SUMAR":
        señal = "🟢 SUMAR"
        color = COLOR_VERDE
        accion = f"Aumentar posición — subponderado {abs(diff_sharpe)*100:.1f}% vs óptimo Sharpe"
    elif score_total >= 70:
        señal = "🟢 COMPRAR / MANTENER"
        color = COLOR_VERDE
        accion = "Señal técnica fuerte — mantener o aumentar si hay liquidez"
    elif score_total >= 55 and mk_señal == "SUMAR":
        señal = "🟡 CONSIDERAR SUMAR"
        color = COLOR_AZUL
        accion = f"Subponderado {abs(diff_sharpe)*100:.1f}% — esperar confirmación técnica"
    elif score_total >= 45:
        señal = "🟡 MANTENER"
        color = COLOR_NARANJA
        accion = "Posición en línea con el óptimo — sin acción urgente"
    elif score_total >= 30 and mk_señal == "REDUCIR":
        señal = "🔴 REDUCIR"
        color = COLOR_ROJO
        accion = f"Sobreponderado {abs(diff_sharpe)*100:.1f}% + señal técnica débil — considerar reducir"
    elif score_total >= 30:
        señal = "🟠 MONITOREAR"
        color = COLOR_NARANJA
        accion = "Señal técnica débil — monitorear de cerca"
    else:
        señal = "🔴 VENDER / REDUCIR"
        color = COLOR_ROJO
        accion = "Señal técnica muy débil + sobreponderado — reducir posición"

    resultado["señal"]  = señal
    resultado["color"]  = color
    resultado["accion_sugerida"] = accion

    # Resumen textual
    partes = []
    mk_d = resultado["detalle"].get("markowitz", {})
    partes.append(f"Markowitz: {mk_d.get('señal','—')} ({mk_d.get('diferencia_%',0):+.1f}%)")
    if "rsi" in resultado["detalle"]:
        rsi_d = resultado["detalle"]["rsi"]
        partes.append(f"RSI {rsi_d['valor']:.1f} ({rsi_d['zona']})")
        if rsi_d["divergencia"] != "—":
            partes.append(f"div. {rsi_d['divergencia']}")
    if "squeeze_adx" in resultado["detalle"]:
        sqz_d = resultado["detalle"]["squeeze_adx"]
        if sqz_d["squeeze_activo"]:
            partes.append(f"Squeeze {sqz_d['nivel_compresion']}")
        partes.append(f"ADX {sqz_d['adx']:.1f} ({sqz_d['adx_fuerza']})")
    if "order_blocks" in resultado["detalle"]:
        partes.append(resultado["detalle"]["order_blocks"]["posicion"])

    resultado["resumen"] = " | ".join(partes)
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ═══════════════════════════════════════════════════════════════════════════════

def _grafico_scores(df_señales: pd.DataFrame) -> go.Figure:
    df = df_señales.sort_values("score", ascending=True)
    colors = []
    for _, row in df.iterrows():
        s = row["score"]
        if s >= 70:   colors.append(COLOR_VERDE)
        elif s >= 55: colors.append(COLOR_AZUL)
        elif s >= 45: colors.append(COLOR_NARANJA)
        else:         colors.append(COLOR_ROJO)

    fig = go.Figure(go.Bar(
        x=df["score"], y=df["ticker"],
        orientation="h",
        marker_color=colors,
        text=[f"{s}/100" for s in df["score"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Score: %{x}/100<extra></extra>"
    ))
    fig.add_vline(x=70, line_dash="dash", line_color=COLOR_VERDE,
                  annotation_text="SUMAR", annotation_position="top")
    fig.add_vline(x=45, line_dash="dash", line_color=COLOR_NARANJA,
                  annotation_text="MANTENER", annotation_position="top")
    fig.add_vline(x=30, line_dash="dash", line_color=COLOR_ROJO,
                  annotation_text="REDUCIR", annotation_position="top")
    fig.update_layout(
        title="Score de rotación por ticker (0-100)",
        xaxis=dict(range=[0, 110], title="Score"),
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=max(300, len(df) * 40 + 80),
        showlegend=False
    )
    return fig

def _grafico_pesos(df_señales: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Peso actual", x=df_señales["ticker"],
        y=df_señales["peso_actual"],
        marker_color=COLOR_AZUL,
        hovertemplate="<b>%{x}</b><br>Actual: %{y:.1f}%<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        name="Óptimo Sharpe", x=df_señales["ticker"],
        y=df_señales["peso_optimo_sharpe"],
        marker_color=COLOR_VERDE,
        hovertemplate="<b>%{x}</b><br>Óptimo Sharpe: %{y:.1f}%<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        name="Óptimo Mín.Var", x=df_señales["ticker"],
        y=df_señales["peso_optimo_minvar"],
        marker_color=COLOR_NARANJA,
        hovertemplate="<b>%{x}</b><br>Óptimo MinVar: %{y:.1f}%<extra></extra>"
    ))
    fig.update_layout(
        barmode="group",
        title="Peso actual vs Portafolios óptimos (%)",
        yaxis_title="Peso (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=380,
        legend=dict(bgcolor=BG_CARD)
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def render():
    st.title("🔄 Señal de Rotación")
    st.markdown(
        "Señal combinada por ticker: **Markowitz + RSI + Squeeze + ADX + Order Blocks**. "
        "Te dice qué hacer con cada posición de tu cartera."
    )

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")

        # Selector de cartera
        uid = _get_user_id()
        df_carteras = cartera_db.listar_carteras(usuario_id=uid)
        if df_carteras.empty:
            st.warning("No tenés carteras. Creá una en Mi Cartera.")
            return

        opciones = {f"{r['nombre']} ({r['moneda_base']})": r['id']
                    for _, r in df_carteras.iterrows()}
        sel = st.selectbox("Cartera a analizar", list(opciones.keys()),
                           key="rot_cartera_sel")
        cartera_id = opciones[sel]

        anios = st.slider("Años de historia (Markowitz)", 1, 10, 3)
        incluir_tecnico = st.checkbox("Incluir análisis técnico", value=True,
                                       help="Descarga datos diarios para RSI, Squeeze y Order Blocks")
        periodo_tec = st.selectbox("Período técnico", ["1y", "2y", "3y"], index=1)
        analizar = st.button("▶️ Calcular señales", type="primary",
                             use_container_width=True)

    if not analizar:
        st.info("👈 Seleccioná tu cartera y presioná **Calcular señales**.")
        st.markdown("---")
        st.markdown("## ¿Cómo se calcula la señal?")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **⚖️ Markowitz (30 pts)**
            - Compara tu peso actual vs el portafolio óptimo de Máximo Sharpe
            - Subponderado → señal de sumar
            - Sobreponderado → señal de reducir

            **📉 RSI (25 pts)**
            - Sobreventa (RSI<30) → señal alcista
            - Sobrecompra (RSI>70) → señal bajista
            - Divergencias bull/bear suman/restan puntos
            """)
        with col2:
            st.markdown("""
            **🔥 Squeeze + ADX (25 pts)**
            - Squeeze activo con momentum positivo → expansión alcista inminente
            - ADX fuerte en dirección alcista → tendencia confirmada

            **🧱 Order Blocks (20 pts)**
            - Precio en zona de soporte institucional → señal de compra
            - Precio en zona de resistencia → señal de venta
            """)

        st.markdown("""
        | Score | Señal | Acción |
        |-------|-------|--------|
        | 70-100 + subponderado | 🟢 SUMAR | Aumentar posición |
        | 70-100 | 🟢 COMPRAR/MANTENER | Mantener o aumentar |
        | 55-69 + subponderado | 🟡 CONSIDERAR SUMAR | Esperar confirmación |
        | 45-54 | 🟡 MANTENER | Sin acción urgente |
        | 30-44 + sobreponderado | 🔴 REDUCIR | Reducir posición |
        | 0-29 | 🔴 VENDER/REDUCIR | Reducir urgente |
        """)
        return

    # ── Obtener posiciones ────────────────────────────────────────────────────
    df_pos = cartera_db.listar_posiciones(cartera_id)
    if df_pos.empty:
        st.error("❌ La cartera no tiene posiciones de acciones/CEDEARs.")
        return

    tickers = df_pos["ticker"].unique().tolist()
    # Filtrar tickers con sufijo .BA para Markowitz (usar el subyacente)
    tickers_mk = [t for t in tickers if not t.endswith(".BA")]
    if len(tickers_mk) < 2:
        st.warning("Se necesitan al menos 2 tickers internacionales para Markowitz.")
        tickers_mk = tickers[:max(2, len(tickers))]

    # ── Markowitz ─────────────────────────────────────────────────────────────
    with st.spinner("📐 Calculando portafolios óptimos..."):
        try:
            df_close = core.descargar_precios(tuple(tickers_mk), anios=anios)
            if df_close.empty or df_close.shape[1] < 2:
                st.error("❌ Datos insuficientes para Markowitz.")
                return
            mk = core.calcular_markowitz(df_close)
            tickers_ok = mk["cols"]
            w_sharpe   = dict(zip(tickers_ok, mk["w_max"]))
            w_minvar   = dict(zip(tickers_ok, mk["w_min"]))
            w_equal    = dict(zip(tickers_ok, mk["w_eq"]))
        except Exception as e:
            st.error(f"❌ Error en Markowitz: {e}")
            return

    # Calcular pesos actuales de la cartera
    ccl = core.obtener_dolar_ccl()
    df_pnl = cartera_db.calcular_pnl(cartera_id, ccl=ccl)
    pesos_actuales = cartera_db.pesos_cartera(df_pnl)
    pesos_dict = dict(zip(
        pesos_actuales["Ticker"],
        pesos_actuales["Peso (%)"] / 100
    )) if not pesos_actuales.empty else {}

    # ── Análisis técnico por ticker ───────────────────────────────────────────
    datos_ohlcv = {}
    if incluir_tecnico:
        prog = st.progress(0)
        status = st.empty()
        for i, t in enumerate(tickers_ok):
            status.text(f"📊 Análisis técnico: {t}...")
            try:
                df_t = yf.download(t, period=periodo_tec, interval="1d",
                                   progress=False, auto_adjust=True)
                if isinstance(df_t.columns, pd.MultiIndex):
                    df_t.columns = df_t.columns.droplevel(1)
                if not df_t.empty and len(df_t) >= 50:
                    datos_ohlcv[t] = df_t
            except Exception:
                pass
            prog.progress((i+1)/len(tickers_ok))
        prog.empty()
        status.empty()

    # ── Calcular señales ──────────────────────────────────────────────────────
    señales = []
    for t in tickers_ok:
        peso_actual = pesos_dict.get(t, 0)
        señal = calcular_señal_rotacion(
            ticker=t,
            peso_actual=peso_actual,
            peso_optimo_sharpe=w_sharpe.get(t, 0),
            peso_optimo_minvar=w_minvar.get(t, 0),
            df_ohlcv=datos_ohlcv.get(t)
        )
        señales.append(señal)

    # Ordenar por score descendente
    señales.sort(key=lambda x: x["score"], reverse=True)
    df_señales = pd.DataFrame([{
        "ticker":             s["ticker"],
        "score":              s["score"],
        "señal":              s["señal"],
        "peso_actual":        s["peso_actual"],
        "peso_optimo_sharpe": s["peso_optimo_sharpe"],
        "peso_optimo_minvar": s["peso_optimo_minvar"],
        "accion":             s["accion_sugerida"],
        "resumen":            s["resumen"],
    } for s in señales])

    # ── Resumen ejecutivo ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🎯 Resumen ejecutivo")

    n_sumar    = sum(1 for s in señales if "SUMAR" in s["señal"] or "COMPRAR" in s["señal"])
    n_mantener = sum(1 for s in señales if "MANTENER" in s["señal"] or "CONSIDERAR" in s["señal"])
    n_reducir  = sum(1 for s in señales if "REDUCIR" in s["señal"] or "VENDER" in s["señal"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Sumar/Comprar", n_sumar)
    c2.metric("🟡 Mantener", n_mantener)
    c3.metric("🔴 Reducir/Vender", n_reducir)
    c4.metric("📊 Tickers analizados", len(señales))

    # ── Cards por ticker ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📋 Señal por ticker")

    for s in señales:
        color = s["color"]
        score = s["score"]

        # Barra de score
        pct = score / 100
        bar_color = COLOR_VERDE if score >= 70 else (COLOR_NARANJA if score >= 45 else COLOR_ROJO)

        st.markdown(
            f'<div style="background:{BG_CARD};padding:16px 20px;border-radius:10px;'
            f'border-left:5px solid {color};margin-bottom:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<span style="font-size:18px;font-weight:700;color:white">{s["ticker"]}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="background:{color};color:#fff;padding:3px 12px;'
            f'border-radius:12px;font-size:13px;font-weight:600">{s["señal"]}</span>'
            f'</div>'
            f'<div style="text-align:right">'
            f'<span style="color:{bar_color};font-size:22px;font-weight:700">{score}/100</span>'
            f'</div>'
            f'</div>'
            f'<div style="margin:8px 0 4px 0;background:#333;border-radius:4px;height:6px">'
            f'<div style="width:{pct*100:.0f}%;background:{bar_color};height:6px;border-radius:4px"></div>'
            f'</div>'
            f'<div style="color:#ccc;font-size:13px;margin-top:6px">'
            f'💡 <b>{s["accion_sugerida"]}</b>'
            f'</div>'
            f'<div style="color:#888;font-size:12px;margin-top:4px">{s["resumen"]}</div>'
            f'<div style="display:flex;gap:20px;margin-top:8px">'
            f'<span style="color:#aaa;font-size:11px">Peso actual: <b style="color:white">{s["peso_actual"]:.1f}%</b></span>'
            f'<span style="color:#aaa;font-size:11px">Óptimo Sharpe: <b style="color:{COLOR_VERDE}">{s["peso_optimo_sharpe"]:.1f}%</b></span>'
            f'<span style="color:#aaa;font-size:11px">Óptimo MinVar: <b style="color:{COLOR_NARANJA}">{s["peso_optimo_minvar"]:.1f}%</b></span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    # ── Gráficos ──────────────────────────────────────────────────────────────
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 Scores", "⚖️ Pesos", "📋 Tabla detalle"])

    with tab1:
        st.plotly_chart(_grafico_scores(df_señales), use_container_width=True)

    with tab2:
        st.plotly_chart(_grafico_pesos(df_señales), use_container_width=True)

    with tab3:
        def color_señal(val):
            if "SUMAR" in str(val) or "COMPRAR" in str(val):
                return "color: #00c896; font-weight: bold"
            if "REDUCIR" in str(val) or "VENDER" in str(val):
                return "color: #f74f4f; font-weight: bold"
            return "color: #f7a34f"

        def color_score(val):
            try:
                v = int(val)
                if v >= 70: return "background-color: #1b2d1b; color: #00c896; font-weight: bold"
                if v >= 45: return "background-color: #2d2a1b; color: #f7a34f"
                return "background-color: #2d1b1b; color: #f74f4f"
            except Exception:
                return ""

        cols_show = ["ticker","score","señal","peso_actual",
                     "peso_optimo_sharpe","peso_optimo_minvar","accion"]
        st.dataframe(
            df_señales[cols_show].style
                .map(color_señal, subset=["señal"])
                .map(color_score, subset=["score"])
                .format({
                    "peso_actual":        "{:.1f}%",
                    "peso_optimo_sharpe": "{:.1f}%",
                    "peso_optimo_minvar": "{:.1f}%",
                }),
            use_container_width=True, hide_index=True
        )

        # Exportar
        from io import BytesIO
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_señales.to_excel(writer, sheet_name="Señales rotación", index=False)
        st.download_button(
            "⬇️ Exportar señales a Excel",
            data=buf.getvalue(),
            file_name=f"señales_rotacion_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )