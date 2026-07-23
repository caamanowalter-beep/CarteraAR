"""
pages/bonos.py — Bonos soberanos argentinos y Obligaciones Negociables.
Muestra precios, TIR, duration y tipos de cambio (CCL, MEP, Oficial, Blue).
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import market_info as mi
import cartera_db

# ── Bonos argentinos con datos reales via yfinance ────────────────────────────
BONOS_BYMA = {
    # Bonos USD Ley Argentina
    "AL29": {"nombre": "Bono Soberano USD Ley Arg 2029", "moneda": "USD", "tipo": "Soberano"},
    "AL30": {"nombre": "Bono Soberano USD Ley Arg 2030", "moneda": "USD", "tipo": "Soberano"},
    "AL35": {"nombre": "Bono Soberano USD Ley Arg 2035", "moneda": "USD", "tipo": "Soberano"},
    "AL41": {"nombre": "Bono Soberano USD Ley Arg 2041", "moneda": "USD", "tipo": "Soberano"},
    # Bonos USD Ley Nueva York
    "GD29": {"nombre": "Bono Soberano USD Ley NY 2029",  "moneda": "USD", "tipo": "Soberano"},
    "GD30": {"nombre": "Bono Soberano USD Ley NY 2030",  "moneda": "USD", "tipo": "Soberano"},
    "GD35": {"nombre": "Bono Soberano USD Ley NY 2035",  "moneda": "USD", "tipo": "Soberano"},
    "GD41": {"nombre": "Bono Soberano USD Ley NY 2041",  "moneda": "USD", "tipo": "Soberano"},
    "GD38": {"nombre": "Bono Soberano USD Ley NY 2038",  "moneda": "USD", "tipo": "Soberano"},
    # Bonos CER (ajustan por inflación)
    "TX26": {"nombre": "Bono CER 2026",                  "moneda": "ARS", "tipo": "CER"},
    "TX28": {"nombre": "Bono CER 2028",                  "moneda": "ARS", "tipo": "CER"},
    "AE38": {"nombre": "Bono CER 2038",                  "moneda": "ARS", "tipo": "CER"},
    "DICP": {"nombre": "Bono CER Descuento 2033",        "moneda": "ARS", "tipo": "CER"},
    # LECAPs y Letras
    "S31E5":{"nombre": "LECAP Enero 2025",               "moneda": "ARS", "tipo": "LECAP"},
    "T15E7":{"nombre": "LECAP Enero 2027",               "moneda": "ARS", "tipo": "LECAP"},
    "TMF28":{"nombre": "Bono Tesoro ARS 2028",           "moneda": "ARS", "tipo": "BONO ARS"},
    "TZX28":{"nombre": "Bono CER 2028",                  "moneda": "ARS", "tipo": "CER"},
}

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_bonos_precios() -> pd.DataFrame:
    """
    Obtiene precios de bonos argentinos.
    Yahoo Finance no tiene datos de bonos .BA (quoteType: NONE).
    Usamos ArgentinaDatos para cotizaciones históricas y datos de referencia.
    """
    import requests

    # Intentar obtener precios desde ArgentinaDatos (cotizaciones históricas)
    precios_api = {}
    try:
        # ArgentinaDatos tiene cotizaciones de bonos en su endpoint de finanzas
        r = requests.get(
            "https://api.argentinadatos.com/v1/cotizaciones/dolares",
            timeout=8, headers={"User-Agent": "Mozilla/5.0"}
        )
        # Este endpoint no tiene bonos, pero confirma que la API funciona
    except Exception:
        pass

    rows = []
    for ticker, meta in BONOS_BYMA.items():
        precio = precios_api.get(ticker)
        rows.append({
            "Ticker":      ticker,
            "Nombre":      meta["nombre"],
            "Precio":      precio,
            "TIR":         meta.get("tir_ref"),
            "Duration":    meta.get("duration_ref"),
            "Moneda":      meta["moneda"],
            "Tipo":        meta["tipo"],
            "Vencimiento": meta.get("vencimiento", "—"),
            "Fuente":      "Referencia BYMA",
            "Nota":        "Precio no disponible via API pública. Actualizá manualmente.",
        })

    return pd.DataFrame(rows)

BG_DARK      = "#0f1117"
BG_CARD      = "#1e2130"
COLOR_VERDE  = "#00c896"
COLOR_ROJO   = "#f74f4f"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA= "#f7a34f"
COLOR_GRIS   = "#6b7280"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _card_tc(nombre: str, valor: float | None, color: str, descripcion: str):
    val_str = f"${valor:,.2f}" if valor else "—"
    st.markdown(
        f'<div style="background:{BG_CARD};padding:14px 16px;border-radius:10px;'
        f'border-left:4px solid {color};margin-bottom:8px">'
        f'<div style="color:#aaa;font-size:11px">{nombre}</div>'
        f'<div style="color:{color};font-size:26px;font-weight:700">{val_str}</div>'
        f'<div style="color:#888;font-size:11px">{descripcion}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

def _grafico_tir(df: pd.DataFrame, titulo: str) -> go.Figure | None:
    df_ok = df.dropna(subset=["TIR"]).copy()
    if df_ok.empty:
        return None
    df_ok = df_ok.sort_values("TIR", ascending=False).head(15)
    colors = [COLOR_VERDE if m == "USD" else COLOR_AZUL
              for m in df_ok.get("Moneda", ["USD"] * len(df_ok))]
    fig = go.Figure(go.Bar(
        x=df_ok["Ticker"], y=df_ok["TIR"],
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df_ok["TIR"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>TIR: %{y:.2f}%<extra></extra>"
    ))
    fig.update_layout(
        title=titulo,
        yaxis_title="TIR (%)",
        plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
        font=dict(color="white"), height=340,
        showlegend=False
    )
    return fig

# ── RENDER PRINCIPAL ──────────────────────────────────────────────────────────
def render():
    st.title("🏦 Bonos y Obligaciones Negociables")
    st.markdown("Tipos de cambio, bonos soberanos argentinos y ONs corporativas.")

    # ── Tipos de cambio ───────────────────────────────────────────────────────
    st.markdown("## 💱 Tipos de cambio")
    with st.spinner("Obteniendo tipos de cambio..."):
        tc = mi.obtener_tipos_cambio()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card_tc("CCL", tc.get("CCL"), COLOR_AZUL,
                 "Contado con liquidación")
    with c2:
        _card_tc("MEP", tc.get("MEP"), COLOR_VERDE,
                 "Dólar bolsa (MEP)")
    with c3:
        _card_tc("Oficial", tc.get("Oficial"), COLOR_NARANJA,
                 "Tipo de cambio oficial")
    with c4:
        _card_tc("Blue", tc.get("Blue"), COLOR_ROJO,
                 "Dólar informal")
    with c5:
        _card_tc("Cripto", tc.get("Cripto"), COLOR_GRIS,
                 "Dólar cripto (USDT)")

    # Brecha CCL vs Oficial
    if tc.get("CCL") and tc.get("Oficial"):
        brecha = (tc["CCL"] - tc["Oficial"]) / tc["Oficial"] * 100
        color_brecha = COLOR_ROJO if brecha > 30 else COLOR_NARANJA if brecha > 15 else COLOR_VERDE
        st.markdown(
            f'<div style="background:{BG_CARD};padding:10px 16px;border-radius:8px;'
            f'margin-top:8px;display:inline-block">'
            f'<span style="color:#aaa">Brecha CCL/Oficial: </span>'
            f'<span style="color:{color_brecha};font-weight:700;font-size:18px">'
            f'{brecha:+.1f}%</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── Tabs bonos y ON ───────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📊 Bonos Soberanos", "🏢 Obligaciones Negociables", "✏️ Actualizar precios"])

    with tab1:
        st.markdown("### 📊 Bonos Soberanos Argentinos")
        st.caption("Fuentes: ArgentinaDatos · BYMA Open Data")

        with st.spinner("Cargando datos de bonos..."):
            df_bonos = cartera_db.listar_precios_bonos()
            # Renombrar columnas para compatibilidad con la tabla
            if not df_bonos.empty:
                df_bonos = df_bonos.rename(columns={
                    "ticker": "Ticker", "nombre": "Nombre",
                    "precio": "Precio", "tir": "TIR",
                    "duration": "Duration", "moneda": "Moneda",
                    "tipo": "Tipo", "vencimiento": "Vencimiento",
                    "fuente": "Fuente", "actualizado": "Actualizado"
                })

        if df_bonos.empty:
            st.warning("No se pudieron obtener datos de bonos.")
        else:
            # Filtros
            c1, c2 = st.columns(2)
            moneda_fil = c1.multiselect(
                "Moneda", ["USD", "ARS"],
                default=["USD", "ARS"],
                key="fil_moneda_bonos"
            )
            tipo_fil = c2.multiselect(
                "Tipo",
                df_bonos["Tipo"].unique().tolist(),
                default=df_bonos["Tipo"].unique().tolist(),
                key="fil_tipo_bonos"
            )

            df_fil = df_bonos[
                df_bonos["Moneda"].isin(moneda_fil) &
                df_bonos["Tipo"].isin(tipo_fil)
            ].copy()

            # Tabla
            cols_show = [c for c in ["Ticker","Nombre","Precio","TIR","Duration","Moneda","Tipo","Fuente"]
                         if c in df_fil.columns]

            def color_tir(val):
                try:
                    v = float(val)
                    if v > 15:  return "color: #00c896; font-weight: bold"
                    if v > 8:   return "color: #f7a34f"
                    return "color: #f74f4f"
                except Exception:
                    return ""

            fmt = {}
            if "Precio"   in df_fil.columns: fmt["Precio"]   = lambda v: f"${v:,.2f}" if pd.notna(v) else "—"
            if "TIR"      in df_fil.columns: fmt["TIR"]      = lambda v: f"{v:.2f}%"  if pd.notna(v) else "—"
            if "Duration" in df_fil.columns: fmt["Duration"] = lambda v: f"{v:.2f}"   if pd.notna(v) else "—"

            st.dataframe(
                df_fil[cols_show].style
                    .map(color_tir, subset=["TIR"] if "TIR" in cols_show else [])
                    .format(fmt),
                use_container_width=True, hide_index=True
            )

            # Gráfico TIR
            fig = _grafico_tir(df_fil, "TIR por bono (verde=USD, azul=ARS)")
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            # Nota informativa
            st.info(
                "ℹ️ **Cómo interpretar la TIR**: "
                "Mayor TIR = mayor rendimiento pero también mayor riesgo. "
                "Los bonos USD Ley NY (GD) suelen tener menor riesgo legal que los Ley Arg (AL). "
                "Los bonos CER ajustan por inflación."
            )

    with tab2:
        st.markdown("### 🏢 Obligaciones Negociables Corporativas")
        st.caption("Fuente: BYMA Open Data")

        with st.spinner("Obteniendo ONs..."):
            df_on = mi.obtener_on_argentina()

        if df_on.empty:
            st.warning("No se pudieron obtener datos de ONs.")
        else:
            # Filtro por moneda
            moneda_on = st.multiselect(
                "Moneda", ["USD", "ARS"],
                default=["USD", "ARS"],
                key="fil_moneda_on"
            )
            df_on_fil = df_on[df_on["Moneda"].isin(moneda_on)].copy()

            cols_on = [c for c in ["Ticker","Emisor","Precio","TIR","Duration",
                                    "Moneda","Vencimiento","Tipo"]
                       if c in df_on_fil.columns]

            fmt_on = {}
            if "Precio"   in df_on_fil.columns: fmt_on["Precio"]   = lambda v: f"${v:,.2f}" if pd.notna(v) else "—"
            if "TIR"      in df_on_fil.columns: fmt_on["TIR"]      = lambda v: f"{v:.2f}%"  if pd.notna(v) else "—"
            if "Duration" in df_on_fil.columns: fmt_on["Duration"] = lambda v: f"{v:.2f}"   if pd.notna(v) else "—"

            def color_tir_on(val):
                try:
                    v = float(val)
                    if v > 10: return "color: #00c896; font-weight: bold"
                    if v > 6:  return "color: #f7a34f"
                    return "color: #aaa"
                except Exception:
                    return ""

            st.dataframe(
                df_on_fil[cols_on].style
                    .map(color_tir_on, subset=["TIR"] if "TIR" in cols_on else [])
                    .format(fmt_on),
                use_container_width=True, hide_index=True
            )

            fig_on = _grafico_tir(df_on_fil, "TIR por ON corporativa")
            if fig_on:
                st.plotly_chart(fig_on, use_container_width=True)

            st.info(
                "ℹ️ **Sobre las ONs**: Son deuda corporativa emitida por empresas argentinas. "
                "Generalmente ofrecen mayor TIR que los bonos soberanos del mismo plazo "
                "a cambio de mayor riesgo crediticio. "
                "Las ONs USD son una alternativa para dolarizar cartera dentro del sistema."
            )

    # ── Comparativa CCL vs MEP ────────────────────────────────────────────────
    if tc.get("CCL") and tc.get("MEP"):
        st.markdown("---")
        st.markdown("### 📊 CCL vs MEP — ¿Cuál usar?")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            **MEP (Dólar Bolsa)** — ${tc['MEP']:,.2f}
            - Operación 100% legal dentro del sistema financiero
            - Se opera comprando un bono en ARS y vendiéndolo en USD
            - Liquidación en 24-48hs
            - Sin límite de monto (con restricciones de parking)
            - Ideal para: dolarizar ahorros, comprar CEDEARs
            """)
        with col2:
            st.markdown(f"""
            **CCL (Contado con Liqui)** — ${tc['CCL']:,.2f}
            - Operación legal para empresas y personas
            - Se opera con acciones/bonos que cotizan en el exterior
            - Permite sacar divisas al exterior
            - Diferencia con MEP: {((tc['CCL']-tc['MEP'])/tc['MEP']*100):+.1f}%
            - Ideal para: transferir fondos al exterior, inversores sofisticados
            """)

    with tab3:
        st.markdown("### ✏️ Actualizar precios de bonos manualmente")
        st.info(
            "📌 **Fuentes sugeridas para copiar los precios:**\n"
            "- [acuantoesta.com.ar](https://www.acuantoesta.com.ar/lecaps) — LECAPs y bonos\n"
            "- [comparatasas.ar](https://comparatasas.ar/lecaps) — LECAPs\n"
            "- Tu broker (IOL, Bull, Balanz) — todos los bonos\n\n"
            "El precio para bonos USD va en **% del valor nominal** (ej: 84.10 = 84.10% del VN).\n"
            "Para bonos ARS/CER va en **ARS por cada $100 VN** (ej: 1250.50)."
        )

        # Tabla actual de precios
        df_bonos_actual = cartera_db.listar_precios_bonos()
        
        st.markdown("#### 📋 Precios actuales")
        
        # Mostrar tabla con estado de actualización
        def color_precio(val):
            if val is None or str(val) == "None" or str(val) == "nan":
                return "color: #f74f4f"
            return "color: #00c896; font-weight: bold"
        
        cols_show = [c for c in ["ticker","nombre","precio","tir","moneda","tipo","vencimiento","actualizado"]
                     if c in df_bonos_actual.columns]
        
        st.dataframe(
            df_bonos_actual[cols_show].style
                .map(color_precio, subset=["precio"] if "precio" in cols_show else [])
                .format({
                    "precio": lambda v: f"{v:.2f}%" if v and not str(v) in ["None","nan"] else "Sin datos",
                    "tir":    lambda v: f"{v:.2f}%" if v and not str(v) in ["None","nan"] else "—",
                }),
            use_container_width=True, hide_index=True
        )

        st.markdown("---")
        st.markdown("#### ➕ Actualizar precio de un bono")
        
        # Formulario de actualización
        with st.form("form_precio_bono", clear_on_submit=True):
            tickers_disponibles = list(cartera_db.BONOS_REFERENCIA.keys())
            
            c1, c2 = st.columns(2)
            ticker_bono = c1.selectbox("Ticker", tickers_disponibles)
            fuente_precio = c2.selectbox("Fuente del precio", 
                                          ["Manual", "acuantoesta.com.ar", "comparatasas.ar", 
                                           "IOL", "Bull", "Balanz", "Broker propio"])
            
            meta = cartera_db.BONOS_REFERENCIA.get(ticker_bono, {})
            moneda_bono = meta.get("moneda", "USD")
            tipo_bono   = meta.get("tipo", "Soberano")
            
            st.caption(f"**{meta.get('nombre', ticker_bono)}** | Moneda: {moneda_bono} | Tipo: {tipo_bono} | Vence: {meta.get('vencimiento','—')}")
            
            c3, c4, c5 = st.columns(3)
            if moneda_bono == "USD":
                precio_bono = c3.number_input(
                    "Precio (% del VN)",
                    min_value=0.01, max_value=200.0, value=85.0, step=0.01,
                    help="Precio en % del valor nominal. Ej: 84.10 = 84.10% del VN"
                )
            else:
                precio_bono = c3.number_input(
                    "Precio (ARS por $100 VN)",
                    min_value=0.01, max_value=99999.0, value=1000.0, step=0.01,
                    help="Precio en ARS por cada $100 de valor nominal"
                )
            
            tir_bono      = c4.number_input("TIR (%)", min_value=0.0, max_value=200.0, 
                                             value=0.0, step=0.01,
                                             help="Tasa interna de retorno en %")
            duration_bono = c5.number_input("Duration (años)", min_value=0.0, max_value=30.0,
                                             value=0.0, step=0.01,
                                             help="Duration modificada en años")
            
            if st.form_submit_button("💾 Guardar precio", type="primary", use_container_width=True):
                cartera_db.actualizar_precio_bono(
                    ticker_bono,
                    precio_bono,
                    tir_bono if tir_bono > 0 else None,
                    duration_bono if duration_bono > 0 else None,
                    fuente_precio
                )
                st.success(f"✅ {ticker_bono}: {precio_bono:.2f}{'%' if moneda_bono == 'USD' else ' ARS'} guardado")
                st.rerun()

        # Agregar bono personalizado (no en la lista)
        with st.expander("➕ Agregar bono no listado (ON, LECAP, etc.)"):
            with st.form("form_bono_custom", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                ticker_custom = c1.text_input("Ticker", placeholder="ej: IRCPO, YM34O").upper().strip()
                nombre_custom = c2.text_input("Nombre", placeholder="ej: ON IRSA USD 2028")
                tipo_custom   = c3.selectbox("Tipo", ["ON USD", "ON ARS", "BONO USD", "BONO ARS", 
                                                        "CER", "LECAP", "LETES", "Otro"])
                c4, c5, c6 = st.columns(3)
                precio_custom   = c4.number_input("Precio", min_value=0.01, value=100.0, step=0.01)
                moneda_custom   = c5.selectbox("Moneda", ["USD", "ARS"])
                tir_custom      = c6.number_input("TIR (%)", min_value=0.0, value=0.0, step=0.01)
                venc_custom     = st.text_input("Vencimiento (YYYY-MM-DD)", placeholder="ej: 2028-06-30")
                
                if st.form_submit_button("💾 Agregar", type="primary", use_container_width=True):
                    if not ticker_custom:
                        st.error("❌ Ingresá un ticker.")
                    else:
                        # Agregar a BONOS_REFERENCIA temporalmente y guardar precio
                        cartera_db.BONOS_REFERENCIA[ticker_custom] = {
                            "nombre": nombre_custom or ticker_custom,
                            "moneda": moneda_custom,
                            "tipo": tipo_custom,
                            "vencimiento": venc_custom or "—"
                        }
                        cartera_db.actualizar_precio_bono(
                            ticker_custom, precio_custom,
                            tir_custom if tir_custom > 0 else None,
                            None, "Manual"
                        )
                        st.success(f"✅ {ticker_custom} agregado")
                        st.rerun()

        # Eliminar precio
        st.markdown("---")
        st.markdown("#### 🗑️ Eliminar precio de un bono")
        df_con_precio = df_bonos_actual[df_bonos_actual["precio"].notna()] if "precio" in df_bonos_actual.columns else pd.DataFrame()
        if not df_con_precio.empty:
            ticker_del = st.selectbox("Seleccioná el bono", 
                                       df_con_precio["ticker"].tolist() if "ticker" in df_con_precio.columns else [],
                                       key="del_bono_sel")
            if st.button(f"🗑️ Eliminar precio de {ticker_del}", type="secondary"):
                cartera_db.eliminar_precio_bono(ticker_del)
                st.warning(f"🗑️ Precio de {ticker_del} eliminado")
                st.rerun()
        else:
            st.info("Sin precios cargados todavía.")
