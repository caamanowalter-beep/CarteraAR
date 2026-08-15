"""
pages/crypto.py — Módulo de criptomonedas para Cartera AR.
Gestión de holdings crypto con precios en tiempo real desde CoinGecko.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
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

BG_DARK     = "#0f1117"
BG_CARD     = "#1e2130"
COLOR_VERDE = "#00c896"
COLOR_ROJO  = "#f74f4f"
COLOR_AZUL  = "#4f8ef7"
COLOR_NARANJA = "#f7a34f"

# Colores por crypto
CRYPTO_COLORS = {
    "BTC": "#F7931A", "ETH": "#627EEA", "USDT": "#26A17B", "BNB": "#F3BA2F",
    "SOL": "#9945FF", "XRP": "#346AA9", "USDC": "#2775CA", "ADA": "#0D1E2D",
    "AVAX": "#E84142", "DOGE": "#C2A633", "DOT": "#E6007A", "MATIC": "#8247E5",
    "LINK": "#2A5ADA", "UNI": "#FF007A", "LTC": "#BFBBBB", "BCH": "#8DC351",
}

def _color_ganancia(val):
    try:
        v = float(val)
        return f"color: {'#00c896' if v >= 0 else '#f74f4f'}; font-weight: bold"
    except Exception:
        return ""

def _fmt(v, fmt, fallback="—"):
    try:
        return fmt.format(v) if v is not None and str(v) not in ("nan", "None") else fallback
    except Exception:
        return fallback

def render():
    st.title("🪙 Criptomonedas")
    st.markdown("Gestioná tus holdings de criptomonedas con precios en tiempo real.")

    if not (AUTH_OK and _auth.esta_logueado()):
        st.warning("Iniciá sesión para ver tus criptomonedas.")
        return

    uid = _get_user_id()
    ccl = core.obtener_dolar_ccl()

    # ── Selector de cartera ───────────────────────────────────────────────────
    df_carteras = cartera_db.listar_carteras(usuario_id=uid)
    if df_carteras.empty:
        st.info("No tenés carteras creadas. Creá una en Mi Cartera.")
        return

    opciones = {f"{row['nombre']} ({row.get('moneda_base','USD')})": row['id']
                for _, row in df_carteras.iterrows()}
    sel = st.sidebar.selectbox("Cartera", list(opciones.keys()),
                                key="crypto_cartera_sel")
    cartera_id   = opciones[sel]
    nombre_cart  = sel.split(" (")[0]

    # ── Resumen ───────────────────────────────────────────────────────────────
    df_pnl = cartera_db.calcular_pnl_crypto(cartera_id, ccl=ccl)

    if not df_pnl.empty:
        costo_total = df_pnl["Costo (USD)"].sum()
        valor_total = df_pnl["Valor actual (USD)"].dropna().sum()
        gan_total   = df_pnl["Ganancia (USD)"].dropna().sum()
        gan_pct     = (gan_total / costo_total * 100) if costo_total > 0 else 0
        n_pos       = len(df_pnl)

        c1, c2, c3, c4, c5 = st.columns(5)
        gan_color = COLOR_VERDE if gan_total >= 0 else COLOR_ROJO
        c1.metric("Valor actual (USD)", f"${valor_total:,.2f}")
        c2.metric("Costo total (USD)",  f"${costo_total:,.2f}")
        c3.metric("Ganancia (USD)",
                  f"${gan_total:+,.2f}" if df_pnl["Ganancia (USD)"].notna().any() else "—",
                  delta=f"{gan_pct:+.2f}%" if df_pnl["Ganancia (USD)"].notna().any() else None)
        c4.metric("Posiciones", n_pos)
        c5.metric("CCL", f"${ccl:,.0f}")

        st.markdown("---")

        # Gráficos
        col1, col2 = st.columns(2)
        with col1:
            # Composición por valor
            df_comp = df_pnl[df_pnl["Valor actual (USD)"].notna()].copy()
            if not df_comp.empty:
                colors = [CRYPTO_COLORS.get(s, COLOR_AZUL) for s in df_comp["Simbolo"]]
                fig = go.Figure(go.Pie(
                    labels=df_comp["Simbolo"],
                    values=df_comp["Valor actual (USD)"],
                    hole=0.4,
                    marker_colors=colors,
                ))
                fig.update_layout(
                    title="Composición por valor (USD)",
                    plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
                    font=dict(color="white"), height=320,
                    margin=dict(t=40, b=10, l=10, r=10)
                )
                st.plotly_chart(fig, use_container_width=True, key="crypto_comp")

        with col2:
            # Ganancia % por crypto
            df_gan = df_pnl[df_pnl["Ganancia (%)"].notna()].copy()
            if not df_gan.empty:
                df_gan = df_gan.sort_values("Ganancia (%)")
                colors_bar = [COLOR_VERDE if v >= 0 else COLOR_ROJO
                              for v in df_gan["Ganancia (%)"]]
                fig2 = go.Figure(go.Bar(
                    x=df_gan["Simbolo"],
                    y=df_gan["Ganancia (%)"],
                    marker_color=colors_bar,
                    text=[f"{v:+.1f}%" for v in df_gan["Ganancia (%)"]],
                    textposition="outside",
                ))
                fig2.add_hline(y=0, line_dash="dash", line_color="#888")
                fig2.update_layout(
                    title="Ganancia % por crypto",
                    plot_bgcolor=BG_DARK, paper_bgcolor=BG_CARD,
                    font=dict(color="white"), height=320,
                    margin=dict(t=40, b=10, l=10, r=10)
                )
                st.plotly_chart(fig2, use_container_width=True, key="crypto_gan")

        # Tabla detallada
        st.markdown("#### Posiciones detalladas")
        cols_show = [c for c in ["Simbolo","Cantidad","Precio compra (USD)",
                                  "Precio actual (USD)","Costo (USD)",
                                  "Valor actual (USD)","Ganancia (USD)",
                                  "Ganancia (%)","Ganancia (ARS)","Exchange"]
                     if c in df_pnl.columns]
        st.dataframe(
            df_pnl[cols_show].style
                .map(_color_ganancia, subset=[c for c in ["Ganancia (USD)","Ganancia (%)"]
                                               if c in df_pnl.columns])
                .format({
                    "Cantidad":            lambda v: _fmt(v, "{:,.6f}"),
                    "Precio compra (USD)": lambda v: _fmt(v, "${:,.4f}"),
                    "Precio actual (USD)": lambda v: _fmt(v, "${:,.4f}"),
                    "Costo (USD)":         lambda v: _fmt(v, "${:,.2f}"),
                    "Valor actual (USD)":  lambda v: _fmt(v, "${:,.2f}"),
                    "Ganancia (USD)":      lambda v: _fmt(v, "${:+,.2f}"),
                    "Ganancia (%)":        lambda v: _fmt(v, "{:+.2f}%"),
                    "Ganancia (ARS)":      lambda v: _fmt(v, "${:+,.0f}"),
                }, na_rep="—"),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No tenés criptomonedas cargadas en esta cartera. Agregá tu primera posición abajo.")

    st.markdown("---")

    # ── Agregar posición ──────────────────────────────────────────────────────
    st.markdown("#### ➕ Agregar / Actualizar posición crypto")

    # Selector de crypto fuera del form
    cryptos_disponibles = sorted(cartera_db.CRYPTO_IDS.keys())
    key_crypto = f"crypto_sel_{cartera_id}"
    if key_crypto not in st.session_state:
        st.session_state[key_crypto] = "BTC"

    col_sel, col_info = st.columns([2, 3])
    with col_sel:
        crypto_sel = st.selectbox(
            "Criptomoneda",
            cryptos_disponibles,
            index=cryptos_disponibles.index(st.session_state[key_crypto])
                  if st.session_state[key_crypto] in cryptos_disponibles else 0,
            key=key_crypto
        )

    # Mostrar precio actual si está disponible
    with col_info:
        with st.spinner("Obteniendo precio..."):
            precio_actual_dict = cartera_db.obtener_precios_crypto([crypto_sel])
            precio_actual = precio_actual_dict.get(crypto_sel)
        if precio_actual:
            st.metric(f"Precio actual {crypto_sel}",
                      f"${precio_actual:,.4f} USD",
                      f"≈ ${precio_actual * ccl:,.0f} ARS")
        else:
            st.info(f"Sin precio disponible para {crypto_sel}")

    with st.form(f"form_crypto_{cartera_id}", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        cantidad_c    = c1.number_input("Cantidad", min_value=0.000001,
                                         value=0.01, step=0.001, format="%.6f")
        precio_compra = c2.number_input("Precio compra (USD)", min_value=0.0001,
                                         value=float(precio_actual) if precio_actual else 1.0,
                                         step=0.01, format="%.4f")
        exchange_c    = c3.selectbox("Exchange / Billetera",
                                      ["Binance", "Nexo", "Coinbase", "Kraken",
                                       "OKX", "Bybit", "Lemon", "Belo", "Ripio",
                                       "Satoshi Tango", "Otro"])
        c4, c5 = st.columns(2)
        fecha_c = c4.date_input("Fecha de compra", value=date.today())
        notas_c = c5.text_input("Notas (opcional)")

        if st.form_submit_button("✅ Agregar posición", type="primary",
                                  use_container_width=True):
            try:
                cartera_db.agregar_crypto(
                    cartera_id, crypto_sel, cantidad_c, precio_compra,
                    exchange_c, str(fecha_c), crypto_sel, notas_c
                )
                costo = cantidad_c * precio_compra
                st.success(
                    f"✅ {cantidad_c:.6f} {crypto_sel} @ ${precio_compra:,.4f} USD "
                    f"(costo: ${costo:,.2f} USD) agregado a {nombre_cart}"
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # ── Eliminar posición ─────────────────────────────────────────────────────
    df_crypto = cartera_db.listar_crypto(cartera_id)
    if not df_crypto.empty:
        st.markdown("---")
        st.markdown("#### 🗑️ Eliminar posición")
        ticker_del = st.selectbox("Crypto a eliminar",
                                   df_crypto["simbolo"].tolist(),
                                   key=f"del_crypto_{cartera_id}")
        if st.button(f"🗑️ Eliminar {ticker_del}", type="secondary",
                     key=f"btn_del_crypto_{cartera_id}"):
            cartera_db.eliminar_crypto(cartera_id, ticker_del)
            st.success(f"✅ {ticker_del} eliminado")
            st.rerun()

    # ── Info de mercado ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📊 Mercado crypto (Top 10)")
    with st.spinner("Cargando datos de mercado..."):
        try:
            import requests
            url = ("https://api.coingecko.com/api/v3/coins/markets"
                   "?vs_currency=usd&order=market_cap_desc&per_page=10"
                   "&page=1&sparkline=false&price_change_percentage=24h")
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                market_data = r.json()
                df_market = pd.DataFrame([{
                    "Crypto":     f"{d['symbol'].upper()} — {d['name']}",
                    "Precio USD": d["current_price"],
                    "Cap. Mercado": d["market_cap"],
                    "Cambio 24h %": d["price_change_percentage_24h"],
                    "Vol. 24h":   d["total_volume"],
                } for d in market_data])

                st.dataframe(
                    df_market.style
                        .map(_color_ganancia, subset=["Cambio 24h %"])
                        .format({
                            "Precio USD":    "${:,.4f}",
                            "Cap. Mercado":  "${:,.0f}",
                            "Cambio 24h %":  "{:+.2f}%",
                            "Vol. 24h":      "${:,.0f}",
                        }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("No se pudo obtener datos de mercado en este momento.")
        except Exception as e:
            st.info(f"No se pudo obtener datos de mercado: {e}")