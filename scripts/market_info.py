"""
market_info.py — Módulo de información de mercado por ticker.
=============================================================
Obtiene desde fuentes públicas:
  1. Noticias recientes        → Yahoo Finance RSS
  2. Ratings de analistas      → Yahoo Finance (yfinance)
  3. Precio objetivo consenso  → Yahoo Finance (yfinance)
  4. Earnings / dividendos     → Yahoo Finance (yfinance)
  5. Datos de ETF              → Yahoo Finance (yfinance)
  6. Resumen ejecutivo         → Yahoo Finance info dict

Fuentes utilizadas:
  - Yahoo Finance (yfinance + RSS feed)
  - Finviz (scraping básico de ratings)
  - Investing.com (próximos earnings via scraping)

Sin API keys requeridas — todo público.
"""

import requests
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import yfinance as yf

# ═══════════════════════════════════════════════════════════════════════════════
# TIPOS DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Noticia:
    titulo: str
    fuente: str
    fecha: str
    url: str
    resumen: str = ""

@dataclass
class RatingAnalista:
    firma: str
    accion: str          # "Buy", "Hold", "Sell", "Upgrade", "Downgrade"
    precio_objetivo: Optional[float]
    fecha: str

@dataclass
class DatosETF:
    es_etf: bool
    categoria: str
    aum_usd: Optional[float]          # Assets Under Management
    yield_anual: Optional[float]
    retorno_ytd: Optional[float]
    retorno_1y: Optional[float]
    retorno_3y: Optional[float]
    retorno_5y: Optional[float]
    beta_3y: Optional[float]
    num_holdings: Optional[int]
    indice_seguido: str
    top_holdings: list[dict]          # [{"ticker": "AAPL", "peso": 0.12}]
    clasificacion_riesgo: str         # "Defensivo" | "Moderado" | "Agresivo"
    rol_en_cartera: str               # "Diversificador" | "Amplificador" | "Defensivo"

@dataclass
class ProximoEvento:
    tipo: str                         # "earnings" | "dividendo" | "split"
    fecha: str
    descripcion: str

@dataclass
class InfoMercado:
    ticker: str
    nombre: str
    precio_actual: Optional[float]
    moneda: str
    es_etf: bool

    # Noticias
    noticias: list[Noticia]

    # Analistas (solo acciones)
    ratings: list[RatingAnalista]
    precio_objetivo_consenso: Optional[float]
    precio_objetivo_alto: Optional[float]
    precio_objetivo_bajo: Optional[float]
    recomendacion_consenso: str       # "strongBuy" | "buy" | "hold" | "sell"
    num_analistas: Optional[int]
    upside_potencial: Optional[float] # % upside vs precio actual

    # Earnings y dividendos
    proximo_earnings: Optional[str]
    eps_estimado: Optional[float]
    dividendo_anual: Optional[float]
    yield_dividendo: Optional[float]
    proximos_eventos: list[ProximoEvento]

    # ETF (solo si es ETF)
    etf: Optional[DatosETF]

    # Resumen
    descripcion_empresa: str
    pais: str
    empleados: Optional[int]
    sitio_web: str


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def _get(url: str, timeout: int = 10) -> Optional[requests.Response]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception:
        pass
    return None

def _fmt_fecha(ts) -> str:
    """Convierte timestamp Unix o string a fecha legible."""
    if ts is None:
        return "—"
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
        return str(ts)
    except Exception:
        return str(ts)

