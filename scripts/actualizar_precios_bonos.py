"""
actualizar_precios_bonos.py
Script local para obtener precios de bonos argentinos y subirlos a Supabase.
Ejecutar desde tu PC: python actualizar_precios_bonos.py

Fuentes (en orden de prioridad):
1. Yahoo Finance (.BA) — bonos que cotizan en BYMA
2. Rava / Comparatasas / Bonistas (scraping desde tu PC)
3. Entrada manual como fallback
"""

import psycopg2
import requests
import yfinance as yf
from datetime import date, datetime
import json
import re

# ── Configuración ─────────────────────────────────────────────────────────────
DATABASE_URL = "postgresql://postgres.vcrnckjhuohtqeqaopmo:Wc4001Bc3086@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0',
    'Accept': 'application/json, text/html',
}

# Bonos con sus tickers .BA y moneda
BONOS = {
    # Soberanos USD
    "AL29":  {"ba": "AL29.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley Arg 2029"},
    "AL30":  {"ba": "AL30.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley Arg 2030"},
    "AL35":  {"ba": "AL35.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley Arg 2035"},
    "AL41":  {"ba": "AL41.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley Arg 2041"},
    "GD29":  {"ba": "GD29.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley NY 2029"},
    "GD30":  {"ba": "GD30.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley NY 2030"},
    "GD35":  {"ba": "GD35.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley NY 2035"},
    "GD41":  {"ba": "GD41.BA",  "moneda": "USD", "tipo": "Soberano", "nombre": "Bono Soberano USD Ley NY 2041"},
    "AE38":  {"ba": "AE38.BA",  "moneda": "ARS", "tipo": "Soberano CER", "nombre": "Bono CER 2038"},
    # Bonos CER / Pesos
    "TX26":  {"ba": "TX26.BA",  "moneda": "ARS", "tipo": "CER", "nombre": "Bono CER 2026"},
    "TX28":  {"ba": "TX28.BA",  "moneda": "ARS", "tipo": "CER", "nombre": "Bono CER 2028"},
    "DICP":  {"ba": "DICP.BA",  "moneda": "ARS", "tipo": "CER", "nombre": "Discount Pesos CER"},
    "TZX28": {"ba": "TZX28.BA", "moneda": "ARS", "tipo": "CER", "nombre": "Bono CER 2028"},
    # LECAPs
    "T15E7": {"ba": "T15E7.BA", "moneda": "ARS", "tipo": "LECAP", "nombre": "LECAP Ene 2027"},
    "TMF28": {"ba": "TMF28.BA", "moneda": "ARS", "tipo": "LECAP", "nombre": "LECAP Feb 2028"},
    # ONs corporativas
    "IRCPO": {"ba": "IRCPO.BA", "moneda": "USD", "tipo": "ON", "nombre": "ON IRSA Propiedades"},
    "YM34O": {"ba": "YM34O.BA", "moneda": "USD", "tipo": "ON", "nombre": "ON YPF 2034"},
    "DNC7O": {"ba": "DNC7O.BA", "moneda": "USD", "tipo": "ON", "nombre": "ON Corporativo"},
    "TLCPO": {"ba": "TLCPO.BA", "moneda": "USD", "tipo": "ON", "nombre": "ON Telecom"},
}

# ── Funciones de obtención de precios ─────────────────────────────────────────

