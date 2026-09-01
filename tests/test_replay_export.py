from __future__ import annotations

import json

from aegis_alpha.exporter import export_public_snapshot
from aegis_alpha.replay import replay_file


def test_five_scenario_replay(settings) -> None:
    results = replay_file("fixtures/replay_scenarios.json", settings)
    assert len(results) == 5
    assert all(item["matched"] for item in results)


def test_public_export_has_no_secret_fields(store, tmp_path) -> None:
    store.record_event("example", {"api_key": "secret-value", "safe": "visible"})
    path = export_public_snapshot(store, tmp_path / "public.json")
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert "secret-value" not in text
    assert payload["paper_trading_only"] is True
