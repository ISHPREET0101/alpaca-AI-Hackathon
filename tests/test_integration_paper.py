from __future__ import annotations

import os

import pytest

from aegis_alpha.broker.alpaca_gateway import AlpacaGateway
from aegis_alpha.config import Settings


@pytest.mark.skipif(
    not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_SECRET_KEY"),
    reason="paper credentials not configured",
)
def test_paper_account_and_clock_are_reachable() -> None:
    settings = Settings.from_env()
    gateway = AlpacaGateway(settings)
    account = gateway.get_account()
    clock = gateway.get_clock()
    assert account.status
    assert clock.next_open
