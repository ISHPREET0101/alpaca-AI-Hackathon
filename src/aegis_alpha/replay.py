from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aegis_alpha.config import Settings
from aegis_alpha.indicators import assess_regime
from aegis_alpha.models import MarketBar


def _scenario_bars(scenario: dict[str, Any]) -> list[MarketBar]:
    if "market_bars" in scenario:
        bars = [MarketBar.model_validate(bar) for bar in scenario["market_bars"]]
        if len(bars) < 30:
            raise ValueError("Historical replay scenarios require at least 30 bars")
        return bars
    start = datetime.fromisoformat(scenario["start"])
    base = float(scenario.get("base", 500))
    slope = float(scenario.get("slope", 0))
    noise = float(scenario.get("noise", 0.02))
    bars = []
    for index in range(int(scenario.get("bars", 78))):
        price = base + slope * index + math.sin(index * 1.7) * noise
        bars.append(
            MarketBar(
                timestamp=start + timedelta(minutes=5 * index),
                open=max(0.01, price - slope / 2),
                high=max(0.02, price + abs(noise) + 0.05),
                low=max(0.01, price - abs(noise) - 0.05),
                close=max(0.01, price),
                volume=1_000_000 + index * 1_000,
                vwap=max(0.01, price - slope),
            )
        )
    return bars


def replay_file(path: str | Path, settings: Settings) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios", [])
    if len(scenarios) < 5:
        raise ValueError("Replay input must contain at least five scenarios or market days")
    results = []
    for scenario in scenarios:
        assessment = assess_regime(_scenario_bars(scenario))
        results.append(
            {
                "name": scenario["name"],
                "expected": scenario.get("expected"),
                "actual": assessment.regime.value,
                "matched": scenario.get("expected") in {None, assessment.regime.value},
                "data_source": (
                    "provided_market_bars"
                    if "market_bars" in scenario
                    else "synthetic_scenario"
                ),
                "assessment": assessment.model_dump(mode="json"),
            }
        )
    return results


def build_replay_report(path: str | Path, settings: Settings) -> dict[str, Any]:
    results = replay_file(path, settings)
    matched = sum(bool(item["matched"]) for item in results)
    sources = sorted({str(item["data_source"]) for item in results})
    return {
        "schema_version": 1,
        "validation_scope": "regime_classification_only",
        "performance_claim": "none",
        "warning": (
            "This replay validates deterministic signal classification. It does not model "
            "option fills, slippage, fees, or strategy P&L."
        ),
        "input": str(path),
        "data_sources": sources,
        "summary": {
            "scenario_count": len(results),
            "matched_count": matched,
            "classification_accuracy": matched / len(results),
            "all_matched": matched == len(results),
        },
        "results": results,
    }


def write_replay_report(
    path: str | Path, settings: Settings, output: str | Path
) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_replay_report(path, settings), indent=2, default=str),
        encoding="utf-8",
    )
    return output_path
