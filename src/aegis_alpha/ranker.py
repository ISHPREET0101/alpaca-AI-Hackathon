from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from pydantic import ValidationError

from .config import Settings
from .models import RankerResult, RegimeAssessment, SpreadCandidate


class Ranker(Protocol):
    def rank(self, regime: RegimeAssessment, candidates: list[SpreadCandidate]) -> RankerResult: ...


class RuleBasedRanker:
    """Deterministic offline/demo ranker; competition runs should use LLMRanker."""

    def rank(self, regime: RegimeAssessment, candidates: list[SpreadCandidate]) -> RankerResult:
        if not candidates:
            return RankerResult(
                selected_index=None,
                thesis="No structurally valid spread exists for this cycle.",
                confidence=0,
                evidence=tuple(regime.reasons),
                invalidation="A valid and liquid candidate becomes available.",
                source="rule",
            )
        best = max(range(len(candidates)), key=lambda index: candidates[index].score)
        candidate = candidates[best]
        confidence = max(0.0, min(0.85, 0.55 + candidate.score / 5))
        return RankerResult(
            selected_index=best,
            thesis=f"{regime.regime.value.title()} regime supports {candidate.strategy}.",
            confidence=confidence,
            evidence=tuple(regime.reasons),
            invalidation="Regime becomes neutral/opposite or the spread fails liquidity gates.",
            source="rule",
        )


class LLMRanker:
    def __init__(self, settings: Settings, timeout_seconds: int = 20) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    def rank(self, regime: RegimeAssessment, candidates: list[SpreadCandidate]) -> RankerResult:
        if not candidates:
            return RuleBasedRanker().rank(regime, candidates)
        if not self.settings.llm_api_key or not self.settings.llm_model:
            raise RuntimeError("LLM_API_KEY and LLM_MODEL are required in LLM ranker mode")
        compact_candidates = [
            {
                "index": index,
                "strategy": candidate.strategy,
                "expiry": candidate.expiry.isoformat(),
                "long": candidate.long_contract.symbol,
                "short": candidate.short_contract.symbol,
                "long_delta": candidate.long_contract.delta,
                "limit_debit": candidate.limit_debit,
                "quote_width_ratio": candidate.quote_width_ratio,
                "deterministic_score": candidate.score,
            }
            for index, candidate in enumerate(candidates)
        ]
        schema = {
            "selected_index": "integer or null",
            "thesis": "non-empty string",
            "confidence": "number from 0 to 1",
            "evidence": ["short factual string"],
            "invalidation": "non-empty string",
            "source": "llm",
        }
        prompt = (
            "Rank only the supplied defined-risk option spreads. Do not invent contracts, "
            "change sizing, or override risk rules. Return JSON only.\n"
            f"Required shape: {json.dumps(schema)}\n"
            f"Regime: {regime.model_dump_json()}\n"
            f"Candidates: {json.dumps(compact_candidates)}"
        )
        body = json.dumps(
            {
                "model": self.settings.llm_model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a constrained options candidate ranker. Output strict JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.settings.llm_base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode())
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            parsed["source"] = "llm"
            result = RankerResult.model_validate(parsed)
        except (OSError, KeyError, ValueError, ValidationError, urllib.error.URLError) as exc:
            raise RuntimeError(f"LLM ranking failed closed: {exc}") from exc
        if result.selected_index is not None and not 0 <= result.selected_index < len(candidates):
            raise RuntimeError(
                "LLM ranking failed closed: selected_index is outside candidate list"
            )
        return result


def build_ranker(settings: Settings) -> Ranker:
    return LLMRanker(settings) if settings.ranker_mode == "llm" else RuleBasedRanker()
