"""
notificaciones.py — Sistema de notificaciones multi-canal.
Soporta: Telegram, Email (Gmail/SMTP), y notificaciones en la app.

Configuración por usuario en Supabase tabla: config_notificaciones
"""
import os
import smtplib
import requests
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import cartera_db

# ═══════════════════════════════════════════════════════════════════════════════
# TABLA DE CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def init_notificaciones_db() -> None:
    """Crea la tabla de configuración de notificaciones."""
    con = cartera_db._get_connection()
    cur = con.cursor()
    pk = "SERIAL" if cartera_db.USE_POSTGRES else "INTEGER"
    ai = "" if cartera_db.USE_POSTGRES else "AUTOINCREMENT"
    try:
        cur.execute(f"""CREATE TABLE IF NOT EXISTS config_notificaciones (
            id              {pk} PRIMARY KEY {ai},
            usuario_id      INTEGER NOT NULL UNIQUE,
            telegram_token  TEXT,
            telegram_chat_id TEXT,
            telegram_activo INTEGER NOT NULL DEFAULT 0,
            email_destino   TEXT,
            email_smtp_user TEXT,
            email_smtp_pass TEXT,
            email_activo    INTEGER NOT NULL DEFAULT 0,
            notif_precio_bajo  INTEGER NOT NULL DEFAULT 1,
            notif_precio_alto  INTEGER NOT NULL DEFAULT 1,
            notif_rsi_bajo     INTEGER NOT NULL DEFAULT 1,
            notif_rsi_alto     INTEGER NOT NULL DEFAULT 1,
            notif_snapshot     INTEGER NOT NULL DEFAULT 0,
            actualizado     TEXT
        )""")
        # Tabla de historial de notificaciones enviadas
        cur.execute(f"""CREATE TABLE IF NOT EXISTS historial_notificaciones (
            id          {pk} PRIMARY KEY {ai},
            usuario_id  INTEGER NOT NULL,
            cartera_id  INTEGER,
            ticker      TEXT,
            tipo        TEXT NOT NULL,
            mensaje     TEXT NOT NULL,
            canal       TEXT NOT NULL,
            enviado     INTEGER NOT NULL DEFAULT 0,
            fecha       TEXT NOT NULL,
            error       TEXT
        )""")
        con.commit()
    except Exception:
        pass
    finally:
        con.close()

# ═══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def get_config(usuario_id: int) -> dict:
    """Obtiene la configuración de notificaciones de un usuario."""
    try:
        df = cartera_db._read_sql(
            "SELECT * FROM config_notificaciones WHERE usuario_id=?",
            [usuario_id]
        )
        if df.empty:
            return _config_default(usuario_id)
        return df.iloc[0].to_dict()
    except Exception:
        return _config_default(usuario_id)

def _config_default(usuario_id: int) -> dict:
    return {
        "usuario_id": usuario_id,
        "telegram_token": None, "telegram_chat_id": None, "telegram_activo": 0,
        "email_destino": None, "email_smtp_user": None, "email_smtp_pass": None,
        "email_activo": 0,
        "notif_precio_bajo": 1, "notif_precio_alto": 1,
        "notif_rsi_bajo": 1, "notif_rsi_alto": 1,
        "notif_snapshot": 0,
    }

