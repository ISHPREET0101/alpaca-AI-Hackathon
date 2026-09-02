from __future__ import annotations

from aegis_alpha.broker.fake import FakeBrokerGateway
from aegis_alpha.models import ExecutionRecord, OrderIntent
from aegis_alpha.monitor import PositionMonitor


def _open_trade(store, candidate, market_now) -> OrderIntent:
    intent = OrderIntent.from_candidate(
        cycle_id="cycle-monitor",
        candidate=candidate,
        quantity=1,
        take_profit_pct=0.40,
        stop_loss_pct=-0.30,
    )
    store.record_execution(
        ExecutionRecord(
            cycle_id=intent.cycle_id,
            client_order_id=intent.client_order_id,
            alpaca_order_id="paper-open",
            status="filled",
            submitted_at=market_now,
            dry_run=False,
        ),
        intent,
    )
    return intent


def test_monitor_forces_end_of_day_exit(settings, store, candidate, market_now) -> None:
    intent = _open_trade(store, candidate, market_now)
    close_time = market_now.replace(hour=15, minute=45)
    broker = FakeBrokerGateway(True, close_time)

    exits = PositionMonitor(settings, broker, store).run(dry_run=False, now=close_time)

    assert len(exits) == 1
    assert exits[0].client_order_id == f"{intent.client_order_id}-close"
    assert store.list_open_trades() == []
    assert store.trade_status(intent.client_order_id) == "closing"
    assert store.open_trade_summary() == (1, intent.maximum_loss)


def test_monitor_keeps_flat_pnl_position_before_cutoff(
    settings, store, candidate, market_now
) -> None:
    _open_trade(store, candidate, market_now)
    broker = FakeBrokerGateway(True, market_now)

    exits = PositionMonitor(settings, broker, store).run(dry_run=False, now=market_now)

    assert exits == []


def test_monitor_exits_when_bullish_signal_is_invalidated(
    settings, store, candidate, market_now
) -> None:
    intent = _open_trade(store, candidate, market_now)
    broker = FakeBrokerGateway(False, market_now)

    exits = PositionMonitor(settings, broker, store).run(dry_run=False, now=market_now)

    assert len(exits) == 1
    assert store.trade_status(intent.client_order_id) == "closing"


def test_monitor_confirms_close_only_after_positions_disappear(
    settings, store, candidate, market_now
) -> None:
    intent = _open_trade(store, candidate, market_now)
    store.mark_trade_closing(intent.client_order_id)
    broker = FakeBrokerGateway(True, market_now)

    exits = PositionMonitor(settings, broker, store).run(dry_run=False, now=market_now)

    assert exits == []
    assert store.trade_status(intent.client_order_id) == "closed"
    assert store.open_trade_summary() == (0, 0.0)
