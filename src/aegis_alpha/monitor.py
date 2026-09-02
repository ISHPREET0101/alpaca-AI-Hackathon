from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from aegis_alpha.broker.base import BrokerGateway
from aegis_alpha.config import Settings
from aegis_alpha.indicators import assess_regime
from aegis_alpha.models import ExecutionRecord, Regime
from aegis_alpha.store import AuditStore


class PositionMonitor:
    def __init__(self, settings: Settings, broker: BrokerGateway, store: AuditStore) -> None:
        self.settings = settings
        self.broker = broker
        self.store = store

    def run(
        self, dry_run: bool | None = None, now: datetime | None = None
    ) -> list[ExecutionRecord]:
        dry_run = self.settings.dry_run if dry_run is None else dry_run
        now = now or datetime.now(timezone.utc)
        market_now = now.astimezone(ZoneInfo(self.settings.market_timezone))
        force_exit = market_now.time() >= time(
            self.settings.force_exit_hour, self.settings.force_exit_minute
        )
        exits: list[ExecutionRecord] = []
        chains: dict[str, dict[str, object]] = {}
        position_symbols = {
            position.symbol for position in self.broker.get_positions() if position.quantity != 0
        }
        opened, partial = self.store.reconcile_pending_trades(position_symbols)
        for client_order_id in opened:
            self.store.record_event(
                "position_open_confirmed",
                {"client_order_id": client_order_id, "source": "broker_positions"},
            )
        for client_order_id in partial:
            self.store.record_event(
                "partial_spread_fill_detected",
                {"client_order_id": client_order_id},
                severity="critical",
            )
        reconciled = self.store.reconcile_closing_trades(position_symbols)
        for client_order_id in reconciled:
            self.store.record_event(
                "position_close_confirmed",
                {"client_order_id": client_order_id, "source": "broker_positions"},
            )
        regimes: dict[str, Regime] = {}
        for intent, entry_debit in self.store.list_open_trades():
            if intent.underlying not in chains:
                chain = self.broker.get_option_chain(intent.underlying, now=now)
                chains[intent.underlying] = {contract.symbol: contract for contract in chain}
            contracts = chains[intent.underlying]
            long_contract = contracts.get(intent.legs[0].symbol)
            short_contract = contracts.get(intent.legs[1].symbol)
            if long_contract is None or short_contract is None:
                self.store.record_event(
                    "monitor_missing_quotes",
                    {"client_order_id": intent.client_order_id},
                    severity="warning",
                )
                continue
            current_credit = max(0.01, long_contract.bid - short_contract.ask)
            pnl_pct = (current_credit - entry_debit) / entry_debit
            exit_reason = None
            if pnl_pct >= intent.take_profit_pct:
                exit_reason = "take_profit"
            elif pnl_pct <= intent.stop_loss_pct:
                exit_reason = "stop_loss"
            elif force_exit:
                exit_reason = "end_of_day_cutoff"
            else:
                if intent.underlying not in regimes:
                    try:
                        bars = self.broker.get_bars(intent.underlying, end=now)
                        regimes[intent.underlying] = assess_regime(bars).regime
                    except Exception as exc:
                        self.store.record_event(
                            "monitor_signal_unavailable",
                            {
                                "client_order_id": intent.client_order_id,
                                "error": str(exc),
                            },
                            severity="warning",
                        )
                current_regime = regimes.get(intent.underlying)
                expected_regime = (
                    Regime.BULLISH
                    if intent.strategy == "bull_call_debit_spread"
                    else Regime.BEARISH
                )
                if current_regime is not None and current_regime != expected_regime:
                    exit_reason = "signal_invalidated"
            should_exit = exit_reason is not None
            if not should_exit:
                continue
            self.store.record_event(
                "position_exit_triggered",
                {
                    "client_order_id": intent.client_order_id,
                    "reason": exit_reason,
                    "estimated_pnl_pct": round(pnl_pct, 6),
                },
            )
            execution = self.broker.close_spread(intent, current_credit, dry_run=dry_run)
            self.store.record_execution(execution)
            if execution.status == "filled" and not dry_run:
                self.store.mark_trade_closed(intent.client_order_id)
            elif execution.status in {"accepted", "new", "partially_filled"} and not dry_run:
                self.store.mark_trade_closing(intent.client_order_id)
            exits.append(execution)
        return exits
