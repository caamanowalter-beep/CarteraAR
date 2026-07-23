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

        # Gráficos
        st.markdown("---")
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