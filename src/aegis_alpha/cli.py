from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import uuid
from dataclasses import replace
from datetime import datetime
from datetime import time as clock_time
from pathlib import Path
from zoneinfo import ZoneInfo

from aegis_alpha.broker import AlpacaGateway, FakeBrokerGateway
from aegis_alpha.broker.cli_adapter import AlpacaCLIAdapter
from aegis_alpha.config import Settings
from aegis_alpha.exporter import export_public_snapshot
from aegis_alpha.monitor import PositionMonitor
from aegis_alpha.orchestrator import AgentOrchestrator
from aegis_alpha.ranker import RuleBasedRanker, build_ranker
from aegis_alpha.replay import build_replay_report, write_replay_report
from aegis_alpha.store import AuditStore


def _print(value) -> None:
    print(json.dumps(value, indent=2, default=str))


def _live_components(settings: Settings):
    settings.validate_safety(require_credentials=True)
    store = AuditStore(settings.database_path)
    broker = AlpacaGateway(settings)
    cli_adapter = AlpacaCLIAdapter(settings)
    orchestrator = AgentOrchestrator(
        settings,
        broker,
        store,
        build_ranker(settings),
        cli_adapter=cli_adapter,
        require_cli=True,
    )
    return store, broker, cli_adapter, orchestrator


def command_preflight(settings: Settings) -> int:
    checks = []
    try:
        settings.validate_safety(require_credentials=False)
        checks.append({"name": "paper_only_configuration", "passed": True})
    except ValueError as exc:
        checks.append({"name": "paper_only_configuration", "passed": False, "detail": str(exc)})
    checks.append(
        {
            "name": "credentials_present",
            "passed": bool(settings.api_key and settings.secret_key),
            "detail": "Credentials are read from environment and never printed.",
        }
    )
    cli = AlpacaCLIAdapter(settings)
    checks.append(
        {
            "name": "alpaca_cli_available",
            "passed": cli.available(),
            "detail": f"expected executable={settings.cli_path}",
        }
    )
    if settings.api_key and settings.secret_key:
        try:
            broker = AlpacaGateway(settings)
            account = broker.get_account()
            clock = broker.get_clock()
            checks.append({"name": "paper_api", "passed": True, "account_status": account.status})
            checks.append({"name": "market_clock", "passed": True, "is_open": clock.is_open})
            checks.append(
                {
                    "name": "starting_equity",
                    "passed": abs(account.equity - settings.starting_equity) < 0.01,
                    "detail": (
                        f"equity={account.equity:.2f}, expected={settings.starting_equity:.2f}"
                    ),
                }
            )
            if settings.competition_account_id:
                checks.append(
                    {
                        "name": "competition_account_id",
                        "passed": account.account_id == settings.competition_account_id,
                    }
                )
        except Exception as exc:
            checks.append({"name": "paper_api", "passed": False, "detail": str(exc)})
    _print(
        {"paper_trading_only": True, "checks": checks, "passed": all(c["passed"] for c in checks)}
    )
    return 0 if all(check["passed"] for check in checks) else 1


def command_demo(settings: Settings) -> int:
    local_settings = replace(
        settings,
        database_path=Path(tempfile.gettempdir()) / f"aegis-alpha-demo-{uuid.uuid4().hex}.db",
        dry_run=True,
        ranker_mode="rule",
        kill_switch=False,
    )
    market_zone = ZoneInfo(local_settings.market_timezone)
    demo_now = datetime.combine(datetime.now(market_zone).date(), clock_time(14, 0), market_zone)
    broker = FakeBrokerGateway(bullish=True, now=demo_now)
    store = AuditStore(local_settings.database_path)
    orchestrator = AgentOrchestrator(
        local_settings,
        broker,
        store,
        RuleBasedRanker(),
        cli_adapter=None,
        require_cli=False,
    )
    decisions = orchestrator.run_cycle(dry_run=True, now=demo_now)
    output = export_public_snapshot(store, "artifacts/public/dashboard.json")
    replay_output = write_replay_report(
        "fixtures/replay_scenarios.json",
        local_settings,
        "artifacts/public/replay_report.json",
    )
    _print(
        {
            "mode": "offline_synthetic_dry_run",
            "decisions": [decision.model_dump(mode="json") for decision in decisions],
            "dashboard_snapshot": str(output),
            "replay_report": str(replay_output),
        }
    )
    return 0


def command_cycle(settings: Settings, execute: bool, confirmed: bool) -> int:
    if execute and not confirmed:
        raise SystemExit("Execution requires both --execute and --confirm-paper")
    store, broker, _, orchestrator = _live_components(settings)
    decisions = orchestrator.run_cycle(dry_run=not execute)
    exits = PositionMonitor(settings, broker, store).run(dry_run=not execute)
    _print(
        {
            "decisions": [decision.model_dump(mode="json") for decision in decisions],
            "exits": [exit_record.model_dump(mode="json") for exit_record in exits],
        }
    )
    return 0


def command_schedule(
    settings: Settings, execute: bool, confirmed: bool, max_cycles: int | None
) -> int:
    if execute and not confirmed:
        raise SystemExit("Execution requires both --execute and --confirm-paper")
    count = 0
    while max_cycles is None or count < max_cycles:
        command_cycle(settings, execute, confirmed)
        count += 1
        if max_cycles is None or count < max_cycles:
            time.sleep(settings.cycle_seconds)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aegis Alpha paper-options agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    subparsers.add_parser("demo")
    cycle = subparsers.add_parser("cycle")
    cycle.add_argument("--dry-run", action="store_true")
    cycle.add_argument("--execute", action="store_true")
    cycle.add_argument("--confirm-paper", action="store_true")
    schedule = subparsers.add_parser("schedule")
    schedule.add_argument("--dry-run", action="store_true")
    schedule.add_argument("--execute", action="store_true")
    schedule.add_argument("--confirm-paper", action="store_true")
    schedule.add_argument("--max-cycles", type=int)
    replay = subparsers.add_parser("replay")
    replay.add_argument("--input", required=True)
    replay.add_argument("--output", default="artifacts/public/replay_report.json")
    subparsers.add_parser("reconcile")
    export = subparsers.add_parser("export")
    export.add_argument("--output", default="artifacts/public/dashboard.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    settings = Settings.from_env()
    try:
        if arguments.command == "preflight":
            return command_preflight(settings)
        if arguments.command == "demo":
            return command_demo(settings)
        if arguments.command == "cycle":
            return command_cycle(settings, arguments.execute, arguments.confirm_paper)
        if arguments.command == "schedule":
            return command_schedule(
                settings, arguments.execute, arguments.confirm_paper, arguments.max_cycles
            )
        if arguments.command == "replay":
            report = build_replay_report(arguments.input, settings)
            write_replay_report(arguments.input, settings, arguments.output)
            _print(report)
            return 0 if report["summary"]["all_matched"] else 1
        if arguments.command == "reconcile":
            store, broker, cli_adapter, _ = _live_components(settings)
            result = cli_adapter.reconcile(broker.get_account(), broker.get_positions())
            store.record_reconciliation(result)
            _print(result.model_dump(mode="json"))
            return 0 if result.matched else 1
        if arguments.command == "export":
            path = export_public_snapshot(AuditStore(settings.database_path), arguments.output)
            _print({"output": str(path)})
            return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        _print({"error": str(exc), "failed_closed": True})
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
