"""
Historico.py — v3
=================
Cambios respecto a v2:
  1. Sin tickers predeterminados como fallback:
     si el usuario no ingresa tickers, el programa avisa y sale.
     (La cartera personal será la fuente en la versión Streamlit)
  2. Al finalizar los 3 escenarios, llama automáticamente a
     generar_reporte.py para producir el reporte ejecutivo legible.
  3. Estructura preparada para información de mercado (Fase siguiente).
"""

import requests
import os
import sys
import subprocess
import tabula
import pdfplumber
import yfinance as yf
import pandas as pd
import numpy as np
import camelot
from datetime import datetime
from dateutil.relativedelta import relativedelta
from scipy.optimize import minimize
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from fuentes import get_bonos_us, get_bonos_ar, get_merval
import cedear_mapper

# =========================================
# DEFINIR RAÍZ DEL PROYECTO
# =========================================
if getattr(sys, 'frozen', False):
    PROYECTO_RAIZ = os.path.dirname(sys.executable)
else:
    PROYECTO_RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

data_dir = os.path.join(PROYECTO_RAIZ, "data")

# =========================================
# CONFIGURACIÓN GENERAL
# =========================================
# [CAMBIO v3] Sin TICKERS_DEFAULT como fallback.
# El usuario DEBE ingresar sus tickers manualmente.
# En la versión Streamlit, la cartera personal será la fuente.
ANIOS     = 10
INTERVALO = '1mo'
START_DATE = (datetime.today() - relativedelta(years=ANIOS)).strftime('%Y-%m-%d')
END_DATE   = datetime.today().strftime('%Y-%m-%d')

# =========================================
# CORRECCIONES DE TICKERS CONOCIDOS
# =========================================
CORRECCIONES_TICKER = {
    "APPL":      "AAPL",
    "GOOG":      "GOOGL",
    "TESLA":     "TSLA",
    "MICROSOFT": "MSFT",
    "AMAZON":    "AMZN",
    "DISN":      "DIS",
    "BRKA":      "BRK-A",
    "BRKB":      "BRK-B",
    "CGPA2":     "CGPA2.BA",
    "SAMI":      "SAMI.BA",
    "TXAR":      "TXARD.BA",
    "ALUA":      "ALUAD.BA",
    "CELU":      "CELU.BA",
    "TRAN":      "TRAND.BA",
    "PETR3":     "PETR3.SA",
    "PAMP":      "PAM"
}

# =========================================
# MAPA DE TICKERS BYMA (CEDEAR en ARS)
# Algunos tickers tienen nombres distintos en Yahoo Finance Argentina.
# Formato: "TICKER_NYSE" -> "TICKER_BYMA_YAHOO"
# La mayoría siguen el patrón TICKER.BA, pero hay excepciones.
# =========================================
TICKERS_BYMA = {
    # Estándar (TICKER.BA) — se generan automáticamente
    # Excepciones conocidas:
    "BRK-A":  "BRK-A.BA",
    "BRK-B":  "BRK-B.BA",
    # NU Holdings: cotiza en BYMA como depositary receipt
    # Yahoo Finance Argentina lo registra como NU.BA
    "NU":     "NU.BA",
    # Tickers que NO tienen CEDEAR en BYMA (devuelven Sin precio BYMA)
    "IBIT":   None,   # Bitcoin ETF — sin CEDEAR
    "URA":    None,   # Uranium ETF — sin CEDEAR
    "ARKK":   None,   # ARK Innovation — sin CEDEAR directo
}

def get_ticker_byma(ticker: str) -> str | None:
    """
    Retorna el ticker de Yahoo Finance para el CEDEAR en BYMA.
    - Si ya tiene sufijo .BA → lo usa tal cual (no duplica)
    - Si está en TICKERS_BYMA → usa el valor del mapa (puede ser None)
    - Si es ETF internacional conocido → None (sin CEDEAR)
    - Por defecto → agrega sufijo .BA
    """
    t = ticker.upper()

    # Si ya tiene sufijo .BA, no agregar de nuevo
    if t.endswith(".BA"):
        return t

    # Si está en el mapa de excepciones
    if t in TICKERS_BYMA:
        return TICKERS_BYMA[t]   # puede ser None si no tiene CEDEAR

    # ETFs sectoriales y otros sin CEDEAR conocido
    ETF_SIN_CEDEAR = {
        "XLV", "XLRE", "XLE", "XLI", "XLK", "XLY", "XLB", "XLU",
        "GLD", "SLV", "TLT", "HYG", "LQD", "EEM", "EFA", "VWO",
        "IWM", "VOO", "IVV", "DIA", "VTI", "SCHD", "JEPI",
    }
    if t in ETF_SIN_CEDEAR:
        return None

    return t + ".BA"             # patrón estándar

