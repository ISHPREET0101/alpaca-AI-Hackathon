from __future__ import annotations

from datetime import datetime
from typing import Protocol

from aegis_alpha.models import (
    AccountSnapshot,
    ExecutionRecord,
    MarketBar,
    MarketClock,
    OptionSnapshot,
    OrderIntent,
    PositionSnapshot,
)


class BrokerGateway(Protocol):
    def get_account(self) -> AccountSnapshot: ...

    def get_clock(self) -> MarketClock: ...

    def get_bars(self, symbol: str, end: datetime | None = None) -> list[MarketBar]: ...

    def get_option_chain(
        self, symbol: str, now: datetime | None = None
    ) -> list[OptionSnapshot]: ...

    def get_positions(self) -> list[PositionSnapshot]: ...

    def submit_spread(self, intent: OrderIntent, dry_run: bool) -> ExecutionRecord: ...

    def close_spread(
        self, intent: OrderIntent, limit_credit: float, dry_run: bool
    ) -> ExecutionRecord: ...