def guardar_config(usuario_id: int, config: dict) -> bool:
    """Guarda la configuración de notificaciones."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        if cartera_db.USE_POSTGRES:
            cartera_db._execute("""
                INSERT INTO config_notificaciones
                    (usuario_id, telegram_token, telegram_chat_id, telegram_activo,
                     email_destino, email_smtp_user, email_smtp_pass, email_activo,
                     notif_precio_bajo, notif_precio_alto, notif_rsi_bajo, notif_rsi_alto,
                     notif_snapshot, actualizado)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (usuario_id) DO UPDATE SET
                    telegram_token=EXCLUDED.telegram_token,
                    telegram_chat_id=EXCLUDED.telegram_chat_id,
                    telegram_activo=EXCLUDED.telegram_activo,
                    email_destino=EXCLUDED.email_destino,
                    email_smtp_user=EXCLUDED.email_smtp_user,
                    email_smtp_pass=EXCLUDED.email_smtp_pass,
                    email_activo=EXCLUDED.email_activo,
                    notif_precio_bajo=EXCLUDED.notif_precio_bajo,
                    notif_precio_alto=EXCLUDED.notif_precio_alto,
                    notif_rsi_bajo=EXCLUDED.notif_rsi_bajo,
                    notif_rsi_alto=EXCLUDED.notif_rsi_alto,
                    notif_snapshot=EXCLUDED.notif_snapshot,
                    actualizado=EXCLUDED.actualizado
            """, (usuario_id,
                  config.get("telegram_token"), config.get("telegram_chat_id"),
                  int(config.get("telegram_activo", 0)),
                  config.get("email_destino"), config.get("email_smtp_user"),
                  config.get("email_smtp_pass"), int(config.get("email_activo", 0)),
                  int(config.get("notif_precio_bajo", 1)),
                  int(config.get("notif_precio_alto", 1)),
                  int(config.get("notif_rsi_bajo", 1)),
                  int(config.get("notif_rsi_alto", 1)),
                  int(config.get("notif_snapshot", 0)), ahora))
        else:
            cartera_db._execute("""
                INSERT INTO config_notificaciones
                    (usuario_id, telegram_token, telegram_chat_id, telegram_activo,
                     email_destino, email_smtp_user, email_smtp_pass, email_activo,
                     notif_precio_bajo, notif_precio_alto, notif_rsi_bajo, notif_rsi_alto,
                     notif_snapshot, actualizado)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(usuario_id) DO UPDATE SET
                    telegram_token=excluded.telegram_token,
                    telegram_chat_id=excluded.telegram_chat_id,
                    telegram_activo=excluded.telegram_activo,
                    email_destino=excluded.email_destino,
                    email_smtp_user=excluded.email_smtp_user,
                    email_smtp_pass=excluded.email_smtp_pass,
                    email_activo=excluded.email_activo,
                    notif_precio_bajo=excluded.notif_precio_bajo,
                    notif_precio_alto=excluded.notif_precio_alto,
                    notif_rsi_bajo=excluded.notif_rsi_bajo,
                    notif_rsi_alto=excluded.notif_rsi_alto,
                    notif_snapshot=excluded.notif_snapshot,
                    actualizado=excluded.actualizado
            """, (usuario_id,
                  config.get("telegram_token"), config.get("telegram_chat_id"),
                  int(config.get("telegram_activo", 0)),
                  config.get("email_destino"), config.get("email_smtp_user"),
                  config.get("email_smtp_pass"), int(config.get("email_activo", 0)),
                  int(config.get("notif_precio_bajo", 1)),
                  int(config.get("notif_precio_alto", 1)),
                  int(config.get("notif_rsi_bajo", 1)),
                  int(config.get("notif_rsi_alto", 1)),
                  int(config.get("notif_snapshot", 0)), ahora))
        return True
    except Exception as e:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# ENVÍO DE NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════════════════════

def enviar_telegram(token: str, chat_id: str, mensaje: str) -> tuple[bool, str]:
    """
    Envía un mensaje por Telegram.
    token: token del bot (obtenido de @BotFather)
    chat_id: ID del chat (obtenido de @userinfobot)
    """
    if not token or not chat_id:
        return False, "Token o chat_id no configurado"
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code == 200:
            return True, "OK"
        else:
            data = r.json()
            return False, data.get("description", f"Error {r.status_code}")
    except Exception as e:
        return False, str(e)

def enviar_email(smtp_user: str, smtp_pass: str, destino: str,
                 asunto: str, cuerpo: str) -> tuple[bool, str]:
    """
    Envía un email via Gmail SMTP.
    smtp_user: tu email de Gmail
    smtp_pass: contraseña de aplicación de Gmail (no la contraseña normal)
    destino: email destinatario
    """
    if not smtp_user or not smtp_pass or not destino:
        return False, "Configuración de email incompleta"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"]    = smtp_user
        msg["To"]      = destino

        # Versión texto plano
        texto_plano = cuerpo.replace("<b>", "").replace("</b>", "").replace("<br>", "\n")
        msg.attach(MIMEText(texto_plano, "plain", "utf-8"))

        # Versión HTML
        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#0f1117;color:#e2e8f0;padding:20px">
        <div style="max-width:500px;margin:0 auto;background:#1e2130;border-radius:10px;padding:20px">
        <h2 style="color:#4f8ef7">📈 Cartera AR — Alerta</h2>
        <p>{cuerpo.replace(chr(10), '<br>')}</p>
        <hr style="border-color:#2d3748">
        <p style="color:#888;font-size:12px">Cartera AR v3.0 — Financieramente.ok</p>
        </div></body></html>
        """
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, destino, msg.as_string())
        return True, "OK"
    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación. Verificá la contraseña de aplicación de Gmail."
    except Exception as e:
        return False, str(e)

