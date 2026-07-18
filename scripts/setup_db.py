"""
setup_db.py — Crea todas las tablas necesarias en Supabase.
Ejecutar UNA SOLA VEZ desde la carpeta scripts/:
    python setup_db.py
"""
import psycopg2

DATABASE_URL = "postgresql://postgres.vcrnckjhuohtqeqaopmo:Wc4001Bc3086@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

STATEMENTS = [
    # Tabla usuarios
    """CREATE TABLE IF NOT EXISTS usuarios (
        id            SERIAL PRIMARY KEY,
        email         TEXT    NOT NULL UNIQUE,
        nombre        TEXT    NOT NULL,
        password_hash TEXT    NOT NULL,
        salt          TEXT    NOT NULL,
        creado        TEXT    NOT NULL,
        activo        INTEGER NOT NULL DEFAULT 1,
        es_admin      INTEGER NOT NULL DEFAULT 0
    )""",

    # Columna usuario_id en carteras
    "ALTER TABLE carteras ADD COLUMN IF NOT EXISTS usuario_id INTEGER DEFAULT NULL",

    # Tabla renta_fija
    """CREATE TABLE IF NOT EXISTS renta_fija (
        id                SERIAL PRIMARY KEY,
        cartera_id        INTEGER NOT NULL,
        ticker            TEXT    NOT NULL,
        tipo              TEXT    NOT NULL DEFAULT 'BONO',
        nombre            TEXT,
        valor_nominal     REAL    NOT NULL,
        precio_compra_pct REAL    NOT NULL,
        moneda            TEXT    NOT NULL DEFAULT 'USD',
        fecha_compra      TEXT    NOT NULL,
        fecha_vencimiento TEXT,
        tir_compra        REAL,
        notas             TEXT,
        UNIQUE(cartera_id, ticker)
    )""",

    # Tabla fci
    """CREATE TABLE IF NOT EXISTS fci (
        id               SERIAL PRIMARY KEY,
        cartera_id       INTEGER NOT NULL,
        nombre_fondo     TEXT    NOT NULL,
        gerenciadora     TEXT,
        cuotapartes      REAL    NOT NULL,
        valor_cuotaparte REAL    NOT NULL,
        moneda           TEXT    NOT NULL DEFAULT 'ARS',
        fecha_compra     TEXT    NOT NULL,
        tipo_fondo       TEXT    DEFAULT 'Money Market',
        notas            TEXT,
        UNIQUE(cartera_id, nombre_fondo)
    )""",

    # Tabla movimientos (si no existe)
    """CREATE TABLE IF NOT EXISTS movimientos (
        id         SERIAL PRIMARY KEY,
        cartera_id INTEGER NOT NULL,
        fecha      TEXT    NOT NULL,
        tipo       TEXT    NOT NULL,
        ticker     TEXT    NOT NULL,
        cantidad   REAL    NOT NULL,
        precio     REAL    NOT NULL,
        moneda     TEXT    NOT NULL DEFAULT 'USD',
        comision   REAL    DEFAULT 0,
        notas      TEXT
    )""",

    # Tabla ganancias_realizadas (si no existe)
    """CREATE TABLE IF NOT EXISTS ganancias_realizadas (
        id                 SERIAL PRIMARY KEY,
        cartera_id         INTEGER NOT NULL,
        ticker             TEXT    NOT NULL,
        fecha_venta        TEXT    NOT NULL,
        cantidad_vendida   REAL    NOT NULL,
        precio_compra_prom REAL    NOT NULL,
        precio_venta       REAL    NOT NULL,
        moneda             TEXT    NOT NULL DEFAULT 'USD',
        ganancia_usd       REAL,
        ganancia_pct       REAL
    )""",

    # Tabla alertas (si no existe)
    """CREATE TABLE IF NOT EXISTS alertas (
        id         SERIAL PRIMARY KEY,
        cartera_id INTEGER NOT NULL,
        ticker     TEXT    NOT NULL,
        tipo       TEXT    NOT NULL,
        valor      REAL    NOT NULL,
        activa     INTEGER NOT NULL DEFAULT 1,
        creada     TEXT    NOT NULL
    )""",

    # Columna es_cedear en posiciones (si no existe)
    "ALTER TABLE posiciones ADD COLUMN IF NOT EXISTS es_cedear INTEGER NOT NULL DEFAULT 0",
]

def main():
    print("Conectando a Supabase...")
    try:
        con = psycopg2.connect(DATABASE_URL, connect_timeout=15)
        cur = con.cursor()
        print("✅ Conexión exitosa\n")

        for i, stmt in enumerate(STATEMENTS, 1):
            nombre = stmt.strip().split('\n')[0][:60]
            try:
                cur.execute(stmt)
                con.commit()
                print(f"✅ [{i}/{len(STATEMENTS)}] {nombre}")
            except Exception as e:
                con.rollback()
                err = str(e).strip()
                if "already exists" in err or "duplicate" in err.lower():
                    print(f"⚠️  [{i}/{len(STATEMENTS)}] Ya existe: {nombre[:40]}")
                else:
                    print(f"❌ [{i}/{len(STATEMENTS)}] Error: {err[:80]}")

        con.close()
        print("\n✅ Setup completado. Todas las tablas están listas.")
        print("\nPróximo paso: ejecutar la app y crear tu cuenta de usuario.")

    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("\nVerificá que tenés psycopg2 instalado:")
        print("  pip install psycopg2-binary")

if __name__ == "__main__":
    main()