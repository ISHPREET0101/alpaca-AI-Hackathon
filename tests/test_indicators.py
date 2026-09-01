from __future__ import annotations

from aegis_alpha.broker.fake import FakeBrokerGateway
from aegis_alpha.indicators import assess_regime
from aegis_alpha.models import Regime


def test_bullish_regime(market_now) -> None:
    assessment = assess_regime(FakeBrokerGateway(True, market_now).get_bars("SPY"))
    assert assessment.regime is Regime.BULLISH
    assert assessment.ema_fast > assessment.ema_slow


def test_bearish_regime(market_now) -> None:
    assessment = assess_regime(FakeBrokerGateway(False, market_now).get_bars("SPY"))
    assert assessment.regime is Regime.BEARISH
    assert assessment.ema_fast < assessment.ema_slow


def test_requires_enough_bars(market_now) -> None:
    bars = FakeBrokerGateway(True, market_now).get_bars("SPY")[:20]
    try:
        assess_regime(bars)
    except ValueError as exc:
        assert "30" in str(exc)
    else:
        raise AssertionError("short histories must fail closed")
