"""
pages/historial.py — Historial P&L en el tiempo.
Registra snapshots diarios del valor de la cartera y muestra
la evolución temporal con gráficos interactivos.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
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

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE HISTORIAL
# ═══════════════════════════════════════════════════════════════════════════════

def guardar_snapshot(cartera_id: int, ccl: float) -> dict:
    """
    Guarda un snapshot del valor actual de la cartera en la tabla historial_pnl.
    Retorna el resumen guardado.
    """
    try:
        # Asegurar que la tabla existe antes de insertar
        init_historial_db()
        df_pnl = cartera_db.calcular_pnl(cartera_id, ccl=ccl)
        res    = cartera_db.resumen_cartera(df_pnl)

        valor_usd = res.get("Valor actual (USD)", 0) or 0
        costo_usd = res.get("Costo total (USD)", 0) or 0
        gan_usd   = res.get("Ganancia total (USD)", 0) or 0
        gan_pct   = res.get("Ganancia total (%)", 0) or 0
        n_pos     = res.get("Posiciones", 0) or 0

        hoy = date.today().strftime("%Y-%m-%d")

        # Upsert: si ya hay snapshot de hoy, actualizar
        if cartera_db.USE_POSTGRES:
            cartera_db._execute("""
                INSERT INTO historial_pnl
                    (cartera_id, fecha, valor_usd, costo_usd, ganancia_usd,
                     ganancia_pct, ccl, n_posiciones)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cartera_id, fecha) DO UPDATE SET
                    valor_usd=EXCLUDED.valor_usd,
                    costo_usd=EXCLUDED.costo_usd,
                    ganancia_usd=EXCLUDED.ganancia_usd,
                    ganancia_pct=EXCLUDED.ganancia_pct,
                    ccl=EXCLUDED.ccl,
                    n_posiciones=EXCLUDED.n_posiciones
            """, (cartera_id, hoy, valor_usd, costo_usd, gan_usd,
                  gan_pct, ccl, n_pos))
        else:
            cartera_db._execute("""
                INSERT INTO historial_pnl
                    (cartera_id, fecha, valor_usd, costo_usd, ganancia_usd,
                     ganancia_pct, ccl, n_posiciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cartera_id, fecha) DO UPDATE SET
                    valor_usd=excluded.valor_usd,
                    costo_usd=excluded.costo_usd,
                    ganancia_usd=excluded.ganancia_usd,
                    ganancia_pct=excluded.ganancia_pct,
                    ccl=excluded.ccl,
                    n_posiciones=excluded.n_posiciones
            """, (cartera_id, hoy, valor_usd, costo_usd, gan_usd,
                  gan_pct, ccl, n_pos))

        return {"fecha": hoy, "valor_usd": valor_usd, "ganancia_pct": gan_pct}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

def listar_historial(cartera_id: int, dias: int = 365) -> pd.DataFrame:
    """Lista el historial de P&L de una cartera."""
    desde = (date.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    try:
        return cartera_db._read_sql(
            "SELECT * FROM historial_pnl WHERE cartera_id=? AND fecha>=? ORDER BY fecha",
            [cartera_id, desde]
        )
    except Exception:
        return pd.DataFrame()

def init_historial_db() -> bool:
    """Crea la tabla historial_pnl si no existe. Retorna True si OK."""
    con = cartera_db._get_connection()
    cur = con.cursor()
    pk = "SERIAL" if cartera_db.USE_POSTGRES else "INTEGER"
    ai = "" if cartera_db.USE_POSTGRES else "AUTOINCREMENT"
    try:
        cur.execute(f"""CREATE TABLE IF NOT EXISTS historial_pnl (
            id            {pk} PRIMARY KEY {ai},
            cartera_id    INTEGER NOT NULL,
            fecha         TEXT    NOT NULL,
            valor_usd     REAL,
            costo_usd     REAL,
            ganancia_usd  REAL,
            ganancia_pct  REAL,
            ccl           REAL,
            n_posiciones  INTEGER,
            UNIQUE(cartera_id, fecha)
        )""")
        con.commit()
        return True
    except Exception as e:
        return False
    finally:
        con.close()

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ═══════════════════════════════════════════════════════════════════════════════

def _grafico_valor_tiempo(df: pd.DataFrame, nombre: str) -> go.Figure:
    """Gráfico de área del valor de la cartera en el tiempo."""
    fig = go.Figure()

    # Área de valor
    fig.add_trace(go.Scatter(
        x=df["fecha"], y=df["valor_usd"],
        mode="lines", name="Valor (USD)",
        line=dict(color=COLOR_AZUL, width=2),
        fill="tozeroy",
        fillcolor="rgba(79,142,247,0.1)",
        hovertemplate="<b>%{x}</b><br>Valor: $%{y:,.2f} USD<extra></extra>"
    ))

    # Línea de costo
    if "costo_usd" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["fecha"], y=df["costo_usd"],
            mode="lines", name="Costo invertido",
            line=dict(color=COLOR_GRIS if hasattr(go, 'COLOR_GRIS') else "#6b7280",
                      width=1.5, dash="dash"),
            hovertemplate="<b>%{x}</b><br>Costo: $%{y:,.2f} USD<extra></extra>"
        ))

    fig.update_layout(
        title=f"Evolución del valor — {nombre}",
        xaxis_title="Fecha",
        yaxis_title="USD",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=380,
        legend=dict(bgcolor=BG_CARD),
        hovermode="x unified"
    )
    return fig

def _grafico_ganancia_tiempo(df: pd.DataFrame, nombre: str) -> go.Figure:
    """Gráfico de ganancia % en el tiempo."""
    colors = [COLOR_VERDE if v >= 0 else COLOR_ROJO
              for v in df["ganancia_pct"].fillna(0)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["fecha"], y=df["ganancia_pct"],
        marker_color=colors,
        name="Ganancia %",
        hovertemplate="<b>%{x}</b><br>Ganancia: %{y:+.2f}%<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#888")

    fig.update_layout(
        title=f"Ganancia % histórica — {nombre}",
        xaxis_title="Fecha",
        yaxis_title="Ganancia (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=320,
        showlegend=False
    )
    return fig

def _grafico_ganancia_usd(df: pd.DataFrame, nombre: str) -> go.Figure:
    """Gráfico de ganancia en USD en el tiempo."""
    fig = go.Figure()
    gan = df["ganancia_usd"].fillna(0)
    colors = [COLOR_VERDE if v >= 0 else COLOR_ROJO for v in gan]

    fig.add_trace(go.Scatter(
        x=df["fecha"], y=gan,
        mode="lines+markers",
        line=dict(color=COLOR_VERDE, width=2),
        marker=dict(color=colors, size=5),
        fill="tozeroy",
        fillcolor="rgba(0,200,150,0.1)",
        hovertemplate="<b>%{x}</b><br>Ganancia: $%{y:+,.2f} USD<extra></extra>"
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#888")

    fig.update_layout(
        title=f"Ganancia USD histórica — {nombre}",
        xaxis_title="Fecha",
        yaxis_title="Ganancia (USD)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=320,
        showlegend=False
    )
    return fig

def _grafico_comparacion_carteras(historiales: dict) -> go.Figure:
    """Compara la evolución de múltiples carteras."""
    fig = go.Figure()
    colors = [COLOR_AZUL, COLOR_VERDE, COLOR_NARANJA, COLOR_ROJO, "#9b59b6"]

    for i, (nombre, df) in enumerate(historiales.items()):
        if df.empty or "ganancia_pct" not in df.columns:
            continue
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=df["fecha"], y=df["ganancia_pct"],
            mode="lines", name=nombre,
            line=dict(color=color, width=2),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br>%{{y:+.2f}}%<extra></extra>"
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="#888")
    fig.update_layout(
        title="Comparación de carteras — Ganancia % histórica",
        xaxis_title="Fecha",
        yaxis_title="Ganancia (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=400,
        legend=dict(bgcolor=BG_CARD),
        hovermode="x unified"
    )
    return fig

# ═══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def render():
    st.title("📈 Historial P&L")
    st.markdown("Evolución del valor de tu cartera en el tiempo.")

    # Inicializar tabla
    init_historial_db()

    uid = _get_user_id()
    df_carteras = cartera_db.listar_carteras(usuario_id=uid)

    if df_carteras.empty:
        st.info("👈 Creá una cartera en **💼 Mi Cartera** para ver el historial.")
        return

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuración")

        opciones = {f"{r['nombre']} ({r['moneda_base']})": r['id']
                    for _, r in df_carteras.iterrows()}
        opciones["📊 Todas las carteras"] = -1

        sel = st.selectbox("Cartera", list(opciones.keys()), key="hist_cart_sel")
        cartera_id = opciones[sel]
        nombre_sel = sel.split(" (")[0]

        periodo = st.selectbox("Período", ["1 mes", "3 meses", "6 meses", "1 año", "Todo"], index=3)
        dias_map = {"1 mes": 30, "3 meses": 90, "6 meses": 180, "1 año": 365, "Todo": 3650}
        dias = dias_map[periodo]

        st.markdown("---")
        st.markdown("### 📸 Guardar snapshot")
        st.caption("Guardá el valor actual de tu cartera para construir el historial.")

        with st.spinner("Obteniendo CCL..."):
            ccl = core.obtener_dolar_ccl()
        st.metric("CCL actual", f"${ccl:,.0f}")

        if st.button("📸 Guardar snapshot de hoy", type="primary", use_container_width=True):
            # Asegurar que la tabla existe
            init_historial_db()
            if cartera_id == -1:
                errores = []
                for _, row in df_carteras.iterrows():
                    res = guardar_snapshot(row['id'], ccl)
                    if "error" in res:
                        errores.append(f"{row['nombre']}: {res['error']}")
                if errores:
                    st.error(f"❌ Errores: {'; '.join(errores)}")
                else:
                    st.success("✅ Snapshots guardados para todas las carteras")
            else:
                res = guardar_snapshot(cartera_id, ccl)
                if "error" in res:
                    st.error(f"❌ Error al guardar: {res['error']}")
                    if "traceback" in res:
                        with st.expander("Ver detalle del error"):
                            st.code(res["traceback"])
                    st.info("💡 Ejecutá el SQL en Supabase para crear la tabla historial_pnl")
                else:
                    st.success(f"✅ Snapshot guardado: ${res.get('valor_usd', 0):,.2f} USD ({res.get('fecha','')})")
            st.rerun()

    # ── Contenido principal ───────────────────────────────────────────────────
    if cartera_id == -1:
        # Comparación de todas las carteras
        st.markdown("### 📊 Comparación de todas las carteras")
        historiales = {}
        for _, row in df_carteras.iterrows():
            df_h = listar_historial(row['id'], dias)
            if not df_h.empty:
                historiales[row['nombre']] = df_h

        if not historiales:
            st.info("Sin historial disponible. Guardá snapshots diarios para ver la evolución.")
            _mostrar_instrucciones()
            return

        st.plotly_chart(_grafico_comparacion_carteras(historiales),
                        use_container_width=True)

        # Tabla resumen
        st.markdown("### 📋 Resumen por cartera")
        rows = []
        for nombre, df_h in historiales.items():
            if df_h.empty:
                continue
            primer = df_h.iloc[0]
            ultimo = df_h.iloc[-1]
            rows.append({
                "Cartera":          nombre,
                "Primer registro":  primer["fecha"],
                "Último registro":  ultimo["fecha"],
                "Valor actual":     f"${ultimo.get('valor_usd', 0):,.2f}",
                "Ganancia actual":  f"{ultimo.get('ganancia_pct', 0):+.2f}%",
                "Snapshots":        len(df_h),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    else:
        # Historial de una cartera específica
        df_hist = listar_historial(cartera_id, dias)

        if df_hist.empty:
            st.info(f"Sin historial para **{nombre_sel}**. Guardá el primer snapshot.")
            _mostrar_instrucciones()
            return

        # Métricas resumen
        primer = df_hist.iloc[0]
        ultimo = df_hist.iloc[-1]
        n_dias = len(df_hist)

        valor_ini = float(primer.get("valor_usd", 0) or 0)
        valor_fin = float(ultimo.get("valor_usd", 0) or 0)
        gan_total = valor_fin - valor_ini
        gan_pct_total = (gan_total / valor_ini * 100) if valor_ini > 0 else 0

        st.markdown(f"### 📊 {nombre_sel} — {periodo}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Valor actual",    f"${valor_fin:,.2f}")
        c2.metric("📥 Valor inicial",   f"${valor_ini:,.2f}")
        gan_color = "normal"
        c3.metric("📈 Ganancia período", f"${gan_total:+,.2f}",
                  delta=f"{gan_pct_total:+.2f}%", delta_color=gan_color)
        c4.metric("📅 Snapshots",       n_dias)
        c5.metric("💱 CCL último",      f"${float(ultimo.get('ccl', ccl)):,.0f}")

        st.markdown("---")

        # Tabs de gráficos
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Valor en el tiempo",
            "💹 Ganancia %",
            "💵 Ganancia USD",
            "📋 Tabla detalle"
        ])

        with tab1:
            st.plotly_chart(_grafico_valor_tiempo(df_hist, nombre_sel),
                            use_container_width=True)

        with tab2:
            st.plotly_chart(_grafico_ganancia_tiempo(df_hist, nombre_sel),
                            use_container_width=True)

        with tab3:
            st.plotly_chart(_grafico_ganancia_usd(df_hist, nombre_sel),
                            use_container_width=True)

        with tab4:
            cols_show = [c for c in ["fecha","valor_usd","costo_usd",
                                      "ganancia_usd","ganancia_pct","ccl","n_posiciones"]
                         if c in df_hist.columns]
            st.dataframe(
                df_hist[cols_show].sort_values("fecha", ascending=False).style.format({
                    "valor_usd":    "${:,.2f}",
                    "costo_usd":    "${:,.2f}",
                    "ganancia_usd": "${:+,.2f}",
                    "ganancia_pct": "{:+.2f}%",
                    "ccl":          "${:,.0f}",
                }),
                use_container_width=True, hide_index=True
            )

            # Exportar
            from io import BytesIO
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_hist.to_excel(writer, sheet_name="Historial P&L", index=False)
            st.download_button(
                "⬇️ Exportar historial a Excel",
                data=buf.getvalue(),
                file_name=f"historial_{nombre_sel.replace(' ','_')}_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        # Estadísticas adicionales
        st.markdown("---")
        st.markdown("### 📊 Estadísticas del período")
        c1, c2, c3, c4 = st.columns(4)
        gan_vals = df_hist["ganancia_pct"].dropna()
        c1.metric("📈 Máxima ganancia",  f"{gan_vals.max():+.2f}%" if not gan_vals.empty else "—")
        c2.metric("📉 Mínima ganancia",  f"{gan_vals.min():+.2f}%" if not gan_vals.empty else "—")
        c3.metric("📊 Ganancia promedio", f"{gan_vals.mean():+.2f}%" if not gan_vals.empty else "—")
        val_vals = df_hist["valor_usd"].dropna()
        c4.metric("💰 Valor máximo",     f"${val_vals.max():,.2f}" if not val_vals.empty else "—")


def _mostrar_instrucciones():
    """Muestra instrucciones para empezar a usar el historial."""
    st.markdown("---")
    st.markdown("### 📖 ¿Cómo funciona el historial?")
    st.markdown("""
    El historial se construye guardando **snapshots** del valor de tu cartera.
    
    **Para empezar:**
    1. Click en **📸 Guardar snapshot de hoy** en el panel izquierdo
    2. Repetí cada día (o cuando quieras registrar el valor)
    3. Con el tiempo verás la evolución en los gráficos
    
    **Tip**: Podés automatizar el snapshot guardándolo cada vez que abrís la app.
    
    **¿Qué se guarda?**
    - Valor total de la cartera en USD
    - Costo total invertido
    - Ganancia/pérdida en USD y %
    - CCL del día
    - Número de posiciones
    """)