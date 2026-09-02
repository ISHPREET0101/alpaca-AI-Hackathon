from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import (
    AccountSnapshot,
    AgentDecision,
    ExecutionRecord,
    OrderIntent,
    ReconciliationResult,
)


class AuditStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS decisions (
                    cycle_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    underlying TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions (
                    client_order_id TEXT PRIMARY KEY,
                    cycle_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_id TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS account_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    equity REAL NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconciliations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    matched INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS open_trades (
                    client_order_id TEXT PRIMARY KEY,
                    underlying TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    entry_debit REAL NOT NULL,
                    risk_dollars REAL NOT NULL,
                    status TEXT NOT NULL,
                    intent TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS locks (
                    name TEXT PRIMARY KEY,
                    acquired_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _json(value: BaseModel | dict[str, Any] | list[Any]) -> str:
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        return json.dumps(value, default=str, separators=(",", ":"))

    def record_decision(self, decision: AgentDecision) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO decisions
                (cycle_id, created_at, underlying, action, reason, payload)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    decision.cycle_id,
                    decision.timestamp.isoformat(),
                    decision.underlying,
                    decision.action.value,
                    decision.reason,
                    self._json(decision),
                ),
            )

    def record_execution(
        self, execution: ExecutionRecord, intent: OrderIntent | None = None
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO executions
                (client_order_id, cycle_id, created_at, status, request_id, payload)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    execution.client_order_id,
                    execution.cycle_id,
                    execution.submitted_at.isoformat(),
                    execution.status,
                    execution.request_id,
                    self._json(execution),
                ),
            )
            if intent and execution.status in {"accepted", "new", "filled", "dry_run"}:
                trade_status = (
                    "simulated"
                    if execution.dry_run
                    else "open"
                    if execution.status == "filled"
                    else "pending_open"
                )
                connection.execute(
                    """INSERT OR IGNORE INTO open_trades
                    (client_order_id, underlying, opened_at, entry_debit,
                     risk_dollars, status, intent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        intent.client_order_id,
                        intent.underlying,
                        execution.submitted_at.isoformat(),
                        intent.limit_debit,
                        intent.maximum_loss,
                        trade_status,
                        self._json(intent),
                    ),
                )

    def record_account(self, account: AccountSnapshot) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO account_snapshots (created_at, account_id, equity, payload)
                VALUES (?, ?, ?, ?)""",
                (
                    account.captured_at.isoformat(),
                    account.account_id,
                    account.equity,
                    self._json(account),
                ),
            )

    def record_reconciliation(self, result: ReconciliationResult) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO reconciliations (created_at, matched, payload) VALUES (?, ?, ?)",
                (result.checked_at.isoformat(), int(result.matched), self._json(result)),
            )

    def record_event(
        self, event_type: str, payload: dict[str, Any], severity: str = "info"
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO events
                (created_at, event_type, severity, payload) VALUES (?, ?, ?, ?)""",
                (now, event_type, severity, self._json(payload)),
            )

    def execution_exists(self, client_order_id: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM executions WHERE client_order_id = ?", (client_order_id,)
            ).fetchone()
        return row is not None

    def open_trade_summary(self) -> tuple[int, float]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS count, COALESCE(SUM(risk_dollars), 0) AS risk
                FROM open_trades WHERE status IN ('pending_open', 'open', 'closing')"""
            ).fetchone()
        return int(row["count"]), float(row["risk"])

    def list_open_trades(self) -> list[tuple[OrderIntent, float]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT intent, entry_debit FROM open_trades WHERE status = 'open'"
            ).fetchall()
        return [
            (OrderIntent.model_validate_json(row["intent"]), float(row["entry_debit"]))
            for row in rows
        ]

    def mark_trade_closed(self, client_order_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE open_trades SET status = 'closed' WHERE client_order_id = ?",
                (client_order_id,),
            )

    def mark_trade_closing(self, client_order_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE open_trades SET status = 'closing' WHERE client_order_id = ?",
                (client_order_id,),
            )

    def reconcile_pending_trades(
        self, position_symbols: set[str]
    ) -> tuple[list[str], list[str]]:
        """Promote fully present spreads; identify dangerous one-leg partial fills."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT client_order_id, intent FROM open_trades WHERE status = 'pending_open'"
            ).fetchall()
            opened: list[str] = []
            partial: list[str] = []
            for row in rows:
                intent = OrderIntent.model_validate_json(row["intent"])
                present = sum(leg.symbol in position_symbols for leg in intent.legs)
                if present == len(intent.legs):
                    connection.execute(
                        "UPDATE open_trades SET status = 'open' WHERE client_order_id = ?",
                        (row["client_order_id"],),
                    )
                    opened.append(str(row["client_order_id"]))
                elif present:
                    partial.append(str(row["client_order_id"]))
        return opened, partial

    def reconcile_closing_trades(self, position_symbols: set[str]) -> list[str]:
        """Close pending records only after neither option leg remains at the broker."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT client_order_id, intent FROM open_trades WHERE status = 'closing'"
            ).fetchall()
            closed: list[str] = []
            for row in rows:
                intent = OrderIntent.model_validate_json(row["intent"])
                if not any(leg.symbol in position_symbols for leg in intent.legs):
                    connection.execute(
                        "UPDATE open_trades SET status = 'closed' WHERE client_order_id = ?",
                        (row["client_order_id"],),
                    )
                    closed.append(str(row["client_order_id"]))
        return closed

    def trade_status(self, client_order_id: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT status FROM open_trades WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchone()
        return str(row["status"]) if row else None

    def traded_underlying_today(self, underlying: str, iso_date: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT 1 FROM open_trades
                WHERE underlying = ? AND substr(opened_at, 1, 10) = ? LIMIT 1""",
                (underlying, iso_date),
            ).fetchone()
        return row is not None

    def latest_trade_time(self, underlying: str) -> datetime | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT MAX(opened_at) AS opened_at FROM open_trades WHERE underlying = ?",
                (underlying,),
            ).fetchone()
        return datetime.fromisoformat(row["opened_at"]) if row and row["opened_at"] else None

    def acquire_lock(self, name: str, stale_after_seconds: int) -> bool:
        now = datetime.now(timezone.utc)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT acquired_at FROM locks WHERE name = ?", (name,)
            ).fetchone()
            if row:
                acquired = datetime.fromisoformat(row["acquired_at"])
                if (now - acquired).total_seconds() < stale_after_seconds:
                    return False
            connection.execute(
                "INSERT OR REPLACE INTO locks (name, acquired_at) VALUES (?, ?)",
                (name, now.isoformat()),
            )
        return True

    def release_lock(self, name: str) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM locks WHERE name = ?", (name,))

    def query_rows(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        allowed = {"decisions", "executions", "account_snapshots", "reconciliations", "events"}
        if table not in allowed:
            raise ValueError(f"Unsupported table: {table}")
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT ?",
                (limit,),  # noqa: S608
            ).fetchall()
        return [dict(row) for row in rows]

    def trade_rows(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM open_trades ORDER BY opened_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
