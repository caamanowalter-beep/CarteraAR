"""
pages/inicio.py — Dashboard principal con resumen de inversiones por grupo.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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

def _card_metrica(titulo: str, valor: str, subtitulo: str = "",
                  color: str = COLOR_AZUL, delta: str = None):
    delta_html = ""
    if delta:
        d_color = COLOR_VERDE if "+" in delta else COLOR_ROJO
        delta_html = f'<div style="color:{d_color};font-size:14px;font-weight:600">{delta}</div>'
    st.markdown(
        f'<div style="background:{BG_CARD};padding:16px 20px;border-radius:10px;'
        f'border-left:4px solid {color};margin-bottom:8px">'
        f'<div style="color:#aaa;font-size:12px">{titulo}</div>'
        f'<div style="color:white;font-size:24px;font-weight:700">{valor}</div>'
        f'{delta_html}'
        f'<div style="color:#888;font-size:11px">{subtitulo}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

CHART_HEIGHT = 360  # altura uniforme para todos los gráficos del dashboard

def _grafico_composicion_total(grupos: dict) -> go.Figure:
    """Gráfico de torta con composición total de la cartera."""
    labels = list(grupos.keys())
    values = [g["valor_usd"] for g in grupos.values()]
    colors = [COLOR_AZUL, COLOR_VERDE, COLOR_NARANJA, COLOR_ROJO, "#9b59b6", "#1abc9c"]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.45,
        marker_colors=colors[:len(labels)],
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>$%{value:,.2f} USD<br>%{percent}<extra></extra>"
    ))
    fig.update_layout(
        title="Composición total de la cartera",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=CHART_HEIGHT,
        legend=dict(bgcolor=BG_CARD),
        margin=dict(t=50, b=20, l=20, r=20)
    )
    return fig


def _grafico_composicion_detallada(df_pnl: pd.DataFrame, ccl: float) -> go.Figure:
    """
    Gráfico de torta detallado separando:
    - Acciones internacionales vs CEDEARs
    - Por sector (Tecnología, Consumo, Energía, ETFs, etc.)
    """
    if df_pnl.empty:
        return None

    # Mapeo de tickers a sector
    SECTORES = {
        # Tecnología
        "AAPL":"Tecnología","MSFT":"Tecnología","NVDA":"Tecnología",
        "GOOGL":"Tecnología","META":"Tecnología","AMZN":"Tecnología",
        "AMD":"Tecnología","INTC":"Tecnología","IBM":"Tecnología",
        "MU":"Tecnología","TSLA":"Tecnología","ANET":"Tecnología",
        "CRWD":"Tecnología","PLTR":"Tecnología",
        # Consumo masivo
        "KO":"Consumo masivo","MCD":"Consumo masivo","PEP":"Consumo masivo",
        "WMT":"Consumo masivo","COST":"Consumo masivo","PG":"Consumo masivo",
        # Finanzas
        "V":"Finanzas","MA":"Finanzas","JPM":"Finanzas","BAC":"Finanzas",
        "GS":"Finanzas","MS":"Finanzas","BRK-B":"Finanzas",
        "GGAL":"Finanzas AR","BMA":"Finanzas AR","BBAR":"Finanzas AR",
        "SUPV":"Finanzas AR","BYMA":"Finanzas AR",
        # Energía
        "XLE":"ETF Energía","CVX":"Energía","XOM":"Energía",
        "YPFD":"Energía AR","PAMP":"Energía AR","CEPU":"Energía AR",
        "TGSU2":"Energía AR","EDN":"Energía AR",
        # ETFs
        "SPY":"ETF Mercado","QQQ":"ETF Mercado","DIA":"ETF Mercado",
        "IWM":"ETF Mercado","XLF":"ETF Finanzas","XLP":"ETF Consumo",
        "XLV":"ETF Salud","XLC":"ETF Comunicación","XLK":"ETF Tecnología",
        "IBIT":"ETF Cripto","URA":"ETF Uranio","ARKK":"ETF Innovación",
        # Salud
        "JNJ":"Salud","PFE":"Salud","MRK":"Salud","ABBV":"Salud",
        # Materiales/Industria
        "RIO":"Materiales","LOMA":"Materiales AR","ALUA":"Materiales AR",
        # Comunicación
        "MELI":"Comunicación","VIST":"Energía AR","NU":"Finanzas",
        "DISN":"Entretenimiento","DIS":"Entretenimiento",
        # Otros argentinos
        "TECO2":"Telecom AR","IRSA":"Real Estate AR",
    }

    COLORES_SECTOR = {
        "Tecnología":       "#4f8ef7",
        "Consumo masivo":   "#f7a34f",
        "Finanzas":         "#00c896",
        "Finanzas AR":      "#1abc9c",
        "Energía":          "#e74c3c",
        "Energía AR":       "#c0392b",
        "ETF Mercado":      "#9b59b6",
        "ETF Finanzas":     "#8e44ad",
        "ETF Consumo":      "#d35400",
        "ETF Salud":        "#27ae60",
        "ETF Tecnología":   "#2980b9",
        "ETF Cripto":       "#f39c12",
        "ETF Uranio":       "#7f8c8d",
        "ETF Innovación":   "#16a085",
        "ETF Comunicación": "#2c3e50",
        "Salud":            "#2ecc71",
        "Materiales":       "#95a5a6",
        "Materiales AR":    "#7f8c8d",
        "Comunicación":     "#3498db",
        "Entretenimiento":  "#e67e22",
        "Telecom AR":       "#1abc9c",
        "Real Estate AR":   "#e74c3c",
        "Otros":            "#bdc3c7",
    }

    # Agrupar por sector
    sectores_valor = {}
    for _, row in df_pnl.iterrows():
        ticker = str(row.get("Ticker", "")).upper().replace(".BA", "")
        valor  = float(row.get("Valor actual (USD)") or 0)
        if valor <= 0:
            continue
        sector = SECTORES.get(ticker, "Otros")
        sectores_valor[sector] = sectores_valor.get(sector, 0) + valor

    if not sectores_valor:
        return None

    # Ordenar por valor
    sectores_sorted = sorted(sectores_valor.items(), key=lambda x: x[1], reverse=True)
    labels = [s[0] for s in sectores_sorted]
    values = [s[1] for s in sectores_sorted]
    colors = [COLORES_SECTOR.get(l, "#bdc3c7") for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.4,
        marker_colors=colors,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>$%{value:,.2f} USD<br>%{percent}<extra></extra>"
    ))
    fig.update_layout(
        title="Composición por sector",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=CHART_HEIGHT,
        legend=dict(bgcolor=BG_CARD, font=dict(size=10)),
        margin=dict(t=50, b=20, l=20, r=20)
    )
    return fig


def _grafico_composicion_tipo(df_pnl: pd.DataFrame) -> go.Figure:
    """
    Gráfico separando Acciones internacionales vs CEDEARs.
    """
    if df_pnl.empty:
        return None

    tipo_valor = {}
    for _, row in df_pnl.iterrows():
        tipo  = str(row.get("Tipo", "Internacional 🌎"))
        valor = float(row.get("Valor actual (USD)") or 0)
        if valor <= 0:
            continue
        # Simplificar etiqueta
        if "CEDEAR" in tipo or "Local" in tipo or "🇦🇷" in tipo:
            key = "CEDEARs 🇦🇷"
        else:
            key = "Acciones 🌎"
        tipo_valor[key] = tipo_valor.get(key, 0) + valor

    if not tipo_valor:
        return None

    labels = list(tipo_valor.keys())
    values = list(tipo_valor.values())
    colors = [COLOR_AZUL if "🌎" in l else COLOR_VERDE for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.4,
        marker_colors=colors,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>$%{value:,.2f} USD<br>%{percent}<extra></extra>"
    ))
    fig.update_layout(
        title="Acciones vs CEDEARs",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=CHART_HEIGHT,
        legend=dict(bgcolor=BG_CARD),
        margin=dict(t=50, b=20, l=20, r=20)
    )
    return fig

def _grafico_ganancia_grupos(grupos: dict) -> go.Figure:
    """Gráfico de barras con ganancia % por grupo."""
    labels, ganancias, colors = [], [], []
    for nombre, g in grupos.items():
        if g.get("ganancia_pct") is not None:
            labels.append(nombre)
            ganancias.append(g["ganancia_pct"])
            colors.append(COLOR_VERDE if g["ganancia_pct"] >= 0 else COLOR_ROJO)

    if not labels:
        return None

    fig = go.Figure(go.Bar(
        x=labels, y=ganancias,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in ganancias],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Ganancia: %{y:+.1f}%<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#888")
    fig.update_layout(
        title="Ganancia % por grupo de inversión",
        yaxis_title="Ganancia (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=CHART_HEIGHT,
        showlegend=False,
        margin=dict(t=50, b=20, l=40, r=20)
    )
    return fig


def _vista_movil_rapida(df_carteras, ccl):
    """Vista ultra-compacta para móvil — solo métricas clave."""
    st.markdown("### 📱 Resumen rápido")
    uid = _get_user_id()

    total_valor = 0
    total_gan   = 0
    total_gan_pct = 0
    n_carteras  = 0

    for _, row in df_carteras.iterrows():
        try:
            df_pnl = cartera_db.calcular_pnl(row['id'], ccl=ccl)
            if not df_pnl.empty:
                res = cartera_db.resumen_cartera(df_pnl)
                total_valor += res.get("Valor actual (USD)", 0) or 0
                total_gan   += res.get("Ganancia total (USD)", 0) or 0
                n_carteras  += 1
        except Exception:
            pass

    if total_valor > 0:
        total_gan_pct = (total_gan / (total_valor - total_gan) * 100) if (total_valor - total_gan) > 0 else 0

    # Métricas en 2 columnas (más compacto en móvil)
    c1, c2 = st.columns(2)
    c1.metric("💰 Valor total", f"${total_valor:,.0f}")
    gan_color = "normal"
    c2.metric("📈 Ganancia", f"${total_gan:+,.0f}",
              delta=f"{total_gan_pct:+.1f}%", delta_color=gan_color)

    c3, c4 = st.columns(2)
    c3.metric("💱 CCL", f"${ccl:,.0f}")
    c4.metric("💼 Carteras", n_carteras)

    st.markdown("---")
    st.markdown("**Accesos rápidos:**")
    col1, col2 = st.columns(2)
    with col1:
        st.page_link("pages/mi_cartera.py", label="💼 Mi Cartera", icon="💼") if False else None
        if st.button("💼 Mi Cartera", use_container_width=True, key="mob_cartera"):
            st.session_state["_nav_override"] = "💼 Mi Cartera"
            st.rerun()
        if st.button("🇦🇷 CEDEARs", use_container_width=True, key="mob_cedears"):
            st.session_state["_nav_override"] = "🇦🇷 CEDEARs"
            st.rerun()
    with col2:
        if st.button("🔄 Señal Rotación", use_container_width=True, key="mob_rotacion"):
            st.session_state["_nav_override"] = "🔄 Señal de Rotación"
            st.rerun()
        if st.button("🏦 Bonos y ON", use_container_width=True, key="mob_bonos"):
            st.session_state["_nav_override"] = "🏦 Bonos y ON"
            st.rerun()


def render():
    # Header con logo
    import os
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logo_financieramente.png")
    col_logo, col_titulo = st.columns([1, 5])
    with col_logo:
        if os.path.exists(logo_path):
            st.image(logo_path, width=70)
    with col_titulo:
        st.markdown(
            '<div style="padding-top:8px">'
            '<span style="font-size:26px;font-weight:700;color:white">Cartera AR</span><br>'
            '<a href="https://www.instagram.com/financieramente.ok?igsh=MTFkbDJwdDEzNWYzcA==" '
            'target="_blank" style="color:#4f8ef7;font-size:13px;text-decoration:none">'
            '📸 @financieramente.ok</a>'
            '</div>',
            unsafe_allow_html=True
        )

    uid = _get_user_id()
    if uid and AUTH_OK and _auth.esta_logueado():
        u = _auth.get_usuario_actual()
        st.markdown(f"Bienvenido, **{u['nombre']}** 👋")

    df_carteras = cartera_db.listar_carteras(usuario_id=uid)

    # ── Sin carteras → mostrar bienvenida ────────────────────────────────────
    if df_carteras.empty:
        st.info("👈 Todavía no tenés carteras. Ir a **💼 Mi Cartera** para crear una.")
        st.markdown("---")
        st.markdown("## ¿Qué podés hacer con Cartera AR?")
        col1, col2 = st.columns(2)
        with col1:
            st.info("📊 **Análisis de Cartera**\n\nMarkowitz, Sharpe, frontera eficiente y fundamentales")
            st.info("🇦🇷 **CEDEARs**\n\nValor implícito vs precio ARS con CCL en tiempo real")
            st.info("🔄 **Señal de Rotación**\n\nMarkowitz + RSI + Squeeze + Order Blocks")
        with col2:
            st.info("💼 **Mi Cartera**\n\nAcciones, CEDEARs, Bonos, LECAPs, ONs y FCIs")
            st.info("📰 **Info de Mercado**\n\nNoticias, ratings, ETFs y tipos de cambio")
            st.info("🏦 **Bonos y ON**\n\nBonos soberanos, ONs corporativas, MEP y CCL")
        return

    # ── Selector de cartera ───────────────────────────────────────────────────
    opciones = {f"{r['nombre']} ({r['moneda_base']})": r['id']
                for _, r in df_carteras.iterrows()}
    opciones["📊 Todas las carteras"] = -1

    sel = st.selectbox("Ver dashboard de:", list(opciones.keys()),
                       key="inicio_cartera_sel")
    cartera_ids = ([r['id'] for _, r in df_carteras.iterrows()]
                   if opciones[sel] == -1 else [opciones[sel]])

    # ── Obtener CCL ───────────────────────────────────────────────────────────
    with st.spinner("Obteniendo CCL..."):
        ccl = core.obtener_dolar_ccl()

    # ── Calcular datos por grupo ──────────────────────────────────────────────
    grupos = {
        "Acciones/CEDEARs": {"valor_usd": 0, "costo_usd": 0, "ganancia_usd": 0,
                              "ganancia_pct": None, "items": 0},
        "Renta Fija":        {"valor_usd": 0, "costo_usd": 0, "ganancia_usd": 0,
                              "ganancia_pct": None, "items": 0},
        "FCIs":              {"valor_usd": 0, "costo_usd": 0, "ganancia_usd": 0,
                              "ganancia_pct": None, "items": 0},
        "Dividendos cobrados":{"valor_usd": 0, "costo_usd": 0, "ganancia_usd": 0,
                               "ganancia_pct": None, "items": 0},
        "Saldo disponible":  {"valor_usd": 0, "costo_usd": 0, "ganancia_usd": 0,
                              "ganancia_pct": None, "items": 0},
    }

    total_dividendos_usd = 0
    total_saldo_usd = 0

    for cid in cartera_ids:
        # Acciones/CEDEARs
        try:
            df_pnl = cartera_db.calcular_pnl(cid, ccl=ccl)
            if not df_pnl.empty:
                res = cartera_db.resumen_cartera(df_pnl)
                grupos["Acciones/CEDEARs"]["valor_usd"] += res.get("Valor actual (USD)", 0) or 0
                grupos["Acciones/CEDEARs"]["costo_usd"]  += res.get("Costo total (USD)", 0) or 0
                grupos["Acciones/CEDEARs"]["ganancia_usd"] += res.get("Ganancia total (USD)", 0) or 0
                grupos["Acciones/CEDEARs"]["items"] += res.get("Posiciones", 0)
        except Exception:
            pass

        # Renta fija
        try:
            df_rf = cartera_db.calcular_pnl_renta_fija(cid, ccl=ccl)
            if not df_rf.empty:
                grupos["Renta Fija"]["valor_usd"] += df_rf["Valor actual (USD)"].sum()
                grupos["Renta Fija"]["costo_usd"]  += df_rf["Costo (USD)"].sum()
                grupos["Renta Fija"]["ganancia_usd"] += df_rf["Ganancia (USD)"].sum()
                grupos["Renta Fija"]["items"] += len(df_rf)
        except Exception:
            pass

        # FCIs
        try:
            df_fci = cartera_db.calcular_pnl_fci(cid, ccl=ccl)
            if not df_fci.empty:
                grupos["FCIs"]["valor_usd"] += df_fci["Valor actual (USD)"].sum()
                grupos["FCIs"]["costo_usd"]  += df_fci["Costo (USD)"].sum()
                grupos["FCIs"]["ganancia_usd"] += df_fci["Ganancia (USD)"].sum()
                grupos["FCIs"]["items"] += len(df_fci)
        except Exception:
            pass

        # Dividendos
        try:
            res_div = cartera_db.resumen_dividendos(cid)
            total_dividendos_usd += res_div.get("total_usd", 0)
            grupos["Dividendos cobrados"]["valor_usd"] += res_div.get("total_usd", 0)
            grupos["Dividendos cobrados"]["items"] += res_div.get("cobros", 0)
        except Exception:
            pass

        # Saldo disponible
        try:
            saldo = cartera_db.saldo_actual(cid)
            total_saldo_usd += saldo.get("usd", 0)
            grupos["Saldo disponible"]["valor_usd"] += saldo.get("usd", 0)
            grupos["Saldo disponible"]["items"] += saldo.get("movimientos", 0)
        except Exception:
            pass

    # Calcular ganancia % por grupo
    for nombre, g in grupos.items():
        if g["costo_usd"] > 0:
            g["ganancia_pct"] = round(g["ganancia_usd"] / g["costo_usd"] * 100, 2)

    # Totales
    total_valor  = sum(g["valor_usd"] for g in grupos.values())
    total_costo  = sum(g["costo_usd"] for g in grupos.values())
    total_gan    = sum(g["ganancia_usd"] for g in grupos.values())
    total_gan_pct = (total_gan / total_costo * 100) if total_costo > 0 else 0

    # ── Métricas globales ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💰 Resumen total de la cartera")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card_metrica("Valor total (USD)", f"${total_valor:,.2f}",
                      f"≈ ${total_valor * ccl:,.0f} ARS", COLOR_AZUL)
    with c2:
        _card_metrica("Costo total (USD)", f"${total_costo:,.2f}",
                      "Capital invertido", COLOR_GRIS)
    with c3:
        gan_color = COLOR_VERDE if total_gan >= 0 else COLOR_ROJO
        _card_metrica("Ganancia no realizada", f"${total_gan:+,.2f}",
                      f"≈ ${total_gan * ccl:+,.0f} ARS", gan_color,
                      delta=f"{total_gan_pct:+.2f}%")
    with c4:
        _card_metrica("Dividendos cobrados", f"${total_dividendos_usd:,.2f}",
                      "Total histórico USD", COLOR_VERDE)
    with c5:
        saldo_color = COLOR_VERDE if total_saldo_usd >= 0 else COLOR_NARANJA
        _card_metrica("Saldo disponible", f"${total_saldo_usd:,.2f}",
                      "Efectivo sin invertir", saldo_color)

    # ── Dashboard por grupo ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Detalle por grupo de inversión")

    grupos_con_datos = {k: v for k, v in grupos.items() if v["valor_usd"] > 0 or v["items"] > 0}

    if not grupos_con_datos:
        st.info("Sin datos de inversiones. Cargá posiciones en **💼 Mi Cartera**.")
    else:
        # Cards por grupo
        cols = st.columns(min(len(grupos_con_datos), 3))
        for i, (nombre, g) in enumerate(grupos_con_datos.items()):
            with cols[i % 3]:
                gan_pct = g.get("ganancia_pct")
                gan_str = f"{gan_pct:+.2f}%" if gan_pct is not None else "—"
                gan_color = COLOR_VERDE if (gan_pct or 0) >= 0 else COLOR_ROJO
                color_grupo = {
                    "Acciones/CEDEARs":    COLOR_AZUL,
                    "Renta Fija":          COLOR_NARANJA,
                    "FCIs":                COLOR_VERDE,
                    "Dividendos cobrados": "#9b59b6",
                    "Saldo disponible":    COLOR_GRIS,
                }.get(nombre, COLOR_AZUL)

                pct_total = (g["valor_usd"] / total_valor * 100) if total_valor > 0 else 0

                st.markdown(
                    f'<div style="background:{BG_CARD};padding:14px 16px;border-radius:10px;'
                    f'border-left:4px solid {color_grupo};margin-bottom:10px">'
                    f'<div style="color:#aaa;font-size:11px">{nombre}</div>'
                    f'<div style="color:white;font-size:20px;font-weight:700">'
                    f'${g["valor_usd"]:,.2f} USD</div>'
                    f'<div style="display:flex;gap:12px;margin-top:6px">'
                    f'<span style="color:#aaa;font-size:11px">{g["items"]} instrumentos</span>'
                    f'<span style="color:{gan_color};font-size:12px;font-weight:600">{gan_str}</span>'
                    f'<span style="color:#aaa;font-size:11px">{pct_total:.1f}% del total</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # Gráficos — tabs para diferentes vistas
        st.markdown("---")
        tab_g1, tab_g2, tab_g3, tab_g4 = st.tabs([
            "📊 Por grupo", "🌎 Acciones vs CEDEARs",
            "🏭 Por sector", "📈 Ganancia %"
        ])

        with tab_g1:
            col1, col2 = st.columns(2)
            with col1:
                fig_comp = _grafico_composicion_total(grupos_con_datos)
                st.plotly_chart(fig_comp, use_container_width=True)
            with col2:
                fig_gan = _grafico_ganancia_grupos(grupos_con_datos)
                if fig_gan:
                    st.plotly_chart(fig_gan, use_container_width=True)
                else:
                    st.info("Sin datos de ganancia para graficar.")

        with tab_g2:
            # Obtener df_pnl de la primera cartera con datos
            df_pnl_tab = pd.DataFrame()
            for cid in cartera_ids:
                try:
                    _df = cartera_db.calcular_pnl(cid, ccl=ccl)
                    if not _df.empty:
                        df_pnl_tab = pd.concat([df_pnl_tab, _df], ignore_index=True)
                except Exception:
                    pass
            fig_tipo = _grafico_composicion_tipo(df_pnl_tab)
            if fig_tipo:
                st.plotly_chart(fig_tipo, use_container_width=True)
                # Tabla resumen
                if not df_pnl_tab.empty and "Tipo" in df_pnl_tab.columns:
                    resumen_tipo = df_pnl_tab.groupby("Tipo").agg(
                        Tickers=("Ticker", "count"),
                        Valor_USD=("Valor actual (USD)", "sum"),
                        Ganancia_USD=("Ganancia (USD)", "sum")
                    ).round(2).reset_index()
                    resumen_tipo.columns = ["Tipo", "Tickers", "Valor (USD)", "Ganancia (USD)"]
                    st.dataframe(resumen_tipo, use_container_width=True, hide_index=True)
            else:
                st.info("Sin datos suficientes para este gráfico.")

        with tab_g3:
            fig_sector = _grafico_composicion_detallada(df_pnl_tab, ccl)
            if fig_sector:
                st.plotly_chart(fig_sector, use_container_width=True)
                st.caption("Los sectores se asignan automáticamente según el ticker. "
                           "Tickers no reconocidos aparecen como 'Otros'.")
            else:
                st.info("Sin datos suficientes para este gráfico.")

        with tab_g4:
            fig_gan2 = _grafico_ganancia_grupos(grupos_con_datos)
            if fig_gan2:
                st.plotly_chart(fig_gan2, use_container_width=True)
            else:
                st.info("Sin datos de ganancia para graficar.")

    # ── Tipos de cambio ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💱 Tipos de cambio")
    try:
        from market_info import obtener_tipos_cambio
        tc = obtener_tipos_cambio()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CCL",     f"${tc.get('CCL', ccl):,.2f}"    if tc.get('CCL')     else f"${ccl:,.2f}")
        c2.metric("MEP",     f"${tc.get('MEP'):,.2f}"          if tc.get('MEP')     else "—")
        c3.metric("Oficial", f"${tc.get('Oficial'):,.2f}"      if tc.get('Oficial') else "—")
        c4.metric("Blue",    f"${tc.get('Blue'):,.2f}"          if tc.get('Blue')    else "—")
    except Exception:
        st.metric("CCL", f"${ccl:,.2f}")