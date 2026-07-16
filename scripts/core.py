"""
core.py — Lógica de negocio compartida entre todas las páginas Streamlit.
Contiene: descarga de datos, fundamentales, Markowitz, CCL, CEDEAR.
"""
import os, json, requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta
from scipy.optimize import minimize
import streamlit as st
import cedear_mapper

# =========================================
# CONFIGURACIÓN
# =========================================
TICKERS_DEFAULT = [
    'AAPL','MSFT','NVDA','KO','MCD','TSLA','INTC','AMD','AMZN','ARKK',
    'DOW','GOOGL','MELI','META','PBR','QQQ','SPY','RIO','SNOW','V',
    'VIST','XLF','XLP'
]
ANIOS     = 10
INTERVALO = '1mo'

CORRECCIONES_TICKER = {
    "APPL":"AAPL","GOOG":"GOOGL","TESLA":"TSLA","MICROSOFT":"MSFT",
    "AMAZON":"AMZN","DISN":"DIS","BRKA":"BRK-A","BRKB":"BRK-B",
    "PAMP":"PAM","TECO2":"TEO"
}

def corregir_ticker(t: str) -> str:
    return CORRECCIONES_TICKER.get(t.upper(), t.upper())

# =========================================
# DESCARGA DE PRECIOS (con caché Streamlit)
# =========================================
@st.cache_data(ttl=3600, show_spinner=False)
def descargar_precios(tickers: tuple, anios: int = ANIOS) -> pd.DataFrame:
    start = (datetime.today() - relativedelta(years=anios)).strftime('%Y-%m-%d')
    end   = datetime.today().strftime('%Y-%m-%d')
    df = yf.download(list(tickers), start=start, end=end,
                     interval=INTERVALO, progress=False, auto_adjust=True)
    df_close = df['Close'] if isinstance(df.columns, pd.MultiIndex) else df
    return df_close.dropna(axis=1, how="all").sort_index()

# =========================================
# FUNDAMENTALES (con caché Streamlit)
# =========================================
@st.cache_data(ttl=3600, show_spinner=False)
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
            "ROIC_proxy":         info.get("returnOnInvestedCapital", info.get("returnOnEquity")),
            "EPS":                info.get("trailingEps"),
            "freeCashflow":       info.get("freeCashflow"),
            "currentPrice":       info.get("currentPrice") or info.get("regularMarketPrice"),
            "Sector":             info.get("sector"),
            "Industria":          info.get("industry"),
            "MarketCap":          info.get("marketCap"),
            "Nombre":             info.get("longName") or info.get("shortName"),
            "Tipo":               cedear_mapper.clasificar_ticker(ticker),
        }
    except Exception:
        return {k: None for k in [
            "Ticker","forwardPE","trailingPE","priceToBook","enterpriseValue",
            "enterpriseToEbitda","quickRatio","currentRatio","totalDebt","debtToEquity",
            "earningsGrowth","revenueGrowth","operatingCashflow","assetTurnover",
            "grossMargins","operatingMargins","profitMargins","ROA","ROE","ROIC_proxy",
            "EPS","freeCashflow","currentPrice","Sector","Industria","MarketCap","Nombre","Tipo"
        ]}

def evaluar_recomendacion(margen, roic, crecimiento) -> str:
    if margen is not None and roic is not None and crecimiento is not None:
        if margen > 0.20 and roic > 0.15 and crecimiento > 0.10:
            return "🟢 Alta proyección"
        elif margen > 0.15 and roic > 0.10:
            return "🟡 Interesante"
        else:
            return "🔴 Débil"
    return "⚪ Sin datos"

def score_fundamental(info: dict) -> float:
    """Score 0-100 basado en fundamentales."""
    score = 0
    checks = [
        (info.get("profitMargins"),   lambda x: x > 0.20, 20),
        (info.get("profitMargins"),   lambda x: x > 0.10, 10),
        (info.get("ROIC_proxy"),      lambda x: x > 0.15, 20),
        (info.get("ROIC_proxy"),      lambda x: x > 0.10, 10),
        (info.get("revenueGrowth"),   lambda x: x > 0.10, 15),
        (info.get("debtToEquity"),    lambda x: x < 100,  10),
        (info.get("freeCashflow"),    lambda x: x > 0,    10),
        (info.get("currentRatio"),    lambda x: x > 1.5,  5),
    ]
    for val, cond, pts in checks:
        if val is not None:
            try:
                if cond(val):
                    score += pts
            except Exception:
                pass
    return min(score, 100)

