from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from aegis_alpha.models import (
    AccountSnapshot,
    ExecutionRecord,
    MarketBar,
    MarketClock,
    OptionSnapshot,
    OptionType,
    OrderIntent,
    PositionSnapshot,
)


class FakeBrokerGateway:
    """Deterministic broker used by offline demos and tests."""

    def __init__(self, bullish: bool = True, now: datetime | None = None) -> None:
        self.now = now or datetime.now(timezone.utc)
        self.bullish = bullish
        self.submitted: list[OrderIntent] = []

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(
            account_id="paper-demo-account",
            equity=100_000,
            cash=100_000,
            buying_power=200_000,
            options_buying_power=100_000,
            status="ACTIVE",
            captured_at=self.now,
        )

    def get_clock(self) -> MarketClock:
        return MarketClock(
            timestamp=self.now,
            is_open=True,
            next_open=self.now,
            next_close=self.now + timedelta(hours=6),
        )

    def get_bars(self, symbol: str, end: datetime | None = None) -> list[MarketBar]:
        end = end or self.now
        slope = 0.12 if self.bullish else -0.12
        bars: list[MarketBar] = []
        for index in range(60):
            price = 500 + slope * index + math.sin(index * 1.7) * 0.35
            bars.append(
                MarketBar(
                    timestamp=end - timedelta(minutes=(59 - index) * 5),
                    open=price - slope / 2,
                    high=price + 0.15,
                    low=price - 0.15,
                    close=price,
                    volume=1_000_000 + index * 5_000,
                    vwap=price - slope,
                )
            )
        return bars

    def get_option_chain(self, symbol: str, now: datetime | None = None) -> list[OptionSnapshot]:
        now = now or self.now
        expiry = now.date() + timedelta(days=14)
        contracts: list[OptionSnapshot] = []
        for option_type in (OptionType.CALL, OptionType.PUT):
            for offset, delta in [(-5, 0.60), (0, 0.45), (5, 0.30), (10, 0.20)]:
                strike = 500 + offset
                signed_delta = delta if option_type is OptionType.CALL else -delta
                premium = max(0.5, 5 - abs(offset) * 0.25)
                symbol_suffix = "C" if option_type is OptionType.CALL else "P"
                contracts.append(
                    OptionSnapshot(
                        symbol=f"{symbol}{expiry:%y%m%d}{symbol_suffix}{int(strike * 1000):08d}",
                        underlying=symbol,
                        expiry=expiry,
                        strike=strike,
                        option_type=option_type,
                        bid=premium - 0.02,
                        ask=premium + 0.02,
                        delta=signed_delta,
                        quote_timestamp=now,
                    )
                )
        return contracts

    def get_positions(self) -> list[PositionSnapshot]:
        return []

    def submit_spread(self, intent: OrderIntent, dry_run: bool) -> ExecutionRecord:
        self.submitted.append(intent)
        return ExecutionRecord(
            cycle_id=intent.cycle_id,
            client_order_id=intent.client_order_id,
            alpaca_order_id=None if dry_run else "paper-demo-order",
            status="dry_run" if dry_run else "accepted",
            dry_run=dry_run,
            raw={"fake": True, "limit_debit": intent.limit_debit},
        )

    def close_spread(
        self, intent: OrderIntent, limit_credit: float, dry_run: bool
    ) -> ExecutionRecord:
        return ExecutionRecord(
            cycle_id=intent.cycle_id,
            client_order_id=f"{intent.client_order_id}-close",
            alpaca_order_id=None if dry_run else "paper-demo-close-order",
            status="dry_run" if dry_run else "accepted",
            dry_run=dry_run,
            raw={"fake": True, "limit_credit": limit_credit},
        )
