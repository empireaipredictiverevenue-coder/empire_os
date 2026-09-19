"""Observed-history content decay detection."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ContentDecayResult:
    refresh_required: bool | None
    reasons: tuple[str, ...]
    evidence: Mapping[str, Any]
    recommendation: str | None
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def evaluate_content_decay(
    history: Iterable[Mapping[str, Any]],
    *,
    last_modified_at: str | None = None,
    as_of: datetime | None = None,
    stale_days: int = 365,
    decline_ratio: float = 0.2,
) -> ContentDecayResult:
    rows = [dict(r) for r in history]
    reasons: list[str] = []
    evidence: dict[str, Any] = {"observations": len(rows)}

    if len(rows) >= 2:
        first, last = rows[0], rows[-1]
        for metric in ("impressions", "clicks", "ctr", "conversions"):
            old, new = _num(first, metric), _num(last, metric)
            if old is None or new is None or old <= 0:
                continue
            ratio = (old - new) / old
            if ratio >= decline_ratio:
                reasons.append(f"falling_{metric}")
                evidence[f"{metric}_decline_ratio"] = round(ratio, 4)

        old_pos, new_pos = _num(first, "average_position"), _num(last, "average_position")
        if old_pos is not None and new_pos is not None and new_pos > old_pos:
            worsening = (new_pos - old_pos) / max(old_pos, 1.0)
            if worsening >= decline_ratio:
                reasons.append("ranking_deterioration")
                evidence["average_position_worsening_ratio"] = round(worsening, 4)

    if last_modified_at:
        try:
            modified = datetime.fromisoformat(last_modified_at.replace("Z", "+00:00"))
            if modified.tzinfo is None:
                modified = modified.replace(tzinfo=timezone.utc)
            now = as_of or datetime.now(timezone.utc)
            age_days = (now - modified).days
            evidence["content_age_days"] = age_days
            if age_days >= stale_days:
                reasons.append("stale_content")
        except ValueError:
            evidence["last_modified_parse_error"] = True

    enough_evidence = len(rows) >= 2 or "content_age_days" in evidence
    if not enough_evidence:
        return ContentDecayResult(
            None,
            (),
            evidence,
            None,
        )
    return ContentDecayResult(
        bool(reasons),
        tuple(dict.fromkeys(reasons)),
        evidence,
        "mark_refresh_required_for_review" if reasons else "no_refresh_recommended",
    )
