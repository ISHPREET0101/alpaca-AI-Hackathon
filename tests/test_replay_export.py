from __future__ import annotations

import json

from aegis_alpha.exporter import export_public_snapshot
from aegis_alpha.models import ExecutionRecord, OrderIntent
from aegis_alpha.replay import build_replay_report, replay_file, write_replay_report


def test_five_scenario_replay(settings) -> None:
    results = replay_file("fixtures/replay_scenarios.json", settings)
    assert len(results) == 5
    assert all(item["matched"] for item in results)
    assert {item["data_source"] for item in results} == {"synthetic_scenario"}


def test_replay_report_is_explicitly_not_a_pnl_claim(settings, tmp_path) -> None:
    report = build_replay_report("fixtures/replay_scenarios.json", settings)
    output = write_replay_report(
        "fixtures/replay_scenarios.json", settings, tmp_path / "replay.json"
    )

    assert report["summary"]["classification_accuracy"] == 1.0
    assert report["validation_scope"] == "regime_classification_only"
    assert report["performance_claim"] == "none"
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["all_matched"]


def test_public_export_has_no_secret_fields(store, tmp_path) -> None:
    store.record_event("example", {"api_key": "secret-value", "safe": "visible"})
    path = export_public_snapshot(store, tmp_path / "public.json")
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert "secret-value" not in text
    assert payload["paper_trading_only"] is True


def test_public_export_includes_safe_trade_lifecycle(store, candidate, tmp_path) -> None:
    intent = OrderIntent.from_candidate("export-cycle", candidate, 1, 0.40, -0.30)
    store.record_execution(
        ExecutionRecord(
            cycle_id=intent.cycle_id,
            client_order_id=intent.client_order_id,
            status="accepted",
            dry_run=False,
        ),
        intent,
    )

    payload = json.loads(
        export_public_snapshot(store, tmp_path / "public.json").read_text(encoding="utf-8")
    )

    assert payload["summary"]["active_trade_count"] == 1
    assert payload["trades"][0]["status"] == "pending_open"
    assert payload["trades"][0]["strategy"] == "bull_call_debit_spread"
