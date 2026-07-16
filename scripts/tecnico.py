"""
tecnico.py — Motor de análisis técnico puro (sin gráficos).
Traduce a Python/pandas los indicadores Pine Script compartidos:
  1. RSI (14) + divergencias bull/bear + estadística histórica
  2. Cruces MA 9/21 + estadística post-cruce histórica
  3. Squeeze Momentum + ADX + niveles de compresión
  4. Order Blocks volumétricos + soportes/resistencias activos
  5. Señal combinada + score 0-100

Entrada:  DataFrame OHLCV de yfinance (columnas: Open, High, Low, Close, Volume)
Salida:   dict con todos los valores, estadísticas y señales — sin gráficos
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# TIPOS DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResultadoRSI:
    valor_actual: float
    zona: str                          # "sobrecompra" | "neutral" | "sobreventa"
    periodos_en_zona: int              # cuántas barras lleva en esa zona
    divergencia: Optional[str]         # "bullish" | "bearish" | None
    pct_tiempo_sobrecompra: float      # % histórico en RSI > 70
    pct_tiempo_sobreventa: float       # % histórico en RSI < 30
    pct_rebote_tras_sobreventa: float  # % de veces que RSI<30 → precio +5% en 20 días
    pct_caida_tras_sobrecompra: float  # % de veces que RSI>70 → precio -5% en 20 días
    duracion_media_sobreventa: float   # barras promedio en RSI < 30
    duracion_media_sobrecompra: float  # barras promedio en RSI > 70
    serie: pd.Series                   # serie completa para uso interno

@dataclass
class Cruce:
    fecha: str
    tipo: str                  # "golden" | "death"
    precio_en_cruce: float
    retorno_10d: Optional[float]
    retorno_20d: Optional[float]
    retorno_30d: Optional[float]
    retorno_60d: Optional[float]
    duracion_barras: Optional[int]     # cuántas barras duró hasta el siguiente cruce

@dataclass
class ResultadoMA:
    ma9_actual: float
    ma21_actual: float
    tendencia: str                     # "alcista" | "bajista"
    barras_desde_cruce: int
    ultimo_cruce: Optional[Cruce]
    cruces_historicos: list[Cruce]
    # Estadísticas agregadas
    golden_cross_retorno_10d_prom: Optional[float]
    golden_cross_retorno_20d_prom: Optional[float]
    golden_cross_retorno_30d_prom: Optional[float]
    golden_cross_retorno_60d_prom: Optional[float]
    death_cross_retorno_10d_prom: Optional[float]
    death_cross_retorno_20d_prom: Optional[float]
    death_cross_retorno_30d_prom: Optional[float]
    death_cross_retorno_60d_prom: Optional[float]
    total_golden_cross: int
    total_death_cross: int
    duracion_media_tendencia: float    # barras promedio entre cruces

@dataclass
class ResultadoSqueeze:
    squeeze_activo: bool
    nivel_compresion: str              # "alto" | "medio" | "bajo" | "sin squeeze"
    momentum_valor: float
    momentum_direccion: str            # "subiendo" | "bajando"
    momentum_acelerando: bool          # True si |val| > |val anterior|
    adx_valor: float
    adx_fuerza: str                    # "muy fuerte">40 | "fuerte">25 | "moderado">20 | "débil"
    di_plus: float
    di_minus: float
    direccion_adx: str                 # "alcista" | "bajista"
    pct_tiempo_squeeze: float          # % histórico con squeeze activo
    retorno_post_squeeze_prom: float   # retorno promedio en 10d tras liberación

@dataclass
class OrderBlock:
    tipo: str                          # "bull" | "bear"
    precio_top: float
    precio_btm: float
    fecha: str
    fuerza_bull_pct: float             # % volumen alcista en la zona
    fuerza_bear_pct: float
    volumen: float
    activo: bool                       # True si no fue violado
    distancia_pct: float               # distancia % al precio actual

@dataclass
class ResultadoOrderBlocks:
    soportes: list[OrderBlock]         # OBs bullish activos (precio debajo)
    resistencias: list[OrderBlock]     # OBs bearish activos (precio arriba)
    ob_soporte_mas_cercano: Optional[OrderBlock]
    ob_resistencia_mas_cercana: Optional[OrderBlock]
    precio_actual_vs_ob: str           # "en soporte" | "en resistencia" | "en zona neutral"
    pct_respeto_soporte: float         # % histórico de veces que el precio rebotó en OB bull
    pct_respeto_resistencia: float     # % histórico de veces que el precio rechazó en OB bear

@dataclass
class ResultadoTecnico:
    ticker: str
    precio_actual: float
    rsi: ResultadoRSI
    ma: ResultadoMA
    squeeze: ResultadoSqueeze
    order_blocks: ResultadoOrderBlocks
    score: int                         # 0-100
    señal: str                         # "🟢 COMPRAR" | "🟡 NEUTRAL" | "🔴 VENDER"
    resumen: str                       # texto explicativo de la señal
    componentes_score: dict            # desglose del score por indicador


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════════════════════

def _rma(series: pd.Series, period: int) -> pd.Series:
    """
    RMA (Wilder's Moving Average) — equivalente al ta.rma() de Pine Script.
    Es un EWM con alpha = 1/period y adjust=False.
    """
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    return _rma(tr, period)


def _pivot_low(series: pd.Series, left: int, right: int) -> pd.Series:
    """
    Detecta pivot lows: mínimos locales con `left` barras a la izquierda
    y `right` barras a la derecha siendo mayores.
    Retorna la serie con el valor del pivot o NaN.
    """
    result = pd.Series(np.nan, index=series.index)
    for i in range(left, len(series) - right):
        window = series.iloc[i - left: i + right + 1]
        if series.iloc[i] == window.min():
            result.iloc[i] = series.iloc[i]
    return result


def _pivot_high(series: pd.Series, left: int, right: int) -> pd.Series:
    """Detecta pivot highs."""
    result = pd.Series(np.nan, index=series.index)
    for i in range(left, len(series) - right):
        window = series.iloc[i - left: i + right + 1]
        if series.iloc[i] == window.max():
            result.iloc[i] = series.iloc[i]
    return result


def _linreg(series: pd.Series, period: int) -> pd.Series:
    """
    Regresión lineal rolling — equivalente a linreg() de Pine Script.
    Retorna el valor proyectado al último punto de cada ventana.
    """
    result = pd.Series(np.nan, index=series.index)
    arr = series.values
    for i in range(period - 1, len(arr)):
        y = arr[i - period + 1: i + 1]
        if np.isnan(y).any():
            continue
        x = np.arange(period)
        coeffs = np.polyfit(x, y, 1)
        result.iloc[i] = coeffs[0] * (period - 1) + coeffs[1]
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 1. RSI + DIVERGENCIAS
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_rsi(df: pd.DataFrame, period: int = 14,
                 lookback_left: int = 5, lookback_right: int = 5,
                 range_lower: int = 5, range_upper: int = 60) -> ResultadoRSI:
    """
    Calcula RSI con la fórmula exacta del Pine Script (usando RMA de Wilder),
    detecta divergencias bull/bear y genera estadísticas históricas.
    """
    close = df["Close"]

    # ── Cálculo RSI (fórmula Pine Script) ────────────────────────────────────
    change = close.diff()
    up     = _rma(change.clip(lower=0), period)
    down   = _rma((-change).clip(lower=0), period)
    rsi    = pd.Series(np.where(down == 0, 100,
                       np.where(up == 0, 0,
                       100 - (100 / (1 + up / down)))),
                       index=close.index)

    # ── Valor actual y zona ───────────────────────────────────────────────────
    val_actual = float(rsi.iloc[-1])
    if val_actual >= 70:
        zona = "sobrecompra"
    elif val_actual <= 30:
        zona = "sobreventa"
    else:
        zona = "neutral"

    # Períodos consecutivos en zona actual
    periodos_en_zona = 0
    for v in reversed(rsi.values):
        if zona == "sobrecompra" and v >= 70:
            periodos_en_zona += 1
        elif zona == "sobreventa" and v <= 30:
            periodos_en_zona += 1
        elif zona == "neutral" and 30 < v < 70:
            periodos_en_zona += 1
        else:
            break

    # ── Divergencias ─────────────────────────────────────────────────────────
    divergencia = None
    try:
        pl = _pivot_low(rsi, lookback_left, lookback_right)
        ph = _pivot_high(rsi, lookback_left, lookback_right)
        low_s  = df["Low"]
        high_s = df["High"]

        # Bullish: precio hace LL pero RSI hace HL
        pl_idx = pl.dropna().index
        if len(pl_idx) >= 2:
            i1, i2 = pl_idx[-2], pl_idx[-1]
            bars_between = rsi.index.get_loc(i2) - rsi.index.get_loc(i1)
            if range_lower <= bars_between <= range_upper:
                if rsi[i2] > rsi[i1] and low_s[i2] < low_s[i1]:
                    divergencia = "bullish"

        # Bearish: precio hace HH pero RSI hace LH
        if divergencia is None:
            ph_idx = ph.dropna().index
            if len(ph_idx) >= 2:
                i1, i2 = ph_idx[-2], ph_idx[-1]
                bars_between = rsi.index.get_loc(i2) - rsi.index.get_loc(i1)
                if range_lower <= bars_between <= range_upper:
                    if rsi[i2] < rsi[i1] and high_s[i2] > high_s[i1]:
                        divergencia = "bearish"
    except Exception:
        pass

    # ── Estadísticas históricas ───────────────────────────────────────────────
    total = len(rsi.dropna())
    pct_sobrecompra = float((rsi >= 70).sum() / total * 100) if total > 0 else 0.0
    pct_sobreventa  = float((rsi <= 30).sum() / total * 100) if total > 0 else 0.0

    # Duración media en zonas extremas
    def _duracion_media_zona(mask: pd.Series) -> float:
        duraciones = []
        count = 0
        for v in mask:
            if v:
                count += 1
            elif count > 0:
                duraciones.append(count)
                count = 0
        if count > 0:
            duraciones.append(count)
        return float(np.mean(duraciones)) if duraciones else 0.0

    dur_sobreventa  = _duracion_media_zona(rsi <= 30)
    dur_sobrecompra = _duracion_media_zona(rsi >= 70)

    # % rebote tras sobreventa (RSI<30 → precio +5% en 20 días)
    rebotes, caidas = [], []
    for i in range(len(rsi) - 20):
        if rsi.iloc[i] <= 30:
            ret_20d = (close.iloc[i + 20] - close.iloc[i]) / close.iloc[i] * 100
            rebotes.append(ret_20d >= 5)
        if rsi.iloc[i] >= 70:
            ret_20d = (close.iloc[i + 20] - close.iloc[i]) / close.iloc[i] * 100
            caidas.append(ret_20d <= -5)

    pct_rebote = float(np.mean(rebotes) * 100) if rebotes else 0.0
    pct_caida  = float(np.mean(caidas)  * 100) if caidas  else 0.0

    return ResultadoRSI(
        valor_actual=round(val_actual, 2),
        zona=zona,
        periodos_en_zona=periodos_en_zona,
        divergencia=divergencia,
        pct_tiempo_sobrecompra=round(pct_sobrecompra, 1),
        pct_tiempo_sobreventa=round(pct_sobreventa, 1),
        pct_rebote_tras_sobreventa=round(pct_rebote, 1),
        pct_caida_tras_sobrecompra=round(pct_caida, 1),
        duracion_media_sobreventa=round(dur_sobreventa, 1),
        duracion_media_sobrecompra=round(dur_sobrecompra, 1),
        serie=rsi
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CRUCES MA 9/21 + ESTADÍSTICA POST-CRUCE
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_ma_cruces(df: pd.DataFrame,
                       short_period: int = 9,
                       long_period: int = 21) -> ResultadoMA:
    """
    Calcula MA 9 y MA 21, detecta todos los cruces históricos y genera
    estadísticas de retorno post-cruce (10, 20, 30, 60 días).
    """
    close = df["Close"]
    ma9   = _sma(close, short_period)
    ma21  = _sma(close, long_period)

    # ── Valores actuales ──────────────────────────────────────────────────────
    ma9_actual  = float(ma9.iloc[-1])
    ma21_actual = float(ma21.iloc[-1])
    tendencia   = "alcista" if ma9_actual > ma21_actual else "bajista"

    # ── Detección de cruces ───────────────────────────────────────────────────
    # Golden Cross: ma9 cruza ma21 hacia arriba
    # Death Cross:  ma9 cruza ma21 hacia abajo
    cruces_raw = []
    for i in range(1, len(ma9)):
        if pd.isna(ma9.iloc[i]) or pd.isna(ma21.iloc[i]):
            continue
        prev_diff = ma9.iloc[i-1] - ma21.iloc[i-1]
        curr_diff = ma9.iloc[i]   - ma21.iloc[i]
        if pd.isna(prev_diff) or pd.isna(curr_diff):
            continue
        if prev_diff <= 0 and curr_diff > 0:
            cruces_raw.append((i, "golden"))
        elif prev_diff >= 0 and curr_diff < 0:
            cruces_raw.append((i, "death"))

    # ── Calcular retornos post-cruce ──────────────────────────────────────────
    close_arr = close.values
    idx_arr   = close.index

    cruces_obj: list[Cruce] = []
    for k, (i, tipo) in enumerate(cruces_raw):
        precio_cruce = float(close_arr[i])
        fecha_cruce  = str(idx_arr[i].date()) if hasattr(idx_arr[i], 'date') else str(idx_arr[i])

        def _ret(dias):
            j = i + dias
            if j < len(close_arr):
                return round((close_arr[j] - precio_cruce) / precio_cruce * 100, 2)
            return None

        # Duración hasta el siguiente cruce
        dur = None
        if k + 1 < len(cruces_raw):
            dur = cruces_raw[k+1][0] - i

        cruces_obj.append(Cruce(
            fecha=fecha_cruce,
            tipo=tipo,
            precio_en_cruce=round(precio_cruce, 2),
            retorno_10d=_ret(10),
            retorno_20d=_ret(20),
            retorno_30d=_ret(30),
            retorno_60d=_ret(60),
            duracion_barras=dur
        ))

    # ── Estadísticas agregadas ────────────────────────────────────────────────
    def _prom(lista, attr):
        vals = [getattr(c, attr) for c in lista if getattr(c, attr) is not None]
        return round(float(np.mean(vals)), 2) if vals else None

    golden = [c for c in cruces_obj if c.tipo == "golden"]
    death  = [c for c in cruces_obj if c.tipo == "death"]

    dur_todos = [c.duracion_barras for c in cruces_obj if c.duracion_barras is not None]
    dur_media = round(float(np.mean(dur_todos)), 1) if dur_todos else 0.0

    # Barras desde el último cruce
    barras_desde = 0
    if cruces_raw:
        barras_desde = len(close) - 1 - cruces_raw[-1][0]

    ultimo_cruce = cruces_obj[-1] if cruces_obj else None

    return ResultadoMA(
        ma9_actual=round(ma9_actual, 4),
        ma21_actual=round(ma21_actual, 4),
        tendencia=tendencia,
        barras_desde_cruce=barras_desde,
        ultimo_cruce=ultimo_cruce,
        cruces_historicos=cruces_obj[-10:],   # últimos 10 cruces
        golden_cross_retorno_10d_prom=_prom(golden, "retorno_10d"),
        golden_cross_retorno_20d_prom=_prom(golden, "retorno_20d"),
        golden_cross_retorno_30d_prom=_prom(golden, "retorno_30d"),
        golden_cross_retorno_60d_prom=_prom(golden, "retorno_60d"),
        death_cross_retorno_10d_prom=_prom(death, "retorno_10d"),
        death_cross_retorno_20d_prom=_prom(death, "retorno_20d"),
        death_cross_retorno_30d_prom=_prom(death, "retorno_30d"),
        death_cross_retorno_60d_prom=_prom(death, "retorno_60d"),
        total_golden_cross=len(golden),
        total_death_cross=len(death),
        duracion_media_tendencia=dur_media
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SQUEEZE MOMENTUM + ADX
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_squeeze_adx(df: pd.DataFrame,
                          bb_length: int = 20, bb_mult: float = 2.0,
                          kc_length: int = 20, kc_mult: float = 1.5,
                          momentum_length: int = 20,
                          adx_length: int = 14,
                          adx_key_level: int = 23) -> ResultadoSqueeze:
    """
    Traduce exactamente el Pine Script de Squeeze M. + ADX + TTM:
    - Squeeze: BB dentro de KC → compresión de volatilidad
    - Momentum: regresión lineal sobre (close - midpoint)
    - ADX: fuerza de tendencia con DI+ y DI-
    """
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    bb_basis = _sma(close, bb_length)
    bb_dev   = close.rolling(bb_length).std() * bb_mult
    bb_upper = bb_basis + bb_dev
    bb_lower = bb_basis - bb_dev

    # ── Keltner Channels ──────────────────────────────────────────────────────
    kc_basis = _sma(close, kc_length)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    kc_dev   = _sma(tr, kc_length) * kc_mult
    kc_upper = kc_basis + kc_dev
    kc_lower = kc_basis - kc_dev

    # ── Squeeze detection ─────────────────────────────────────────────────────
    sqz_on  = (bb_lower > kc_lower) & (bb_upper < kc_upper)   # compresión activa
    sqz_off = (bb_lower < kc_lower) & (bb_upper > kc_upper)   # expansión activa

    # Niveles de compresión (KC con múltiplos 1.0, 1.5, 2.0)
    kc_upper_high = kc_basis + _sma(tr, kc_length) * 1.0
    kc_lower_high = kc_basis - _sma(tr, kc_length) * 1.0
    kc_upper_mid  = kc_basis + _sma(tr, kc_length) * 1.5
    kc_lower_mid  = kc_basis - _sma(tr, kc_length) * 1.5
    kc_upper_low  = kc_basis + _sma(tr, kc_length) * 2.0
    kc_lower_low  = kc_basis - _sma(tr, kc_length) * 2.0

    high_sqz = (bb_lower >= kc_lower_high) | (bb_upper <= kc_upper_high)
    mid_sqz  = (bb_lower >= kc_lower_mid)  | (bb_upper <= kc_upper_mid)
    low_sqz  = (bb_lower >= kc_lower_low)  | (bb_upper <= kc_upper_low)

    # ── Momentum lineal (Pine Script: linreg de close - midpoint) ─────────────
    highest_high = high.rolling(momentum_length).max()
    lowest_low   = low.rolling(momentum_length).min()
    midpoint     = (highest_high + lowest_low) / 2 + _sma(close, momentum_length)
    midpoint     = midpoint / 2
    momentum_src = close - midpoint
    momentum     = _linreg(momentum_src, momentum_length)

    mom_actual   = float(momentum.iloc[-1])  if not pd.isna(momentum.iloc[-1])  else 0.0
    mom_anterior = float(momentum.iloc[-2])  if not pd.isna(momentum.iloc[-2])  else 0.0
    mom_dir      = "subiendo" if mom_actual > mom_anterior else "bajando"
    mom_acel     = abs(mom_actual) > abs(mom_anterior)

    # ── Squeeze actual ────────────────────────────────────────────────────────
    sqz_activo = bool(sqz_on.iloc[-1])
    if sqz_activo:
        if bool(high_sqz.iloc[-1]):
            nivel = "alto"
        elif bool(mid_sqz.iloc[-1]):
            nivel = "medio"
        else:
            nivel = "bajo"
    else:
        nivel = "sin squeeze"

    # ── ADX ───────────────────────────────────────────────────────────────────
    # Movimiento direccional
    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=close.index)
    minus_dm  = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=close.index)

    tr_rma    = _rma(tr, adx_length)
    plus_di   = 100 * _rma(plus_dm, adx_length) / tr_rma.replace(0, np.nan)
    minus_di  = 100 * _rma(minus_dm, adx_length) / tr_rma.replace(0, np.nan)
    dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx       = _rma(dx, adx_length)

    adx_val   = float(adx.iloc[-1])   if not pd.isna(adx.iloc[-1])   else 0.0
    di_plus   = float(plus_di.iloc[-1])  if not pd.isna(plus_di.iloc[-1])  else 0.0
    di_minus  = float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 0.0

    if adx_val >= 40:
        adx_fuerza = "muy fuerte"
    elif adx_val >= 25:
        adx_fuerza = "fuerte"
    elif adx_val >= 20:
        adx_fuerza = "moderado"
    else:
        adx_fuerza = "débil"

    dir_adx = "alcista" if di_plus > di_minus else "bajista"

    # ── Estadísticas históricas ───────────────────────────────────────────────
    total_barras = len(sqz_on.dropna())
    pct_squeeze  = float(sqz_on.sum() / total_barras * 100) if total_barras > 0 else 0.0

    # Retorno promedio en 10d tras liberación del squeeze (sqz_on → sqz_off)
    retornos_post = []
    for i in range(1, len(sqz_on) - 10):
        if sqz_on.iloc[i-1] and not sqz_on.iloc[i]:   # liberación
            ret = (close.iloc[i+10] - close.iloc[i]) / close.iloc[i] * 100
            retornos_post.append(float(ret))
    ret_post_prom = round(float(np.mean(retornos_post)), 2) if retornos_post else 0.0

    return ResultadoSqueeze(
        squeeze_activo=sqz_activo,
        nivel_compresion=nivel,
        momentum_valor=round(mom_actual, 4),
        momentum_direccion=mom_dir,
        momentum_acelerando=mom_acel,
        adx_valor=round(adx_val, 2),
        adx_fuerza=adx_fuerza,
        di_plus=round(di_plus, 2),
        di_minus=round(di_minus, 2),
        direccion_adx=dir_adx,
        pct_tiempo_squeeze=round(pct_squeeze, 1),
        retorno_post_squeeze_prom=ret_post_prom
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ORDER BLOCKS VOLUMÉTRICOS
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_order_blocks(df: pd.DataFrame,
                           swing_length: int = 8,
                           show_last_x: int = 4,
                           violation_type: str = "wick") -> ResultadoOrderBlocks:
    """
    Traduce el indicador Price Action Volumetric Order Blocks [UAlgo].
    Detecta zonas de acumulación institucional usando swings + volumen.

    Lógica:
    - Bearish OB: cuando precio rompe un swing low → busca la vela verde
      más alta en las últimas `swing_length` barras → zona de resistencia
    - Bullish OB: cuando precio rompe un swing high → busca la vela roja
      más baja en las últimas `swing_length` barras → zona de soporte
    - Fuerza: % de volumen alcista vs bajista en la zona del OB
    - Violación: si precio cierra (o hace wick) por fuera del OB → se invalida
    """
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    open_  = df["Open"]
    volume = df["Volume"]

    precio_actual = float(close.iloc[-1])

    # ── Swing highs y lows ────────────────────────────────────────────────────
    swing_highs = _pivot_high(high, swing_length, swing_length)
    swing_lows  = _pivot_low(low,  swing_length, swing_length)

    bullish_obs: list[OrderBlock] = []
    bearish_obs: list[OrderBlock] = []

    # ── Detectar Order Blocks ─────────────────────────────────────────────────
    for i in range(swing_length, len(close) - swing_length):
        # ── Bearish OB: precio rompe swing low ────────────────────────────────
        if not pd.isna(swing_lows.iloc[i]):
            swing_low_val = float(swing_lows.iloc[i])
            # Buscar si en alguna barra posterior el precio cierra por debajo
            for j in range(i + 1, min(i + swing_length * 3, len(close))):
                if float(close.iloc[j]) < swing_low_val:
                    # Encontrar la vela verde más alta en las últimas swing_length barras antes de i
                    best_top, best_btm, best_idx, best_vol = 0.0, 0.0, i, 0.0
                    for k in range(max(0, i - swing_length), i + 1):
                        if float(close.iloc[k]) > float(open_.iloc[k]):  # vela verde
                            if float(high.iloc[k]) > best_top:
                                best_top = float(high.iloc[k])
                                best_btm = float(low.iloc[k])
                                best_idx = k
                                best_vol = float(volume.iloc[k])

                    if best_top > 0:
                        # Calcular fuerza volumétrica en la zona
                        bull_vol = sum(
                            float(volume.iloc[m])
                            for m in range(max(0, best_idx - swing_length), best_idx + 1)
                            if float(close.iloc[m]) > float(open_.iloc[m])
                        )
                        bear_vol = sum(
                            float(volume.iloc[m])
                            for m in range(max(0, best_idx - swing_length), best_idx + 1)
                            if float(close.iloc[m]) <= float(open_.iloc[m])
                        )
                        total_vol = bull_vol + bear_vol
                        bull_pct = bull_vol / total_vol * 100 if total_vol > 0 else 50.0
                        bear_pct = 100 - bull_pct

                        # Verificar si fue violado
                        violado = False
                        for v in range(j, len(close)):
                            if violation_type == "wick":
                                if float(high.iloc[v]) > best_top:
                                    violado = True; break
                            else:
                                if float(close.iloc[v]) > best_top:
                                    violado = True; break

                        dist_pct = (precio_actual - best_top) / precio_actual * 100

                        bearish_obs.append(OrderBlock(
                            tipo="bear",
                            precio_top=round(best_top, 4),
                            precio_btm=round(best_btm, 4),
                            fecha=str(df.index[best_idx].date()) if hasattr(df.index[best_idx], 'date') else str(df.index[best_idx]),
                            fuerza_bull_pct=round(bull_pct, 1),
                            fuerza_bear_pct=round(bear_pct, 1),
                            volumen=round(best_vol, 0),
                            activo=not violado,
                            distancia_pct=round(dist_pct, 2)
                        ))
                    break

        # ── Bullish OB: precio rompe swing high ───────────────────────────────
        if not pd.isna(swing_highs.iloc[i]):
            swing_high_val = float(swing_highs.iloc[i])
            for j in range(i + 1, min(i + swing_length * 3, len(close))):
                if float(close.iloc[j]) > swing_high_val:
                    # Buscar la vela roja más baja en las últimas swing_length barras
                    best_top, best_btm, best_idx, best_vol = 0.0, float('inf'), i, 0.0
                    for k in range(max(0, i - swing_length), i + 1):
                        if float(close.iloc[k]) < float(open_.iloc[k]):  # vela roja
                            if float(low.iloc[k]) < best_btm:
                                best_btm = float(low.iloc[k])
                                best_top = float(high.iloc[k])
                                best_idx = k
                                best_vol = float(volume.iloc[k])

                    if best_btm < float('inf'):
                        bull_vol = sum(
                            float(volume.iloc[m])
                            for m in range(max(0, best_idx - swing_length), best_idx + 1)
                            if float(close.iloc[m]) > float(open_.iloc[m])
                        )
                        bear_vol = sum(
                            float(volume.iloc[m])
                            for m in range(max(0, best_idx - swing_length), best_idx + 1)
                            if float(close.iloc[m]) <= float(open_.iloc[m])
                        )
                        total_vol = bull_vol + bear_vol
                        bull_pct = bull_vol / total_vol * 100 if total_vol > 0 else 50.0
                        bear_pct = 100 - bull_pct

                        violado = False
                        for v in range(j, len(close)):
                            if violation_type == "wick":
                                if float(low.iloc[v]) < best_btm:
                                    violado = True; break
                            else:
                                if float(close.iloc[v]) < best_btm:
                                    violado = True; break

                        dist_pct = (precio_actual - best_btm) / precio_actual * 100

                        bullish_obs.append(OrderBlock(
                            tipo="bull",
                            precio_top=round(best_top, 4),
                            precio_btm=round(best_btm, 4),
                            fecha=str(df.index[best_idx].date()) if hasattr(df.index[best_idx], 'date') else str(df.index[best_idx]),
                            fuerza_bull_pct=round(bull_pct, 1),
                            fuerza_bear_pct=round(bear_pct, 1),
                            volumen=round(best_vol, 0),
                            activo=not violado,
                            distancia_pct=round(dist_pct, 2)
                        ))
                    break

    # ── Filtrar activos y ordenar por cercanía ────────────────────────────────
    soportes     = sorted([ob for ob in bullish_obs if ob.activo and ob.precio_top < precio_actual],
                          key=lambda x: abs(x.distancia_pct))[:show_last_x]
    resistencias = sorted([ob for ob in bearish_obs if ob.activo and ob.precio_btm > precio_actual],
                          key=lambda x: abs(x.distancia_pct))[:show_last_x]

    ob_sop  = soportes[0]     if soportes     else None
    ob_res  = resistencias[0] if resistencias else None

    # Posición del precio respecto a OBs
    en_soporte     = ob_sop and ob_sop.precio_btm <= precio_actual <= ob_sop.precio_top
    en_resistencia = ob_res and ob_res.precio_btm <= precio_actual <= ob_res.precio_top
    if en_soporte:
        pos = "en soporte"
    elif en_resistencia:
        pos = "en resistencia"
    else:
        pos = "zona neutral"

    # ── Estadísticas históricas de respeto ───────────────────────────────────
    def _pct_respeto(obs_list: list[OrderBlock], es_soporte: bool) -> float:
        respetados = 0
        total = len(obs_list)
        for ob in obs_list:
            if es_soporte:
                # Respetado si precio no cayó por debajo del btm tras el OB
                respetados += 1 if not ob.activo is False else 0
            else:
                respetados += 1 if not ob.activo is False else 0
        return round(respetados / total * 100, 1) if total > 0 else 0.0

    pct_sop = _pct_respeto([ob for ob in bullish_obs], True)
    pct_res = _pct_respeto([ob for ob in bearish_obs], False)

    return ResultadoOrderBlocks(
        soportes=soportes,
        resistencias=resistencias,
        ob_soporte_mas_cercano=ob_sop,
        ob_resistencia_mas_cercana=ob_res,
        precio_actual_vs_ob=pos,
        pct_respeto_soporte=pct_sop,
        pct_respeto_resistencia=pct_res
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SEÑAL COMBINADA + SCORE 0-100
# ═══════════════════════════════════════════════════════════════════════════════

def _calcular_score(rsi: ResultadoRSI, ma: ResultadoMA,
                    sqz: ResultadoSqueeze, ob: ResultadoOrderBlocks) -> tuple[int, dict]:
    """
    Score 0-100 compuesto por 4 componentes con pesos:
      RSI         25 pts
      MA Cruces   25 pts
      Squeeze/ADX 25 pts
      Order Blocks 25 pts
    """
    componentes = {}

    # ── RSI (25 pts) ──────────────────────────────────────────────────────────
    score_rsi = 0
    if rsi.zona == "sobreventa":
        score_rsi += 20   # señal de compra fuerte
        if rsi.divergencia == "bullish":
            score_rsi += 5   # divergencia confirma
    elif rsi.zona == "neutral":
        score_rsi += 12
        if rsi.divergencia == "bullish":
            score_rsi += 5
        elif rsi.divergencia == "bearish":
            score_rsi -= 5
    elif rsi.zona == "sobrecompra":
        score_rsi += 3
        if rsi.divergencia == "bearish":
            score_rsi -= 3
    componentes["RSI"] = max(0, min(25, score_rsi))

    # ── MA Cruces (25 pts) ────────────────────────────────────────────────────
    score_ma = 0
    if ma.tendencia == "alcista":
        score_ma += 15
        # Cruce reciente (< 10 barras) suma más
        if ma.barras_desde_cruce <= 10 and ma.ultimo_cruce and ma.ultimo_cruce.tipo == "golden":
            score_ma += 10
        elif ma.barras_desde_cruce <= 30:
            score_ma += 5
    else:
        score_ma += 5
        if ma.barras_desde_cruce <= 10 and ma.ultimo_cruce and ma.ultimo_cruce.tipo == "death":
            score_ma -= 5
    componentes["MA Cruces"] = max(0, min(25, score_ma))

    # ── Squeeze + ADX (25 pts) ────────────────────────────────────────────────
    score_sqz = 0
    # Squeeze activo con momentum positivo = setup de compra
    if sqz.squeeze_activo and sqz.momentum_valor > 0 and sqz.momentum_direccion == "subiendo":
        score_sqz += 15
    elif sqz.squeeze_activo and sqz.momentum_valor < 0:
        score_sqz += 5   # squeeze pero momentum negativo
    elif not sqz.squeeze_activo and sqz.momentum_valor > 0:
        score_sqz += 10  # expansión alcista
    else:
        score_sqz += 3

    # ADX
    if sqz.adx_fuerza in ("fuerte", "muy fuerte") and sqz.direccion_adx == "alcista":
        score_sqz += 10
    elif sqz.adx_fuerza in ("fuerte", "muy fuerte") and sqz.direccion_adx == "bajista":
        score_sqz += 2
    elif sqz.adx_fuerza == "moderado":
        score_sqz += 5
    componentes["Squeeze+ADX"] = max(0, min(25, score_sqz))

    # ── Order Blocks (25 pts) ─────────────────────────────────────────────────
    score_ob = 12  # base neutral
    if ob.precio_actual_vs_ob == "en soporte":
        score_ob += 13   # precio en zona de demanda institucional
    elif ob.precio_actual_vs_ob == "en resistencia":
        score_ob -= 8    # precio en zona de oferta institucional
    elif ob.ob_soporte_mas_cercano:
        dist = abs(ob.ob_soporte_mas_cercano.distancia_pct)
        if dist < 2:
            score_ob += 8   # muy cerca del soporte
        elif dist < 5:
            score_ob += 4
    componentes["Order Blocks"] = max(0, min(25, score_ob))

    total = sum(componentes.values())
    return total, componentes


def _generar_resumen(rsi: ResultadoRSI, ma: ResultadoMA,
                     sqz: ResultadoSqueeze, ob: ResultadoOrderBlocks,
                     score: int) -> tuple[str, str]:
    """Genera señal textual y resumen explicativo."""
    if score >= 65:
        señal = "🟢 COMPRAR"
    elif score >= 45:
        señal = "🟡 NEUTRAL"
    else:
        señal = "🔴 VENDER"

    partes = []

    # RSI
    if rsi.zona == "sobreventa":
        partes.append(f"RSI {rsi.valor_actual:.1f} (sobreventa)")
    elif rsi.zona == "sobrecompra":
        partes.append(f"RSI {rsi.valor_actual:.1f} (sobrecompra)")
    else:
        partes.append(f"RSI {rsi.valor_actual:.1f} (neutral)")
    if rsi.divergencia:
        partes.append(f"divergencia {rsi.divergencia}")

    # MA
    partes.append(f"tendencia {ma.tendencia} ({ma.barras_desde_cruce} barras)")

    # Squeeze
    if sqz.squeeze_activo:
        partes.append(f"squeeze {sqz.nivel_compresion} activo")
    partes.append(f"ADX {sqz.adx_valor:.1f} ({sqz.adx_fuerza})")

    # OB
    partes.append(ob.precio_actual_vs_ob)

    resumen = " | ".join(partes)
    return señal, resumen


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def analizar(df: pd.DataFrame, ticker: str = "") -> ResultadoTecnico:
    """
    Función principal. Recibe un DataFrame OHLCV de yfinance y retorna
    el análisis técnico completo con estadísticas y señal combinada.

    Uso:
        import yfinance as yf
        import tecnico

        df = yf.download("AAPL", period="2y", interval="1d", auto_adjust=True)
        resultado = tecnico.analizar(df, "AAPL")
        print(resultado.señal)
        print(resultado.resumen)
        print(resultado.ma.golden_cross_retorno_60d_prom)
    """
    # Normalizar columnas (yfinance puede devolver MultiIndex)
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(1, axis=1)

    # Asegurar columnas necesarias
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame falta columnas: {missing}")

    df = df.dropna(subset=["Close"]).copy()
    if len(df) < 50:
        raise ValueError("Se necesitan al menos 50 barras para el análisis técnico.")

    precio_actual = float(df["Close"].iloc[-1])

    rsi_res = calcular_rsi(df)
    ma_res  = calcular_ma_cruces(df)
    sqz_res = calcular_squeeze_adx(df)
    ob_res  = calcular_order_blocks(df)

    score, componentes = _calcular_score(rsi_res, ma_res, sqz_res, ob_res)
    señal, resumen     = _generar_resumen(rsi_res, ma_res, sqz_res, ob_res, score)

    return ResultadoTecnico(
        ticker=ticker,
        precio_actual=round(precio_actual, 4),
        rsi=rsi_res,
        ma=ma_res,
        squeeze=sqz_res,
        order_blocks=ob_res,
        score=score,
        señal=señal,
        resumen=resumen,
        componentes_score=componentes
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS PARA STREAMLIT (output tabular)
# ═══════════════════════════════════════════════════════════════════════════════

def resumen_tabla(res: ResultadoTecnico) -> dict:
    """Versión plana del resultado para mostrar en una tabla Streamlit."""
    ob = res.order_blocks
    ma = res.ma
    return {
        "Ticker":              res.ticker,
        "Precio":              res.precio_actual,
        "Score":               res.score,
        "Señal":               res.señal,
        "RSI":                 res.rsi.valor_actual,
        "RSI Zona":            res.rsi.zona,
        "RSI Divergencia":     res.rsi.divergencia or "—",
        "Tendencia MA":        ma.tendencia,
        "Barras desde cruce":  ma.barras_desde_cruce,
        "Último cruce":        ma.ultimo_cruce.tipo if ma.ultimo_cruce else "—",
        "GC ret.60d hist.":    f"{ma.golden_cross_retorno_60d_prom:+.1f}%" if ma.golden_cross_retorno_60d_prom else "—",
        "DC ret.60d hist.":    f"{ma.death_cross_retorno_60d_prom:+.1f}%" if ma.death_cross_retorno_60d_prom else "—",
        "Squeeze":             "Activo" if res.squeeze.squeeze_activo else "Inactivo",
        "Compresión":          res.squeeze.nivel_compresion,
        "Momentum":            f"{res.squeeze.momentum_valor:+.3f} ({res.squeeze.momentum_direccion})",
        "ADX":                 res.squeeze.adx_valor,
        "ADX Fuerza":          res.squeeze.adx_fuerza,
        "Dirección ADX":       res.squeeze.direccion_adx,
        "Soporte cercano":     f"${ob.ob_soporte_mas_cercano.precio_btm:.2f}–${ob.ob_soporte_mas_cercano.precio_top:.2f}" if ob.ob_soporte_mas_cercano else "—",
        "Resistencia cercana": f"${ob.ob_resistencia_mas_cercana.precio_btm:.2f}–${ob.ob_resistencia_mas_cercana.precio_top:.2f}" if ob.ob_resistencia_mas_cercana else "—",
        "Precio vs OB":        ob.precio_actual_vs_ob,
        "Resumen":             res.resumen,
    }


def cruces_tabla(res: ResultadoTecnico) -> pd.DataFrame:
    """DataFrame con el historial de cruces MA para mostrar en Streamlit."""
    rows = []
    for c in res.ma.cruces_historicos:
        rows.append({
            "Fecha":          c.fecha,
            "Tipo":           "🟢 Golden Cross" if c.tipo == "golden" else "🔴 Death Cross",
            "Precio cruce":   c.precio_en_cruce,
            "Ret. 10d":       f"{c.retorno_10d:+.1f}%" if c.retorno_10d is not None else "—",
            "Ret. 20d":       f"{c.retorno_20d:+.1f}%" if c.retorno_20d is not None else "—",
            "Ret. 30d":       f"{c.retorno_30d:+.1f}%" if c.retorno_30d is not None else "—",
            "Ret. 60d":       f"{c.retorno_60d:+.1f}%" if c.retorno_60d is not None else "—",
            "Duración (barras)": c.duracion_barras if c.duracion_barras else "—",
        })
    return pd.DataFrame(rows)


def order_blocks_tabla(res: ResultadoTecnico) -> pd.DataFrame:
    """DataFrame con soportes y resistencias activos."""
    rows = []
    for ob in res.order_blocks.soportes:
        rows.append({
            "Tipo":        "🟢 Soporte",
            "Zona":        f"${ob.precio_btm:.2f} – ${ob.precio_top:.2f}",
            "Fecha":       ob.fecha,
            "Fuerza Bull": f"{ob.fuerza_bull_pct:.1f}%",
            "Fuerza Bear": f"{ob.fuerza_bear_pct:.1f}%",
            "Distancia":   f"{ob.distancia_pct:+.2f}%",
            "Volumen":     f"{ob.volumen:,.0f}",
        })
    for ob in res.order_blocks.resistencias:
        rows.append({
            "Tipo":        "🔴 Resistencia",
            "Zona":        f"${ob.precio_btm:.2f} – ${ob.precio_top:.2f}",
            "Fecha":       ob.fecha,
            "Fuerza Bull": f"{ob.fuerza_bull_pct:.1f}%",
            "Fuerza Bear": f"{ob.fuerza_bear_pct:.1f}%",
            "Distancia":   f"{ob.distancia_pct:+.2f}%",
            "Volumen":     f"{ob.volumen:,.0f}",
        })
    return pd.DataFrame(rows)