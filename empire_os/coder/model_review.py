"""Advisory review by a model distinct from the writer model."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .context import ContextPack
from .models import ModelRoute, VerificationVerdict
from .provider import ModelProvider, ModelRequest


@dataclass(frozen=True)
class ModelReview:
    provider: str
    model: str
    verdict: VerificationVerdict
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    advisory_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "advisory_only": self.advisory_only,
        }


class ModelReviewError(RuntimeError):
    pass


class DistinctModelReviewer:
    """Strict-JSON advisory reviewer; never replaces deterministic checks."""

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    def review(
        self,
        *,
        task_id: str,
        objective: str,
        context: ContextPack,
        route: ModelRoute,
        changed_files: tuple[str, ...],
        diff_excerpt: str,
        max_output_chars: int = 1600,
    ) -> ModelReview:
        response = self.provider.complete(ModelRequest(
            task_id=task_id,
            instruction=(
                "Act as an independent code reviewer, not the writer. "
                "Review the changed-file list and diff excerpt against the "
                "task objective and supplied repository evidence. Do not claim "
                "tests you did not run. Return STRICT JSON only: "
                '{"verdict":"PASS|FAIL|PASS_WITH_WARNINGS",'
                '"reasons":["..."],"warnings":["..."]}. '
                "This review is advisory; deterministic security/tests remain "
                "authoritative.\n\nOBJECTIVE:\n"
                + objective
                + "\n\nCHANGED FILES:\n"
                + json.dumps(list(changed_files))
                + "\n\nDIFF EXCERPT:\n"
                + diff_excerpt[:16000]
            ),
            context=context,
            route=route,
            max_output_chars=max_output_chars,
        ))
        if response.error:
            raise ModelReviewError(response.error)
        try:
            raw = json.loads(response.text.strip())
            verdict = VerificationVerdict(str(raw["verdict"]))
            reasons = self._strings(raw.get("reasons"))
            warnings = self._strings(raw.get("warnings"))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise ModelReviewError(
                "verifier model did not return valid strict JSON"
            ) from exc
        return ModelReview(
            provider=route.provider,
            model=route.model,
            verdict=verdict,
            reasons=reasons,
            warnings=warnings,
            advisory_only=True,
        )

    @staticmethod
    def _strings(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise TypeError("review fields must be string arrays")
        return tuple(item[:1000] for item in value)
