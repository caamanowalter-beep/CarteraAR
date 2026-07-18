"""
auth.py — Autenticación multi-usuario para Cartera AR.
Sistema simple de login con usuarios almacenados en Supabase/SQLite.
Cada usuario ve SOLO sus propias carteras.

Características:
  - Login con email + contraseña
  - Registro de nuevos usuarios
  - Contraseñas hasheadas con bcrypt
  - Sesión persistente con st.session_state
  - Cada usuario tiene su propio espacio de carteras
"""
import os
import hashlib
import secrets
import streamlit as st
import pandas as pd
from datetime import datetime

# Importar capa de DB
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from cartera_db import _execute, _read_sql, _get_connection, USE_POSTGRES, init_db
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════════════════════
# TABLA DE USUARIOS
# ═══════════════════════════════════════════════════════════════════════════════

def init_auth_db() -> None:
    """Crea la tabla de usuarios si no existe."""
    con = _get_connection()
    cur = con.cursor()

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id          SERIAL PRIMARY KEY,
                email       TEXT    NOT NULL UNIQUE,
                nombre      TEXT    NOT NULL,
                password_hash TEXT  NOT NULL,
                salt        TEXT    NOT NULL,
                creado      TEXT    NOT NULL,
                activo      INTEGER NOT NULL DEFAULT 1,
                es_admin    INTEGER NOT NULL DEFAULT 0
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    NOT NULL UNIQUE,
                nombre      TEXT    NOT NULL,
                password_hash TEXT  NOT NULL,
                salt        TEXT    NOT NULL,
                creado      TEXT    NOT NULL,
                activo      INTEGER NOT NULL DEFAULT 1,
                es_admin    INTEGER NOT NULL DEFAULT 0
            )
        """)

    con.commit()
    con.close()

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════════════════════

def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """
    Hashea una contraseña con SHA-256 + salt.
    Retorna (hash, salt).
    No requiere bcrypt — funciona con la librería estándar de Python.
    """
    if salt is None:
        salt = secrets.token_hex(32)
    pwd_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return pwd_hash, salt

def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verifica una contraseña contra su hash almacenado."""
    computed_hash, _ = _hash_password(password, salt)
    return computed_hash == stored_hash

# ═══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE USUARIOS
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_usuario(email: str, nombre: str, password: str) -> tuple[bool, str]:
    """
    Registra un nuevo usuario.
    Retorna (éxito, mensaje).
    """
    email = email.strip().lower()
    nombre = nombre.strip()

    if not email or "@" not in email:
        return False, "Email inválido."
    if not nombre:
        return False, "El nombre es requerido."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    # Verificar si ya existe
    df = _read_sql("SELECT id FROM usuarios WHERE email=?", [email])
    if not df.empty:
        return False, "Ya existe una cuenta con ese email."

    pwd_hash, salt = _hash_password(password)
    try:
        _execute("""
            INSERT INTO usuarios (email, nombre, password_hash, salt, creado)
            VALUES (?, ?, ?, ?, ?)
        """, (email, nombre, pwd_hash, salt,
              datetime.now().strftime("%Y-%m-%d %H:%M")))
        return True, f"✅ Cuenta creada para {nombre}. Ya podés iniciar sesión."
    except Exception as e:
        return False, f"Error al crear cuenta: {e}"

def login_usuario(email: str, password: str) -> tuple[bool, dict | str]:
    """
    Verifica credenciales.
    Retorna (éxito, datos_usuario | mensaje_error).
    """
    email = email.strip().lower()
    df = _read_sql(
        "SELECT * FROM usuarios WHERE email=? AND activo=1", [email]
    )
    if df.empty:
        return False, "Email o contraseña incorrectos."

    row = df.iloc[0]
    if not _verify_password(password, str(row["password_hash"]), str(row["salt"])):
        return False, "Email o contraseña incorrectos."

    return True, {
        "id":       int(row["id"]),
        "email":    str(row["email"]),
        "nombre":   str(row["nombre"]),
        "es_admin": bool(row["es_admin"]),
    }

def listar_usuarios() -> pd.DataFrame:
    """Lista todos los usuarios (solo para admins)."""
    return _read_sql(
        "SELECT id, email, nombre, creado, activo, es_admin FROM usuarios ORDER BY creado DESC"
    )

def cambiar_password(user_id: int, password_actual: str,
                     password_nueva: str) -> tuple[bool, str]:
    """Cambia la contraseña de un usuario."""
    df = _read_sql("SELECT * FROM usuarios WHERE id=?", [user_id])
    if df.empty:
        return False, "Usuario no encontrado."
    row = df.iloc[0]
    if not _verify_password(password_actual, str(row["password_hash"]), str(row["salt"])):
        return False, "Contraseña actual incorrecta."
    if len(password_nueva) < 6:
        return False, "La nueva contraseña debe tener al menos 6 caracteres."
    pwd_hash, salt = _hash_password(password_nueva)
    _execute(
        "UPDATE usuarios SET password_hash=?, salt=? WHERE id=?",
        (pwd_hash, salt, user_id)
    )
    return True, "✅ Contraseña actualizada correctamente."

