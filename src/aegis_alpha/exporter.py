from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aegis_alpha.store import AuditStore


def _decode_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decoded: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if "payload" in item:
            try:
                item["payload"] = json.loads(item["payload"])
            except (TypeError, json.JSONDecodeError):
                item["payload"] = {}
        decoded.append(item)
    return decoded


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(secret in lowered for secret in ("api_key", "secret", "token", "credential")):
                continue
            if lowered == "account_id" and item:
                clean[key] = f"paper-{hashlib.sha256(str(item).encode()).hexdigest()[:8]}"
            else:
                clean[key] = _redact(item)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def build_public_snapshot(store: AuditStore) -> dict[str, Any]:
    accounts = _decode_rows(store.query_rows("account_snapshots", limit=200))
    decisions = _decode_rows(store.query_rows("decisions", limit=100))
    executions = _decode_rows(store.query_rows("executions", limit=100))
    reconciliations = _decode_rows(store.query_rows("reconciliations", limit=30))
    events = _decode_rows(store.query_rows("events", limit=50))
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_trading_only": True,
        "validation": "Paper and synthetic results are not evidence of live profitability.",
        "summary": {
            "latest_equity": accounts[0]["equity"] if accounts else None,
            "decision_count": len(decisions),
            "execution_count": len(executions),
            "last_reconciliation_matched": bool(reconciliations[0]["matched"])
            if reconciliations
            else None,
        },
        "accounts": accounts,
        "decisions": decisions,
        "executions": executions,
        "reconciliations": reconciliations,
        "events": events,
    }
    return _redact(snapshot)


def export_public_snapshot(store: AuditStore, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_public_snapshot(store), indent=2, default=str), encoding="utf-8"
    )
    return path