def _fmt_monto(v: Optional[float], sufijo: str = "") -> str:
    if v is None:
        return "—"
    try:
        v = float(v)
        if abs(v) >= 1e12:
            return f"${v/1e12:.1f}T{sufijo}"
        if abs(v) >= 1e9:
            return f"${v/1e9:.1f}B{sufijo}"
        if abs(v) >= 1e6:
            return f"${v/1e6:.1f}M{sufijo}"
        return f"${v:,.0f}{sufijo}"
    except Exception:
        return "—"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. NOTICIAS — Yahoo Finance RSS
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_noticias_yahoo(ticker: str, max_noticias: int = 8) -> list[Noticia]:
    """
    Obtiene noticias recientes desde el RSS feed de Yahoo Finance.
    No requiere API key.
    """
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    r   = _get(url)
    if not r:
        return []

    noticias = []
    try:
        root = ET.fromstring(r.content)
        ns   = {"media": "http://search.yahoo.com/mrss/"}
        items = root.findall(".//item")
        for item in items[:max_noticias]:
            titulo  = item.findtext("title", "").strip()
            link    = item.findtext("link", "").strip()
            fecha   = item.findtext("pubDate", "").strip()
            desc    = item.findtext("description", "").strip()
            fuente  = item.findtext("source", "Yahoo Finance").strip()

            # Limpiar HTML del resumen
            desc = re.sub(r"<[^>]+>", "", desc)[:300]

            # Formatear fecha
            try:
                dt = datetime.strptime(fecha, "%a, %d %b %Y %H:%M:%S %z")
                fecha_fmt = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                fecha_fmt = fecha[:16]

            noticias.append(Noticia(
                titulo=titulo,
                fuente=fuente or "Yahoo Finance",
                fecha=fecha_fmt,
                url=link,
                resumen=desc
            ))
    except Exception:
        pass

    return noticias


# ═══════════════════════════════════════════════════════════════════════════════
# 2. RATINGS DE ANALISTAS — yfinance
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_ratings(ticker: str, max_ratings: int = 10) -> list[RatingAnalista]:
    """
    Obtiene el historial de ratings de analistas desde Yahoo Finance.
    Compatible con yfinance 0.2.x que usa upgrades_downgrades o recommendations.
    """
    t = yf.Ticker(ticker)
    ratings = []

    # Método 1: upgrades_downgrades (yfinance >= 0.2.40)
    try:
        df = t.upgrades_downgrades
        if df is not None and not df.empty:
            df = df.sort_index(ascending=False).head(max_ratings)
            for idx, row in df.iterrows():
                fecha = idx.strftime("%d/%m/%Y") if hasattr(idx, "strftime") else str(idx)[:10]
                firma  = str(row.get("Firm", "—")).strip()
                accion = str(row.get("ToGrade", row.get("Action", "—"))).strip()
                precio_obj = row.get("PriceTarget") or row.get("priceTarget")
                if firma and firma != "nan" and accion and accion != "nan":
                    ratings.append(RatingAnalista(
                        firma=firma,
                        accion=accion,
                        precio_objetivo=float(precio_obj) if precio_obj else None,
                        fecha=fecha
                    ))
            if ratings:
                return ratings
    except Exception:
        pass

    # Método 2: recommendations (formato antiguo)
    try:
        df = t.recommendations
        if df is None or df.empty:
            return []
        # En yfinance 0.2.x recommendations puede tener formato distinto
        # Intentar detectar columnas disponibles
        cols = df.columns.tolist()
        firma_col  = next((c for c in cols if "firm" in c.lower()), None)
        accion_col = next((c for c in cols if "grade" in c.lower()
                           or "action" in c.lower()), None)
        precio_col = next((c for c in cols if "price" in c.lower()
                           or "target" in c.lower()), None)

        if not firma_col and not accion_col:
            return []

        df = df.sort_index(ascending=False).head(max_ratings)
        for idx, row in df.iterrows():
            fecha = idx.strftime("%d/%m/%Y") if hasattr(idx, "strftime") else str(idx)[:10]
            firma  = str(row.get(firma_col,  "—")).strip() if firma_col  else "—"
            accion = str(row.get(accion_col, "—")).strip() if accion_col else "—"
            precio_obj = row.get(precio_col) if precio_col else None

            if firma != "nan" and accion != "nan" and firma != "—":
                ratings.append(RatingAnalista(
                    firma=firma,
                    accion=accion,
                    precio_objetivo=float(precio_obj) if precio_obj else None,
                    fecha=fecha
                ))
    except Exception:
        pass

    return ratings


