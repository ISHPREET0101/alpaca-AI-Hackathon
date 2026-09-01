from __future__ import annotations

from aegis_alpha.broker.fake import FakeBrokerGateway
from aegis_alpha.indicators import assess_regime
from aegis_alpha.models import OptionType, Regime, RegimeAssessment
from aegis_alpha.strategy import CandidateAgent, CriticAgent


def test_candidate_agent_builds_bull_call_spread(settings, market_now) -> None:
    broker = FakeBrokerGateway(True, market_now)
    regime = assess_regime(broker.get_bars("SPY"))
    candidates = CandidateAgent(settings).generate(
        "SPY", regime, broker.get_option_chain("SPY", market_now), market_now.date()
    )
    assert candidates
    assert candidates[0].option_type is OptionType.CALL
    assert candidates[0].long_contract.strike < candidates[0].short_contract.strike


def test_candidate_agent_builds_bear_put_spread(settings, market_now) -> None:
    broker = FakeBrokerGateway(False, market_now)
    regime = assess_regime(broker.get_bars("QQQ"))
    candidates = CandidateAgent(settings).generate(
        "QQQ", regime, broker.get_option_chain("QQQ", market_now), market_now.date()
    )
    assert candidates
    assert candidates[0].option_type is OptionType.PUT
    assert candidates[0].long_contract.strike > candidates[0].short_contract.strike


def test_neutral_regime_creates_no_candidates(settings, market_now) -> None:
    neutral = RegimeAssessment(
        regime=Regime.NEUTRAL,
        close=500,
        ema_fast=500,
        ema_slow=500,
        vwap=500,
        rsi=50,
        realized_volatility=0.1,
        reasons=("flat",),
    )
    chain = FakeBrokerGateway(True, market_now).get_option_chain("SPY", market_now)
    assert CandidateAgent(settings).generate("SPY", neutral, chain, market_now.date()) == []


def test_critic_rejects_existing_leg(candidate) -> None:
    regime = RegimeAssessment(
        regime=Regime.BULLISH,
        close=501,
        ema_fast=501,
        ema_slow=500,
        vwap=500,
        rsi=60,
        realized_volatility=0.1,
        reasons=("trend",),
    )
    result = CriticAgent().review(candidate, regime, {candidate.long_contract.symbol})
    assert result.approved is False
