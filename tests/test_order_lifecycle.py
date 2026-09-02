from __future__ import annotations

from aegis_alpha.broker.fake import FakeBrokerGateway
from aegis_alpha.models import DecisionAction, ExecutionRecord, OrderIntent, PositionSnapshot
from aegis_alpha.orchestrator import AgentOrchestrator
from aegis_alpha.ranker import RuleBasedRanker


def _intent(candidate) -> OrderIntent:
    return OrderIntent.from_candidate("lifecycle", candidate, 1, 0.40, -0.30)


def test_accepted_entry_is_pending_until_both_legs_exist(store, candidate) -> None:
    intent = _intent(candidate)
    store.record_execution(
        ExecutionRecord(
            cycle_id=intent.cycle_id,
            client_order_id=intent.client_order_id,
            status="accepted",
            dry_run=False,
        ),
        intent,
    )

    assert store.trade_status(intent.client_order_id) == "pending_open"
    assert store.list_open_trades() == []
    assert store.open_trade_summary() == (1, intent.maximum_loss)

    opened, partial = store.reconcile_pending_trades(
        {intent.legs[0].symbol, intent.legs[1].symbol}
    )
    assert opened == [intent.client_order_id]
    assert partial == []
    assert store.trade_status(intent.client_order_id) == "open"


def test_single_leg_fill_is_flagged_without_claiming_open(store, candidate) -> None:
    intent = _intent(candidate)
    store.record_execution(
        ExecutionRecord(
            cycle_id=intent.cycle_id,
            client_order_id=intent.client_order_id,
            status="accepted",
            dry_run=False,
        ),
        intent,
    )

    opened, partial = store.reconcile_pending_trades({intent.legs[0].symbol})

    assert opened == []
    assert partial == [intent.client_order_id]
    assert store.trade_status(intent.client_order_id) == "pending_open"


def test_partial_fill_halts_new_orders(settings, store, candidate, market_now) -> None:
    intent = _intent(candidate)
    store.record_execution(
        ExecutionRecord(
            cycle_id=intent.cycle_id,
            client_order_id=intent.client_order_id,
            status="accepted",
            dry_run=False,
        ),
        intent,
    )
    broker = FakeBrokerGateway(True, market_now)
    broker.get_positions = lambda: [
        PositionSnapshot(
            symbol=intent.legs[0].symbol,
            quantity=1,
            market_value=200,
            unrealized_pl=0,
        )
    ]
    orchestrator = AgentOrchestrator(
        settings,
        broker,
        store,
        RuleBasedRanker(),
        cli_adapter=None,
        require_cli=False,
    )

    decisions = orchestrator.run_cycle(dry_run=True, now=market_now)

    assert all(decision.action is DecisionAction.NO_TRADE for decision in decisions)
    assert all(
        not next(
            check for check in decision.risk_state.checks if check.name == "cli_reconciliation"
        ).passed
        for decision in decisions
    )
