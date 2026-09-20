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

def score_buffett(info: dict) -> dict:
    """
    Score Buffett completo 0-100 con desglose por categoría.
    Basado en los principios de Warren Buffett y Charlie Munger.
    Retorna dict con score total, por categoría y detalle de cada check.
    """
    detalles = []
    score = 0

    # ── 1. RENTABILIDAD (30 pts) ──────────────────────────────────────────────
    # Margen Neto > 20% (ventaja competitiva fuerte)
    margen = info.get("profitMargins")
    if margen is not None:
        if margen > 0.20:
            score += 12; detalles.append(("Margen Neto", f"{margen:.1%}", "✅", 12, "Excelente (>20%)"))
        elif margen > 0.10:
            score += 6;  detalles.append(("Margen Neto", f"{margen:.1%}", "🟡", 6, "Aceptable (>10%)"))
        else:
            detalles.append(("Margen Neto", f"{margen:.1%}", "❌", 0, "Bajo (<10%)"))
    else:
        detalles.append(("Margen Neto", "—", "⚪", 0, "Sin datos"))

    # ROE > 15% (retorno sobre patrimonio)
    roe = info.get("ROE")
    if roe is not None:
        if roe > 0.20:
            score += 10; detalles.append(("ROE", f"{roe:.1%}", "✅", 10, "Excelente (>20%)"))
        elif roe > 0.15:
            score += 6;  detalles.append(("ROE", f"{roe:.1%}", "🟡", 6, "Bueno (>15%)"))
        else:
            detalles.append(("ROE", f"{roe:.1%}", "❌", 0, "Bajo (<15%)"))
    else:
        detalles.append(("ROE", "—", "⚪", 0, "Sin datos"))

    # ROIC > 15% (retorno sobre capital invertido)
    roic = info.get("ROIC_proxy")
    if roic is not None:
        if roic > 0.15:
            score += 8;  detalles.append(("ROIC", f"{roic:.1%}", "✅", 8, "Excelente (>15%)"))
        elif roic > 0.10:
            score += 4;  detalles.append(("ROIC", f"{roic:.1%}", "🟡", 4, "Aceptable (>10%)"))
        else:
            detalles.append(("ROIC", f"{roic:.1%}", "❌", 0, "Bajo (<10%)"))
    else:
        detalles.append(("ROIC", "—", "⚪", 0, "Sin datos"))

    # ── 2. CRECIMIENTO (20 pts) ───────────────────────────────────────────────
    # Crecimiento de ingresos > 10%
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        if rev_growth > 0.15:
            score += 10; detalles.append(("Crec. Ingresos", f"{rev_growth:.1%}", "✅", 10, "Fuerte (>15%)"))
        elif rev_growth > 0.08:
            score += 6;  detalles.append(("Crec. Ingresos", f"{rev_growth:.1%}", "🟡", 6, "Moderado (>8%)"))
        else:
            detalles.append(("Crec. Ingresos", f"{rev_growth:.1%}", "❌", 0, "Lento (<8%)"))
    else:
        detalles.append(("Crec. Ingresos", "—", "⚪", 0, "Sin datos"))

    # Crecimiento de ganancias > 10%
    earn_growth = info.get("earningsGrowth")
    if earn_growth is not None:
        if earn_growth > 0.15:
            score += 10; detalles.append(("Crec. Ganancias", f"{earn_growth:.1%}", "✅", 10, "Fuerte (>15%)"))
        elif earn_growth > 0.08:
            score += 5;  detalles.append(("Crec. Ganancias", f"{earn_growth:.1%}", "🟡", 5, "Moderado (>8%)"))
        else:
            detalles.append(("Crec. Ganancias", f"{earn_growth:.1%}", "❌", 0, "Lento (<8%)"))
    else:
        detalles.append(("Crec. Ganancias", "—", "⚪", 0, "Sin datos"))

    # ── 3. SOLIDEZ FINANCIERA (25 pts) ────────────────────────────────────────
    # Deuda/Equity < 0.5 (baja deuda)
    de = info.get("debtToEquity")
    if de is not None:
        de_norm = de / 100 if de > 5 else de  # normalizar si viene en %
        if de_norm < 0.30:
            score += 10; detalles.append(("Deuda/Equity", f"{de_norm:.2f}x", "✅", 10, "Muy baja (<0.30x)"))
        elif de_norm < 0.80:
            score += 5;  detalles.append(("Deuda/Equity", f"{de_norm:.2f}x", "🟡", 5, "Moderada (<0.80x)"))
        else:
            detalles.append(("Deuda/Equity", f"{de_norm:.2f}x", "❌", 0, "Alta (>0.80x)"))
    else:
        detalles.append(("Deuda/Equity", "—", "⚪", 0, "Sin datos"))

    # Current Ratio > 1.5 (liquidez)
    cr = info.get("currentRatio")
    if cr is not None:
        if cr > 2.0:
            score += 8;  detalles.append(("Current Ratio", f"{cr:.2f}x", "✅", 8, "Excelente (>2.0x)"))
        elif cr > 1.5:
            score += 5;  detalles.append(("Current Ratio", f"{cr:.2f}x", "🟡", 5, "Bueno (>1.5x)"))
        else:
            detalles.append(("Current Ratio", f"{cr:.2f}x", "❌", 0, "Bajo (<1.5x)"))
    else:
        detalles.append(("Current Ratio", "—", "⚪", 0, "Sin datos"))

    # Free Cash Flow positivo
    fcf = info.get("freeCashflow")
    if fcf is not None:
        if fcf > 0:
            score += 7;  detalles.append(("Free Cash Flow", f"${fcf/1e9:.1f}B", "✅", 7, "Positivo"))
        else:
            detalles.append(("Free Cash Flow", f"${fcf/1e9:.1f}B", "❌", 0, "Negativo"))
    else:
        detalles.append(("Free Cash Flow", "—", "⚪", 0, "Sin datos"))

    # ── 4. VALUACIÓN (15 pts) ─────────────────────────────────────────────────
    # P/E Forward razonable
    pe = info.get("forwardPE")
    if pe is not None and pe > 0:
        if pe < 15:
            score += 8;  detalles.append(("P/E Forward", f"{pe:.1f}x", "✅", 8, "Barato (<15x)"))
        elif pe < 25:
            score += 4;  detalles.append(("P/E Forward", f"{pe:.1f}x", "🟡", 4, "Razonable (<25x)"))
        else:
            detalles.append(("P/E Forward", f"{pe:.1f}x", "❌", 0, "Caro (>25x)"))
    else:
        detalles.append(("P/E Forward", "—", "⚪", 0, "Sin datos"))

    # Price to Book < 3
    pb = info.get("priceToBook")
    if pb is not None and pb > 0:
        if pb < 1.5:
            score += 7;  detalles.append(("Price/Book", f"{pb:.2f}x", "✅", 7, "Muy barato (<1.5x)"))
        elif pb < 3.0:
            score += 3;  detalles.append(("Price/Book", f"{pb:.2f}x", "🟡", 3, "Razonable (<3x)"))
        else:
            detalles.append(("Price/Book", f"{pb:.2f}x", "❌", 0, "Caro (>3x)"))
    else:
        detalles.append(("Price/Book", "—", "⚪", 0, "Sin datos"))

    # ── 5. MOAT / VENTAJA COMPETITIVA (10 pts) ────────────────────────────────
    # Margen Bruto > 40% (pricing power)
    gm = info.get("grossMargins")
    if gm is not None:
        if gm > 0.50:
            score += 6;  detalles.append(("Margen Bruto", f"{gm:.1%}", "✅", 6, "Moat fuerte (>50%)"))
        elif gm > 0.35:
            score += 3;  detalles.append(("Margen Bruto", f"{gm:.1%}", "🟡", 3, "Moat moderado (>35%)"))
        else:
            detalles.append(("Margen Bruto", f"{gm:.1%}", "❌", 0, "Sin moat claro (<35%)"))
    else:
        detalles.append(("Margen Bruto", "—", "⚪", 0, "Sin datos"))

    # Margen Operativo > 15%
    om = info.get("operatingMargins")
    if om is not None:
        if om > 0.20:
            score += 4;  detalles.append(("Margen Operativo", f"{om:.1%}", "✅", 4, "Excelente (>20%)"))
        elif om > 0.12:
            score += 2;  detalles.append(("Margen Operativo", f"{om:.1%}", "🟡", 2, "Bueno (>12%)"))
        else:
            detalles.append(("Margen Operativo", f"{om:.1%}", "❌", 0, "Bajo (<12%)"))
    else:
        detalles.append(("Margen Operativo", "—", "⚪", 0, "Sin datos"))

    score = min(score, 100)

    # Clasificación final
    if score >= 75:
        clasificacion = "🟢 Excelente — Buffett lo compraría"
        color = "#00c896"
    elif score >= 55:
        clasificacion = "🟡 Bueno — Vale la pena analizar"
        color = "#f7a34f"
    elif score >= 35:
        clasificacion = "🟠 Regular — Requiere más análisis"
        color = "#f7a34f"
    else:
        clasificacion = "🔴 Débil — No cumple criterios Buffett"
        color = "#f74f4f"

    return {
        "score":         score,
        "clasificacion": clasificacion,
        "color":         color,
        "detalles":      detalles,
        "rentabilidad":  sum(d[3] for d in detalles[:3]),
        "crecimiento":   sum(d[3] for d in detalles[3:5]),
        "solidez":       sum(d[3] for d in detalles[5:8]),
        "valuacion":     sum(d[3] for d in detalles[8:10]),
        "moat":          sum(d[3] for d in detalles[10:]),
    }