# =========================================
# MARKOWITZ
# =========================================
def calcular_markowitz(df_close: pd.DataFrame) -> dict:
    returns      = np.log(df_close / df_close.shift(1)).dropna(how='all')
    mean_returns = returns.mean() * 12
    cov_matrix   = returns.cov() * 12
    cols = mean_returns.index.tolist()
    n    = len(cols)
    w_eq = np.array([1/n]*n)

    def port_ret(w): return float(np.dot(w, mean_returns))
    def port_var(w): return float(np.dot(w.T, np.dot(cov_matrix, w)))
    def port_vol(w): return np.sqrt(port_var(w))
    def sharpe(w, rf=0.0):
        v = port_vol(w)
        return (port_ret(w) - rf) / v if v > 0 else 0.0

    restr  = ({'type':'eq','fun': lambda w: np.sum(w)-1},)
    bounds = tuple((0,1) for _ in range(n))

    w_min = minimize(port_var,          w_eq, method='SLSQP', bounds=bounds, constraints=restr).x
    w_max = minimize(lambda w:-sharpe(w), w_eq, method='SLSQP', bounds=bounds, constraints=restr).x

    estadisticas = pd.DataFrame({
        "Ticker":              cols,
        "Retorno esperado":    mean_returns.values.round(4),
        "Varianza":            np.diag(cov_matrix.values).round(4),
        "Desviación estándar": np.sqrt(np.diag(cov_matrix.values)).round(4),
        "Proporción":          (mean_returns.values / mean_returns.sum()).round(4)
                               if mean_returns.sum() != 0 else np.nan
    })

    pesos = pd.DataFrame({
        "Ticker":          cols,
        "Peso Igual":      np.round(w_eq,  4),
        "Peso Min Var":    np.round(w_min, 4),
        "Peso Max Sharpe": np.round(w_max, 4),
    })

    resumen = pd.DataFrame([
        {"Tipo":"Cartera Equilibrada", "Retorno":round(port_ret(w_eq),4),
         "Volatilidad":round(port_vol(w_eq),4), "Sharpe":round(sharpe(w_eq),4)},
        {"Tipo":"Mínima Varianza",     "Retorno":round(port_ret(w_min),4),
         "Volatilidad":round(port_vol(w_min),4),"Sharpe":round(sharpe(w_min),4)},
        {"Tipo":"Máximo Sharpe",       "Retorno":round(port_ret(w_max),4),
         "Volatilidad":round(port_vol(w_max),4),"Sharpe":round(sharpe(w_max),4)},
    ])

    return {
        "estadisticas": estadisticas,
        "pesos":        pesos,
        "resumen":      resumen,
        "corr":         returns.corr().round(4),
        "cov":          cov_matrix.round(6),
        "cols":         cols,
        "w_eq":         w_eq,
        "w_min":        w_min,
        "w_max":        w_max,
        "mean_returns": mean_returns,
        "cov_matrix":   cov_matrix,
        "port_ret":     port_ret,
        "port_vol":     port_vol,
        "sharpe":       sharpe,
    }

def frontera_eficiente(mk: dict, n_puntos: int = 200) -> pd.DataFrame:
    """Genera puntos de la frontera eficiente para graficar."""
    mean_returns = mk["mean_returns"]
    cov_matrix   = mk["cov_matrix"]
    cols = mk["cols"]
    n    = len(cols)
    w0   = mk["w_eq"]
    restr  = ({'type':'eq','fun': lambda w: np.sum(w)-1},)
    bounds = tuple((0,1) for _ in range(n))

    ret_min = float(mean_returns.min())
    ret_max = float(mean_returns.max())
    targets = np.linspace(ret_min, ret_max, n_puntos)

    puntos = []
    for target in targets:
        restr_t = (
            {'type':'eq','fun': lambda w: np.sum(w)-1},
            {'type':'eq','fun': lambda w, t=target: np.dot(w, mean_returns)-t}
        )
        res = minimize(
            lambda w: float(np.dot(w.T, np.dot(cov_matrix, w))),
            w0, method='SLSQP', bounds=bounds, constraints=restr_t
        )
        if res.success:
            vol = np.sqrt(res.fun)
            sr  = (target / vol) if vol > 0 else 0
            puntos.append({"Retorno": round(target,4), "Volatilidad": round(vol,4), "Sharpe": round(sr,4)})

    return pd.DataFrame(puntos)

