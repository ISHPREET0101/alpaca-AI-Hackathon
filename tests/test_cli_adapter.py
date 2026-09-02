from __future__ import annotations

from aegis_alpha.broker.cli_adapter import AlpacaCLIAdapter
from aegis_alpha.models import AccountSnapshot, PositionSnapshot


def _account() -> AccountSnapshot:
    return AccountSnapshot(
        account_id="paper-account",
        equity=100_000,
        cash=99_000,
        buying_power=198_000,
        options_buying_power=99_000,
        status="ACTIVE",
    )


def _position() -> PositionSnapshot:
    return PositionSnapshot(
        symbol="SPY260915C00500000",
        quantity=1,
        market_value=200,
        unrealized_pl=10,
    )


def test_cli_reconciliation_matches_equivalent_views(settings, monkeypatch) -> None:
    def fake_run_json(self, *arguments):
        if arguments[:2] == ("account", "get"):
            return {"id": "paper-account", "equity": "100000.25"}
        if arguments[:2] == ("position", "list"):
            return [{"symbol": "SPY260915C00500000", "qty": "1"}]
        return []

    monkeypatch.setattr(AlpacaCLIAdapter, "run_json", fake_run_json)

    result = AlpacaCLIAdapter(settings).reconcile(_account(), [_position()])

    assert result.matched
    assert result.differences == ()


def test_cli_reconciliation_halts_on_account_or_position_difference(
    settings, monkeypatch
) -> None:
    def fake_run_json(self, *arguments):
        if arguments[:2] == ("account", "get"):
            return {"id": "different-account", "equity": "99990"}
        if arguments[:2] == ("position", "list"):
            return []
        return []

    monkeypatch.setattr(AlpacaCLIAdapter, "run_json", fake_run_json)

    result = AlpacaCLIAdapter(settings).reconcile(_account(), [_position()])

    assert not result.matched
    assert "account_id differs" in result.differences
    assert any(item.startswith("equity differs") for item in result.differences)
    assert any(item.startswith("position symbols differ") for item in result.differences)


def test_cli_reconciliation_fails_closed_on_malformed_json_shape(settings, monkeypatch) -> None:
    monkeypatch.setattr(AlpacaCLIAdapter, "run_json", lambda self, *arguments: [])

    result = AlpacaCLIAdapter(settings).reconcile(_account(), [])

    assert not result.matched
    assert result.error == "CLI account output must be a JSON object"