def score_fundamental(info: dict) -> float:
    """Score 0-100 simplificado (compatibilidad hacia atrás)."""
    return score_buffett(info)["score"]

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
# MARKOWITZ — MÉTRICAS AVANZADAS
# =========================================

def calcular_beta_cartera(df_close: pd.DataFrame, pesos: np.ndarray,
                           benchmark: str = "SPY") -> float | None:
    """
    Calcula el Beta de la cartera vs un benchmark (SPY por defecto).
    Beta > 1: más volátil que el mercado. Beta < 1: más defensiva.
    """
    try:
        tickers_con_bench = list(df_close.columns) + [benchmark]
        df_bench = yf.download([benchmark], period="2y", interval="1mo",
                                progress=False, auto_adjust=True)["Close"]
        if df_bench.empty:
            return None
        df_combined = df_close.join(df_bench.rename(benchmark), how="inner")
        returns = np.log(df_combined / df_combined.shift(1)).dropna()
        bench_ret = returns[benchmark]
        port_ret_series = returns[list(df_close.columns)].dot(pesos)
        cov_pb = np.cov(port_ret_series, bench_ret)[0][1]
        var_b  = np.var(bench_ret)
        return round(cov_pb / var_b, 3) if var_b > 0 else None
    except Exception:
        return None


