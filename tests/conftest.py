from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from aegis_alpha.config import Settings
from aegis_alpha.models import OptionSnapshot, OptionType, SpreadCandidate
from aegis_alpha.store import AuditStore


@pytest.fixture
def market_now() -> datetime:
    return datetime.combine(
        date(2026, 9, 1),
        datetime.strptime("14:00", "%H:%M").time(),
        ZoneInfo("America/New_York"),
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return replace(
        Settings(),
        database_path=tmp_path / "test.db",
        ranker_mode="rule",
        dry_run=True,
        kill_switch=False,
    )


@pytest.fixture
def store(settings: Settings) -> AuditStore:
    return AuditStore(settings.database_path)


@pytest.fixture
def candidate(market_now: datetime) -> SpreadCandidate:
    expiry = market_now.date() + timedelta(days=14)
    long_contract = OptionSnapshot(
        symbol="SPY260915C00500000",
        underlying="SPY",
        expiry=expiry,
        strike=500,
        option_type=OptionType.CALL,
        bid=1.98,
        ask=2.02,
        delta=0.45,
        quote_timestamp=market_now,
    )
    short_contract = OptionSnapshot(
        symbol="SPY260915C00505000",
        underlying="SPY",
        expiry=expiry,
        strike=505,
        option_type=OptionType.CALL,
        bid=1.00,
        ask=1.04,
        delta=0.30,
        quote_timestamp=market_now,
    )
    return SpreadCandidate(
        underlying="SPY",
        strategy="bull_call_debit_spread",
        expiry=expiry,
        option_type=OptionType.CALL,
        long_contract=long_contract,
        short_contract=short_contract,
        limit_debit=1.02,
        quote_width_ratio=0.08,
        score=0.8,
    )
