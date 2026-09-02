from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from aegis_alpha.config import Settings
from aegis_alpha.models import AccountSnapshot, PositionSnapshot, ReconciliationResult


class CLIUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AlpacaCLIAdapter:
    settings: Settings

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["ALPACA_LIVE_TRADE"] = "false"
        environment["ALPACA_OUTPUT"] = "json"
        environment["ALPACA_QUIET"] = "true"
        if self.settings.cli_profile:
            environment["ALPACA_PROFILE"] = self.settings.cli_profile
        return environment

    def available(self) -> bool:
        return shutil.which(self.settings.cli_path) is not None

    def run_json(self, *arguments: str) -> Any:
        if not self.available():
            raise CLIUnavailable(f"Alpaca CLI was not found at {self.settings.cli_path!r}")
        command = [self.settings.cli_path, *arguments, "--quiet", "--timeout", "30"]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=40,
            env=self._environment(),
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise CLIUnavailable(f"CLI command failed ({completed.returncode}): {message}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise CLIUnavailable("CLI output was not valid JSON") from exc

    def reconcile(
        self,
        sdk_account: AccountSnapshot,
        sdk_positions: list[PositionSnapshot],
    ) -> ReconciliationResult:
        try:
            cli_account = self.run_json("account", "get")
            cli_positions = self.run_json("position", "list")
            cli_orders = self.run_json("order", "list", "--status", "open")
        except CLIUnavailable as exc:
            return ReconciliationResult(matched=False, error=str(exc), differences=(str(exc),))
        if not isinstance(cli_account, dict):
            message = "CLI account output must be a JSON object"
            return ReconciliationResult(matched=False, error=message, differences=(message,))
        if not isinstance(cli_positions, list) or not all(
            isinstance(position, dict) for position in cli_positions
        ):
            message = "CLI position output must be a JSON array of objects"
            return ReconciliationResult(matched=False, error=message, differences=(message,))
        if not isinstance(cli_orders, list) or not all(
            isinstance(order, dict) for order in cli_orders
        ):
            message = "CLI order output must be a JSON array of objects"
            return ReconciliationResult(matched=False, error=message, differences=(message,))
        differences: list[str] = []
        cli_id = str(cli_account.get("id", ""))
        if not cli_id:
            differences.append("CLI account id is missing")
        elif cli_id != sdk_account.account_id:
            differences.append("account_id differs")
        try:
            cli_equity = float(cli_account["equity"])
        except (KeyError, TypeError, ValueError):
            differences.append("CLI account equity is missing or invalid")
        else:
            if abs(cli_equity - sdk_account.equity) > 1.0:
                differences.append(f"equity differs: sdk={sdk_account.equity}, cli={cli_equity}")
        sdk_symbols = {position.symbol for position in sdk_positions if position.quantity != 0}
        try:
            cli_symbols = {
                str(position["symbol"])
                for position in cli_positions
                if float(position.get("qty", 0)) != 0
            }
        except (KeyError, TypeError, ValueError):
            differences.append("CLI position fields are missing or invalid")
            cli_symbols = set()
        if sdk_symbols != cli_symbols:
            differences.append(
                f"position symbols differ: sdk={sorted(sdk_symbols)}, cli={sorted(cli_symbols)}"
            )
        return ReconciliationResult(
            matched=not differences,
            differences=tuple(differences),
            sdk_account=sdk_account.model_dump(mode="json"),
            cli_account=cli_account,
            cli_positions=cli_positions,
            cli_orders=cli_orders,
        )
