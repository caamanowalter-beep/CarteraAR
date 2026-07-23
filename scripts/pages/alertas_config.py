"""
pages/alertas_config.py — Configuración de notificaciones Telegram + Email.
"""
import streamlit as st
import pandas as pd
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cartera_db
import notificaciones

try:
    import auth as _auth
    AUTH_OK = True
except Exception:
    AUTH_OK = False

def _get_user_id():
    if AUTH_OK and _auth.esta_logueado():
        return _auth.get_user_id()
    return None

BG_CARD = "#1e2130"
COLOR_VERDE  = "#00c896"
COLOR_ROJO   = "#f74f4f"
COLOR_AZUL   = "#4f8ef7"
COLOR_NARANJA= "#f7a34f"

def render():
    st.title("🔔 Alertas y Notificaciones")
    st.markdown("Configurá alertas de precio y recibí notificaciones por **Telegram** y/o **Email**.")

    uid = _get_user_id()
    if not uid:
        st.warning("Iniciá sesión para configurar notificaciones.")
        return

    # Inicializar tablas
    notificaciones.init_notificaciones_db()

    # Cargar configuración actual
    config = notificaciones.get_config(uid)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📱 Telegram", "📧 Email", "🔔 Mis alertas", "📋 Historial"
    ])

    # ── TAB 1: TELEGRAM ───────────────────────────────────────────────────────
    with tab1:
        st.markdown("### 📱 Configuración de Telegram")

        st.info("""
        **Cómo configurar Telegram en 3 pasos:**

        **1.** Abrí Telegram y buscá **@BotFather**
        → Escribí `/newbot` → seguí las instrucciones
        → Copiá el **Token** que te da (ej: `123456:ABC-DEF...`)

        **2.** Buscá **@userinfobot** en Telegram
        → Escribí `/start`
        → Copiá tu **Chat ID** (ej: `123456789`)

        **3.** Pegá ambos datos acá abajo y hacé click en **Probar conexión**
        """)

        with st.form("form_telegram"):
            telegram_activo = st.checkbox(
                "✅ Activar notificaciones por Telegram",
                value=bool(config.get("telegram_activo", 0))
            )
            token = st.text_input(
                "Token del Bot",
                value=config.get("telegram_token") or "",
                type="password",
                placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
            )
            chat_id = st.text_input(
                "Chat ID",
                value=config.get("telegram_chat_id") or "",
                placeholder="123456789"
            )

            c1, c2 = st.columns(2)
            probar = c1.form_submit_button("🧪 Probar conexión", use_container_width=True)
            guardar = c2.form_submit_button("💾 Guardar", type="primary", use_container_width=True)

            if probar and token and chat_id:
                ok, err = notificaciones.enviar_telegram(
                    token, chat_id,
                    "✅ <b>Cartera AR</b> — Conexión exitosa!\n\nTus alertas llegarán aquí."
                )
                if ok:
                    st.success("✅ Mensaje de prueba enviado correctamente")
                else:
                    st.error(f"❌ Error: {err}")

            if guardar:
                config["telegram_activo"]  = int(telegram_activo)
                config["telegram_token"]   = token or None
                config["telegram_chat_id"] = chat_id or None
                if notificaciones.guardar_config(uid, config):
                    st.success("✅ Configuración de Telegram guardada")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar")

        # Estado actual
        if config.get("telegram_activo") and config.get("telegram_token"):
            st.success("✅ Telegram configurado y activo")
        else:
            st.warning("⚠️ Telegram no configurado")

    # ── TAB 2: EMAIL ──────────────────────────────────────────────────────────
    with tab2:
        st.markdown("### 📧 Configuración de Email")

        st.info("""
        **Cómo configurar Gmail:**

        **1.** Ir a tu cuenta Google → **Seguridad** → **Verificación en 2 pasos** (activar si no está)

        **2.** Ir a **Contraseñas de aplicaciones**
        → Seleccionar "Correo" y "Windows/Mac"
        → Copiar la contraseña de 16 caracteres generada

        **3.** Pegar esa contraseña acá (NO tu contraseña normal de Gmail)

        ⚠️ La contraseña de aplicación se guarda encriptada en Supabase.
        """)

        with st.form("form_email"):
            email_activo = st.checkbox(
                "✅ Activar notificaciones por Email",
                value=bool(config.get("email_activo", 0))
            )
            smtp_user = st.text_input(
                "Tu email de Gmail",
                value=config.get("email_smtp_user") or "",
                placeholder="tu@gmail.com"
            )
            smtp_pass = st.text_input(
                "Contraseña de aplicación (16 caracteres)",
                value=config.get("email_smtp_pass") or "",
                type="password",
                placeholder="xxxx xxxx xxxx xxxx"
            )
            email_destino = st.text_input(
                "Email destinatario (puede ser el mismo u otro)",
                value=config.get("email_destino") or "",
                placeholder="destino@gmail.com"
            )

            c1, c2 = st.columns(2)
            probar_email = c1.form_submit_button("🧪 Probar email", use_container_width=True)
            guardar_email = c2.form_submit_button("💾 Guardar", type="primary", use_container_width=True)

            if probar_email and smtp_user and smtp_pass and email_destino:
                ok, err = notificaciones.enviar_email(
                    smtp_user, smtp_pass, email_destino,
                    "✅ Cartera AR — Prueba de conexión",
                    "Conexión exitosa. Tus alertas llegarán a este email."
                )
                if ok:
                    st.success(f"✅ Email de prueba enviado a {email_destino}")
                else:
                    st.error(f"❌ Error: {err}")

            if guardar_email:
                config["email_activo"]    = int(email_activo)
                config["email_smtp_user"] = smtp_user or None
                config["email_smtp_pass"] = smtp_pass or None
                config["email_destino"]   = email_destino or None
                if notificaciones.guardar_config(uid, config):
                    st.success("✅ Configuración de Email guardada")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar")

        # Estado actual
        if config.get("email_activo") and config.get("email_smtp_user"):
            st.success(f"✅ Email configurado → {config.get('email_destino')}")
        else:
            st.warning("⚠️ Email no configurado")

    # ── TAB 3: MIS ALERTAS ────────────────────────────────────────────────────
    with tab3:
        st.markdown("### 🔔 Mis alertas activas")

        df_carteras = cartera_db.listar_carteras(usuario_id=uid)
        if df_carteras.empty:
            st.info("Sin carteras. Creá una en Mi Cartera.")
        else:
            # Selector de cartera
            opciones = {f"{r['nombre']}": r['id'] for _, r in df_carteras.iterrows()}
            sel = st.selectbox("Cartera", list(opciones.keys()), key="alert_cart_sel")
            cid = opciones[sel]

            # Agregar alerta
            with st.expander("➕ Nueva alerta", expanded=True):
                with st.form("form_nueva_alerta_notif", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    ticker_a = c1.text_input("Ticker", placeholder="ej: AAPL").upper().strip()
                    tipo_a   = c2.selectbox("Tipo", [
                        "PRECIO_BAJO", "PRECIO_ALTO"
                    ])
                    valor_a  = c3.number_input("Valor umbral", min_value=0.0,
                                                value=100.0, step=1.0)

                    # Canales
                    st.markdown("**Canales de notificación:**")
                    cc1, cc2 = st.columns(2)
                    usar_telegram = cc1.checkbox(
                        "📱 Telegram",
                        value=bool(config.get("telegram_activo")),
                        disabled=not bool(config.get("telegram_activo"))
                    )
                    usar_email = cc2.checkbox(
                        "📧 Email",
                        value=bool(config.get("email_activo")),
                        disabled=not bool(config.get("email_activo"))
                    )

                    if not config.get("telegram_activo") and not config.get("email_activo"):
                        st.warning("⚠️ Configurá al menos un canal (Telegram o Email) para recibir notificaciones.")

                    if st.form_submit_button("✅ Crear alerta", type="primary", use_container_width=True):
                        if not ticker_a:
                            st.error("❌ Ingresá un ticker.")
                        else:
                            cartera_db.agregar_alerta(cid, ticker_a, tipo_a, valor_a)
                            st.success(f"✅ Alerta creada: {ticker_a} {tipo_a} @ {valor_a}")
                            st.rerun()

            # Listar alertas
            df_alertas = cartera_db.listar_alertas(cid)
            if df_alertas.empty:
                st.info("Sin alertas activas en esta cartera.")
            else:
                st.markdown(f"**{len(df_alertas)} alerta(s) activa(s):**")
                for _, row in df_alertas.iterrows():
                    tipo_icon = {"PRECIO_BAJO": "📉", "PRECIO_ALTO": "📈",
                                 "RSI_BAJO": "🟢", "RSI_ALTO": "🔴"}.get(str(row["tipo"]), "🔔")
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(
                        f'<div style="background:{BG_CARD};padding:8px 12px;'
                        f'border-radius:6px;margin-bottom:4px">'
                        f'{tipo_icon} <b>{row["ticker"]}</b> — {row["tipo"].replace("_"," ")} '
                        f'@ <b>{row["valor"]}</b>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    if c2.button("❌", key=f"del_alerta_notif_{row['id']}"):
                        cartera_db.desactivar_alerta(int(row["id"]))
                        st.rerun()

            # Verificar alertas manualmente
            st.markdown("---")
            if st.button("🔍 Verificar alertas ahora", use_container_width=True):
                with st.spinner("Verificando precios..."):
                    ccl = cartera_db.obtener_dolar_ccl() if hasattr(cartera_db, 'obtener_dolar_ccl') else 1200.0
                    try:
                        from core import obtener_dolar_ccl
                        ccl = obtener_dolar_ccl()
                    except Exception:
                        pass
                    disparadas = notificaciones.verificar_alertas(uid, ccl)
                if disparadas:
                    st.success(f"✅ {len(disparadas)} alerta(s) disparada(s) y notificación(es) enviada(s)")
                    for d in disparadas:
                        st.write(f"  • {d['ticker']}: {d['tipo']} @ {d['valor']:.2f}")
                else:
                    st.info("Sin alertas disparadas en este momento.")

    # ── TAB 4: HISTORIAL ──────────────────────────────────────────────────────
    with tab4:
        st.markdown("### 📋 Historial de notificaciones")
        df_hist = notificaciones.listar_historial_notificaciones(uid)
        if df_hist.empty:
            st.info("Sin notificaciones enviadas todavía.")
        else:
            def color_enviado(val):
                return "color: #00c896" if val else "color: #f74f4f"

            cols_show = [c for c in ["fecha","ticker","tipo","canal","enviado","error"]
                         if c in df_hist.columns]
            st.dataframe(
                df_hist[cols_show].style
                    .map(color_enviado, subset=["enviado"] if "enviado" in cols_show else [])
                    .format({"enviado": lambda v: "✅ Enviado" if v else "❌ Error"}),
                use_container_width=True, hide_index=True
            )