def calcular_var(df_close: pd.DataFrame, pesos: np.ndarray,
                 confianza: float = 0.95, horizonte: int = 21) -> dict:
    """
    Calcula el Value at Risk (VaR) histórico y paramétrico.
    confianza: 0.95 = 95%, 0.99 = 99%
    horizonte: días (21 = 1 mes, 252 = 1 año)
    Retorna dict con VaR histórico y paramétrico en %.
    """
    try:
        returns = np.log(df_close / df_close.shift(1)).dropna()
        port_returns = returns.dot(pesos)
        # VaR histórico
        var_hist = float(np.percentile(port_returns, (1 - confianza) * 100))
        var_hist_h = var_hist * np.sqrt(horizonte)
        # VaR paramétrico (distribución normal)
        from scipy import stats
        z = stats.norm.ppf(1 - confianza)
        mu  = port_returns.mean()
        sig = port_returns.std()
        var_param   = float(mu + z * sig)
        var_param_h = var_param * np.sqrt(horizonte)
        return {
            "var_hist_diario":   round(var_hist * 100, 3),
            "var_hist_mensual":  round(var_hist_h * 100, 3),
            "var_param_diario":  round(var_param * 100, 3),
            "var_param_mensual": round(var_param_h * 100, 3),
            "confianza":         confianza,
        }
    except Exception:
        return {}


def calcular_sortino(df_close: pd.DataFrame, pesos: np.ndarray,
                     rf_anual: float = 0.0) -> float | None:
    """
    Calcula el Sortino Ratio (penaliza solo la volatilidad negativa).
    Sortino > 1: buena relación retorno/riesgo bajista.
    Sortino > 2: excelente.
    """
    try:
        returns = np.log(df_close / df_close.shift(1)).dropna()
        port_returns = returns.dot(pesos)
        rf_mensual = rf_anual / 12
        exceso = port_returns - rf_mensual
        downside = exceso[exceso < 0]
        downside_std = np.sqrt((downside ** 2).mean()) * np.sqrt(12)
        ret_anual = port_returns.mean() * 12
        if downside_std == 0:
            return None
        return round((ret_anual - rf_anual) / downside_std, 3)
    except Exception:
        return None


def calcular_max_drawdown(df_close: pd.DataFrame, pesos: np.ndarray) -> float | None:
    """
    Calcula el Maximum Drawdown de la cartera.
    Representa la mayor caída desde un pico hasta un valle.
    """
    try:
        port_value = (df_close * pesos).sum(axis=1)
        port_value = port_value / port_value.iloc[0]
        rolling_max = port_value.cummax()
        drawdown = (port_value - rolling_max) / rolling_max
        return round(float(drawdown.min()) * 100, 2)
    except Exception:
        return None


def calcular_metricas_avanzadas(df_close: pd.DataFrame, mk: dict) -> dict:
    """
    Calcula todas las métricas avanzadas de Markowitz para los 3 portafolios.
    Retorna dict con métricas para cada tipo de cartera.
    """
    resultados = {}
    carteras = {
        "Equilibrada":   mk["w_eq"],
        "Min. Varianza": mk["w_min"],
        "Max. Sharpe":   mk["w_max"],
    }
    for nombre, pesos in carteras.items():
        var_data = calcular_var(df_close, pesos)
        sortino  = calcular_sortino(df_close, pesos)
        mdd      = calcular_max_drawdown(df_close, pesos)
        resultados[nombre] = {
            "VaR 95% diario (%)":   var_data.get("var_hist_diario"),
            "VaR 95% mensual (%)":  var_data.get("var_hist_mensual"),
            "Sortino Ratio":        sortino,
            "Max Drawdown (%)":     mdd,
        }
    return resultados


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
