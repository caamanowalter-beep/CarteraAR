"""
verificar_supabase.py — Verificación completa del estado de Supabase.
Ejecutar desde scripts/:
    python verificar_supabase.py

Verifica:
  1. Conexión a Supabase
  2. Todas las tablas existen con las columnas correctas
  3. Integridad de datos (carteras → usuarios, posiciones → carteras)
  4. Estadísticas generales
  5. Sugiere correcciones si hay problemas
"""
import psycopg2
from datetime import datetime

DATABASE_URL = "postgresql://postgres.vcrnckjhuohtqeqaopmo:Wc4001Bc3086@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

# Tablas requeridas con sus columnas clave
TABLAS_REQUERIDAS = {
    "usuarios":            ["id", "email", "nombre", "password_hash", "salt", "activo"],
    "carteras":            ["id", "nombre", "moneda_base", "activa", "usuario_id"],
    "posiciones":          ["id", "cartera_id", "ticker", "cantidad", "precio_promedio", "es_cedear"],
    "movimientos":         ["id", "cartera_id", "fecha", "tipo", "ticker", "cantidad", "precio"],
    "ganancias_realizadas":["id", "cartera_id", "ticker", "fecha_venta", "ganancia_usd"],
    "alertas":             ["id", "cartera_id", "ticker", "tipo", "valor", "activa"],
    "renta_fija":          ["id", "cartera_id", "ticker", "tipo", "valor_nominal", "precio_compra_pct"],
    "fci":                 ["id", "cartera_id", "nombre_fondo", "cuotapartes", "valor_cuotaparte"],
}

def verificar():
    print("=" * 60)
    print("  VERIFICACIÓN DE SUPABASE — Cartera AR")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    # ── Conexión ──────────────────────────────────────────────────────────────
    print("\n📡 Verificando conexión...")
    try:
        con = psycopg2.connect(DATABASE_URL, connect_timeout=15)
        cur = con.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0][:50]
        print(f"  ✅ Conexión exitosa — {version}")
    except Exception as e:
        print(f"  ❌ Error de conexión: {e}")
        return

    # ── Tablas ────────────────────────────────────────────────────────────────
    print("\n📋 Verificando tablas...")
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    tablas_existentes = {row[0] for row in cur.fetchall()}

    tablas_ok = True
    for tabla, cols_requeridas in TABLAS_REQUERIDAS.items():
        if tabla not in tablas_existentes:
            print(f"  ❌ FALTA tabla: {tabla}")
            tablas_ok = False
            continue

        # Verificar columnas
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='{tabla}'
        """)
        cols_existentes = {row[0] for row in cur.fetchall()}
        cols_faltantes = set(cols_requeridas) - cols_existentes

        if cols_faltantes:
            print(f"  ⚠️  {tabla}: faltan columnas {cols_faltantes}")
        else:
            cur.execute(f"SELECT COUNT(*) FROM {tabla}")
            count = cur.fetchone()[0]
            print(f"  ✅ {tabla} ({count} registros)")

    # ── Estadísticas ──────────────────────────────────────────────────────────
    print("\n📊 Estadísticas generales...")
    try:
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1")
        n_usuarios = cur.fetchone()[0]
        print(f"  👥 Usuarios activos: {n_usuarios}")

        cur.execute("SELECT COUNT(*) FROM carteras WHERE activa=1")
        n_carteras = cur.fetchone()[0]
        print(f"  💼 Carteras activas: {n_carteras}")

        cur.execute("SELECT COUNT(*) FROM posiciones")
        n_pos = cur.fetchone()[0]
        print(f"  📈 Posiciones (acciones/CEDEARs): {n_pos}")

        cur.execute("SELECT COUNT(*) FROM renta_fija")
        n_rf = cur.fetchone()[0]
        print(f"  🏦 Instrumentos renta fija: {n_rf}")

        cur.execute("SELECT COUNT(*) FROM fci")
        n_fci = cur.fetchone()[0]
        print(f"  📈 FCIs: {n_fci}")

        cur.execute("SELECT COUNT(*) FROM movimientos")
        n_mov = cur.fetchone()[0]
        print(f"  📝 Movimientos registrados: {n_mov}")

        cur.execute("SELECT COUNT(*) FROM alertas WHERE activa=1")
        n_alert = cur.fetchone()[0]
        print(f"  🔔 Alertas activas: {n_alert}")
    except Exception as e:
        print(f"  ⚠️ Error en estadísticas: {e}")

    # ── Integridad de datos ───────────────────────────────────────────────────
    print("\n🔍 Verificando integridad de datos...")
    try:
        # Carteras sin usuario
        cur.execute("SELECT COUNT(*) FROM carteras WHERE usuario_id IS NULL AND activa=1")
        sin_usuario = cur.fetchone()[0]
        if sin_usuario > 0:
            print(f"  ⚠️  {sin_usuario} cartera(s) sin usuario asignado")
            cur.execute("SELECT id, nombre FROM carteras WHERE usuario_id IS NULL AND activa=1")
            for c in cur.fetchall():
                print(f"     → ID={c[0]} | {c[1]}")
            print(f"     Ejecutar: UPDATE carteras SET usuario_id=1 WHERE usuario_id IS NULL;")
        else:
            print(f"  ✅ Todas las carteras tienen usuario asignado")

        # Posiciones sin cartera válida
        cur.execute("""
            SELECT COUNT(*) FROM posiciones p
            WHERE NOT EXISTS (SELECT 1 FROM carteras c WHERE c.id=p.cartera_id AND c.activa=1)
        """)
        pos_huerfanas = cur.fetchone()[0]
        if pos_huerfanas > 0:
            print(f"  ⚠️  {pos_huerfanas} posición(es) sin cartera válida")
        else:
            print(f"  ✅ Todas las posiciones tienen cartera válida")

        # Usuarios por cartera
        print("\n  📋 Detalle por usuario:")
        cur.execute("""
            SELECT u.nombre, u.email, COUNT(c.id) as n_carteras
            FROM usuarios u
            LEFT JOIN carteras c ON c.usuario_id=u.id AND c.activa=1
            WHERE u.activo=1
            GROUP BY u.id, u.nombre, u.email
            ORDER BY u.id
        """)
        for row in cur.fetchall():
            print(f"     {row[0]} ({row[1]}): {row[2]} cartera(s)")

    except Exception as e:
        print(f"  ⚠️ Error en integridad: {e}")

    # ── RLS (Row Level Security) ───────────────────────────────────────────────
    print("\n🔒 Verificando Row Level Security...")
    try:
        cur.execute("""
            SELECT tablename, rowsecurity FROM pg_tables
            WHERE schemaname='public'
            ORDER BY tablename
        """)
        for row in cur.fetchall():
            estado = "✅ RLS activo" if row[1] else "⚠️  Sin RLS"
            print(f"  {estado}: {row[0]}")
    except Exception as e:
        print(f"  ⚠️ No se pudo verificar RLS: {e}")

    con.close()
    print("\n" + "=" * 60)
    print("  ✅ Verificación completada")
    print("=" * 60)

if __name__ == "__main__":
    verificar()