from __future__ import annotations

from aegis_alpha.broker.fake import FakeBrokerGateway
from aegis_alpha.models import DecisionAction
from aegis_alpha.orchestrator import AgentOrchestrator
from aegis_alpha.ranker import RuleBasedRanker


def build(settings, store, broker):
    return AgentOrchestrator(
        settings,
        broker,
        store,
        RuleBasedRanker(),
        cli_adapter=None,
        require_cli=False,
    )


def test_offline_cycle_prepares_only_dry_run_orders(settings, store, market_now) -> None:
    broker = FakeBrokerGateway(True, market_now)
    decisions = build(settings, store, broker).run_cycle(dry_run=True, now=market_now)
    assert {decision.action for decision in decisions} == {DecisionAction.BUY_SPREAD}
    assert len(broker.submitted) == 2
    assert all(decision.order_intent.maximum_loss <= 500 for decision in decisions)


def test_duplicate_cycle_does_not_submit_again(settings, store, market_now) -> None:
    broker = FakeBrokerGateway(True, market_now)
    orchestrator = build(settings, store, broker)
    orchestrator.run_cycle(dry_run=True, now=market_now)
    first_count = len(broker.submitted)
    orchestrator.run_cycle(dry_run=True, now=market_now)
    assert len(broker.submitted) == first_count


def test_required_missing_cli_fails_closed(settings, store, market_now) -> None:
    broker = FakeBrokerGateway(True, market_now)
    orchestrator = AgentOrchestrator(
        settings,
        broker,
        store,
        RuleBasedRanker(),
        cli_adapter=None,
        require_cli=True,
    )
    decisions = orchestrator.run_cycle(dry_run=True, now=market_now)
    assert {decision.action for decision in decisions} == {DecisionAction.NO_TRADE}


def test_cycle_lock_prevents_concurrent_run(settings, store, market_now) -> None:
    broker = FakeBrokerGateway(True, market_now)
    assert store.acquire_lock("agent-cycle", stale_after_seconds=600)
    try:
        try:
            build(settings, store, broker).run_cycle(dry_run=True, now=market_now)
        except RuntimeError as exc:
            assert "already running" in str(exc)
        else:
            raise AssertionError("concurrent cycle should be blocked")
    finally:
        store.release_lock("agent-cycle")
