from __future__ import annotations

import pytest

from aegis_alpha.indicators import assess_regime
from aegis_alpha.ranker import LLMRanker, RuleBasedRanker


def test_rule_ranker_selects_from_supplied_candidates(candidate, market_now) -> None:
    from aegis_alpha.broker.fake import FakeBrokerGateway

    regime = assess_regime(FakeBrokerGateway(True, market_now).get_bars("SPY"))
    result = RuleBasedRanker().rank(regime, [candidate])
    assert result.selected_index == 0
    assert result.source == "rule"


def test_llm_ranker_fails_closed_without_credentials(settings, candidate, market_now) -> None:
    from aegis_alpha.broker.fake import FakeBrokerGateway

    regime = assess_regime(FakeBrokerGateway(True, market_now).get_bars("SPY"))
    with pytest.raises(RuntimeError, match="required"):
        LLMRanker(settings).rank(regime, [candidate])
