"""
cartera_db.py — Gestión multi-cartera con soporte dual SQLite / PostgreSQL (Supabase).
- Local (desarrollo): usa SQLite en data/cartera.db
- Nube (Streamlit Cloud): usa PostgreSQL via Supabase
  Requiere variable de entorno DATABASE_URL o secrets.toml de Streamlit.

Instalación para Supabase:
    pip install psycopg2-binary
"""
import os
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# ═══════════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE ENTORNO Y CONEXIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def _get_database_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        import streamlit as st
        url = st.secrets.get("database", {}).get("url")
        if url:
            return url
    except Exception:
        pass
    return None

DATABASE_URL = _get_database_url()
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
        # Verificar conexión al importar
        _test_con = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        _test_con.close()
        print("✅ Usando PostgreSQL (Supabase)")
    except ImportError:
        print("⚠️ psycopg2 no instalado — usando SQLite local")
        USE_POSTGRES = False
    except Exception as _e:
        print(f"⚠️ No se pudo conectar a PostgreSQL ({_e}) — usando SQLite local")
        USE_POSTGRES = False

_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "cartera.db"
)

# ═══════════════════════════════════════════════════════════════════════════════
# CAPA DE ABSTRACCIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def _get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        os.makedirs(os.path.dirname(_SQLITE_PATH), exist_ok=True)
        return sqlite3.connect(_SQLITE_PATH)

def _read_sql(query: str, params: list = None) -> pd.DataFrame:
    if USE_POSTGRES:
        query = query.replace("?", "%s")
    con = _get_connection()
    try:
        if params:
            return pd.read_sql(query, con, params=params)
        return pd.read_sql(query, con)
    finally:
        con.close()

def _execute(query: str, params: tuple = None) -> None:
    if USE_POSTGRES:
        query = query.replace("?", "%s")
    con = _get_connection()
    try:
        cur = con.cursor()
        cur.execute(query, params) if params else cur.execute(query)
        con.commit()
    finally:
        con.close()

def _execute_returning(query: str, params: tuple = None) -> int:
    if USE_POSTGRES:
        query = query.replace("?", "%s")
        if "RETURNING id" not in query.upper():
            query = query.rstrip(";") + " RETURNING id"
    con = _get_connection()
    try:
        cur = con.cursor()
        cur.execute(query, params) if params else cur.execute(query)
        new_id = cur.fetchone()[0] if USE_POSTGRES else cur.lastrowid
        con.commit()
        return new_id
    finally:
        con.close()

# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN DE TABLAS
# ═══════════════════════════════════════════════════════════════════════════════

