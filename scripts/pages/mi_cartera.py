"""
pages/mi_cartera.py — Gestión multi-cartera: posiciones, movimientos y P&L.
Soporta múltiples carteras en paralelo con finalidades diferentes.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartera_db
import core

BG_DARK      = "#0f1117"
BG_CARD      = "#1e2130"
COLOR_VERDE  = "#00c896"
COLOR_ROJO   = "#f74f4f"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA= "#f7a34f"

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS VISUALES
# ═══════════════════════════════════════════════════════════════════════════════

def _color_ganancia(val):
    try:
        v = float(val)
        return f"color: {'#00c896' if v >= 0 else '#f74f4f'}; font-weight: bold"
    except Exception:
        return ""

def _grafico_composicion(df_pnl: pd.DataFrame, titulo: str) -> go.Figure:
    grp = df_pnl.groupby("Ticker")["Valor actual (USD)"].sum().dropna()
    fig = px.pie(
        values=grp.values, names=grp.index,
        title=titulo, hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig.update_layout(
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=340
    )
    return fig

def _grafico_ganancia_barras(df_pnl: pd.DataFrame) -> go.Figure:
    grp = df_pnl.groupby("Ticker")["Ganancia (%)"].mean().dropna().sort_values()
    colors = [COLOR_VERDE if v >= 0 else COLOR_ROJO for v in grp.values]
    fig = go.Figure(go.Bar(
        x=grp.index, y=grp.values,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in grp.values],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Ganancia: %{y:+.1f}%<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#888")
    fig.update_layout(
        title="Ganancia % por ticker",
        yaxis_title="Ganancia (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=320,
        showlegend=False
    )
    return fig

def _grafico_costo_vs_valor(df_pnl: pd.DataFrame) -> go.Figure:
    grp = df_pnl.groupby("Ticker")[["Costo total (USD)", "Valor actual (USD)"]].sum().dropna()
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Costo (USD)", x=grp.index,
                         y=grp["Costo total (USD)"], marker_color=COLOR_AZUL))
    fig.add_trace(go.Bar(name="Valor actual", x=grp.index,
                         y=grp["Valor actual (USD)"], marker_color=COLOR_VERDE))
    fig.update_layout(
        barmode="group", title="Costo vs Valor actual por ticker",
        yaxis_title="USD",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=320,
        legend=dict(bgcolor=BG_CARD)
    )
    return fig

# ═══════════════════════════════════════════════════════════════════════════════
# SELECTOR DE CARTERA (sidebar)
# ═══════════════════════════════════════════════════════════════════════════════

def _selector_cartera() -> tuple[int | None, str]:
    """Retorna (cartera_id, nombre_cartera) seleccionada."""
    df_carteras = cartera_db.listar_carteras()

    if df_carteras.empty:
        return None, ""

    opciones = {
        f"{row['nombre']} ({row['moneda_base']})": row['id']
        for _, row in df_carteras.iterrows()
    }
    sel_label = st.selectbox(
        "Seleccioná tu cartera",
        list(opciones.keys()),
        key="sel_cartera_principal"
    )
    cartera_id = opciones[sel_label]
    nombre     = sel_label.split(" (")[0]
    return cartera_id, nombre

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: GESTIÓN DE CARTERAS
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_gestionar_carteras():
    st.markdown("### 🗂️ Mis carteras")

    df_carteras = cartera_db.listar_carteras()

    if not df_carteras.empty:
        for _, row in df_carteras.iterrows():
            c1, c2, c3 = st.columns([4, 2, 1])
            c1.markdown(
                f'<div style="background:{BG_CARD};padding:10px 14px;'
                f'border-radius:8px;border-left:3px solid {COLOR_AZUL}">'
                f'<span style="color:white;font-weight:700">{row["nombre"]}</span>'
                f'&nbsp;&nbsp;<span style="color:#aaa;font-size:12px">'
                f'{row["descripcion"] or ""}</span><br>'
                f'<span style="color:{COLOR_AZUL};font-size:12px">'
                f'Moneda base: {row["moneda_base"]} | Creada: {row["creada"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            c2.write("")
            if c3.button("🗑️", key=f"del_cart_{row['id']}",
                         help="Eliminar cartera"):
                cartera_db.eliminar_cartera(row["id"])
                st.rerun()
    else:
        st.info("No tenés carteras creadas todavía.")

    st.markdown("---")
    st.markdown("### ➕ Crear nueva cartera")
    with st.form("form_nueva_cartera", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        nombre      = c1.text_input("Nombre", placeholder="ej: Largo Plazo")
        descripcion = c2.text_input("Descripción", placeholder="ej: Acciones growth")
        moneda      = c3.selectbox("Moneda base", ["USD", "ARS"])
        if st.form_submit_button("✅ Crear cartera", type="primary",
                                  use_container_width=True):
            if nombre.strip():
                cid = cartera_db.crear_cartera(nombre, descripcion, moneda)
                if cid > 0:
                    st.success(f"✅ Cartera '{nombre}' creada.")
                    st.rerun()
                else:
                    st.error("Ya existe una cartera con ese nombre.")
            else:
                st.error("Ingresá un nombre para la cartera.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: RESUMEN P&L
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_resumen(cartera_id: int, nombre: str, ccl: float):
    df_pos = cartera_db.listar_posiciones(cartera_id)

    if df_pos.empty:
        st.info(
            f"La cartera **{nombre}** no tiene posiciones. "
            "Usá las pestañas **Agregar posición** o **Importar CSV** para cargar tus activos."
        )
        return

    with st.spinner("Calculando P&L en tiempo real..."):
        df_pnl = cartera_db.calcular_pnl(cartera_id, ccl=ccl)

    resumen = cartera_db.resumen_cartera(df_pnl)
    gan_usd = resumen.get("Ganancia total (USD)", 0)
    gan_pct = resumen.get("Ganancia total (%)", 0)

    # Métricas globales
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Valor actual", f"${resumen.get('Valor actual (USD)',0):,.2f}")
    c2.metric("📥 Costo total",  f"${resumen.get('Costo total (USD)',0):,.2f}")
    c3.metric("📈 Ganancia (USD)", f"${gan_usd:,.2f}",
              delta=f"{gan_pct:+.2f}%", delta_color="normal")
    c4.metric("📊 Posiciones", resumen.get("Posiciones", 0))
    c5.metric("💱 CCL", f"${ccl:,.0f}")

    st.markdown("---")

    # Tabla de posiciones
    st.markdown("#### 📋 Posiciones detalladas")
    cols_show = ["Ticker", "Cantidad", "Precio promedio", "Moneda orig.",
                 "Precio actual (USD)", "Costo total (USD)",
                 "Valor actual (USD)", "Ganancia (USD)", "Ganancia (%)",
                 "Ganancia (ARS)", "Notas"]
    cols_ok = [c for c in cols_show if c in df_pnl.columns]

    st.dataframe(
        df_pnl[cols_ok].style
            .applymap(_color_ganancia, subset=["Ganancia (USD)", "Ganancia (%)"])
            .format({
                "Precio promedio":     "${:,.2f}",
                "Precio actual (USD)": lambda v: f"${v:,.2f}" if v else "—",
                "Costo total (USD)":   "${:,.2f}",
                "Valor actual (USD)":  lambda v: f"${v:,.2f}" if v else "—",
                "Ganancia (USD)":      lambda v: f"${v:+,.2f}" if v else "—",
                "Ganancia (%)":        lambda v: f"{v:+.2f}%" if v else "—",
                "Ganancia (ARS)":      lambda v: f"${v:+,.0f}" if v else "—",
            }),
        use_container_width=True, hide_index=True
    )

    # Gráficos
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(_grafico_composicion(df_pnl, f"Composición — {nombre}"),
                        use_container_width=True)
    with c2:
        st.plotly_chart(_grafico_ganancia_barras(df_pnl),
                        use_container_width=True)
    st.plotly_chart(_grafico_costo_vs_valor(df_pnl), use_container_width=True)

    # Ganancias realizadas
    gr = cartera_db.ganancias_realizadas_resumen(cartera_id)
    if gr.get("operaciones", 0) > 0:
        st.markdown("---")
        st.markdown("#### 💰 Ganancias realizadas (ventas cerradas)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total realizado (USD)", f"${gr['total_usd']:+,.2f}")
        c2.metric("Operaciones",           gr["operaciones"])
        c3.metric("✅ Ganadoras",           gr["ganadoras"])
        c4.metric("❌ Perdedoras",          gr["perdedoras"])

        df_gr = cartera_db.listar_ganancias_realizadas(cartera_id)
        if not df_gr.empty:
            st.dataframe(
                df_gr[["ticker","fecha_venta","cantidad_vendida",
                        "precio_compra_prom","precio_venta",
                        "ganancia_usd","ganancia_pct"]].style
                    .applymap(_color_ganancia, subset=["ganancia_usd","ganancia_pct"])
                    .format({
                        "precio_compra_prom": "${:,.2f}",
                        "precio_venta":       "${:,.2f}",
                        "ganancia_usd":       "${:+,.2f}",
                        "ganancia_pct":       "{:+.2f}%",
                    }),
                use_container_width=True, hide_index=True
            )

    # Exportar
    st.markdown("---")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_pnl.to_excel(writer, sheet_name="P&L", index=False)
        if gr.get("operaciones", 0) > 0:
            cartera_db.listar_ganancias_realizadas(cartera_id).to_excel(
                writer, sheet_name="Realizadas", index=False
            )
    st.download_button(
        f"⬇️ Exportar {nombre} a Excel",
        data=buf.getvalue(),
        file_name=f"cartera_{nombre.replace(' ','_')}_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: AGREGAR POSICIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_agregar_posicion(cartera_id: int, nombre: str):
    st.markdown(f"### ➕ Agregar posición a **{nombre}**")
    st.info(
        "Usá este formulario para cargar el **estado actual** de una posición. "
        "Ingresá el precio promedio de compra (sin necesidad de reconstruir el historial completo)."
    )

    with st.form("form_posicion", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ticker        = c1.text_input("Ticker", placeholder="ej: AAPL").upper().strip()
        cantidad      = c2.number_input("Cantidad de acciones", min_value=0.0001,
                                        value=1.0, step=0.01)
        c3, c4, c5 = st.columns(3)
        precio        = c3.number_input("Precio promedio de compra",
                                        min_value=0.0001, value=100.0, step=0.01)
        moneda        = c4.selectbox("Moneda", ["USD", "ARS"])
        fecha_ref     = c5.date_input("Fecha de referencia", value=date.today())
        notas         = st.text_input("Notas (opcional)",
                                      placeholder="ej: Posición acumulada 2022-2024")

        if st.form_submit_button("✅ Agregar / Actualizar posición",
                                  type="primary", use_container_width=True):
            if not ticker:
                st.error("❌ Ingresá un ticker válido.")
            else:
                cartera_db.agregar_posicion(
                    cartera_id, ticker, cantidad, precio,
                    moneda, str(fecha_ref), notas
                )
                st.success(f"✅ {cantidad} × {ticker} @ {precio} {moneda} agregado a {nombre}")
                st.rerun()

    # Eliminar posición
    df_pos = cartera_db.listar_posiciones(cartera_id)
    if not df_pos.empty:
        st.markdown("---")
        st.markdown("#### 🗑️ Eliminar posición")
        ticker_del = st.selectbox(
            "Seleccioná el ticker a eliminar",
            df_pos["ticker"].tolist(),
            key="del_pos_sel"
        )
        if st.button(f"🗑️ Eliminar {ticker_del} de {nombre}",
                     type="secondary"):
            cartera_db.eliminar_posicion(cartera_id, ticker_del)
            st.warning(f"🗑️ {ticker_del} eliminado de {nombre}")
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: REGISTRAR MOVIMIENTO
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_movimientos(cartera_id: int, nombre: str):
    st.markdown(f"### 📝 Registrar movimiento en **{nombre}**")
    st.info(
        "Registrá compras y ventas nuevas. "
        "El sistema actualiza automáticamente el precio promedio ponderado."
    )

    with st.form("form_movimiento", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        tipo     = c1.selectbox("Tipo", ["COMPRA", "VENTA"])
        ticker   = c2.text_input("Ticker", placeholder="ej: MSFT").upper().strip()
        fecha_op = c3.date_input("Fecha", value=date.today())

        c4, c5, c6, c7 = st.columns(4)
        cantidad = c4.number_input("Cantidad", min_value=0.0001, value=1.0, step=0.01)
        precio   = c5.number_input("Precio unitario", min_value=0.0001,
                                    value=100.0, step=0.01)
        moneda   = c6.selectbox("Moneda", ["USD", "ARS"])
        comision = c7.number_input("Comisión", min_value=0.0, value=0.0, step=0.01)
        notas    = st.text_input("Notas (opcional)")

        if st.form_submit_button(f"✅ Registrar {tipo}",
                                  type="primary", use_container_width=True):
            if not ticker:
                st.error("❌ Ingresá un ticker válido.")
            else:
                try:
                    cartera_db.registrar_movimiento(
                        cartera_id, tipo, ticker, cantidad, precio,
                        moneda, str(fecha_op), comision, notas
                    )
                    icono = "🟢" if tipo == "COMPRA" else "🔴"
                    st.success(
                        f"{icono} {tipo}: {cantidad} × {ticker} @ "
                        f"${precio:,.2f} {moneda} registrado en {nombre}"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    # Historial de movimientos
    st.markdown("---")
    st.markdown("#### 📋 Historial de movimientos")
    df_mov = cartera_db.listar_movimientos(cartera_id)
    if not df_mov.empty:
        def color_tipo(val):
            return "color: #00c896" if val == "COMPRA" else "color: #f74f4f"
        st.dataframe(
            df_mov[["fecha","tipo","ticker","cantidad","precio",
                    "moneda","comision","notas"]].style
                .applymap(color_tipo, subset=["tipo"])
                .format({
                    "precio":   "${:,.2f}",
                    "comision": "${:,.2f}",
                }),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("Sin movimientos registrados todavía.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: IMPORTAR CSV/EXCEL
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_importar(cartera_id: int, nombre: str):
    st.markdown(f"### 📥 Importar posiciones a **{nombre}**")

    st.markdown("""
    Subí un archivo CSV o Excel con tus posiciones actuales.
    El sistema acepta los siguientes formatos de columnas:

    | Columna | Requerida | Descripción |
    |---------|-----------|-------------|
    | `ticker` | ✅ | Símbolo del activo (ej: AAPL, MELI) |
    | `cantidad` | ✅ | Cantidad de acciones/unidades |
    | `precio_promedio` | ✅ | Precio promedio de compra |
    | `moneda` | ⚪ | USD o ARS (default: USD) |
    | `fecha_referencia` | ⚪ | Fecha de referencia (default: hoy) |
    | `notas` | ⚪ | Comentarios opcionales |

    **Nombres alternativos aceptados**: symbol, accion, activo, precio, precio_compra,
    cant, qty, currency, divisa, fecha, date, nota, comentario
    """)

    # Descargar template
    template_csv = cartera_db.generar_template_csv()
    st.download_button(
        "⬇️ Descargar template CSV",
        data=template_csv,
        file_name="template_cartera.csv",
        mime="text/csv"
    )

    st.markdown("---")
    archivo = st.file_uploader(
        "Subir archivo de posiciones",
        type=["csv", "xlsx", "xls"],
        help="CSV o Excel con las columnas indicadas arriba"
    )

    if archivo:
        try:
            if archivo.name.endswith(".csv"):
                # Intentar diferentes separadores
                try:
                    df_import = pd.read_csv(archivo, sep=",")
                except Exception:
                    df_import = pd.read_csv(archivo, sep=";")
            else:
                df_import = pd.read_excel(archivo)

            st.markdown("**Vista previa del archivo:**")
            st.dataframe(df_import.head(10), use_container_width=True)

            if st.button("✅ Importar posiciones", type="primary",
                         use_container_width=True):
                importadas, errores = cartera_db.importar_posiciones_csv(
                    cartera_id, df_import
                )
                if importadas > 0:
                    st.success(f"✅ {importadas} posiciones importadas a {nombre}")
                if errores:
                    for e in errores:
                        st.warning(f"⚠️ {e}")
                if importadas > 0:
                    st.rerun()

        except Exception as e:
            st.error(f"❌ Error al leer el archivo: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: COMPARAR CARTERAS
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_comparar(ccl: float):
    st.markdown("### 📊 Comparar carteras")

    df_carteras = cartera_db.listar_carteras()
    if df_carteras.empty or len(df_carteras) < 2:
        st.info("Necesitás al menos 2 carteras para comparar.")
        return

    # Resumen de todas las carteras
    rows = []
    for _, cart in df_carteras.iterrows():
        cid    = cart["id"]
        nombre = cart["nombre"]
        df_pnl = cartera_db.calcular_pnl(cid, ccl=ccl)
        if df_pnl.empty:
            continue
        res = cartera_db.resumen_cartera(df_pnl)
        gr  = cartera_db.ganancias_realizadas_resumen(cid)
        rows.append({
            "Cartera":              nombre,
            "Moneda base":          cart["moneda_base"],
            "Posiciones":           res.get("Posiciones", 0),
            "Costo total (USD)":    res.get("Costo total (USD)", 0),
            "Valor actual (USD)":   res.get("Valor actual (USD)", 0),
            "Ganancia no realiz.":  res.get("Ganancia total (USD)", 0),
            "Ganancia %":           res.get("Ganancia total (%)", 0),
            "Ganancia realizada":   gr.get("total_usd", 0),
            "Operaciones":          gr.get("operaciones", 0),
        })

    if not rows:
        st.info("Sin datos suficientes para comparar.")
        return

    df_comp = pd.DataFrame(rows)

    # Tabla comparativa
    st.dataframe(
        df_comp.style
            .applymap(_color_ganancia,
                      subset=["Ganancia no realiz.", "Ganancia %", "Ganancia realizada"])
            .format({
                "Costo total (USD)":   "${:,.2f}",
                "Valor actual (USD)":  "${:,.2f}",
                "Ganancia no realiz.": "${:+,.2f}",
                "Ganancia %":          "{:+.2f}%",
                "Ganancia realizada":  "${:+,.2f}",
            }),
        use_container_width=True, hide_index=True
    )

    # Gráfico comparativo
    if len(df_comp) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Costo total", x=df_comp["Cartera"],
            y=df_comp["Costo total (USD)"], marker_color=COLOR_AZUL
        ))
        fig.add_trace(go.Bar(
            name="Valor actual", x=df_comp["Cartera"],
            y=df_comp["Valor actual (USD)"], marker_color=COLOR_VERDE
        ))
        fig.update_layout(
            barmode="group", title="Comparación de carteras",
            yaxis_title="USD",
            plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
            font=dict(color="white"), height=340,
            legend=dict(bgcolor=BG_CARD)
        )
        st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: ALERTAS
# ═══════════════════════════════════════════════════════════════════════════════

def _tab_alertas(cartera_id: int, nombre: str):
    st.markdown(f"### 🔔 Alertas — {nombre}")

    with st.expander("➕ Nueva alerta"):
        with st.form("form_alerta", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            ticker_a = c1.text_input("Ticker").upper().strip()
            tipo_a   = c2.selectbox("Tipo", [
                "PRECIO_BAJO", "PRECIO_ALTO", "RSI_BAJO", "RSI_ALTO"
            ])
            valor_a  = c3.number_input("Valor umbral", min_value=0.0,
                                        value=100.0, step=1.0)
            if st.form_submit_button("✅ Crear alerta", use_container_width=True):
                if ticker_a:
                    cartera_db.agregar_alerta(cartera_id, ticker_a, tipo_a, valor_a)
                    st.success(f"✅ Alerta: {ticker_a} {tipo_a} @ {valor_a}")
                    st.rerun()

    df_alertas = cartera_db.listar_alertas(cartera_id)
    if df_alertas.empty:
        st.info("Sin alertas activas.")
        return

    for _, row in df_alertas.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.markdown(
            f'<div style="background:{BG_CARD};padding:8px 12px;'
            f'border-radius:6px;margin-bottom:4px">'
            f'<span style="color:white;font-weight:700">{row["ticker"]}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:{COLOR_NARANJA};font-size:12px">{row["tipo"]}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="color:#aaa;font-size:12px">@ {row["valor"]}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
        if c2.button("❌", key=f"del_alerta_{row['id']}"):
            cartera_db.desactivar_alerta(row["id"])
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def render():
    st.title("💼 Mis Carteras")
    st.markdown("Gestioná múltiples carteras con finalidades diferentes.")

    # CCL
    with st.spinner("Obteniendo CCL..."):
        ccl = core.obtener_dolar_ccl()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 💼 Carteras")
        df_carteras = cartera_db.listar_carteras()

        if df_carteras.empty:
            st.warning("No tenés carteras. Creá una en la pestaña **Gestionar**.")
            cartera_id, nombre_cartera = None, ""
        else:
            cartera_id, nombre_cartera = _selector_cartera()

        st.markdown(f"**CCL:** ${ccl:,.0f}")
        st.markdown("---")
        st.caption(f"{len(df_carteras)} cartera(s) activa(s)")

    # ── Tabs principales ──────────────────────────────────────────────────────
    tab_gest, tab_res, tab_add, tab_mov, tab_imp, tab_comp, tab_alert = st.tabs([
        "🗂️ Gestionar",
        "📊 Resumen P&L",
        "➕ Agregar posición",
        "📝 Movimientos",
        "📥 Importar CSV",
        "📈 Comparar carteras",
        "🔔 Alertas",
    ])

    with tab_gest:
        _tab_gestionar_carteras()

    if cartera_id is None:
        for tab in [tab_res, tab_add, tab_mov, tab_imp, tab_alert]:
            with tab:
                st.info("👈 Primero creá una cartera en la pestaña **Gestionar**.")
        with tab_comp:
            st.info("👈 Primero creá al menos 2 carteras.")
        return

    with tab_res:
        _tab_resumen(cartera_id, nombre_cartera, ccl)

    with tab_add:
        _tab_agregar_posicion(cartera_id, nombre_cartera)

    with tab_mov:
        _tab_movimientos(cartera_id, nombre_cartera)

    with tab_imp:
        _tab_importar(cartera_id, nombre_cartera)

    with tab_comp:
        _tab_comparar(ccl)

    with tab_alert:
        _tab_alertas(cartera_id, nombre_cartera)