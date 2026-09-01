from __future__ import annotations

from datetime import date

from .config import Settings
from .models import (
    CriticResult,
    OptionSnapshot,
    OptionType,
    Regime,
    RegimeAssessment,
    SpreadCandidate,
)


class CandidateAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(
        self,
        underlying: str,
        regime: RegimeAssessment,
        chain: list[OptionSnapshot],
        today: date,
    ) -> list[SpreadCandidate]:
        if regime.regime is Regime.NEUTRAL:
            return []
        desired_type = OptionType.CALL if regime.regime is Regime.BULLISH else OptionType.PUT
        eligible = [
            contract
            for contract in chain
            if contract.underlying == underlying
            and contract.option_type is desired_type
            and contract.tradable
            and self.settings.min_dte <= (contract.expiry - today).days <= self.settings.max_dte
            and contract.ask > 0
        ]
        candidates: list[SpreadCandidate] = []
        for expiry in sorted({contract.expiry for contract in eligible}):
            contracts = sorted(
                [contract for contract in eligible if contract.expiry == expiry],
                key=lambda contract: contract.strike,
            )
            if len(contracts) < 2:
                continue
            long_contracts = sorted(
                contracts,
                key=lambda contract: abs(abs(contract.delta) - self.settings.target_delta),
            )[:4]
            for long_contract in long_contracts:
                if desired_type is OptionType.CALL:
                    shorts = [c for c in contracts if c.strike > long_contract.strike]
                else:
                    shorts = [c for c in contracts if c.strike < long_contract.strike]
                    shorts.reverse()
                if not shorts:
                    continue
                short_contract = shorts[0]
                natural_debit = long_contract.ask - short_contract.bid
                midpoint_debit = long_contract.midpoint - short_contract.midpoint
                if natural_debit <= 0 or midpoint_debit <= 0:
                    continue
                width = (long_contract.ask - long_contract.bid) + (
                    short_contract.ask - short_contract.bid
                )
                quote_width_ratio = width / midpoint_debit
                strategy = (
                    "bull_call_debit_spread"
                    if desired_type is OptionType.CALL
                    else "bear_put_debit_spread"
                )
                score = (
                    1.0
                    - abs(abs(long_contract.delta) - self.settings.target_delta)
                    - min(quote_width_ratio, 1.0)
                    - ((expiry - today).days / 100)
                )
                candidates.append(
                    SpreadCandidate(
                        underlying=underlying,
                        strategy=strategy,
                        expiry=expiry,
                        option_type=desired_type,
                        long_contract=long_contract,
                        short_contract=short_contract,
                        limit_debit=round(natural_debit, 2),
                        quote_width_ratio=quote_width_ratio,
                        score=score,
                    )
                )
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:8]


class CriticAgent:
    def review(
        self,
        candidate: SpreadCandidate | None,
        regime: RegimeAssessment,
        existing_symbols: set[str],
    ) -> CriticResult:
        reasons: list[str] = []
        if candidate is None:
            reasons.append("No candidate selected")
        else:
            expected = OptionType.CALL if regime.regime is Regime.BULLISH else OptionType.PUT
            if regime.regime is Regime.NEUTRAL:
                reasons.append("Neutral regimes cannot open positions")
            if candidate.option_type is not expected:
                reasons.append("Candidate direction contradicts the regime")
            if candidate.long_contract.expiry != candidate.short_contract.expiry:
                reasons.append("Spread legs must use the same expiry")
            if candidate.long_contract.underlying != candidate.short_contract.underlying:
                reasons.append("Spread legs must use the same underlying")
            if (
                candidate.long_contract.symbol in existing_symbols
                or candidate.short_contract.symbol in existing_symbols
            ):
                reasons.append("A spread leg is already held")
            if candidate.limit_debit <= 0:
                reasons.append("Spread is not a positive-debit trade")
        return CriticResult(approved=not reasons, reasons=tuple(reasons or ["Structure valid"]))
