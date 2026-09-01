from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from aegis_alpha.models import AccountSnapshot
from aegis_alpha.risk import RiskGuard


def account(equity: float = 100_000) -> AccountSnapshot:
    return AccountSnapshot(
        account_id="paper",
        equity=equity,
        cash=equity,
        buying_power=equity,
        options_buying_power=equity,
        status="ACTIVE",
    )


def failed_names(state) -> set[str]:
    return {check.name for check in state.checks if not check.passed}


def test_valid_candidate_gets_bounded_quantity(settings, store, candidate, market_now) -> None:
    state, quantity = RiskGuard(settings, store).evaluate(
        account(), candidate, now=market_now, cli_matched=True
    )
    assert quantity == 4
    assert not failed_names(state)
    assert candidate.maximum_loss_per_contract * quantity <= 500


def test_stale_quote_is_rejected(settings, store, candidate, market_now) -> None:
    stale = candidate.model_copy(
        update={
            "long_contract": candidate.long_contract.model_copy(
                update={"quote_timestamp": market_now - timedelta(minutes=2)}
            )
        }
    )
    state, quantity = RiskGuard(settings, store).evaluate(account(), stale, now=market_now)
    assert quantity == 0
    assert "quote_freshness" in failed_names(state)


def test_drawdown_and_kill_switch_are_rejected(settings, store, candidate, market_now) -> None:
    unsafe = replace(settings, kill_switch=True)
    state, quantity = RiskGuard(unsafe, store).evaluate(account(98_000), candidate, now=market_now)
    assert quantity == 0
    assert {"kill_switch", "daily_drawdown"}.issubset(failed_names(state))


def test_cli_mismatch_is_rejected(settings, store, candidate, market_now) -> None:
    state, quantity = RiskGuard(settings, store).evaluate(
        account(), candidate, now=market_now, cli_matched=False
    )
    assert quantity == 0
    assert "cli_reconciliation" in failed_names(state)


def test_wide_quote_is_rejected(settings, store, candidate, market_now) -> None:
    wide = candidate.model_copy(update={"quote_width_ratio": 0.20})
    state, _ = RiskGuard(settings, store).evaluate(account(), wide, now=market_now)
    assert "quote_width" in failed_names(state)
