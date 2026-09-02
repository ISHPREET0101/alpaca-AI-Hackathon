from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from aegis_alpha.broker.base import BrokerGateway
from aegis_alpha.broker.cli_adapter import AlpacaCLIAdapter
from aegis_alpha.config import Settings
from aegis_alpha.indicators import assess_regime
from aegis_alpha.models import (
    AgentDecision,
    CriticResult,
    DecisionAction,
    OrderIntent,
    RankerResult,
    ReconciliationResult,
)
from aegis_alpha.ranker import Ranker
from aegis_alpha.risk import RiskGuard
from aegis_alpha.store import AuditStore
from aegis_alpha.strategy import CandidateAgent, CriticAgent


class AgentOrchestrator:
    def __init__(
        self,
        settings: Settings,
        broker: BrokerGateway,
        store: AuditStore,
        ranker: Ranker,
        cli_adapter: AlpacaCLIAdapter | None = None,
        require_cli: bool = True,
    ) -> None:
        self.settings = settings
        self.broker = broker
        self.store = store
        self.ranker = ranker
        self.cli_adapter = cli_adapter
        self.require_cli = require_cli
        self.candidate_agent = CandidateAgent(settings)
        self.critic_agent = CriticAgent()
        self.risk_guard = RiskGuard(settings, store)

    @staticmethod
    def _cycle_id(underlying: str, now: datetime) -> str:
        bucket = int(now.timestamp()) // 300
        return sha256(f"{underlying}:{bucket}".encode()).hexdigest()[:24]

    def _reconcile(self, account, positions) -> ReconciliationResult:
        if self.cli_adapter is None:
            if self.require_cli:
                return ReconciliationResult(
                    matched=False,
                    differences=("CLI reconciliation is required but no adapter is configured",),
                    error="CLI adapter missing",
                )
            return ReconciliationResult(matched=True)
        result = self.cli_adapter.reconcile(account, positions)
        self.store.record_reconciliation(result)
        return result

    def run_cycle(
        self, dry_run: bool | None = None, now: datetime | None = None
    ) -> list[AgentDecision]:
        now = now or datetime.now(timezone.utc)
        dry_run = self.settings.dry_run if dry_run is None else dry_run
        self.settings.validate_safety(require_credentials=False)
        if not self.store.acquire_lock("agent-cycle", stale_after_seconds=600):
            raise RuntimeError("Another agent cycle is already running")
        try:
            account = self.broker.get_account()
            positions = self.broker.get_positions()
            self.store.record_account(account)
            position_symbols = {
                position.symbol for position in positions if position.quantity != 0
            }
            opened, partial = self.store.reconcile_pending_trades(position_symbols)
            for client_order_id in opened:
                self.store.record_event(
                    "position_open_confirmed",
                    {"client_order_id": client_order_id, "source": "pretrade_positions"},
                )
            for client_order_id in partial:
                self.store.record_event(
                    "partial_spread_fill_halt",
                    {"client_order_id": client_order_id},
                    severity="critical",
                )
            closed = self.store.reconcile_closing_trades(position_symbols)
            for client_order_id in closed:
                self.store.record_event(
                    "position_close_confirmed",
                    {"client_order_id": client_order_id, "source": "pretrade_positions"},
                )
            if (
                self.settings.competition_account_id
                and account.account_id != self.settings.competition_account_id
            ):
                raise RuntimeError("Connected account does not match COMPETITION_ACCOUNT_ID")
            reconciliation = self._reconcile(account, positions)
            execution_state_safe = reconciliation.matched and not partial
            decisions = [
                self._run_underlying(
                    symbol,
                    account,
                    positions,
                    execution_state_safe,
                    dry_run,
                    now,
                )
                for symbol in self.settings.underlyings
            ]
            post_positions = self.broker.get_positions()
            post_reconciliation = self._reconcile(account, post_positions)
            if not post_reconciliation.matched:
                self.store.record_event(
                    "post_cycle_reconciliation_failed",
                    post_reconciliation.model_dump(mode="json"),
                    severity="critical",
                )
            return decisions
        finally:
            self.store.release_lock("agent-cycle")

    def _run_underlying(
        self,
        symbol,
        account,
        positions,
        cli_matched: bool,
        dry_run: bool,
        now: datetime,
    ) -> AgentDecision:
        cycle_id = self._cycle_id(symbol, now)
        bars = self.broker.get_bars(symbol, end=now)
        regime = assess_regime(bars)
        chain = self.broker.get_option_chain(symbol, now=now)
        candidates = self.candidate_agent.generate(symbol, regime, chain, now.date())
        try:
            ranker_result = self.ranker.rank(regime, candidates)
        except Exception as exc:
            ranker_result = RankerResult(
                selected_index=None,
                thesis="Ranking failed, so the agent failed closed.",
                confidence=0,
                evidence=(str(exc),),
                invalidation="A valid structured ranker response is required.",
                source="error",
            )
        selected = (
            candidates[ranker_result.selected_index]
            if ranker_result.selected_index is not None
            else None
        )
        existing_symbols = {position.symbol for position in positions}
        critic = self.critic_agent.review(selected, regime, existing_symbols)
        risk_state, quantity = self.risk_guard.evaluate(
            account, selected if critic.approved else None, now=now, cli_matched=cli_matched
        )
        all_risk_checks_pass = all(check.passed for check in risk_state.checks)
        intent = None
        action = DecisionAction.NO_TRADE
        reason = "No candidate passed all gates"
        execution = None
        if selected and critic.approved and all_risk_checks_pass and quantity >= 1:
            intent = OrderIntent.from_candidate(
                cycle_id,
                selected,
                quantity,
                self.settings.take_profit_pct,
                self.settings.stop_loss_pct,
            )
            if self.store.execution_exists(intent.client_order_id):
                reason = "Idempotency gate blocked a duplicate order"
            else:
                execution = self.broker.submit_spread(intent, dry_run=dry_run)
                self.store.record_execution(execution, intent)
                if execution.status != "error":
                    action = DecisionAction.BUY_SPREAD
                    reason = (
                        "All deterministic gates passed; order prepared"
                        if dry_run
                        else "Paper order submitted"
                    )
                else:
                    reason = f"Broker rejected the order: {execution.error}"
        decision = AgentDecision(
            cycle_id=cycle_id,
            underlying=symbol,
            regime=regime,
            candidates=tuple(candidates),
            selected_spread=selected,
            ranker=ranker_result,
            critic=critic
            if selected
            else CriticResult(approved=False, reasons=("No candidate selected",)),
            risk_state=risk_state,
            action=action,
            reason=reason,
            order_intent=intent,
        )
        self.store.record_decision(decision)
        return decision
