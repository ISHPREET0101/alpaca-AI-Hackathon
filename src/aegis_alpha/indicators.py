from __future__ import annotations

import math

import pandas as pd

from .models import MarketBar, Regime, RegimeAssessment


def bars_frame(bars: list[MarketBar]) -> pd.DataFrame:
    if not bars:
        raise ValueError("At least one market bar is required")
    frame = pd.DataFrame([bar.model_dump() for bar in bars]).sort_values("timestamp")
    frame = frame.set_index("timestamp")
    return frame


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    relative_strength = gain / loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + relative_strength))
    result = result.mask((loss == 0) & (gain > 0), 100.0)
    result = result.mask((gain == 0) & (loss > 0), 0.0)
    return result.fillna(50.0)


def assess_regime(bars: list[MarketBar]) -> RegimeAssessment:
    if len(bars) < 30:
        raise ValueError("At least 30 five-minute bars are required for a regime assessment")
    frame = bars_frame(bars)
    close = frame["close"]
    ema_fast = close.ewm(span=9, adjust=False).mean()
    ema_slow = close.ewm(span=21, adjust=False).mean()
    volume = frame["volume"].replace(0, float("nan"))
    typical_price = (frame["high"] + frame["low"] + frame["close"]) / 3
    calculated_vwap = (typical_price * volume).cumsum() / volume.cumsum()
    vwap_value = float(calculated_vwap.ffill().iloc[-1])
    rsi_value = float(rsi(close).iloc[-1])
    returns = close.pct_change().dropna()
    realized_vol = float(returns.std(ddof=0) * math.sqrt(78 * 252)) if len(returns) else 0.0
    latest = float(close.iloc[-1])
    fast = float(ema_fast.iloc[-1])
    slow = float(ema_slow.iloc[-1])

    ema_separation = abs(fast - slow) / latest
    vwap_separation = abs(latest - vwap_value) / latest
    meaningful_trend = ema_separation >= 0.0003 and vwap_separation >= 0.0002
    bullish = meaningful_trend and latest > vwap_value and fast > slow and 52 <= rsi_value <= 72
    bearish = meaningful_trend and latest < vwap_value and fast < slow and 28 <= rsi_value <= 48
    reasons = (
        f"close={latest:.2f} vs vwap={vwap_value:.2f}",
        f"ema9={fast:.2f} vs ema21={slow:.2f}",
        f"rsi14={rsi_value:.1f}",
        f"annualized_realized_vol={realized_vol:.2%}",
        f"ema_separation={ema_separation:.3%}",
    )
    regime = Regime.BULLISH if bullish else Regime.BEARISH if bearish else Regime.NEUTRAL
    return RegimeAssessment(
        regime=regime,
        close=latest,
        ema_fast=fast,
        ema_slow=slow,
        vwap=vwap_value,
        rsi=rsi_value,
        realized_volatility=realized_vol,
        reasons=reasons,
    )