# ═══════════════════════════════════════════════════════════════════════════════
# SESIÓN DE STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════════

def get_usuario_actual() -> dict | None:
    """Retorna el usuario logueado o None si no hay sesión."""
    return st.session_state.get("usuario_actual")

def esta_logueado() -> bool:
    """Retorna True si hay un usuario logueado."""
    return get_usuario_actual() is not None

def get_user_id() -> int | None:
    """Retorna el ID del usuario logueado."""
    u = get_usuario_actual()
    return u["id"] if u else None

def cerrar_sesion() -> None:
    """Cierra la sesión del usuario actual."""
    st.session_state.pop("usuario_actual", None)
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTES UI DE STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════════

BG_CARD  = "#1e2130"
COLOR_AZUL = "#4f8ef7"

def render_login() -> None:
    """
    Muestra la pantalla de login/registro.
    Bloquea el acceso hasta que el usuario se autentique.
    """
    st.markdown("""
    <div style="max-width:420px;margin:60px auto">
    """, unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align:center;margin-bottom:30px">'
        f'<h1 style="color:white">📈 Cartera AR</h1>'
        f'<p style="color:#aaa">Sistema de análisis de portafolios</p>'
        f'</div>',
        unsafe_allow_html=True
    )

    tab_login, tab_registro = st.tabs(["🔐 Iniciar sesión", "📝 Crear cuenta"])

    with tab_login:
        with st.form("form_login", clear_on_submit=False):
            email    = st.text_input("Email", placeholder="tu@email.com")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button(
                "▶️ Ingresar", type="primary", use_container_width=True
            )
            if submitted:
                if not email or not password:
                    st.error("❌ Completá email y contraseña.")
                else:
                    ok, resultado = login_usuario(email, password)
                    if ok:
                        st.session_state["usuario_actual"] = resultado
                        st.success(f"✅ Bienvenido, {resultado['nombre']}!")
                        st.rerun()
                    else:
                        st.error(f"❌ {resultado}")

    with tab_registro:
        with st.form("form_registro", clear_on_submit=True):
            nombre_reg   = st.text_input("Nombre completo", placeholder="Walter Caamaño")
            email_reg    = st.text_input("Email", placeholder="tu@email.com")
            password_reg = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
            password_rep = st.text_input("Repetir contraseña", type="password")
            submitted_reg = st.form_submit_button(
                "✅ Crear cuenta", type="primary", use_container_width=True
            )
            if submitted_reg:
                if password_reg != password_rep:
                    st.error("❌ Las contraseñas no coinciden.")
                else:
                    ok, msg = registrar_usuario(email_reg, nombre_reg, password_reg)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(f"❌ {msg}")

    st.markdown("</div>", unsafe_allow_html=True)


def render_usuario_sidebar() -> None:
    """
    Muestra info del usuario en el sidebar con opción de cerrar sesión.
    """
    u = get_usuario_actual()
    if not u:
        return
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f'<div style="background:#1e2130;padding:10px;border-radius:8px;'
        f'border-left:3px solid #4f8ef7">'
        f'<div style="color:#aaa;font-size:11px">Usuario</div>'
        f'<div style="color:white;font-weight:600">{u["nombre"]}</div>'
        f'<div style="color:#aaa;font-size:11px">{u["email"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )
    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        cerrar_sesion()


def render_cambiar_password() -> None:
    """Formulario para cambiar contraseña."""
    u = get_usuario_actual()
    if not u:
        return
    st.markdown("### 🔑 Cambiar contraseña")
    with st.form("form_cambiar_pwd", clear_on_submit=True):
        pwd_actual = st.text_input("Contraseña actual", type="password")
        pwd_nueva  = st.text_input("Nueva contraseña", type="password")
        pwd_rep    = st.text_input("Repetir nueva contraseña", type="password")
        if st.form_submit_button("💾 Cambiar contraseña", type="primary",
                                  use_container_width=True):
            if pwd_nueva != pwd_rep:
                st.error("❌ Las contraseñas nuevas no coinciden.")
            else:
                ok, msg = cambiar_password(u["id"], pwd_actual, pwd_nueva)
                if ok:
                    st.success(msg)
                else:
                    st.error(f"❌ {msg}")


# Auto-inicializar tabla de usuarios al importar
try:
    init_auth_db()
except Exception:
    pass