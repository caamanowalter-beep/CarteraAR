
"""
pages/analisis.py — Análisis de portafolio: Markowitz + Fundamentales.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core
import cedear_mapper

# ── Paleta de colores ─────────────────────────────────────────────────────────
COLOR_VERDE  = "#00c896"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA = "#f7a34f"
COLOR_ROJO   = "#f74f4f"
BG_DARK      = "#0f1117"
BG_CARD      = "#1e2130"

def _fmt_pct(v):
    return f"{v*100:.1f}%" if v is not None else "—"

def _fmt_num(v, dec=2):
    return f"{v:,.{dec}f}" if v is not None else "—"

def _color_recomendacion(rec: str) -> str:
    if "Alta"        in rec: return COLOR_VERDE
    if "Interesante" in rec: return COLOR_AZUL
    if "Débil"       in rec: return COLOR_ROJO
    return "#888"

# ── Gráfico frontera eficiente ────────────────────────────────────────────────
def _grafico_frontera(mk: dict) -> go.Figure:
    fe = core.frontera_eficiente(mk, n_puntos=150)
    fig = go.Figure()

    # Frontera eficiente (solo si hay datos validos)
    if not fe.empty and "Volatilidad" in fe.columns and "Retorno" in fe.columns:
        fig.add_trace(go.Scatter(
            x=fe["Volatilidad"], y=fe["Retorno"],
            mode="lines", name="Frontera eficiente",
            line=dict(color=COLOR_AZUL, width=2),
            hovertemplate="Vol: %{x:.2%}<br>Ret: %{y:.2%}<extra></extra>"
        ))

    # Portafolios óptimos
    for label, w, color in [
        ("Equilibrado",   mk["w_eq"],  COLOR_NARANJA),
        ("Mín. Varianza", mk["w_min"], COLOR_VERDE),
        ("Máx. Sharpe",   mk["w_max"], COLOR_ROJO),
    ]:
        fig.add_trace(go.Scatter(
            x=[mk["port_vol"](w)], y=[mk["port_ret"](w)],
            mode="markers+text", name=label,
            marker=dict(size=12, color=color, symbol="diamond"),
            text=[label], textposition="top center",
            hovertemplate=f"<b>{label}</b><br>Vol: %{{x:.2%}}<br>Ret: %{{y:.2%}}<extra></extra>"
        ))

    # Activos individuales
    est = mk["estadisticas"]
    fig.add_trace(go.Scatter(
        x=est["Desviación estándar"], y=est["Retorno esperado"],
        mode="markers+text", name="Activos",
        marker=dict(size=8, color="#aaa"),
        text=est["Ticker"], textposition="top right",
        hovertemplate="<b>%{text}</b><br>Vol: %{x:.2%}<br>Ret: %{y:.2%}<extra></extra>"
    ))

    fig.update_layout(
        title="Frontera Eficiente de Markowitz",
        xaxis_title="Volatilidad (riesgo anualizado)",
        yaxis_title="Retorno esperado anualizado",
        xaxis_tickformat=".0%", yaxis_tickformat=".0%",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), legend=dict(bgcolor=BG_CARD),
        height=480
    )
    return fig

# ── Gráfico de pesos ──────────────────────────────────────────────────────────
def _grafico_pesos(pesos_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    cols_pesos = ["Peso Igual", "Peso Min Var", "Peso Max Sharpe"]
    colors     = [COLOR_NARANJA, COLOR_VERDE, COLOR_ROJO]
    for col, color in zip(cols_pesos, colors):
        fig.add_trace(go.Bar(
            name=col, x=pesos_df["Ticker"], y=pesos_df[col],
            marker_color=color,
            hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y:.1%}}<extra></extra>"
        ))
    fig.update_layout(
        barmode="group", title="Distribución de Pesos por Portafolio",
        yaxis_tickformat=".0%",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), legend=dict(bgcolor=BG_CARD),
        height=380
    )
    return fig

# ── Heatmap correlaciones ─────────────────────────────────────────────────────
def _grafico_corr(corr: pd.DataFrame) -> go.Figure:
    fig = px.imshow(
        corr, text_auto=".2f", aspect="auto",
        color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
        title="Matriz de Correlaciones"
    )
    fig.update_layout(
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=420
    )
    return fig

# ── Exportar Excel ────────────────────────────────────────────────────────────
def _exportar_excel(df_close, mk, fund_df, reporte_elim) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_close.to_excel(writer,              sheet_name="Precios")
        mk["estadisticas"].to_excel(writer,    sheet_name="Estadísticas",  index=False)
        mk["pesos"].to_excel(writer,           sheet_name="Pesos",         index=False)
        mk["resumen"].to_excel(writer,         sheet_name="Resumen",       index=False)
        mk["corr"].to_excel(writer,            sheet_name="Correlaciones")
        fund_df.to_excel(writer,               sheet_name="Fundamentales", index=False)
        if not reporte_elim.empty:
            reporte_elim.to_excel(writer,      sheet_name="Eliminados",    index=False)
    return buf.getvalue()

# ── RENDER PRINCIPAL ──────────────────────────────────────────────────────────
def render():
    st.title("📊 Análisis de Cartera")
    st.markdown("Ingresá los tickers y parámetros para calcular el portafolio óptimo.")

    # ── Sidebar de parámetros ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Fuente de tickers")

        # Selector de fuente
        fuente = st.radio(
            "Analizar",
            ["📝 Tickers manuales", "💼 Desde Mi Cartera"],
            index=0
        )

        tickers_input = ""
        if fuente == "💼 Desde Mi Cartera":
            # Importar cartera_db para leer carteras
            try:
                import cartera_db
                df_carteras = cartera_db.listar_carteras()
                if df_carteras.empty:
                    st.warning("No tenés carteras creadas. Usá tickers manuales.")
                    fuente = "📝 Tickers manuales"
                else:
                    opciones_cart = {
                        f"{row['nombre']} ({row['moneda_base']})": row['id']
                        for _, row in df_carteras.iterrows()
                    }
                    # Opción para analizar todas las carteras combinadas
                    opciones_cart["🔀 Todas las carteras"] = -1
                    sel_cart = st.selectbox(
                        "Seleccioná cartera",
                        list(opciones_cart.keys()),
                        key="analisis_cartera_sel"
                    )
                    cart_id = opciones_cart[sel_cart]

                    if cart_id == -1:
                        # Todas las carteras
                        tickers_set = set()
                        for _, row in df_carteras.iterrows():
                            df_pos = cartera_db.listar_posiciones(row['id'])
                            if not df_pos.empty:
                                tickers_set.update(df_pos["ticker"].tolist())
                        tickers_lista = list(tickers_set)
                    else:
                        df_pos = cartera_db.listar_posiciones(cart_id)
                        tickers_lista = df_pos["ticker"].tolist() if not df_pos.empty else []

                    if tickers_lista:
                        st.success(f"✅ {len(tickers_lista)} tickers: {', '.join(tickers_lista)}")
                        tickers_input = ", ".join(tickers_lista)
                    else:
                        st.warning("La cartera no tiene posiciones.")
                        fuente = "📝 Tickers manuales"
            except Exception as e:
                st.warning(f"No se pudo leer Mi Cartera: {e}")
                fuente = "📝 Tickers manuales"

        if fuente == "📝 Tickers manuales":
            tickers_input = st.text_area(
                "Tickers (separados por coma)",
                value=tickers_input or "AAPL, MSFT, NVDA, KO, QQQ, SPY, VIST, MELI",
                height=100
            )

        st.markdown("---")
        st.markdown("### ⚙️ Parámetros")
        anios = st.slider("Años de historia", 1, 15, 10)
        st.markdown("**Filtros fundamentales**")
        margen_min = st.slider("Margen Neto mínimo (%)", 0, 50, 20) / 100
        roic_min   = st.slider("ROIC mínimo (%)",        0, 40, 15) / 100
        de_max     = st.slider("D/E máximo",             0.0, 5.0, 2.0, 0.1)
        aplicar_filtro = st.checkbox("Aplicar filtro fundamental", value=False)
        correr = st.button("▶️ Analizar", type="primary", use_container_width=True)

    if not correr:
        st.info("👈 Seleccioná la fuente de tickers en el panel izquierdo y presioná **Analizar**.")
        return

    if not tickers_input.strip():
        st.error("❌ No hay tickers para analizar.")
        return

    # ── Parseo de tickers ─────────────────────────────────────────────────────
    raw = [core.corregir_ticker(t.strip()) for t in tickers_input.split(",") if t.strip()]

    # Expandir tickers con manejo de error robusto
    try:
        tickers_exp, sin_equiv = cedear_mapper.expandir_tickers(raw)
        if sin_equiv:
            st.warning(f"⚠️ Sin equivalencia ADR: {', '.join(sin_equiv)}")
    except Exception:
        # Fallback: usar tickers tal como vienen sin expansión ADR
        tickers_exp = [t for t in raw if t and not t.endswith(".BA")]
        sin_equiv   = []

    # ── Descarga de precios ───────────────────────────────────────────────────
    with st.spinner("📥 Descargando precios históricos..."):
        try:
            df_close = core.descargar_precios(tuple(tickers_exp), anios=anios)
        except Exception as e:
            st.error(f"❌ Error al descargar precios: {e}")
            return

    if df_close.empty or df_close.shape[1] < 2:
        st.error("❌ No hay suficientes datos para calcular el portafolio. Verificá los tickers y la conexión.")
        return

    tickers_ok = df_close.columns.tolist()
    st.success(f"✅ {len(tickers_ok)} tickers con datos: {', '.join(tickers_ok)}")

    # ── Filtro fundamental (opcional) ─────────────────────────────────────────
    reporte_elim = pd.DataFrame()
    if aplicar_filtro:
        with st.spinner("🔍 Aplicando filtro fundamental..."):
            tickers_filtrados, reporte_elim = core.filtrar_por_fundamentales(
                tickers_ok, margen_min, roic_min, de_max
            )
        if len(tickers_filtrados) < len(tickers_ok):
            st.info(f"🔽 Filtro aplicado: {len(tickers_ok)} → {len(tickers_filtrados)} tickers")
        if len(tickers_filtrados) >= 2:
            df_close = df_close[tickers_filtrados]
            tickers_ok = tickers_filtrados
        else:
            st.warning("⚠️ Muy pocos tickers tras el filtro — se usa la lista completa.")

    # ── Markowitz ─────────────────────────────────────────────────────────────
    with st.spinner("📐 Calculando portafolios óptimos..."):
        mk = core.calcular_markowitz(df_close)

    # ── Score Buffett batch ───────────────────────────────────────────────────
    cache_key = f"buffett_scores_{'_'.join(sorted(tickers_ok))}"
    if cache_key not in st.session_state:
        with st.spinner(f"Calculando Score Buffett para {len(tickers_ok)} tickers..."):
            scores_batch = {}
            prog_b = st.progress(0)
            for i_b, t_b in enumerate(tickers_ok):
                try:
                    scores_batch[t_b] = core.score_buffett(core.obtener_fundamentales(t_b))
                except Exception:
                    scores_batch[t_b] = {"score":0,"clasificacion":"Sin datos","color":"#888",
                                          "detalles":[],"rentabilidad":0,"crecimiento":0,
                                          "solidez":0,"valuacion":0,"moat":0}
                prog_b.progress((i_b+1)/len(tickers_ok))
            prog_b.empty()
            st.session_state[cache_key] = scores_batch
    else:
        scores_batch = st.session_state[cache_key]
    st.session_state["_buffett_cache_key"] = cache_key

    # ── Métricas resumen ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🎯 Portafolios Óptimos")
    c1, c2, c3 = st.columns(3)
    res = mk["resumen"]
    for col, row, icon in zip([c1,c2,c3], res.itertuples(), ["⚖️","🛡️","🚀"]):
        with col:
            st.metric(f"{icon} {row.Tipo}",
                      f"Ret: {row.Retorno:.1%}",
                      f"Vol: {row.Volatilidad:.1%} | Sharpe: {row.Sharpe:.2f}")

    
    # ── Métricas avanzadas Markowitz ──────────────────────────────────────────
    with st.spinner("Calculando métricas avanzadas..."):
        try:
            metricas_avz = core.calcular_metricas_avanzadas(df_close, mk)
        except Exception:
            metricas_avz = {}

    if metricas_avz:
        st.markdown("#### Métricas de Riesgo Avanzadas")
        cols_avz = st.columns(3)
        for i_avz, (nombre_avz, metricas_c) in enumerate(metricas_avz.items()):
            with cols_avz[i_avz]:
                st.markdown(f"**{nombre_avz}**")
                var_d   = metricas_c.get("VaR 95% diario (%)")
                var_m   = metricas_c.get("VaR 95% mensual (%)")
                sortino = metricas_c.get("Sortino Ratio")
                mdd     = metricas_c.get("Max Drawdown (%)")
                if var_d   is not None: st.metric("VaR 95% diario",   f"{var_d:.2f}%")
                if var_m   is not None: st.metric("VaR 95% mensual",  f"{var_m:.2f}%")
                if sortino is not None: st.metric("Sortino Ratio",    f"{sortino:.2f}")
                if mdd     is not None: st.metric("Max Drawdown",     f"{mdd:.1f}%")

    # ── Tabs de contenido ─────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Frontera Eficiente", "Pesos", "Correlaciones",
        "Estadísticas", "Score Buffett"
    ])

    with tab1:
        st.plotly_chart(_grafico_frontera(mk), use_container_width=True)

    with tab2:
        st.plotly_chart(_grafico_pesos(mk["pesos"]), use_container_width=True)
        st.dataframe(
            mk["pesos"].style.format({
                "Peso Igual":      "{:.1%}",
                "Peso Min Var":    "{:.1%}",
                "Peso Max Sharpe": "{:.1%}"
            }),
            use_container_width=True, hide_index=True
        )

    with tab3:
        st.plotly_chart(_grafico_corr(mk["corr"]), use_container_width=True)
        st.caption("Valores cercanos a 1 = alta correlación (menor diversificación). Cercanos a -1 = correlación inversa (mayor diversificación).")

    with tab4:
        st.dataframe(
            mk["estadisticas"].style.format({
                "Retorno esperado":    "{:.2%}",
                "Varianza":            "{:.4f}",
                "Desviación estándar": "{:.2%}",
                "Proporción":          "{:.2%}"
            }).map(lambda v: "color: #00c896; font-weight: bold" if isinstance(v, (int,float)) and v > 0.15 else ("color: #f7a34f" if isinstance(v, (int,float)) and v > 0.05 else ""), subset=["Retorno esperado"]),
            use_container_width=True, hide_index=True
        )
        if not reporte_elim.empty:
            st.markdown("#### ❌ Tickers eliminados por filtro fundamental")
            st.dataframe(reporte_elim[["Ticker","Motivo","profitMargins","ROIC_proxy","debtToEquity"]],
                         use_container_width=True, hide_index=True)

    
    with tab5:
        st.markdown("### Score Buffett — Analisis por ticker")
        if tickers_ok and "_buffett_cache_key" in st.session_state:
            sb = st.session_state.get(st.session_state["_buffett_cache_key"], {})
            ticker_buff = st.selectbox("Ticker a analizar", tickers_ok, key="buff_sel")
            res = sb.get(ticker_buff, {})
            if not res:
                with st.spinner(f"Calculando {ticker_buff}..."):
                    try: res = core.score_buffett(core.obtener_fundamentales(ticker_buff))
                    except: res = {}
            if res:
                sc=res.get("score",0); col=res.get("color","#888"); cl=res.get("clasificacion","")
                st.markdown(f'<div style="background:#1e2130;padding:8px 12px;border-radius:8px;border-left:4px solid {col};margin-bottom:8px"><div style="color:#aaa;font-size:10px">Score Buffett</div><div style="color:{col};font-size:28px;font-weight:700">{sc}/100</div><div style="color:white;font-size:12px">{cl}</div></div>', unsafe_allow_html=True)
                cats=[("Rentabilidad",res.get("rentabilidad",0),30,"#4f8ef7"),("Crecimiento",res.get("crecimiento",0),20,"#00c896"),("Solidez",res.get("solidez",0),25,"#f7a34f"),("Valuacion",res.get("valuacion",0),15,"#9b59b6"),("Moat",res.get("moat",0),10,"#1abc9c")]
                st.markdown("#### Desglose")
                cols_c=st.columns(5)
                for i_c,(cat,pts,mx,cc) in enumerate(cats):
                    pct=pts/mx*100 if mx>0 else 0
                    with cols_c[i_c]:
                        st.markdown(f'<div style="background:#1e2130;padding:5px;border-radius:6px;text-align:center"><div style="color:#aaa;font-size:10px">{cat}</div><div style="color:{cc};font-size:16px;font-weight:700">{pts}/{mx}</div><div style="color:#aaa;font-size:10px">{pct:.0f}%</div></div>', unsafe_allow_html=True)
                st.markdown("#### Indicadores")
                det=res.get("detalles",[])
                if det:
                    st.dataframe(pd.DataFrame(det,columns=["Indicador","Valor","Estado","Puntos","Descripcion"]),use_container_width=True,hide_index=True)
                if len(sb)>1:
                    st.markdown("---")
                    st.markdown("#### Ranking Buffett")
                    rk=[{"Ticker":t,"Score":v.get("score",0),"Clasificacion":v.get("clasificacion",""),"Rentabilidad":v.get("rentabilidad",0),"Crecimiento":v.get("crecimiento",0),"Solidez":v.get("solidez",0),"Valuacion":v.get("valuacion",0),"Moat":v.get("moat",0)} for t,v in sb.items()]
                    df_rk=pd.DataFrame(rk).sort_values("Score",ascending=False)
                    st.dataframe(df_rk.style.map(lambda v:"background-color:#1b2d1b;color:#00c896" if isinstance(v,(int,float)) and v>=75 else "background-color:#2d2a1b;color:#f7a34f" if isinstance(v,(int,float)) and v>=55 else "background-color:#2d1b1b;color:#f74f4f" if isinstance(v,(int,float)) and v<35 else "",subset=["Score"]),use_container_width=True,hide_index=True)
            else:
                st.info(f"Sin datos para {ticker_buff}.")
        elif tickers_ok:
            st.info("Presiona **Analizar** para calcular el Score Buffett.")
        else:
            st.info("No hay tickers disponibles.")


    # ── Exportar Excel ────────────────────────────────────────────────────────
    st.markdown("---")
    excel_bytes = _exportar_excel(df_close, mk, pd.DataFrame(), reporte_elim)
    st.download_button(
        "⬇️ Descargar Excel completo",
        data=excel_bytes,
        file_name=f"analisis_cartera_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