EQUIVALENCIAS_VALIDACION = {
    "DISN":  "DIS",
    "BRKA":  "BRK-A",
    "BRKB":  "BRK-B",
    "TECO2": "TEO",
    "BYMA":  "BYMA.BA"
}

def corregir_ticker(ticker: str) -> str:
    return CORRECCIONES_TICKER.get(ticker.upper(), ticker.upper())

# =========================================
# INICIALIZAR MAPA DE EQUIVALENCIAS CEDEAR
# =========================================
print("🗺️  Inicializando mapa de equivalencias CEDEAR...")
try:
    cedear_mapper.inicializar(validar_yahoo=True)
except Exception:
    print("⚠️  Sin red — usando equivalencias curadas sin validación Yahoo")
    cedear_mapper.inicializar(validar_yahoo=False)

# =========================================
# INTERFAZ TKINTER
# =========================================
root = tk.Tk()
root.withdraw()

# Carpeta destino
carpeta_destino = filedialog.askdirectory(
    title="Seleccione carpeta de destino para los reportes"
)
if not carpeta_destino:
    print("❌ No se seleccionó carpeta. Se canceló la ejecución.")
    sys.exit()

# ── [CAMBIO v3] Ingreso obligatorio de tickers ────────────────────────────────
while True:
    entrada = simpledialog.askstring(
        "Ingreso de Tickers",
        "Ingrese los tickers a analizar separados por comas:\n"
        "(Ej: AAPL, MSFT, VIST, YPFD, BMA)\n\n"
        "⚠️  Campo obligatorio — no se usan tickers predeterminados."
    )

    if entrada is None:
        # Usuario canceló el diálogo
        print("❌ Ingreso cancelado. Se canceló la ejecución.")
        sys.exit()

    tickers_raw = [t.strip() for t in entrada.split(",") if t.strip()]

    if tickers_raw:
        break
    else:
        messagebox.showwarning(
            "Tickers requeridos",
            "Debe ingresar al menos un ticker para continuar.\n"
            "Ejemplo: AAPL, MSFT, VIST, YPFD"
        )

TICKERS = [corregir_ticker(t) for t in tickers_raw]
print(f"✅ Tickers ingresados: {TICKERS}")

# Parámetros fundamentales
margen_input = simpledialog.askstring(
    "Margen Neto mínimo",
    "Ingrese Margen Neto mínimo (ej: 0.20 para 20%):\n"
    "(Enter para usar 0.20 por defecto)"
)
roic_input = simpledialog.askstring(
    "ROIC mínimo",
    "Ingrese ROIC mínimo (ej: 0.15 para 15%):\n"
    "(Enter para usar 0.15 por defecto)"
)
deuda_input = simpledialog.askstring(
    "Endeudamiento máximo (D/E)",
    "Ingrese máximo Debt/Equity (ej: 0.5 para 50%):\n"
    "(Enter para usar 0.5 por defecto)"
)

try:
    MARGEN_MIN = float(margen_input) if margen_input else 0.20
    ROIC_MIN   = float(roic_input)   if roic_input   else 0.15
    DEUDA_MAX  = float(deuda_input)  if deuda_input  else 0.5
except ValueError:
    MARGEN_MIN, ROIC_MIN, DEUDA_MAX = 0.20, 0.15, 0.5

# =========================================
# EXPANSIÓN DE TICKERS (local → local + ADR)
# =========================================
tickers_combinados, tickers_sin_equivalencia = cedear_mapper.expandir_tickers(TICKERS)
print(f"✅ Tickers combinados (originales + ADRs): {tickers_combinados}")
print(f"⚠️  Tickers sin ADR ni equivalencia conocida: {tickers_sin_equivalencia}")

# =========================================
# VALIDACIÓN DE TICKERS CONTRA YAHOO
# =========================================
def validar_ticker(ticker: str) -> str | None:
    t = EQUIVALENCIAS_VALIDACION.get(ticker, ticker)
    try:
        prueba = yf.download(t, period="5d", interval="1d",
                             progress=False, auto_adjust=True)
        return t if not prueba.empty else None
    except Exception:
        return None