def obtener_ccl() -> float:
    """Obtiene el CCL actual desde DolarApi."""
    try:
        r = requests.get("https://dolarapi.com/v1/dolares/contadoconliqui", timeout=5, headers=HEADERS)
        if r.status_code == 200:
            return float(r.json().get("venta", 1580))
    except Exception:
        pass
    try:
        r = requests.get("https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return float(data[-1].get("venta", 1580))
    except Exception:
        pass
    return 1580.0


def obtener_precio_yfinance(ticker_ba: str) -> float | None:
    """Obtiene precio en ARS desde Yahoo Finance (.BA)."""
    try:
        info = yf.Ticker(ticker_ba).info
        precio = info.get("currentPrice") or info.get("regularMarketPrice")
        if precio and float(precio) > 0:
            return float(precio)
    except Exception:
        pass
    return None


def obtener_precios_rava() -> dict:
    """
    Intenta obtener precios desde Rava (funciona mejor desde PC local).
    Retorna dict {ticker: precio_ars}
    """
    precios = {}
    try:
        # Rava tiene una API interna que se puede consultar
        urls_rava = [
            "https://www.rava.com/api/cotizaciones?tipo=bonos",
            "https://mercado.rava.com/api/cotizaciones/bonos",
        ]
        for url in urls_rava:
            try:
                r = requests.get(url, timeout=8, headers=HEADERS)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            ticker = item.get("simbolo", item.get("ticker", "")).upper()
                            precio = item.get("ultimo", item.get("price", item.get("close")))
                            if ticker and precio:
                                precios[ticker] = float(precio)
                    elif isinstance(data, dict):
                        for ticker, info in data.items():
                            if isinstance(info, dict):
                                precio = info.get("ultimo", info.get("price"))
                                if precio:
                                    precios[ticker.upper()] = float(precio)
                    if precios:
                        print(f"  ✅ Rava: {len(precios)} precios obtenidos")
                        return precios
            except Exception:
                continue
    except Exception:
        pass
    return precios


def obtener_precios_comparatasas() -> dict:
    """Intenta obtener precios desde Comparatasas."""
    precios = {}
    try:
        urls = [
            "https://comparatasas.ar/api/bonos",
            "https://api.comparatasas.ar/bonos",
            "https://comparatasas.ar/api/v1/bonos",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=8, headers=HEADERS)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            ticker = item.get("ticker", item.get("simbolo", "")).upper()
                            precio = item.get("precio", item.get("ultimo", item.get("close")))
                            if ticker and precio:
                                precios[ticker] = float(precio)
                    if precios:
                        print(f"  ✅ Comparatasas: {len(precios)} precios obtenidos")
                        return precios
            except Exception:
                continue
    except Exception:
        pass
    return precios


def obtener_precios_argentinadatos() -> dict:
    """Intenta obtener precios desde ArgentinaDatos."""
    precios = {}
    try:
        urls = [
            "https://api.argentinadatos.com/v1/cotizaciones/bonos",
            "https://api.argentinadatos.com/v2/cotizaciones/bonos",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            ticker = item.get("ticker", item.get("simbolo", "")).upper()
                            precio = item.get("precio", item.get("ultimo"))
                            if ticker and precio:
                                precios[ticker] = float(precio)
                    if precios:
                        print(f"  ✅ ArgentinaDatos: {len(precios)} precios obtenidos")
                        return precios
            except Exception:
                continue
    except Exception:
        pass
    return precios


# ── Función principal de guardado ─────────────────────────────────────────────

def guardar_precio(con, ticker: str, precio_ars: float, ccl: float,
                   moneda: str, tipo: str, nombre: str, fuente: str = "yfinance"):
    """Guarda o actualiza el precio de un bono en Supabase."""
    cur = con.cursor()
    hoy = date.today().strftime("%Y-%m-%d")

    # precio = precio en % del VN (para bonos USD: precio_ars / CCL)
    # Para bonos USD: precio en ARS / CCL = precio en USD ≈ % del VN (VN=100)
    # Para bonos ARS: precio en ARS / 100 = % del VN
    if moneda == "USD":
        precio_pct = round(precio_ars / ccl, 4)  # precio en USD ≈ % del VN
    else:
        precio_pct = round(precio_ars / 100, 4)  # precio ARS / VN(100)

    try:
        cur.execute("""
            INSERT INTO precios_bonos
                (ticker, nombre, precio, tir, moneda, tipo, fuente, actualizado, precio_ars, fecha_actualizacion)
            VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE SET
                precio = EXCLUDED.precio,
                precio_ars = EXCLUDED.precio_ars,
                fuente = EXCLUDED.fuente,
                actualizado = EXCLUDED.actualizado,
                fecha_actualizacion = EXCLUDED.fecha_actualizacion
        """, (ticker.upper(), nombre, precio_pct, moneda, tipo, fuente, hoy, precio_ars, hoy))
        con.commit()
        return True
    except Exception as e:
        con.rollback()
        print(f"  ❌ Error guardando {ticker}: {e}")
        return False


def guardar_precio_manual(con, ticker: str, precio_pct: float,
                           moneda: str, tipo: str, nombre: str):
    """Guarda precio ingresado manualmente."""
    cur = con.cursor()
    hoy = date.today().strftime("%Y-%m-%d")
    try:
        cur.execute("""
            INSERT INTO precios_bonos
                (ticker, nombre, precio, moneda, tipo, fuente, actualizado, fecha_actualizacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE SET
                precio = EXCLUDED.precio,
                fuente = EXCLUDED.fuente,
                actualizado = EXCLUDED.actualizado,
                fecha_actualizacion = EXCLUDED.fecha_actualizacion
        """, (ticker.upper(), nombre, precio_pct, moneda, tipo, "manual", hoy, hoy))
        con.commit()
        return True
    except Exception as e:
        con.rollback()
        print(f"  ❌ Error guardando {ticker}: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ACTUALIZADOR DE PRECIOS DE BONOS — Cartera AR")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    # Conectar a Supabase
    print("\n📡 Conectando a Supabase...")
    try:
        con = psycopg2.connect(DATABASE_URL)
        print("✅ Conexión exitosa")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return

    # Obtener CCL
    ccl = obtener_ccl()
    print(f"\n💱 CCL actual: ${ccl:,.2f}")

    # Intentar obtener precios de fuentes externas
    print("\n🔍 Buscando precios en fuentes externas...")
    precios_externos = {}
    precios_externos.update(obtener_precios_argentinadatos())
    precios_externos.update(obtener_precios_comparatasas())
    precios_externos.update(obtener_rava_precios := obtener_precios_rava())

    if not precios_externos:
        print("  ⚠️  No se obtuvieron precios de fuentes externas")
        print("  → Intentando Yahoo Finance (.BA)...")

    # Procesar cada bono
    print("\n📊 Procesando bonos...")
    actualizados = 0
    sin_datos = []

    for ticker, info in BONOS.items():
        precio_ars = None
        fuente = None

        # 1. Intentar desde fuentes externas
        if ticker in precios_externos:
            precio_ars = precios_externos[ticker]
            fuente = "api_externa"

        # 2. Intentar Yahoo Finance
        if precio_ars is None:
            precio_ars = obtener_precio_yfinance(info["ba"])
            if precio_ars:
                fuente = "yfinance"

        if precio_ars and precio_ars > 0:
            ok = guardar_precio(con, ticker, precio_ars, ccl,
                                info["moneda"], info["tipo"], info["nombre"], fuente)
            if ok:
                if info["moneda"] == "USD":
                    precio_usd = precio_ars / ccl
                    print(f"  ✅ {ticker:8} | ARS: ${precio_ars:>12,.2f} | USD: ${precio_usd:>8.4f} | {fuente}")
                else:
                    print(f"  ✅ {ticker:8} | ARS: ${precio_ars:>12,.2f} | {fuente}")
                actualizados += 1
        else:
            sin_datos.append(ticker)

    print(f"\n✅ Actualizados automáticamente: {actualizados}/{len(BONOS)}")

    # Entrada manual para los que no tienen precio
    if sin_datos:
        print(f"\n⚠️  Sin precio automático ({len(sin_datos)} bonos):")
        print("   Ingresá el precio en % del VN (ej: AL29 a $83.29 → ingresá 83.29)")
        print("   Presioná Enter para saltar\n")

        for ticker in sin_datos:
            info = BONOS[ticker]
            try:
                entrada = input(f"  {ticker:8} ({info['moneda']}) [{info['nombre'][:30]}]: ").strip()
                if entrada:
                    precio_pct = float(entrada.replace(",", "."))
                    ok = guardar_precio_manual(con, ticker, precio_pct,
                                               info["moneda"], info["tipo"], info["nombre"])
                    if ok:
                        print(f"    ✅ {ticker}: {precio_pct:.4f} guardado")
            except (ValueError, KeyboardInterrupt):
                pass

    # Mostrar resumen final
    print("\n📋 Precios en Supabase:")
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT ticker, nombre, precio, precio_ars, moneda, tipo, fuente, actualizado
            FROM precios_bonos ORDER BY tipo, ticker
        """)
        rows = cur.fetchall()
        print(f"\n  {'Ticker':8} | {'Precio %':>9} | {'Precio ARS':>12} | {'Moneda':6} | {'Tipo':12} | {'Fuente':10} | Fecha")
        print(f"  {'-'*8}-+-{'-'*9}-+-{'-'*12}-+-{'-'*6}-+-{'-'*12}-+-{'-'*10}-+-{'-'*10}")
        for r in rows:
            precio_ars_str = f"${r[3]:>12,.2f}" if r[3] else "     —"
            print(f"  {r[0]:8} | {r[2]:>9.4f} | {precio_ars_str} | {str(r[4]):6} | {str(r[5]):12} | {str(r[6]):10} | {r[7]}")
        print(f"\n  Total: {len(rows)} bonos con precio")
    except Exception as e:
        print(f"  Error al listar: {e}")

    con.close()
    print("\n✅ Proceso completado.")
    print("   Los precios ya están disponibles en la app Cartera AR.")
    print("   Ejecutá este script cada vez que quieras actualizar los precios.")


if __name__ == "__main__":
    main()