def enviar_notificacion(usuario_id: int, ticker: str, tipo: str,
                         valor_actual: float, valor_umbral: float,
                         cartera_id: int = None) -> dict:
    """
    Envía una notificación por todos los canales configurados.
    tipo: PRECIO_BAJO | PRECIO_ALTO | RSI_BAJO | RSI_ALTO
    """
    config = get_config(usuario_id)
    resultados = {}

    # Construir mensaje
    iconos = {
        "PRECIO_BAJO":  "📉",
        "PRECIO_ALTO":  "📈",
        "RSI_BAJO":     "🟢",
        "RSI_ALTO":     "🔴",
    }
    icono = iconos.get(tipo, "🔔")
    descripcion = {
        "PRECIO_BAJO":  f"Precio cayó a ${valor_actual:,.2f} (umbral: ${valor_umbral:,.2f})",
        "PRECIO_ALTO":  f"Precio subió a ${valor_actual:,.2f} (umbral: ${valor_umbral:,.2f})",
        "RSI_BAJO":     f"RSI en {valor_actual:.1f} (sobreventa, umbral: {valor_umbral:.0f})",
        "RSI_ALTO":     f"RSI en {valor_actual:.1f} (sobrecompra, umbral: {valor_umbral:.0f})",
    }.get(tipo, f"Valor: {valor_actual}")

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    mensaje = (
        f"{icono} <b>Alerta Cartera AR</b>\n\n"
        f"<b>Ticker:</b> {ticker}\n"
        f"<b>Tipo:</b> {tipo.replace('_', ' ')}\n"
        f"{descripcion}\n\n"
        f"<i>{fecha}</i>"
    )
    asunto = f"{icono} Cartera AR — Alerta {ticker} ({tipo.replace('_', ' ')})"

    # Enviar por Telegram
    if config.get("telegram_activo") and config.get("telegram_token") and config.get("telegram_chat_id"):
        ok, err = enviar_telegram(
            config["telegram_token"],
            config["telegram_chat_id"],
            mensaje
        )
        resultados["telegram"] = {"ok": ok, "error": err if not ok else None}
        _registrar_notificacion(usuario_id, cartera_id, ticker, tipo, mensaje, "telegram", ok, err)

    # Enviar por Email
    if config.get("email_activo") and config.get("email_smtp_user") and config.get("email_destino"):
        ok, err = enviar_email(
            config["email_smtp_user"],
            config["email_smtp_pass"],
            config["email_destino"],
            asunto,
            mensaje.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        )
        resultados["email"] = {"ok": ok, "error": err if not ok else None}
        _registrar_notificacion(usuario_id, cartera_id, ticker, tipo, mensaje, "email", ok, err)

    return resultados

def _registrar_notificacion(usuario_id, cartera_id, ticker, tipo,
                              mensaje, canal, enviado, error=None):
    """Registra el historial de notificaciones."""
    try:
        cartera_db._execute("""
            INSERT INTO historial_notificaciones
                (usuario_id, cartera_id, ticker, tipo, mensaje, canal, enviado, fecha, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (usuario_id, cartera_id, ticker, tipo, mensaje[:500], canal,
              int(enviado), datetime.now().strftime("%Y-%m-%d %H:%M"), error))
    except Exception:
        pass

def listar_historial_notificaciones(usuario_id: int, limite: int = 50) -> pd.DataFrame:
    """Lista el historial de notificaciones de un usuario."""
    try:
        return cartera_db._read_sql(
            "SELECT * FROM historial_notificaciones WHERE usuario_id=? ORDER BY fecha DESC LIMIT ?",
            [usuario_id, limite]
        )
    except Exception:
        return pd.DataFrame()

# ═══════════════════════════════════════════════════════════════════════════════
# VERIFICACIÓN DE ALERTAS
# ═══════════════════════════════════════════════════════════════════════════════

def verificar_alertas(usuario_id: int, ccl: float = 1200.0) -> list[dict]:
    """
    Verifica todas las alertas activas del usuario y envía notificaciones
    si se cumplen las condiciones.
    Retorna lista de alertas disparadas.
    """
    import yfinance as yf
    disparadas = []

    try:
        df_carteras = cartera_db.listar_carteras(usuario_id=usuario_id)
        if df_carteras.empty:
            return []

        for _, cart in df_carteras.iterrows():
            cid = cart["id"]
            df_alertas = cartera_db.listar_alertas(cid)
            if df_alertas.empty:
                continue

            for _, alerta in df_alertas.iterrows():
                ticker = str(alerta["ticker"])
                tipo   = str(alerta["tipo"])
                umbral = float(alerta["valor"])
                alerta_id = int(alerta["id"])

                try:
                    info = yf.Ticker(ticker).info
                    precio_actual = info.get("currentPrice") or info.get("regularMarketPrice")
                    if not precio_actual:
                        continue
                    precio_actual = float(precio_actual)

                    disparar = False
                    if tipo == "PRECIO_BAJO" and precio_actual <= umbral:
                        disparar = True
                    elif tipo == "PRECIO_ALTO" and precio_actual >= umbral:
                        disparar = True

                    if disparar:
                        res = enviar_notificacion(
                            usuario_id, ticker, tipo,
                            precio_actual, umbral, cid
                        )
                        disparadas.append({
                            "ticker": ticker, "tipo": tipo,
                            "valor": precio_actual, "umbral": umbral,
                            "resultado": res
                        })
                        # Desactivar alerta después de disparar
                        cartera_db.desactivar_alerta(alerta_id)

                except Exception:
                    pass

    except Exception:
        pass

    return disparadas

# Auto-inicializar al importar
try:
    init_notificaciones_db()
except Exception:
    pass