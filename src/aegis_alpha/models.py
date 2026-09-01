from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Regime(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class DecisionAction(str, Enum):
    BUY_SPREAD = "buy_spread"
    EXIT_SPREAD = "exit_spread"
    NO_TRADE = "no_trade"


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


class LegSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class MarketBar(StrictModel):
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    vwap: float | None = Field(default=None, gt=0)


class MarketClock(StrictModel):
    timestamp: datetime
    is_open: bool
    next_open: datetime
    next_close: datetime


class AccountSnapshot(StrictModel):
    account_id: str
    equity: float = Field(gt=0)
    cash: float
    buying_power: float = Field(ge=0)
    options_buying_power: float = Field(ge=0)
    status: str
    captured_at: datetime = Field(default_factory=utc_now)


class PositionSnapshot(StrictModel):
    symbol: str
    quantity: float
    market_value: float
    unrealized_pl: float
    asset_class: str = "option"


class OptionSnapshot(StrictModel):
    symbol: str
    underlying: str
    expiry: date
    strike: float = Field(gt=0)
    option_type: OptionType
    bid: float = Field(ge=0)
    ask: float = Field(gt=0)
    delta: float
    quote_timestamp: datetime
    tradable: bool = True

    @model_validator(mode="after")
    def validate_quote(self) -> OptionSnapshot:
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")
        return self

    @property
    def midpoint(self) -> float:
        return (self.bid + self.ask) / 2


class SpreadLeg(StrictModel):
    symbol: str
    side: LegSide
    position_intent: str
    strike: float


class SpreadCandidate(StrictModel):
    underlying: str
    strategy: str
    expiry: date
    option_type: OptionType
    long_contract: OptionSnapshot
    short_contract: OptionSnapshot
    limit_debit: float = Field(gt=0)
    quote_width_ratio: float = Field(ge=0)
    score: float = 0.0

    @property
    def maximum_loss_per_contract(self) -> float:
        return round(self.limit_debit * 100, 2)


class RegimeAssessment(StrictModel):
    regime: Regime
    close: float
    ema_fast: float
    ema_slow: float
    vwap: float
    rsi: float
    realized_volatility: float
    reasons: tuple[str, ...]


class RankerResult(StrictModel):
    selected_index: int | None
    thesis: str
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[str, ...]
    invalidation: str
    source: str

    @field_validator("thesis", "invalidation")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()


class CriticResult(StrictModel):
    approved: bool
    reasons: tuple[str, ...]


class RiskCheck(StrictModel):
    name: str
    passed: bool
    detail: str


class RiskState(StrictModel):
    equity: float
    session_start_equity: float
    daily_drawdown: float
    aggregate_open_risk: float
    open_positions: int
    kill_switch: bool
    checks: tuple[RiskCheck, ...] = ()


class OrderIntent(StrictModel):
    cycle_id: str
    underlying: str
    strategy: str
    expiry: date
    legs: tuple[SpreadLeg, SpreadLeg]
    quantity: int = Field(ge=1)
    limit_debit: float = Field(gt=0)
    maximum_loss: float = Field(gt=0)
    take_profit_pct: float
    stop_loss_pct: float
    client_order_id: str

    @classmethod
    def from_candidate(
        cls,
        cycle_id: str,
        candidate: SpreadCandidate,
        quantity: int,
        take_profit_pct: float,
        stop_loss_pct: float,
    ) -> OrderIntent:
        digest = sha256(
            f"{cycle_id}:{candidate.long_contract.symbol}:{candidate.short_contract.symbol}".encode()
        ).hexdigest()[:24]
        return cls(
            cycle_id=cycle_id,
            underlying=candidate.underlying,
            strategy=candidate.strategy,
            expiry=candidate.expiry,
            legs=(
                SpreadLeg(
                    symbol=candidate.long_contract.symbol,
                    side=LegSide.BUY,
                    position_intent="buy_to_open",
                    strike=candidate.long_contract.strike,
                ),
                SpreadLeg(
                    symbol=candidate.short_contract.symbol,
                    side=LegSide.SELL,
                    position_intent="sell_to_open",
                    strike=candidate.short_contract.strike,
                ),
            ),
            quantity=quantity,
            limit_debit=candidate.limit_debit,
            maximum_loss=round(candidate.maximum_loss_per_contract * quantity, 2),
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            client_order_id=f"aegis-{digest}",
        )


class ExecutionRecord(StrictModel):
    cycle_id: str
    client_order_id: str
    alpaca_order_id: str | None = None
    request_id: str | None = None
    status: str
    submitted_at: datetime = Field(default_factory=utc_now)
    error: str | None = None
    dry_run: bool = True
    raw: dict[str, Any] = Field(default_factory=dict)


class ReconciliationResult(StrictModel):
    matched: bool
    checked_at: datetime = Field(default_factory=utc_now)
    differences: tuple[str, ...] = ()
    sdk_account: dict[str, Any] = Field(default_factory=dict)
    cli_account: dict[str, Any] = Field(default_factory=dict)
    cli_positions: list[dict[str, Any]] = Field(default_factory=list)
    cli_orders: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class AgentDecision(StrictModel):
    cycle_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    underlying: str
    regime: RegimeAssessment
    candidates: tuple[SpreadCandidate, ...]
    selected_spread: SpreadCandidate | None
    ranker: RankerResult
    critic: CriticResult
    risk_state: RiskState
    action: DecisionAction
    reason: str
    order_intent: OrderIntent | None = None
