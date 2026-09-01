from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from .config import Settings
from .models import AccountSnapshot, RiskCheck, RiskState, SpreadCandidate
from .store import AuditStore


class RiskGuard:
    def __init__(self, settings: Settings, store: AuditStore) -> None:
        self.settings = settings
        self.store = store

    def evaluate(
        self,
        account: AccountSnapshot,
        candidate: SpreadCandidate | None,
        now: datetime | None = None,
        cli_matched: bool = True,
    ) -> tuple[RiskState, int]:
        now = now or datetime.now(timezone.utc)
        open_positions, aggregate_risk = self.store.open_trade_summary()
        drawdown = max(
            0.0, (self.settings.starting_equity - account.equity) / self.settings.starting_equity
        )
        checks: list[RiskCheck] = []

        def check(name: str, passed: bool, detail: str) -> None:
            checks.append(RiskCheck(name=name, passed=passed, detail=detail))

        check("paper_mode", self.settings.paper, "Only paper trading is allowed")
        check("kill_switch", not self.settings.kill_switch, "KILL_SWITCH must be false")
        check("cli_reconciliation", cli_matched, "SDK and CLI snapshots must agree")
        market_now = now.astimezone(ZoneInfo(self.settings.market_timezone)).time()
        check(
            "entry_cutoff",
            market_now < time(15, 30),
            f"market_time={market_now.isoformat(timespec='minutes')}, cutoff=15:30",
        )
        check(
            "daily_drawdown",
            drawdown < self.settings.daily_drawdown_limit,
            f"drawdown={drawdown:.2%}, limit={self.settings.daily_drawdown_limit:.2%}",
        )
        check(
            "position_count",
            open_positions < self.settings.max_positions,
            f"open={open_positions}, limit={self.settings.max_positions}",
        )
        quantity = 0
        if candidate is None:
            check("candidate", False, "No candidate supplied")
        else:
            quote_age = max(
                (now - candidate.long_contract.quote_timestamp).total_seconds(),
                (now - candidate.short_contract.quote_timestamp).total_seconds(),
            )
            check(
                "quote_freshness",
                0 <= quote_age <= self.settings.max_quote_age_seconds,
                f"age={quote_age:.1f}s, max={self.settings.max_quote_age_seconds}s",
            )
            check(
                "quote_width",
                candidate.quote_width_ratio <= self.settings.max_quote_width_ratio,
                (
                    f"ratio={candidate.quote_width_ratio:.2%}, "
                    f"max={self.settings.max_quote_width_ratio:.2%}"
                ),
            )
            traded_today = self.store.traded_underlying_today(
                candidate.underlying, now.date().isoformat()
            )
            check("one_trade_per_day", not traded_today, f"underlying={candidate.underlying}")
            last_trade = self.store.latest_trade_time(candidate.underlying)
            cooldown_ok = (
                last_trade is None
                or (now - last_trade).total_seconds() >= self.settings.cooldown_minutes * 60
            )
            check(
                "cooldown",
                cooldown_ok,
                f"minimum={self.settings.cooldown_minutes} minutes",
            )
            per_contract = candidate.maximum_loss_per_contract
            risk_cap = min(
                self.settings.max_trade_risk_dollars,
                account.equity * self.settings.max_trade_risk_pct,
            )
            quantity = int(risk_cap // per_contract) if per_contract > 0 else 0
            maximum_loss = per_contract * quantity
            check(
                "position_size",
                quantity >= 1,
                f"risk_cap=${risk_cap:.2f}, per_contract=${per_contract:.2f}",
            )
            check(
                "aggregate_risk",
                quantity >= 1 and aggregate_risk + maximum_loss <= self.settings.max_aggregate_risk,
                (
                    f"after_trade=${aggregate_risk + maximum_loss:.2f}, "
                    f"limit=${self.settings.max_aggregate_risk:.2f}"
                ),
            )
            check(
                "buying_power",
                quantity >= 1 and maximum_loss <= account.options_buying_power,
                f"required=${maximum_loss:.2f}, available=${account.options_buying_power:.2f}",
            )
        state = RiskState(
            equity=account.equity,
            session_start_equity=self.settings.starting_equity,
            daily_drawdown=drawdown,
            aggregate_open_risk=aggregate_risk,
            open_positions=open_positions,
            kill_switch=self.settings.kill_switch,
            checks=tuple(checks),
        )
        return state, quantity if all(item.passed for item in checks) else 0
