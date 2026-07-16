"""
cedear_mapper.py — compartido entre Historico.py y la app Streamlit
"""
import os, json, requests
from datetime import datetime, timedelta

_DIR       = os.path.dirname(os.path.abspath(__file__))
CACHE_JSON = os.path.join(_DIR, "data", "cedear_equivalencias.json")
CACHE_TTL  = 7  # días

EQUIVALENCIAS_CURADAS: dict[str, str | None] = {
    # Bancos
    "BMA":   "BMA",    # Banco Macro
    "GGAL":  "GGAL",   # Galicia
    "BBAR":  "BBAR",   # BBVA Argentina
    "SUPV":  "SUPV",   # Supervielle
    "BYMA":  None,     # Bolsa argentina — SIN ADR (≠ BMA)
    # Energía
    "YPFD":  "YPF",
    "PAMP":  "PAM",
    "CEPU":  "CEPU",
    "TGSU2": "TGS",
    "TGNO4": None,
    "COME":  None,
    # Telecom
    "TECO2": "TEO",
    # Industria
    "ALUA":  None,
    "TXAR":  None,
    "IRSA":  "IRS",
    "CRES":  None,
    "AGRO":  None,
    # Otros
    "EDN":   "EDN",
    "LOMA":  None,
    "MIRG":  None,
    "HARG":  None,
}

# Tickers internacionales directos (acciones + ETFs)
# No tienen equivalencia local BYMA — se usan tal cual en Yahoo Finance
INTERNACIONALES_DIRECTOS = {
    # Acciones internacionales
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "KO", "MCD",
    "INTC", "AMD", "DOW", "MELI", "PBR", "RIO", "SNOW", "V", "VIST",
    "DIS", "BRK-A", "BRK-B", "NU", "ANET", "CRWD", "PLTR", "COIN", "SHOP",
    # ETFs — todos son internacionales directos (sin CEDEAR propio)
    "QQQ", "SPY", "DIA", "IWM", "VOO", "IVV", "VTI", "SCHD", "JEPI",
    "XLF", "XLP", "XLC", "XLV", "XLE", "XLI", "XLK", "XLY", "XLB", "XLU", "XLRE",
    "GLD", "SLV", "TLT", "HYG", "LQD", "EEM", "EFA", "VWO",
    "URA", "IBIT", "ARKK", "ARKG", "ARKW",
}


def _fetch_byma() -> dict:
    for url in ["https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/cedears"]:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                items = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
                res = {}
                for item in items:
                    loc = (item.get("simbolo") or item.get("symbol") or "").strip().upper()
                    sub = (item.get("subyacente") or item.get("underlying") or "").strip().upper()
                    if loc and sub and loc != sub:
                        res[loc] = sub
                if res:
                    return res
        except Exception:
            pass
    return {}


def _load_cache() -> dict | None:
    try:
        if not os.path.exists(CACHE_JSON):
            return None
        with open(CACHE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if datetime.now() - datetime.fromisoformat(data["fecha"]) > timedelta(days=CACHE_TTL):
            return None
        return data["equivalencias"]
    except Exception:
        return None


def _save_cache(equiv: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_JSON), exist_ok=True)
        with open(CACHE_JSON, "w", encoding="utf-8") as f:
            json.dump({"fecha": datetime.now().isoformat(), "equivalencias": equiv},
                      f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_MAPA: dict[str, str | None] = {}


def inicializar(validar_yahoo: bool = False) -> None:
    global _MAPA
    cached = _load_cache()
    if cached:
        _MAPA = cached
        return
    byma  = _fetch_byma()
    _MAPA = {**byma, **EQUIVALENCIAS_CURADAS}
    _save_cache(_MAPA)


def get_adr(ticker: str) -> str | None:
    return _MAPA.get(ticker.upper())


def clasificar_ticker(ticker: str) -> str:
    t = ticker.upper()
    # Tickers con sufijo .BA son locales argentinos
    if t.endswith(".BA"):
        return "Local sin ADR"
    if t in INTERNACIONALES_DIRECTOS:
        return "Internacional"
    if _MAPA.get(t) is not None:
        return "ADR"
    if t in _MAPA:
        return "Local sin ADR"
    return "Internacional"  # default


def expandir_tickers(tickers: list[str]) -> tuple[list[str], list[str]]:
    exp, sin = [], []
    for t in tickers:
        u = t.upper()
        if u not in exp:
            exp.append(u)
        # Tickers con sufijo .BA son locales — no tienen ADR
        if u.endswith(".BA"):
            continue
        if u in INTERNACIONALES_DIRECTOS:
            continue
        adr = get_adr(u)
        if adr and adr != u and adr not in exp:
            exp.append(adr)
        elif adr is None and u not in INTERNACIONALES_DIRECTOS:
            sin.append(u)
    return exp, sin


# Auto-inicializar al importar
inicializar()