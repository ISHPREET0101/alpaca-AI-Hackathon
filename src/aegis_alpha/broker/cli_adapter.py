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
        differences: list[str] = []
        cli_id = str(cli_account.get("id", ""))
        if cli_id and cli_id != sdk_account.account_id:
            differences.append("account_id differs")
        cli_equity = float(cli_account.get("equity", 0))
        if abs(cli_equity - sdk_account.equity) > 1.0:
            differences.append(f"equity differs: sdk={sdk_account.equity}, cli={cli_equity}")
        sdk_symbols = {position.symbol for position in sdk_positions if position.quantity != 0}
        cli_symbols = {
            str(position.get("symbol"))
            for position in cli_positions
            if float(position.get("qty", 0)) != 0
        }
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