def obtener_consenso_analistas(info: dict) -> dict:
    """Extrae datos de consenso de analistas del dict de yfinance."""
    precio_actual = info.get("currentPrice") or info.get("regularMarketPrice")
    precio_obj    = info.get("targetMeanPrice")
    precio_alto   = info.get("targetHighPrice")
    precio_bajo   = info.get("targetLowPrice")
    recomendacion = info.get("recommendationKey", "—")
    num_analistas = info.get("numberOfAnalystOpinions")

    upside = None
    if precio_actual and precio_obj:
        try:
            upside = (float(precio_obj) - float(precio_actual)) / float(precio_actual) * 100
        except Exception:
            pass

    return {
        "precio_objetivo_consenso": precio_obj,
        "precio_objetivo_alto":     precio_alto,
        "precio_objetivo_bajo":     precio_bajo,
        "recomendacion_consenso":   recomendacion,
        "num_analistas":            num_analistas,
        "upside_potencial":         round(upside, 2) if upside else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DETECCIÓN Y MÉTRICAS DE ETF
# ═══════════════════════════════════════════════════════════════════════════════

# ETFs conocidos con su índice de referencia
ETF_INDICES = {
    "SPY":  "S&P 500",       "IVV":  "S&P 500",
    "VOO":  "S&P 500",       "QQQ":  "NASDAQ-100",
    "DIA":  "Dow Jones",     "IWM":  "Russell 2000",
    "XLF":  "S&P Financials","XLP":  "S&P Consumer Staples",
    "XLV":  "S&P Health Care","XLC": "S&P Communication",
    "XLE":  "S&P Energy",    "XLI":  "S&P Industrials",
    "XLK":  "S&P Technology","XLY":  "S&P Consumer Disc.",
    "XLB":  "S&P Materials", "XLRE": "S&P Real Estate",
    "XLU":  "S&P Utilities", "GLD":  "Gold",
    "SLV":  "Silver",        "TLT":  "US 20Y Treasuries",
    "HYG":  "High Yield Corp","LQD": "Investment Grade Corp",
    "EEM":  "MSCI Emerging", "EFA":  "MSCI EAFE",
    "VWO":  "MSCI Emerging", "ARKK": "ARK Innovation",
    "IBIT": "Bitcoin",       "URA":  "Uranium",
    "SNOW": "—",
}

def _clasificar_etf(beta: Optional[float], categoria: str) -> tuple[str, str]:
    """Clasifica el ETF por riesgo y rol en cartera."""
    cat_lower = (categoria or "").lower()

    # Por categoría
    if any(x in cat_lower for x in ["bond", "treasury", "fixed", "income"]):
        return "Defensivo", "Diversificador"
    if any(x in cat_lower for x in ["gold", "commodity", "real estate"]):
        return "Moderado", "Diversificador"
    if any(x in cat_lower for x in ["innovation", "ark", "bitcoin", "crypto", "uranium"]):
        return "Agresivo", "Amplificador"

    # Por beta
    if beta is not None:
        if beta < 0.7:
            return "Defensivo", "Diversificador"
        elif beta < 1.1:
            return "Moderado", "Amplificador"
        else:
            return "Agresivo", "Amplificador"

    return "Moderado", "Amplificador"

def obtener_datos_etf(ticker: str, info: dict) -> Optional[DatosETF]:
    """
    Detecta si el ticker es un ETF y obtiene sus métricas específicas.
    Un ticker es ETF si quoteType == 'ETF' o si está en la lista conocida.
    """
    quote_type = info.get("quoteType", "")
    es_etf = (quote_type == "ETF") or (ticker.upper() in ETF_INDICES)

    if not es_etf:
        return None

    categoria    = info.get("category") or info.get("fundFamily") or "—"
    aum          = info.get("totalAssets")
    yield_anual  = info.get("yield") or info.get("dividendYield")
    ret_ytd      = info.get("ytdReturn")
    ret_1y       = info.get("oneYearReturn") or info.get("52WeekChange")
    ret_3y       = info.get("threeYearAverageReturn")
    ret_5y       = info.get("fiveYearAverageReturn")
    beta_3y      = info.get("beta3Year") or info.get("beta")
    num_holdings = info.get("holdings") or info.get("numberOfHoldings")
    indice       = ETF_INDICES.get(ticker.upper(), info.get("legalType", "—"))

    # Top holdings desde yfinance
    top_holdings = []
    try:
        t    = yf.Ticker(ticker)
        hold = t.funds_data.top_holdings if hasattr(t, "funds_data") else None
        if hold is not None and not hold.empty:
            for _, row in hold.head(10).iterrows():
                top_holdings.append({
                    "ticker": str(row.get("Symbol", row.get("symbol", "—"))),
                    "nombre": str(row.get("Name",   row.get("name",   "—"))),
                    "peso":   float(row.get("Holding Percent",
                                   row.get("holdingPercent", 0))) * 100
                })
    except Exception:
        pass

    riesgo, rol = _clasificar_etf(beta_3y, categoria)

    return DatosETF(
        es_etf=True,
        categoria=categoria,
        aum_usd=aum,
        yield_anual=yield_anual,
        retorno_ytd=ret_ytd,
        retorno_1y=ret_1y,
        retorno_3y=ret_3y,
        retorno_5y=ret_5y,
        beta_3y=beta_3y,
        num_holdings=num_holdings,
        indice_seguido=indice,
        top_holdings=top_holdings,
        clasificacion_riesgo=riesgo,
        rol_en_cartera=rol
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PRÓXIMOS EVENTOS (earnings, dividendos)
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_proximos_eventos(ticker: str, info: dict) -> list[ProximoEvento]:
    """Obtiene próximos earnings y dividendos desde yfinance."""
    eventos = []

    # Próximo earnings
    earnings_ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
    if earnings_ts:
        fecha = _fmt_fecha(earnings_ts)
        eps_est = info.get("epsForward") or info.get("epsCurrentYear")
        desc = f"EPS estimado: ${eps_est:.2f}" if eps_est else "Fecha de resultados"
        eventos.append(ProximoEvento(
            tipo="earnings",
            fecha=fecha,
            descripcion=desc
        ))

    # Próximo dividendo
    div_date = info.get("exDividendDate")
    div_rate  = info.get("dividendRate")
    if div_date:
        fecha = _fmt_fecha(div_date)
        desc  = f"Dividendo: ${div_rate:.2f}/acción" if div_rate else "Ex-dividendo"
        eventos.append(ProximoEvento(
            tipo="dividendo",
            fecha=fecha,
            descripcion=desc
        ))

    return eventos


# ═══════════════════════════════════════════════════════════════════════════════
# 5. FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_info_mercado(ticker: str,
                          max_noticias: int = 8,
                          incluir_ratings: bool = True) -> InfoMercado:
    """
    Función principal. Obtiene toda la información de mercado para un ticker.

    Uso:
        import market_info
        info = market_info.obtener_info_mercado("AAPL")
        print(info.precio_objetivo_consenso)
        print(info.noticias[0].titulo)
        print(info.etf)  # None si no es ETF
    """
    t    = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    precio_actual = info.get("currentPrice") or info.get("regularMarketPrice")
    nombre        = info.get("longName") or info.get("shortName") or ticker
    moneda        = info.get("currency", "USD")
    quote_type    = info.get("quoteType", "")
    es_etf        = (quote_type == "ETF") or (ticker.upper() in ETF_INDICES)

    # Noticias
    noticias = obtener_noticias_yahoo(ticker, max_noticias)

    # Ratings y consenso (solo acciones)
    ratings  = []
    consenso = {
        "precio_objetivo_consenso": None,
        "precio_objetivo_alto":     None,
        "precio_objetivo_bajo":     None,
        "recomendacion_consenso":   "—",
        "num_analistas":            None,
        "upside_potencial":         None,
    }
    if incluir_ratings and not es_etf:
        ratings  = obtener_ratings(ticker)
        consenso = obtener_consenso_analistas(info)

    # ETF
    etf_data = obtener_datos_etf(ticker, info) if es_etf else None

    # Eventos
    eventos = obtener_proximos_eventos(ticker, info)

    return InfoMercado(
        ticker=ticker,
        nombre=nombre,
        precio_actual=precio_actual,
        moneda=moneda,
        es_etf=es_etf,
        noticias=noticias,
        ratings=ratings,
        precio_objetivo_consenso=consenso["precio_objetivo_consenso"],
        precio_objetivo_alto=consenso["precio_objetivo_alto"],
        precio_objetivo_bajo=consenso["precio_objetivo_bajo"],
        recomendacion_consenso=consenso["recomendacion_consenso"],
        num_analistas=consenso["num_analistas"],
        upside_potencial=consenso["upside_potencial"],
        proximo_earnings=eventos[0].fecha if eventos and eventos[0].tipo == "earnings" else None,
        eps_estimado=info.get("epsForward"),
        dividendo_anual=info.get("dividendRate"),
        yield_dividendo=info.get("dividendYield"),
        proximos_eventos=eventos,
        etf=etf_data,
        descripcion_empresa=info.get("longBusinessSummary", "")[:500],
        pais=info.get("country", "—"),
        empleados=info.get("fullTimeEmployees"),
        sitio_web=info.get("website", "—"),
    )


def obtener_info_multiples(tickers: list[str],
                            delay_seg: float = 0.5) -> dict[str, InfoMercado]:
    """
    Obtiene información de mercado para múltiples tickers.
    Incluye delay entre requests para no saturar Yahoo Finance.
    """
    resultados = {}
    for i, ticker in enumerate(tickers):
        print(f"  📰 Info mercado {ticker} ({i+1}/{len(tickers)})...")
        try:
            resultados[ticker] = obtener_info_mercado(ticker)
        except Exception as e:
            print(f"     ⚠️ Error {ticker}: {e}")
        if i < len(tickers) - 1:
            time.sleep(delay_seg)
    return resultados


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS PARA EXCEL / STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════════

def noticias_a_df(info_dict: dict[str, InfoMercado]) -> pd.DataFrame:
    """Convierte noticias de todos los tickers a un DataFrame."""
    rows = []
    for ticker, info in info_dict.items():
        for n in info.noticias:
            rows.append({
                "Ticker":  ticker,
                "Fecha":   n.fecha,
                "Fuente":  n.fuente,
                "Título":  n.titulo,
                "Resumen": n.resumen,
                "URL":     n.url,
            })
    return pd.DataFrame(rows)


def ratings_a_df(info_dict: dict[str, InfoMercado]) -> pd.DataFrame:
    """Convierte ratings de analistas a un DataFrame."""
    rows = []
    for ticker, info in info_dict.items():
        # Consenso
        rows.append({
            "Ticker":          ticker,
            "Firma":           "CONSENSO",
            "Acción":          info.recomendacion_consenso,
            "Precio objetivo": info.precio_objetivo_consenso,
            "Upside %":        info.upside_potencial,
            "N° analistas":    info.num_analistas,
            "Fecha":           "—",
        })
        for r in info.ratings:
            rows.append({
                "Ticker":          ticker,
                "Firma":           r.firma,
                "Acción":          r.accion,
                "Precio objetivo": r.precio_objetivo,
                "Upside %":        None,
                "N° analistas":    None,
                "Fecha":           r.fecha,
            })
    return pd.DataFrame(rows)


def etf_a_df(info_dict: dict[str, InfoMercado]) -> pd.DataFrame:
    """Convierte datos de ETFs a un DataFrame."""
    rows = []
    for ticker, info in info_dict.items():
        if not info.es_etf or not info.etf:
            continue
        e = info.etf
        rows.append({
            "Ticker":           ticker,
            "Nombre":           info.nombre,
            "Índice seguido":   e.indice_seguido,
            "Categoría":        e.categoria,
            "AUM":              _fmt_monto(e.aum_usd),
            "Yield anual":      e.yield_anual,
            "Ret. YTD":         e.retorno_ytd,
            "Ret. 1Y":          e.retorno_1y,
            "Ret. 3Y":          e.retorno_3y,
            "Ret. 5Y":          e.retorno_5y,
            "Beta 3Y":          e.beta_3y,
            "N° Holdings":      e.num_holdings,
            "Riesgo":           e.clasificacion_riesgo,
            "Rol en cartera":   e.rol_en_cartera,
        })
    return pd.DataFrame(rows)


def resumen_mercado_df(info_dict: dict[str, InfoMercado]) -> pd.DataFrame:
    """Resumen ejecutivo de información de mercado por ticker."""
    rows = []
    for ticker, info in info_dict.items():
        rows.append({
            "Ticker":              ticker,
            "Nombre":              info.nombre,
            "Tipo":                "ETF" if info.es_etf else "Acción",
            "País":                info.pais,
            "Precio actual":       info.precio_actual,
            "Moneda":              info.moneda,
            "Precio obj. consenso":info.precio_objetivo_consenso,
            "Upside %":            info.upside_potencial,
            "Recomendación":       info.recomendacion_consenso,
            "N° analistas":        info.num_analistas,
            "Próx. earnings":      info.proximo_earnings or "—",
            "EPS estimado":        info.eps_estimado,
            "Dividendo anual":     info.dividendo_anual,
            "Yield dividendo":     info.yield_dividendo,
            "Empleados":           info.empleados,
            "Web":                 info.sitio_web,
            "N° noticias":         len(info.noticias),
        })
    return pd.DataFrame(rows)


def obtener_fundamentales_completo(ticker: str) -> dict:
    """
    Versión mejorada de obtener_fundamentales() que detecta ETFs
    y retorna métricas apropiadas según el tipo de activo.
    Reemplaza a la función homónima en Historico_v3.py y core.py.
    """
    try:
        t    = yf.Ticker(ticker)
        info = t.info or {}
    except Exception:
        info = {}

    quote_type = info.get("quoteType", "")
    es_etf     = (quote_type == "ETF") or (ticker.upper() in ETF_INDICES)

    base = {
        "Ticker":       ticker,
        "Nombre":       info.get("longName") or info.get("shortName"),
        "Tipo":         "ETF" if es_etf else "Acción",
        "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
        "Sector":       info.get("sector"),
        "Industria":    info.get("industry"),
        "MarketCap":    info.get("marketCap") or info.get("totalAssets"),
        "Moneda":       info.get("currency", "USD"),
        "País":         info.get("country"),
    }

    if es_etf:
        # Métricas específicas de ETF
        base.update({
            # Fundamentales no aplican → None explícito con etiqueta
            "forwardPE":          None,
            "trailingPE":         info.get("trailingPE"),  # algunos ETFs lo tienen
            "priceToBook":        None,
            "enterpriseValue":    None,
            "enterpriseToEbitda": None,
            "quickRatio":         None,
            "currentRatio":       None,
            "totalDebt":          None,
            "debtToEquity":       None,
            "earningsGrowth":     None,
            "revenueGrowth":      None,
            "operatingCashflow":  None,
            "assetTurnover":      None,
            "grossMargins":       None,
            "operatingMargins":   None,
            "profitMargins":      None,
            "ROA":                None,
            "ROE":                None,
            "ROIC_proxy":         None,
            "EPS":                None,
            "freeCashflow":       None,
            # Métricas ETF
            "ETF_categoria":      info.get("category") or info.get("fundFamily"),
            "ETF_aum":            info.get("totalAssets"),
            "ETF_yield":          info.get("yield") or info.get("dividendYield"),
            "ETF_retorno_ytd":    info.get("ytdReturn"),
            "ETF_retorno_1y":     info.get("oneYearReturn") or info.get("52WeekChange"),
            "ETF_retorno_3y":     info.get("threeYearAverageReturn"),
            "ETF_retorno_5y":     info.get("fiveYearAverageReturn"),
            "ETF_beta":           info.get("beta3Year") or info.get("beta"),
            "ETF_indice":         ETF_INDICES.get(ticker.upper(), "—"),
            "ETF_num_holdings":   info.get("holdings"),
            "Recomendación":      _recomendacion_etf(info, ticker),
        })
    else:
        # Métricas de acción (igual que antes)
        base.update({
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
            # ETF fields vacíos para acciones
            "ETF_categoria":      None,
            "ETF_aum":            None,
            "ETF_yield":          None,
            "ETF_retorno_ytd":    None,
            "ETF_retorno_1y":     None,
            "ETF_retorno_3y":     None,
            "ETF_retorno_5y":     None,
            "ETF_beta":           info.get("beta"),
            "ETF_indice":         None,
            "ETF_num_holdings":   None,
            "Recomendación":      _recomendacion_accion(info),
        })

    return base


def _recomendacion_accion(info: dict) -> str:
    """Recomendación fundamental para acciones."""
    margen     = info.get("profitMargins")
    roic       = info.get("returnOnInvestedCapital", info.get("returnOnEquity"))
    crecimiento = info.get("revenueGrowth")
    if margen and roic and crecimiento:
        if margen > 0.20 and roic > 0.15 and crecimiento > 0.10:
            return "Alta proyección"
        elif margen > 0.15 and roic > 0.10:
            return "Interesante"
        else:
            return "Débil"
    return "Sin datos"


def _recomendacion_etf(info: dict, ticker: str) -> str:
    """Recomendación basada en métricas de ETF."""
    beta = info.get("beta3Year") or info.get("beta")
    ret_3y = info.get("threeYearAverageReturn")
    cat = (info.get("category") or "").lower()

    if any(x in cat for x in ["bond", "treasury", "fixed"]):
        return "Diversificador defensivo"
    if any(x in cat for x in ["gold", "commodity"]):
        return "Cobertura / Diversificador"
    if any(x in cat for x in ["innovation", "bitcoin", "crypto"]):
        return "Alta volatilidad / Especulativo"

    if beta is not None:
        if beta < 0.7:
            return "Defensivo — baja correlación"
        elif beta > 1.2:
            return "Agresivo — alta correlación"

    if ret_3y is not None:
        if ret_3y > 0.15:
            return "Buen rendimiento histórico"
        elif ret_3y < 0.05:
            return "Rendimiento bajo"

    return "Seguimiento de índice"

# ═══════════════════════════════════════════════════════════════════════════════
# TIPOS DE CAMBIO (CCL, MEP, Oficial, Blue)
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_tipos_cambio() -> dict:
    """
    Obtiene CCL, MEP, Oficial, Blue y Cripto desde APIs públicas argentinas.
    Retorna dict con todos los tipos de cambio disponibles.
    """
    resultado = {
        "CCL":       None,
        "MEP":       None,
        "Oficial":   None,
        "Blue":      None,
        "Cripto":    None,
        "Mayorista": None,
    }
    mapeo = {
        "contadoconliqui": "CCL",
        "bolsa":           "MEP",
        "oficial":         "Oficial",
        "blue":            "Blue",
        "cripto":          "Cripto",
        "mayorista":       "Mayorista",
    }
    for url in [
        "https://dolarapi.com/v1/dolares",
        "https://api.argentinadatos.com/v1/cotizaciones/dolares",
    ]:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                for item in r.json():
                    casa  = item.get("casa", "").lower()
                    venta = item.get("venta")
                    if casa in mapeo and venta and resultado[mapeo[casa]] is None:
                        resultado[mapeo[casa]] = float(venta)
                if resultado["CCL"] or resultado["MEP"]:
                    break
        except Exception:
            pass
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# BONOS SOBERANOS ARGENTINOS
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_bonos_argentina() -> pd.DataFrame:
    """
    Obtiene datos de bonos soberanos argentinos desde APIs públicas.
    Fuentes: ArgentinaDatos, BYMA open data.
    Con fallback a lista de referencia de bonos conocidos.
    """
    bonos = []

    # Fuente 1: ArgentinaDatos
    try:
        r = requests.get(
            "https://api.argentinadatos.com/v1/finanzas/bonos",
            timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            for b in r.json():
                bonos.append({
                    "Ticker":   b.get("simbolo") or b.get("ticker") or "—",
                    "Nombre":   b.get("nombre") or b.get("descripcion") or "—",
                    "Precio":   b.get("precio") or b.get("ultimoPrecio"),
                    "TIR":      b.get("tir") or b.get("rendimiento"),
                    "Duration": b.get("duration") or b.get("duracion"),
                    "Moneda":   b.get("moneda", "USD"),
                    "Tipo":     "Soberano",
                    "Fuente":   "ArgentinaDatos",
                })
    except Exception:
        pass

    # Fuente 2: BYMA open data
    if not bonos:
        try:
            r = requests.get(
                "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/bnown",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            if r.status_code == 200:
                data  = r.json()
                items = data if isinstance(data, list) else data.get("data", [])
                for b in items[:60]:
                    ticker = (b.get("symbol") or b.get("simbolo") or "").strip()
                    if ticker:
                        bonos.append({
                            "Ticker":   ticker,
                            "Nombre":   b.get("description") or b.get("descripcion") or ticker,
                            "Precio":   b.get("price") or b.get("precio") or b.get("settlementPrice"),
                            "TIR":      b.get("yield") or b.get("tir"),
                            "Duration": b.get("duration") or b.get("duracion"),
                            "Moneda":   "USD" if any(x in ticker for x in ["D","GD","AL"]) else "ARS",
                            "Tipo":     "Soberano/Letra",
                            "Fuente":   "BYMA",
                        })
        except Exception:
            pass

    # Fallback: lista de referencia
    if not bonos:
        for t, n, m in [
            ("AL29","Bono Soberano USD Ley Arg 2029","USD"),
            ("GD29","Bono Soberano USD Ley NY 2029","USD"),
            ("AL30","Bono Soberano USD Ley Arg 2030","USD"),
            ("GD30","Bono Soberano USD Ley NY 2030","USD"),
            ("AL35","Bono Soberano USD Ley Arg 2035","USD"),
            ("GD35","Bono Soberano USD Ley NY 2035","USD"),
            ("AL41","Bono Soberano USD Ley Arg 2041","USD"),
            ("GD41","Bono Soberano USD Ley NY 2041","USD"),
            ("TX26","Bono CER 2026","ARS"),
            ("TX28","Bono CER 2028","ARS"),
            ("S31E5","Letra del Tesoro ARS","ARS"),
        ]:
            bonos.append({"Ticker":t,"Nombre":n,"Precio":None,"TIR":None,
                          "Duration":None,"Moneda":m,"Tipo":"Soberano","Fuente":"Referencia"})

    df = pd.DataFrame(bonos)
    for col in ["Precio","TIR","Duration"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# OBLIGACIONES NEGOCIABLES (ON) CORPORATIVAS
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_on_argentina() -> pd.DataFrame:
    """
    Obtiene Obligaciones Negociables corporativas argentinas desde BYMA.
    Con fallback a lista de ONs conocidas.
    """
    ons = []

    try:
        r = requests.get(
            "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/obligaciones-negociables",
            timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            data  = r.json()
            items = data if isinstance(data, list) else data.get("data", [])
            for on in items[:100]:
                ticker = (on.get("symbol") or on.get("simbolo") or "").strip()
                if ticker:
                    ons.append({
                        "Ticker":      ticker,
                        "Emisor":      on.get("issuer") or on.get("emisor") or on.get("description") or ticker,
                        "Precio":      on.get("price") or on.get("precio") or on.get("settlementPrice"),
                        "TIR":         on.get("yield") or on.get("tir"),
                        "Duration":    on.get("duration") or on.get("duracion"),
                        "Moneda":      on.get("currency") or ("USD" if "D" in ticker else "ARS"),
                        "Vencimiento": on.get("maturityDate") or on.get("vencimiento") or "—",
                        "Tipo":        "ON Corporativa",
                    })
    except Exception:
        pass

    # Fallback: ONs conocidas
    if not ons:
        for t, e, m, v in [
            ("YCA6O","YPF SA","USD","2026"),
            ("YMCXO","YPF SA","USD","2029"),
            ("PNDCO","Pampa Energía","USD","2027"),
            ("TLCMO","Telecom Argentina","USD","2026"),
            ("IRCFO","IRSA","USD","2028"),
            ("GNCXO","Genneia","USD","2027"),
            ("MRCAO","Mercado Libre","USD","2028"),
            ("BRCAO","Banco Macro","USD","2026"),
            ("CSCPO","Cresud","USD","2026"),
            ("SUPVO","Supervielle","USD","2027"),
        ]:
            ons.append({"Ticker":t,"Emisor":e,"Precio":None,"TIR":None,
                        "Duration":None,"Moneda":m,"Vencimiento":v,"Tipo":"ON Corporativa"})

    df = pd.DataFrame(ons)
    for col in ["Precio","TIR","Duration"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