tickers_validados = []
for t in tickers_combinados:
    valido = validar_ticker(t)
    if valido:
        tickers_validados.append(valido)
    else:
        print(f"⚠️ {t} descartado (sin datos en Yahoo Finance)")

if not tickers_validados:
    messagebox.showerror(
        "Sin tickers válidos",
        "Ningún ticker ingresado tiene datos válidos en Yahoo Finance.\n"
        "Verificá tu conexión a internet y los tickers ingresados."
    )
    raise ValueError("❌ Ningún ticker válido tras correcciones/validación.")

# =========================================
# FUNDAMENTALES
# =========================================
def obtener_fundamentales(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {
            "Ticker":             ticker,
            "forwardPE":          info.get("forwardPE"),
            "trailingPE":         info.get("trailingPE"),
            "priceToBook":        info.get("priceToBook"),
            "enterpriseValue":    info.get("enterpriseValue"),
            "enterpriseToEbitda": info.get("enterpriseToEbitda"),
            "quickRatio":         info.get("quickRatio"),
            "currentRatio":       info.get("currentRatio"),
            "totalDebt":          info.get("totalDebt"),
            "debtToEquity":       info.get("debtToEquity"),
            "earningsGrowth":     info.get("earningsGrowth"),
            "revenueGrowth":      info.get("revenueGrowth"),
            "operatingCashflow":  info.get("operatingCashflow"),
            "assetTurnover":      info.get("assetTurnover"),
            "grossMargins":       info.get("grossMargins"),
            "operatingMargins":   info.get("operatingMargins"),
            "profitMargins":      info.get("profitMargins"),
            "ROA":                info.get("returnOnAssets"),
            "ROE":                info.get("returnOnEquity"),
            "ROIC_proxy":         info.get("returnOnInvestedCapital",
                                           info.get("returnOnEquity")),
            "EPS":                info.get("trailingEps"),
            "freeCashflow":       info.get("freeCashflow"),
            "currentPrice":       info.get("currentPrice") or
                                  info.get("regularMarketPrice"),
            "Sector":             info.get("sector"),
            "Industria":          info.get("industry"),
            "MarketCap":          info.get("marketCap"),
            "Tipo":               cedear_mapper.clasificar_ticker(ticker),
        }
    except Exception:
        return {k: None for k in [
            "Ticker", "forwardPE", "trailingPE", "priceToBook",
            "enterpriseValue", "enterpriseToEbitda", "quickRatio",
            "currentRatio", "totalDebt", "debtToEquity", "earningsGrowth",
            "revenueGrowth", "operatingCashflow", "assetTurnover",
            "grossMargins", "operatingMargins", "profitMargins",
            "ROA", "ROE", "ROIC_proxy", "EPS", "freeCashflow",
            "currentPrice", "Sector", "Industria", "MarketCap", "Tipo"
        ]}

# =========================================
# FILTRO POR FUNDAMENTALES
# =========================================
def filtrar_por_fundamentales(tickers, margen_min, roic_min, de_max):
    filtrados, reporte = [], []
    for t in tickers:
        datos  = obtener_fundamentales(t)
        margen = datos.get("profitMargins")
        roic   = datos.get("ROIC_proxy")
        deuda  = datos.get("debtToEquity")
        motivo = []
        if margen is None or roic is None or deuda is None:
            motivo.append("Datos incompletos")
        else:
            if margen <= margen_min:
                motivo.append(f"Margen Neto <= {margen_min*100:.0f}%")
            if roic <= roic_min:
                motivo.append(f"ROIC <= {roic_min*100:.0f}%")
            if deuda >= de_max * 100:
                motivo.append(f"D/E >= {de_max:.2f}")
        if motivo:
            datos["Motivo"] = ", ".join(motivo)
            reporte.append(datos)
        else:
            filtrados.append(t)
    if not filtrados:
        filtrados = tickers[:]
    return filtrados, pd.DataFrame(reporte)

# =========================================
# RATIOS CEDEAR DESDE PDF (BYMA)
# =========================================
def _parsear_ratio(ratio_raw: str) -> float | None:
    ratio_raw = ratio_raw.strip()
    try:
        if ":" in ratio_raw:
            n, d = ratio_raw.split(":", 1)
            return float(n) / float(d)
        elif "/" in ratio_raw:
            n, d = ratio_raw.split("/", 1)
            return float(n) / float(d)
        else:
            return float(ratio_raw.replace(",", "."))
    except Exception:
        return None

def obtener_ratios_desde_pdf(ruta_pdf: str,
                              archivo_csv: str = "ratios_cedear.csv") -> dict:
    ratios = {}
    if not ruta_pdf or not os.path.exists(ruta_pdf):
        print(f"❌ PDF no encontrado: {ruta_pdf}")
        return {}

    # 1) pdfplumber
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table[1:]:
                        if row and len(row) >= 4:
                            ticker = str(row[1]).strip().upper()
                            valor  = _parsear_ratio(str(row[3]))
                            if ticker and valor is not None:
                                ratios[ticker] = valor
        if ratios:
            print(f"✅ {len(ratios)} ratios cargados con pdfplumber")
    except Exception as e:
        print(f"⚠️ pdfplumber: {e}")

    # 2) camelot
    if not ratios:
        try:
            for t in camelot.read_pdf(ruta_pdf, pages="all", flavor="lattice"):
                for _, row in t.df.iterrows():
                    if len(row) >= 4:
                        ticker = str(row[1]).strip().upper()
                        valor  = _parsear_ratio(str(row[3]))
                        if ticker and valor is not None and ticker != "CÓDIGO BYMA":
                            ratios[ticker] = valor
            if ratios:
                print(f"✅ {len(ratios)} ratios cargados con camelot")
        except Exception as e:
            print(f"⚠️ camelot: {e}")

    # 3) tabula
    if not ratios:
        try:
            for df in tabula.read_pdf(ruta_pdf, pages="all",
                                      multiple_tables=True, encoding="latin-1"):
                for _, row in df.iterrows():
                    if len(row) >= 4:
                        ticker = str(row[1]).strip().upper()
                        valor  = _parsear_ratio(str(row[3]))
                        if ticker and valor is not None and ticker != "CÓDIGO BYMA":
                            ratios[ticker] = valor
            if ratios:
                print(f"✅ {len(ratios)} ratios cargados con tabula")
        except Exception as e:
            print(f"⚠️ tabula: {e}")

    if ratios:
        pd.DataFrame(list(ratios.items()),
                     columns=["Ticker", "Ratio"]).to_csv(
            archivo_csv, index=False, encoding="utf-8"
        )
        print(f"💾 Ratios guardados en {archivo_csv}")
    else:
        print("❌ No se pudieron extraer ratios del PDF")

    return ratios

def cargar_ratios_csv(archivo: str = "ratios_cedear.csv") -> dict:
    try:
        df = pd.read_csv(archivo)
        return dict(zip(df["Ticker"], df["Ratio"]))
    except FileNotFoundError:
        print(f"⚠️ CSV no encontrado: {archivo}")
        return {}
    except Exception as e:
        print(f"⚠️ Error al cargar CSV: {e}")
        return {}

def guardar_ratios_csv(ratios: dict, archivo: str = "ratios_cedear.csv") -> None:
    pd.DataFrame(list(ratios.items()),
                 columns=["Ticker", "Ratio"]).to_csv(
        archivo, index=False, encoding="utf-8"
    )
    print(f"✅ Ratios guardados en {archivo}")

# ── Inicialización de RATIOS_CEDEAR ──
csv_path = os.path.join(PROYECTO_RAIZ, "data", "ratios_cedear.csv")
if os.path.exists(csv_path):
    RATIOS_CEDEAR = cargar_ratios_csv(csv_path)
    print(f"📂 {len(RATIOS_CEDEAR)} ratios cargados desde CSV")
else:
    pdf_candidates = [
        f for f in os.listdir(data_dir)
        if f.lower().endswith(".pdf") and "cedear" in f.lower()
    ]
    ruta_pdf = os.path.join(data_dir, pdf_candidates[0]) \
               if pdf_candidates else None
    if not ruta_pdf:
        print("⚠️ No se encontró PDF de ratios CEDEAR en data/")
    RATIOS_CEDEAR = obtener_ratios_desde_pdf(ruta_pdf, archivo_csv=csv_path)

def obtener_ratio_cedear(ticker: str) -> float | None:
    return RATIOS_CEDEAR.get(ticker.upper())

# =========================================
# DÓLAR CCL CON FALLBACK
# =========================================
def obtener_dolar_ccl() -> float | None:
    fuentes = [
        {
            "nombre": "DolarApi.com",
            "url":    "https://dolarapi.com/v1/dolares",
            "parser": lambda d: next(
                (x["venta"] for x in d if x["casa"] == "contadoconliqui"), None
            )
        },
        {
            "nombre": "ArgentinaDatos",
            "url":    "https://api.argentinadatos.com/v1/cotizaciones/dolares",
            "parser": lambda d: next(
                (x["venta"] for x in d if x["casa"] == "contadoconliqui"), None
            )
        },
        {
            "nombre": "DolarHoy",
            "url":    "https://www.dolarsi.com/api/api.php?type=valoresprincipales",
            "parser": lambda d: next(
                (float(x["casa"]["venta"].replace(",", "."))
                 for x in d
                 if "contado con liqui" in x["casa"]["nombre"].lower()),
                None
            )
        }
    ]
    for fuente in fuentes:
        try:
            r = requests.get(fuente["url"], timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                valor = fuente["parser"](r.json())
                if valor:
                    print(f"✅ CCL desde {fuente['nombre']}: {valor}")
                    return float(valor)
        except Exception as e:
            print(f"⚠️ {fuente['nombre']}: {e}")
    return None

# =========================================
# RECOMENDACIÓN (claves corregidas)
# =========================================
def evaluar_recomendacion(margen, roic, crecimiento) -> str:
    if margen is not None and roic is not None and crecimiento is not None:
        if margen > 0.20 and roic > 0.15 and crecimiento > 0.10:
            return "Alta proyección"
        elif margen > 0.15 and roic > 0.10:
            return "Interesante"
        else:
            return "Débil"
    return "Sin datos"

# =========================================
# GENERAR EXCEL RESULTADOS
# =========================================
def generar_excel_resultados(tickers, escenario_prefix,
                              reporte_eliminados,
                              tickers_sin_equivalencia=None):

    df = yf.download(tickers, start=START_DATE, end=END_DATE,
                     interval=INTERVALO, progress=False, auto_adjust=True)
    df_close = df['Close'] if isinstance(df.columns, pd.MultiIndex) else df
    df_close = df_close.dropna(axis=1, how="all").sort_index()

    retornos_pct = df_close.pct_change(fill_method=None).dropna(how='all')
    returns      = np.log(df_close / df_close.shift(1)).dropna(how='all')

    mean_returns = returns.mean() * 12
    cov_matrix   = returns.cov() * 12
    cols = mean_returns.index.tolist()
    n    = len(cols)

    estadisticas = pd.DataFrame({
        "Ticker":              cols,
        "Retorno esperado":    mean_returns.values.round(4),
        "Varianza":            np.diag(cov_matrix.values).round(4),
        "Desviación estándar": np.sqrt(np.diag(cov_matrix.values)).round(4),
    })
    total = estadisticas["Retorno esperado"].sum()
    estadisticas["Proporción"] = (
        estadisticas["Retorno esperado"] / total
        if total != 0 else np.nan
    )
    estadisticas = estadisticas.round(4)

    corr_matrix      = returns.corr().round(6)
    weights_equal    = np.array([1 / n] * n)
    markowitz_matrix = np.outer(weights_equal, weights_equal) * cov_matrix.values

    def port_ret(w): return float(np.dot(w, mean_returns))
    def port_var(w): return float(np.dot(w.T, np.dot(cov_matrix, w)))
    def port_vol(w): return np.sqrt(port_var(w))
    def sharpe(w, rf=0.0):
        v = port_vol(w)
        return (port_ret(w) - rf) / v if v > 0 else 0.0

    restricciones = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1},)
    limites       = tuple((0, 1) for _ in range(n))
    w_min_var    = minimize(port_var, weights_equal, method='SLSQP',
                            bounds=limites, constraints=restricciones).x
    w_max_sharpe = minimize(lambda w: -sharpe(w), weights_equal,
                            method='SLSQP', bounds=limites,
                            constraints=restricciones).x

    resumen = pd.concat([
        pd.DataFrame({
            "Tipo":             ["Cartera Equilibrada"],
            "Retorno esperado": [port_ret(weights_equal)],
            "Varianza":         [port_var(weights_equal)],
            "Desviación estándar": [port_vol(weights_equal)]
        }),
        pd.DataFrame({
            "Tipo":             ["Mínima Varianza", "Máximo Sharpe"],
            "Retorno esperado": [port_ret(w_min_var),   port_ret(w_max_sharpe)],
            "Varianza":         [port_var(w_min_var),   port_var(w_max_sharpe)],
            "Desviación estándar": [port_vol(w_min_var), port_vol(w_max_sharpe)]
        })
    ], ignore_index=True).round(4)

    pesos_df = pd.DataFrame({
        "Ticker":          cols,
        "Peso Igual":      np.round(weights_equal, 4),
        "Peso Min Var":    np.round(w_min_var, 4),
        "Peso Max Sharpe": np.round(w_max_sharpe, 4)
    })

    ccl = obtener_dolar_ccl()
    if not ccl:
        ccl = 1200
        print(f"⚠️ Usando CCL estimado: {ccl}")

    fundamentales, cedear_analisis = [], []

    for t in tickers:
        info = obtener_fundamentales(t)

        # Precio USD real del activo subyacente
        precio_usd = info.get("currentPrice")
        ratio      = obtener_ratio_cedear(t)

        # Precio ARS del CEDEAR en BYMA usando mapa de tickers
        ticker_ba = get_ticker_byma(t)
        precio_cedear_ars = None
        if ticker_ba:  # None significa que no tiene CEDEAR
            try:
                info_ba = yf.Ticker(ticker_ba).info
                precio_cedear_ars = info_ba.get("currentPrice") or \
                                    info_ba.get("regularMarketPrice")
                # Validar precio razonable en ARS (> 10 ARS)
                if precio_cedear_ars and float(precio_cedear_ars) < 10:
                    precio_cedear_ars = None
            except Exception:
                precio_cedear_ars = None

        valor_impl = (precio_usd / ratio) * ccl \
                     if precio_usd and ratio else None
        diferencia_pct = (
            round((precio_cedear_ars - valor_impl) / valor_impl * 100, 2)
            if precio_cedear_ars and valor_impl else None
        )
        if precio_cedear_ars and valor_impl:
            estado = "Barato" if precio_cedear_ars < valor_impl else "Caro"
        elif valor_impl and not precio_cedear_ars:
            estado = "Sin precio BYMA"
        else:
            estado = "Sin datos"
        tipo = cedear_mapper.clasificar_ticker(t)

        recomendacion = evaluar_recomendacion(
            info.get("profitMargins"),
            info.get("ROIC_proxy"),
            info.get("revenueGrowth")
        )

        info.update({
            "Precio USD":                   round(precio_usd, 4)        if precio_usd        else None,
            "Ratio CEDEAR":                 ratio,
            "Dólar CCL":                    ccl,
            "Valor implícito CEDEAR (ARS)": round(valor_impl, 2)        if valor_impl        else None,
            "Precio CEDEAR (ARS)":          round(precio_cedear_ars, 2) if precio_cedear_ars else None,
            "Diferencia (%)":               diferencia_pct,
            "Estado CEDEAR":                estado,
            "Tipo":                         tipo,
            "Recomendación":                recomendacion
        })
        fundamentales.append(info)

        cedear_analisis.append({
            "Ticker":                       t,
            "Tipo":                         tipo,
            "Precio USD":                   round(precio_usd, 4)        if precio_usd        else None,
            "Ratio CEDEAR":                 ratio,
            "Dólar CCL":                    ccl,
            "Valor implícito CEDEAR (ARS)": round(valor_impl, 2)        if valor_impl        else None,
            "Precio CEDEAR (ARS)":          round(precio_cedear_ars, 2) if precio_cedear_ars else None,
            "Diferencia (%)":               diferencia_pct,
            "Estado":                       estado
        })

    fundamentales_df = pd.DataFrame(fundamentales)
    columnas_excluir = [
        "Precio USD", "Ratio CEDEAR", "Dólar CCL",
        "Valor implícito CEDEAR (ARS)", "Estado CEDEAR",
        "Precio CEDEAR (ARS)", "Diferencia (%)"
    ]
    fundamentales_df = fundamentales_df.drop(
        columns=[c for c in columnas_excluir if c in fundamentales_df.columns]
    )
    cedear_df = pd.DataFrame(cedear_analisis)

    mejor = estadisticas.sort_values(
        "Retorno esperado", ascending=False
    ).iloc[0]["Ticker"]

    diccionario = pd.DataFrame([
        ["forwardPE",          "Precio sobre ganancias proyectadas",  "<15 atractivo, 15–25 normal"],
        ["trailingPE",         "Precio sobre ganancias históricas",   "<20 atractivo"],
        ["priceToBook",        "Precio sobre valor contable",         "<3 razonable"],
        ["enterpriseValue",    "Valor total de la empresa",           "Depende del sector"],
        ["enterpriseToEbitda", "EV/EBITDA vs flujo operativo",        "<10 atractivo"],
        ["quickRatio",         "Liquidez inmediata",                  ">1 sano"],
        ["currentRatio",       "Liquidez corriente",                  "1.5–2 ideal"],
        ["totalDebt",          "Deuda total",                         "Depende del sector"],
        ["debtToEquity",       "Deuda / patrimonio",                  "<1 conservador"],
        ["earningsGrowth",     "Crecimiento de ganancias",            ">10% atractivo"],
        ["revenueGrowth",      "Crecimiento de ventas",               ">10% atractivo"],
        ["operatingCashflow",  "Flujo de caja operativo",             "Positivo"],
        ["assetTurnover",      "Eficiencia en uso de activos",        ">0.5 aceptable"],
        ["grossMargins",       "Margen bruto",                        ">30% bueno"],
        ["operatingMargins",   "Margen operativo",                    ">15% bueno"],
        ["profitMargins",      "Margen neto",                         ">10% bueno"],
        ["ROA",                "Retorno sobre activos",               ">5% aceptable"],
        ["ROE",                "Retorno sobre patrimonio",            ">10% atractivo"],
        ["ROIC_proxy",         "Retorno sobre capital invertido",     ">10% atractivo"],
        ["EPS",                "Ganancia por acción",                 "Positiva"],
        ["currentPrice",       "Precio de mercado en USD",            "Precio real del activo"],
        ["freeCashflow",       "Flujo de caja libre",                 "Positivo"],
        ["Tipo",               "Clasificación del activo",            "ADR / Local sin ADR / Internacional"]
    ], columns=["Indicador", "Descripción", "Valores típicos"])

    os.makedirs(carpeta_destino, exist_ok=True)
    output_path = os.path.join(
        carpeta_destino, f"{escenario_prefix}_resultados.xlsx"
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_close.to_excel(writer,              sheet_name="Precios")
        retornos_pct.to_excel(writer,          sheet_name="Retornos")
        estadisticas.to_excel(writer,          sheet_name="Estadísticas",   index=False)
        cov_matrix.to_excel(writer,            sheet_name="Covarianzas")
        corr_matrix.to_excel(writer,           sheet_name="Correlaciones")
        pd.DataFrame(markowitz_matrix,
                     index=cols,
                     columns=cols).to_excel(writer,  sheet_name="Markowitz")
        resumen.to_excel(writer,               sheet_name="Resumen",        index=False)
        pesos_df.to_excel(writer,              sheet_name="Pesos",          index=False)
        fundamentales_df.to_excel(writer,      sheet_name="Fundamentales",  index=False)
        cedear_df.to_excel(writer,             sheet_name="Analisis CEDEAR", index=False)
        reporte_eliminados.to_excel(writer,    sheet_name="Eliminados",     index=False)
        pd.DataFrame([
            ["Retorno esperado", "Promedio anualizado de retornos logarítmicos"],
            ["Varianza",         "Riesgo total del activo"],
            ["Sharpe Ratio",     "Retorno ajustado por riesgo"],
            ["Markowitz",        "Modelo de optimización de portafolio"],
            ["Fundamentales",    "Indicadores clave + análisis CEDEAR"],
            ["Recomendación",    f"Comprar CEDEAR de {mejor} por mejor proyección"]
        ]).to_excel(writer, sheet_name="Metodología", index=False, header=False)
        pd.DataFrame([{
            "Ticker recomendado": mejor,
            "Motivo": "Mayor retorno esperado en cartera equilibrada"
        }]).to_excel(writer, sheet_name="Recomendación", index=False)
        diccionario.to_excel(writer,           sheet_name="Diccionario Indicadores", index=False)
        if tickers_sin_equivalencia:
            pd.DataFrame({
                "Ticker sin ADR": tickers_sin_equivalencia
            }).to_excel(writer, sheet_name="Locales sin ADR", index=False)

    print(f"✅ {escenario_prefix}: {output_path} generado")
    return output_path

# =========================================
# EJECUCIÓN DE ESCENARIOS
# =========================================
def ejecutar_escenarios():
    archivos_generados = []

    # Escenario estricto
    t_estrictos, rep_e = filtrar_por_fundamentales(
        tickers_validados, MARGEN_MIN, ROIC_MIN, DEUDA_MAX
    )
    path_e = generar_excel_resultados(
        t_estrictos, "estricto", rep_e, tickers_sin_equivalencia
    )
    archivos_generados.append(("estricto", path_e))

    # Escenario flexible
    t_flexibles, rep_f = filtrar_por_fundamentales(
        tickers_validados, MARGEN_MIN / 2, ROIC_MIN / 2, DEUDA_MAX * 2
    )
    path_f = generar_excel_resultados(
        t_flexibles, "flexible", rep_f, tickers_sin_equivalencia
    )
    archivos_generados.append(("flexible", path_f))

    # Escenario completo (sin filtro)
    path_c = generar_excel_resultados(
        tickers_validados, "completo", pd.DataFrame(), tickers_sin_equivalencia
    )
    archivos_generados.append(("completo", path_c))

    return archivos_generados

# =========================================
# [CAMBIO v3] GENERAR REPORTE EJECUTIVO AUTOMÁTICAMENTE
# Al terminar los 3 escenarios, llama a generar_reporte.py
# sobre el archivo "completo" para producir el reporte legible.
# =========================================
def generar_reporte_ejecutivo(path_completo: str) -> None:
    """
    Llama a generar_reporte.py como subproceso pasándole el
    archivo completo_resultados.xlsx recién generado.
    """
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    reporte_script = os.path.join(script_dir, "generar_reporte.py")

    if not os.path.exists(reporte_script):
        print("⚠️  generar_reporte.py no encontrado en scripts/ — se omite el reporte ejecutivo")
        return

    nombre_base  = os.path.splitext(os.path.basename(path_completo))[0]
    output_reporte = os.path.join(
        os.path.dirname(path_completo),
        f"reporte_ejecutivo_{nombre_base.replace('completo_', '')}.xlsx"
    )

    print(f"\n📊 Generando reporte ejecutivo...")
    print(f"   Input:  {path_completo}")
    print(f"   Output: {output_reporte}")

    try:
        resultado = subprocess.run(
            [sys.executable, reporte_script,
             "--input",  path_completo,
             "--output", output_reporte],
            capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace"   # fix: emojis en Windows cp1252
        )
        if resultado.returncode == 0:
            print(f"✅ Reporte ejecutivo generado: {output_reporte}")
            # Mostrar mensaje al usuario
            messagebox.showinfo(
                "Proceso completado",
                f"✅ Análisis completado exitosamente.\n\n"
                f"Archivos generados en:\n{os.path.dirname(path_completo)}\n\n"
                f"• estricto_resultados.xlsx\n"
                f"• flexible_resultados.xlsx\n"
                f"• completo_resultados.xlsx\n"
                f"• {os.path.basename(output_reporte)} ← REPORTE EJECUTIVO"
            )
        else:
            print(f"⚠️  Error en generar_reporte.py:\n{resultado.stderr}")
            messagebox.showwarning(
                "Reporte parcial",
                f"Los Excel de resultados fueron generados correctamente.\n\n"
                f"El reporte ejecutivo no pudo generarse:\n{resultado.stderr[:200]}"
            )
    except subprocess.TimeoutExpired:
        print("⚠️  Timeout al generar reporte ejecutivo (>5 min)")
    except Exception as e:
        print(f"⚠️  Error al llamar generar_reporte.py: {e}")

# =========================================
# MAIN
# =========================================
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  CARTERA AR — ANÁLISIS DE PORTAFOLIOS")
    print("="*55)
    print(f"  Tickers: {tickers_validados}")
    print(f"  Período: {START_DATE} → {END_DATE}")
    print(f"  Filtros: Margen>{MARGEN_MIN:.0%} | ROIC>{ROIC_MIN:.0%} | D/E<{DEUDA_MAX}")
    print("="*55 + "\n")

    archivos = ejecutar_escenarios()

    # Buscar el archivo completo para el reporte
    path_completo = next(
        (p for nombre, p in archivos if nombre == "completo"), None
    )

    if path_completo:
        generar_reporte_ejecutivo(path_completo)
    else:
        print("⚠️  No se encontró el archivo completo para generar el reporte")

    print("\n✅ Proceso finalizado.")