# =========================================
# DÓLAR CCL
# =========================================
@st.cache_data(ttl=1800, show_spinner=False)
def obtener_dolar_ccl() -> float:
    fuentes = [
        {"url":"https://dolarapi.com/v1/dolares",
         "parser": lambda d: next((x["venta"] for x in d if x["casa"]=="contadoconliqui"),None)},
        {"url":"https://api.argentinadatos.com/v1/cotizaciones/dolares",
         "parser": lambda d: next((x["venta"] for x in d if x["casa"]=="contadoconliqui"),None)},
        {"url":"https://www.dolarsi.com/api/api.php?type=valoresprincipales",
         "parser": lambda d: next((float(x["casa"]["venta"].replace(",","."))
                                   for x in d if "contado con liqui" in x["casa"]["nombre"].lower()),None)},
    ]
    for f in fuentes:
        try:
            r = requests.get(f["url"], timeout=8, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200:
                v = f["parser"](r.json())
                if v:
                    return float(v)
        except Exception:
            pass
    return 1200.0  # fallback

# =========================================
# RATIOS CEDEAR
# =========================================
_RATIOS_CEDEAR: dict = {}

def cargar_ratios_cedear(csv_path: str) -> dict:
    global _RATIOS_CEDEAR
    try:
        df = pd.read_csv(csv_path)
        _RATIOS_CEDEAR = dict(zip(df["Ticker"], df["Ratio"]))
    except Exception:
        _RATIOS_CEDEAR = {}
    return _RATIOS_CEDEAR

def get_ratio_cedear(ticker: str) -> float | None:
    return _RATIOS_CEDEAR.get(ticker.upper())

def analizar_cedear(ticker: str, ccl: float) -> dict:
    info       = obtener_fundamentales(ticker)
    precio_usd = info.get("currentPrice")
    ratio      = get_ratio_cedear(ticker)

    # [BUG CORREGIDO] Precio ARS del CEDEAR en BYMA (ticker + ".BA")
    # Antes: se usaba currentPrice del ticker internacional (precio en USD)
    # Ahora: se busca el ticker con sufijo .BA que cotiza en pesos en BYMA
    precio_ars = None
    try:
        info_ba = yf.Ticker(ticker.upper() + ".BA").info
        precio_ars = info_ba.get("currentPrice") or info_ba.get("regularMarketPrice")
        if precio_ars and float(precio_ars) < 10:
            precio_ars = None
    except Exception:
        precio_ars = None

    valor_impl = (precio_usd / ratio) * ccl if precio_usd and ratio else None
    dif_pct    = round((precio_ars - valor_impl) / valor_impl * 100, 2) \
                 if precio_ars and valor_impl else None
    if precio_ars and valor_impl:
        estado = "🟢 Barato" if precio_ars < valor_impl else "🔴 Caro"
    elif valor_impl and not precio_ars:
        estado = "⚪ Sin precio BYMA"
    else:
        estado = "⚪ Sin datos"

    return {
        "Ticker":                       ticker,
        "Nombre":                       info.get("Nombre"),
        "Tipo":                         cedear_mapper.clasificar_ticker(ticker),
        "Precio USD":                   round(precio_usd, 2) if precio_usd else None,
        "Ratio CEDEAR":                 ratio,
        "Dólar CCL":                    ccl,
        "Valor implícito (ARS)":        round(valor_impl, 2) if valor_impl else None,
        "Precio CEDEAR (ARS)":          round(precio_ars, 2) if precio_ars else None,
        "Diferencia (%)":               dif_pct,
        "Estado":                       estado,
    }

# =========================================
# FILTRO FUNDAMENTAL
# =========================================
def filtrar_por_fundamentales(tickers, margen_min, roic_min, de_max):
    filtrados, reporte = [], []
    for t in tickers:
        d      = obtener_fundamentales(t)
        margen = d.get("profitMargins")
        roic   = d.get("ROIC_proxy")
        deuda  = d.get("debtToEquity")
        motivo = []
        if margen is None or roic is None or deuda is None:
            motivo.append("Datos incompletos")
        else:
            if margen <= margen_min:  motivo.append(f"Margen ≤ {margen_min*100:.0f}%")
            if roic   <= roic_min:    motivo.append(f"ROIC ≤ {roic_min*100:.0f}%")
            if deuda  >= de_max*100:  motivo.append(f"D/E ≥ {de_max:.2f}")
        if motivo:
            d["Motivo"] = ", ".join(motivo)
            reporte.append(d)
        else:
            filtrados.append(t)
    if not filtrados:
        filtrados = tickers[:]
    return filtrados, pd.DataFrame(reporte)