def init_db() -> None:
    con = _get_connection()
    cur = con.cursor()
    pk  = "SERIAL" if USE_POSTGRES else "INTEGER"
    ai  = "" if USE_POSTGRES else "AUTOINCREMENT"

    tablas = [
        f"""CREATE TABLE IF NOT EXISTS carteras (
            id          {pk} PRIMARY KEY {ai},
            nombre      TEXT    NOT NULL UNIQUE,
            descripcion TEXT,
            moneda_base TEXT    NOT NULL DEFAULT 'USD',
            creada      TEXT    NOT NULL,
            activa      INTEGER NOT NULL DEFAULT 1
        )""",
        
        f"""CREATE TABLE IF NOT EXISTS movimientos (
            id         {pk} PRIMARY KEY {ai},
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
        f"""CREATE TABLE IF NOT EXISTS ganancias_realizadas (
            id                 {pk} PRIMARY KEY {ai},
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
        f"""CREATE TABLE IF NOT EXISTS alertas (
            id         {pk} PRIMARY KEY {ai},
            cartera_id INTEGER NOT NULL,
            ticker     TEXT    NOT NULL,
            tipo       TEXT    NOT NULL,
            valor      REAL    NOT NULL,
            activa     INTEGER NOT NULL DEFAULT 1,
            creada     TEXT    NOT NULL
        )""",
    ]
    for sql in tablas:
        cur.execute(sql)
    con.commit()
    con.close()

# ═══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE CARTERAS
# ═══════════════════════════════════════════════════════════════════════════════

def crear_cartera(nombre: str, descripcion: str = "",
                  moneda_base: str = "USD") -> int:
    try:
        return _execute_returning(
            "INSERT INTO carteras (nombre, descripcion, moneda_base, creada) "
            "VALUES (?, ?, ?, ?)",
            (nombre.strip(), descripcion.strip(), moneda_base.upper(),
             datetime.now().strftime("%Y-%m-%d"))
        )
    except Exception:
        df = _read_sql("SELECT id FROM carteras WHERE nombre=?", [nombre.strip()])
        return int(df.iloc[0]["id"]) if not df.empty else -1

def listar_carteras() -> pd.DataFrame:
    return _read_sql("SELECT * FROM carteras WHERE activa=1 ORDER BY nombre")

def eliminar_cartera(cartera_id: int) -> None:
    _execute("UPDATE carteras SET activa=0 WHERE id=?", (cartera_id,))

def renombrar_cartera(cartera_id: int, nuevo_nombre: str,
                      nueva_desc: str = None) -> None:
    if nueva_desc is not None:
        _execute("UPDATE carteras SET nombre=?, descripcion=? WHERE id=?",
                 (nuevo_nombre.strip(), nueva_desc.strip(), cartera_id))
    else:
        _execute("UPDATE carteras SET nombre=? WHERE id=?",
                 (nuevo_nombre.strip(), cartera_id))

def get_cartera_id(nombre: str) -> int | None:
    df = _read_sql("SELECT id FROM carteras WHERE nombre=? AND activa=1", [nombre])
    return int(df.iloc[0]["id"]) if not df.empty else None

# ═══════════════════════════════════════════════════════════════════════════════
# POSICIONES ACTUALES
# ═══════════════════════════════════════════════════════════════════════════════

def agregar_posicion(cartera_id: int, ticker: str, cantidad: float,
                     precio_promedio: float, moneda: str = "USD",
                     fecha_referencia: str = None, notas: str = "",
                     es_cedear: bool = False) -> None:
    """
    es_cedear=True: el ticker es un CEDEAR argentino.
    En ese caso el precio_promedio está en ARS y el precio actual
    se obtiene del ticker .BA (cotización en BYMA en ARS).
    """
    if fecha_referencia is None:
        fecha_referencia = date.today().strftime("%Y-%m-%d")
    # Si es CEDEAR, forzar moneda ARS
    if es_cedear:
        moneda = "ARS"
    if USE_POSTGRES:
        _execute("""
            INSERT INTO posiciones
                (cartera_id, ticker, cantidad, precio_promedio, moneda,
                 fecha_referencia, notas, es_cedear)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cartera_id, ticker) DO UPDATE SET
                cantidad=EXCLUDED.cantidad, precio_promedio=EXCLUDED.precio_promedio,
                moneda=EXCLUDED.moneda, fecha_referencia=EXCLUDED.fecha_referencia,
                notas=EXCLUDED.notas, es_cedear=EXCLUDED.es_cedear
        """, (cartera_id, ticker.upper(), cantidad, precio_promedio,
              moneda.upper(), fecha_referencia, notas, int(es_cedear)))
    else:
        _execute("""
            INSERT INTO posiciones
                (cartera_id, ticker, cantidad, precio_promedio, moneda,
                 fecha_referencia, notas, es_cedear)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cartera_id, ticker) DO UPDATE SET
                cantidad=excluded.cantidad, precio_promedio=excluded.precio_promedio,
                moneda=excluded.moneda, fecha_referencia=excluded.fecha_referencia,
                notas=excluded.notas, es_cedear=excluded.es_cedear
        """, (cartera_id, ticker.upper(), cantidad, precio_promedio,
              moneda.upper(), fecha_referencia, notas, int(es_cedear)))

def eliminar_posicion(cartera_id: int, ticker: str) -> None:
    _execute("DELETE FROM posiciones WHERE cartera_id=? AND ticker=?",
             (cartera_id, ticker.upper()))

def listar_posiciones(cartera_id: int) -> pd.DataFrame:
    return _read_sql(
        "SELECT * FROM posiciones WHERE cartera_id=? ORDER BY ticker",
        [cartera_id]
    )

def importar_posiciones_csv(cartera_id: int,
                             df_csv: pd.DataFrame) -> tuple[int, list[str]]:
    importadas, errores = 0, []
    df_csv.columns = [c.lower().strip().replace(" ", "_") for c in df_csv.columns]
    alias = {
        "symbol":"ticker","accion":"ticker","activo":"ticker",
        "precio":"precio_promedio","precio_compra":"precio_promedio",
        "precio_prom":"precio_promedio","ppc":"precio_promedio",
        "cant":"cantidad","qty":"cantidad",
        "currency":"moneda","divisa":"moneda",
        "fecha":"fecha_referencia","date":"fecha_referencia",
        "nota":"notas","comentario":"notas",
    }
    df_csv = df_csv.rename(columns=alias)
    faltantes = {"ticker","cantidad","precio_promedio"} - set(df_csv.columns)
    if faltantes:
        return 0, [f"Columnas faltantes: {', '.join(faltantes)}"]
    for _, row in df_csv.iterrows():
        try:
            ticker   = str(row["ticker"]).strip().upper()
            cantidad = float(str(row["cantidad"]).replace(",","."))
            precio   = float(str(row["precio_promedio"]).replace(",",".").replace("$",""))
            moneda   = str(row.get("moneda","USD")).strip().upper() or "USD"
            fecha    = str(row.get("fecha_referencia", date.today().strftime("%Y-%m-%d"))).strip()
            notas    = str(row.get("notas","")).strip()
            if not ticker or cantidad <= 0 or precio <= 0:
                errores.append(f"Fila inválida: ticker={ticker}"); continue
            agregar_posicion(cartera_id, ticker, cantidad, precio, moneda, fecha, notas)
            importadas += 1
        except Exception as e:
            errores.append(f"Error en {row.get('ticker','?')}: {e}")
    return importadas, errores

# ═══════════════════════════════════════════════════════════════════════════════
# MOVIMIENTOS
# ═══════════════════════════════════════════════════════════════════════════════

def registrar_movimiento(cartera_id: int, tipo: str, ticker: str,
                         cantidad: float, precio: float,
                         moneda: str = "USD", fecha: str = None,
                         comision: float = 0, notas: str = "") -> None:
    if fecha is None:
        fecha = date.today().strftime("%Y-%m-%d")
    tipo = tipo.upper()
    _execute("""
        INSERT INTO movimientos
            (cartera_id, fecha, tipo, ticker, cantidad, precio, moneda, comision, notas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cartera_id, fecha, tipo, ticker.upper(), cantidad, precio,
          moneda.upper(), comision, notas))

    df_pos = _read_sql(
        "SELECT cantidad, precio_promedio FROM posiciones WHERE cartera_id=? AND ticker=?",
        [cartera_id, ticker.upper()]
    )
    pos = None if df_pos.empty else df_pos.iloc[0]

    if tipo == "COMPRA":
        if pos is not None:
            cant_actual  = float(pos["cantidad"])
            precio_act   = float(pos["precio_promedio"])
            nueva_cant   = cant_actual + cantidad
            nuevo_precio = ((cant_actual * precio_act) + (cantidad * precio)) / nueva_cant
            _execute("UPDATE posiciones SET cantidad=?, precio_promedio=? WHERE cartera_id=? AND ticker=?",
                     (nueva_cant, nuevo_precio, cartera_id, ticker.upper()))
        else:
            _execute("INSERT INTO posiciones (cartera_id, ticker, cantidad, precio_promedio, moneda, fecha_referencia) VALUES (?, ?, ?, ?, ?, ?)",
                     (cartera_id, ticker.upper(), cantidad, precio, moneda.upper(), fecha))

    elif tipo == "VENTA" and pos is not None:
        cant_actual   = float(pos["cantidad"])
        precio_compra = float(pos["precio_promedio"])
        nueva_cant    = cant_actual - cantidad
        ganancia_usd  = (precio - precio_compra) * cantidad - comision
        ganancia_pct  = ((precio - precio_compra) / precio_compra * 100 if precio_compra > 0 else 0)
        _execute("""
            INSERT INTO ganancias_realizadas
                (cartera_id, ticker, fecha_venta, cantidad_vendida,
                 precio_compra_prom, precio_venta, moneda, ganancia_usd, ganancia_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cartera_id, ticker.upper(), fecha, cantidad,
              precio_compra, precio, moneda.upper(), ganancia_usd, ganancia_pct))
        if nueva_cant > 0.0001:
            _execute("UPDATE posiciones SET cantidad=? WHERE cartera_id=? AND ticker=?",
                     (nueva_cant, cartera_id, ticker.upper()))
        else:
            _execute("DELETE FROM posiciones WHERE cartera_id=? AND ticker=?",
                     (cartera_id, ticker.upper()))

def listar_movimientos(cartera_id: int, ticker: str = None) -> pd.DataFrame:
    if ticker:
        return _read_sql(
            "SELECT * FROM movimientos WHERE cartera_id=? AND ticker=? ORDER BY fecha DESC",
            [cartera_id, ticker.upper()]
        )
    return _read_sql(
        "SELECT * FROM movimientos WHERE cartera_id=? ORDER BY fecha DESC",
        [cartera_id]
    )

def listar_ganancias_realizadas(cartera_id: int) -> pd.DataFrame:
    return _read_sql(
        "SELECT * FROM ganancias_realizadas WHERE cartera_id=? ORDER BY fecha_venta DESC",
        [cartera_id]
    )

# ═══════════════════════════════════════════════════════════════════════════════
# P&L EN TIEMPO REAL
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_pnl(cartera_id: int, ccl: float = 1200.0) -> pd.DataFrame:
    """
    Calcula P&L en tiempo real.
    Para CEDEARs (es_cedear=1):
      - precio_promedio está en ARS (lo que pagaste en BYMA)
      - precio actual se obtiene del ticker .BA (cotización ARS en BYMA)
      - la comparación es ARS vs ARS → P&L correcto sin distorsión
    Para acciones internacionales (es_cedear=0):
      - precio_promedio en USD
      - precio actual en USD desde NYSE/NASDAQ
    """
    df_pos = listar_posiciones(cartera_id)
    if df_pos.empty:
        return pd.DataFrame()

    # Descargar precios según tipo de activo
    precios_usd = {}  # ticker → precio en USD (acciones internacionales)
    precios_ars = {}  # ticker → precio en ARS (CEDEARs vía .BA)

    for _, pos in df_pos.iterrows():
        t         = pos["ticker"]
        es_cedear = int(pos.get("es_cedear", 0)) == 1
        try:
            if es_cedear:
                # Buscar precio ARS del CEDEAR en BYMA
                ticker_ba = t.upper() + ".BA" if not t.upper().endswith(".BA") else t.upper()
                info_ba   = yf.Ticker(ticker_ba).info
                p_ars     = info_ba.get("currentPrice") or info_ba.get("regularMarketPrice")
                if p_ars:
                    p_ars_float = float(p_ars)
                    # Rango razonable para CEDEARs en ARS: $10 a $500.000
                    # Yahoo Finance a veces devuelve el precio con punto como
                    # separador de miles (ej: 2790.0 = $2.790 ARS) — correcto.
                    # Si viene como 2790000 es un error de escala.
                    if 10 <= p_ars_float <= 500_000:
                        precios_ars[t] = p_ars_float
                    elif p_ars_float > 500_000:
                        # Intentar corregir dividiendo por 1000
                        p_corregido = p_ars_float / 1000
                        if 10 <= p_corregido <= 500_000:
                            precios_ars[t] = p_corregido
                        else:
                            precios_ars[t] = p_ars_float / 1_000_000
            else:
                info  = yf.Ticker(t).info
                p_usd = info.get("currentPrice") or info.get("regularMarketPrice")
                if p_usd:
                    precios_usd[t] = float(p_usd)
        except Exception:
            pass

    rows = []
    for _, pos in df_pos.iterrows():
        t             = pos["ticker"]
        cantidad      = float(pos["cantidad"])
        precio_compra = float(pos["precio_promedio"])
        moneda        = pos["moneda"]
        es_cedear     = int(pos.get("es_cedear", 0)) == 1

        if es_cedear:
            # ── CEDEAR: todo en ARS ──────────────────────────────────────────
            precio_actual_ars = precios_ars.get(t)
            costo_ars         = precio_compra * cantidad
            valor_ars         = (precio_actual_ars * cantidad) if precio_actual_ars else None
            gan_ars           = (valor_ars - costo_ars) if valor_ars else None
            gan_pct           = (gan_ars / costo_ars * 100) if gan_ars and costo_ars else None
            # Convertir a USD para comparación entre carteras
            costo_usd  = costo_ars / ccl if ccl > 0 else None
            valor_usd  = valor_ars / ccl if valor_ars and ccl > 0 else None
            gan_usd    = gan_ars / ccl if gan_ars and ccl > 0 else None
            precio_usd_display = precio_actual_ars / ccl if precio_actual_ars and ccl > 0 else None

            rows.append({
                "Ticker":              t,
                "Tipo":                "CEDEAR 🇦🇷",
                "Cantidad":            cantidad,
                "Precio promedio":     round(precio_compra, 2),
                "Moneda orig.":        "ARS",
                "Precio actual (ARS)": round(precio_actual_ars, 2) if precio_actual_ars else None,
                "Precio actual (USD)": round(precio_usd_display, 2) if precio_usd_display else None,
                "Costo total (USD)":   round(costo_usd, 2) if costo_usd else None,
                "Valor actual (USD)":  round(valor_usd, 2) if valor_usd else None,
                "Ganancia (USD)":      round(gan_usd, 2) if gan_usd else None,
                "Ganancia (%)":        round(gan_pct, 2) if gan_pct else None,
                "Ganancia (ARS)":      round(gan_ars, 0) if gan_ars else None,
                "Notas":               pos.get("notas", ""),
            })
        else:
            # ── Acción internacional: todo en USD ────────────────────────────
            precio_actual_usd = precios_usd.get(t)
            precio_compra_usd = precio_compra / ccl if moneda == "ARS" and ccl > 0 else precio_compra
            costo_total       = precio_compra_usd * cantidad
            valor_actual      = (precio_actual_usd * cantidad) if precio_actual_usd else None
            gan_usd           = (valor_actual - costo_total) if valor_actual else None
            gan_pct           = (gan_usd / costo_total * 100) if gan_usd and costo_total else None
            gan_ars           = (gan_usd * ccl) if gan_usd else None

            rows.append({
                "Ticker":              t,
                "Tipo":                "Internacional 🌎",
                "Cantidad":            cantidad,
                "Precio promedio":     round(precio_compra_usd, 2),
                "Moneda orig.":        moneda,
                "Precio actual (ARS)": None,
                "Precio actual (USD)": round(precio_actual_usd, 2) if precio_actual_usd else None,
                "Costo total (USD)":   round(costo_total, 2),
                "Valor actual (USD)":  round(valor_actual, 2) if valor_actual else None,
                "Ganancia (USD)":      round(gan_usd, 2) if gan_usd else None,
                "Ganancia (%)":        round(gan_pct, 2) if gan_pct else None,
                "Ganancia (ARS)":      round(gan_ars, 0) if gan_ars else None,
                "Notas":               pos.get("notas", ""),
            })

    return pd.DataFrame(rows)

def resumen_cartera(df_pnl: pd.DataFrame) -> dict:
    if df_pnl.empty: return {}
    costo   = df_pnl["Costo total (USD)"].sum()
    valor   = df_pnl["Valor actual (USD)"].dropna().sum()
    gan_usd = df_pnl["Ganancia (USD)"].dropna().sum()
    gan_pct = (gan_usd / costo * 100) if costo > 0 else 0
    return {
        "Costo total (USD)":    round(costo, 2),
        "Valor actual (USD)":   round(valor, 2),
        "Ganancia total (USD)": round(gan_usd, 2),
        "Ganancia total (%)":   round(gan_pct, 2),
        "Posiciones":           len(df_pnl),
        "Tickers únicos":       df_pnl["Ticker"].nunique(),
    }

def pesos_cartera(df_pnl: pd.DataFrame) -> pd.DataFrame:
    if df_pnl.empty: return pd.DataFrame()
    grp   = df_pnl.groupby("Ticker")["Valor actual (USD)"].sum().dropna()
    total = grp.sum()
    if total == 0: return pd.DataFrame()
    pesos = (grp / total * 100).round(2).reset_index()
    pesos.columns = ["Ticker", "Peso (%)"]
    return pesos

def ganancias_realizadas_resumen(cartera_id: int) -> dict:
    df = listar_ganancias_realizadas(cartera_id)
    if df.empty:
        return {"total_usd": 0, "operaciones": 0, "ganadoras": 0, "perdedoras": 0}
    return {
        "total_usd":   round(df["ganancia_usd"].sum(), 2),
        "operaciones": len(df),
        "ganadoras":   int((df["ganancia_usd"] > 0).sum()),
        "perdedoras":  int((df["ganancia_usd"] < 0).sum()),
        "mejor_op":    df.loc[df["ganancia_usd"].idxmax(), "ticker"],
        "peor_op":     df.loc[df["ganancia_usd"].idxmin(), "ticker"],
    }

def señal_rotacion(ticker: str, peso_actual: float,
                   peso_optimo: float, rsi: float = None) -> str:
    diff = peso_optimo - peso_actual
    if diff > 0.05:    señal_mk = "SUMAR"
    elif diff < -0.05: señal_mk = "REDUCIR"
    else:              señal_mk = "MANTENER"
    if rsi is not None:
        if rsi < 30 and señal_mk == "SUMAR":   return "🟢 SUMAR — sobreventa confirmada"
        elif rsi > 70 and señal_mk == "REDUCIR": return "🔴 REDUCIR — sobrecompra confirmada"
        elif rsi < 30: return "🟡 MONITOREAR — sobreventa pero no subponderado"
        elif rsi > 70: return "🟠 MONITOREAR — sobrecompra pero no sobreponderado"
    if señal_mk == "SUMAR":   return "🟢 SUMAR"
    if señal_mk == "REDUCIR": return "🔴 REDUCIR"
    return "🟡 MANTENER"

# ═══════════════════════════════════════════════════════════════════════════════
# ALERTAS
# ═══════════════════════════════════════════════════════════════════════════════

def agregar_alerta(cartera_id: int, ticker: str, tipo: str, valor: float) -> None:
    _execute("INSERT INTO alertas (cartera_id, ticker, tipo, valor, activa, creada) VALUES (?, ?, ?, ?, 1, ?)",
             (cartera_id, ticker.upper(), tipo, valor, datetime.now().isoformat()))

def listar_alertas(cartera_id: int) -> pd.DataFrame:
    return _read_sql("SELECT * FROM alertas WHERE cartera_id=? AND activa=1 ORDER BY ticker",
                     [cartera_id])

def desactivar_alerta(alerta_id: int) -> None:
    _execute("UPDATE alertas SET activa=0 WHERE id=?", (alerta_id,))

def generar_template_csv() -> str:
    return (
        "ticker,cantidad,precio_promedio,moneda,fecha_referencia,notas\n"
        "AAPL,50,185.00,USD,2024-01-01,Posición largo plazo\n"
        "MELI,10,1450.00,USD,2024-01-01,\n"
        "YPFD,200,15000.00,ARS,2024-01-01,CEDEAR\n"
    )

# Auto-inicializar DB al importar
init_db()