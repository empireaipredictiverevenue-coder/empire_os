"""Evidence-backed search-intent cannibalisation detection."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CannibalisationFinding:
    pages: tuple[str, ...]
    overlap_key: str
    evidence: Mapping[str, Any]
    recommendation: str
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def detect_cannibalisation(
    pages: Iterable[Mapping[str, Any]],
) -> list[CannibalisationFinding]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for raw in pages:
        page = dict(raw)
        query = _norm(page.get("target_query"))
        intent = _norm(page.get("search_intent"))
        topic = _norm(page.get("topic"))
        if not query and not topic:
            continue
        key = (query or "", intent or "", topic or "")
        groups.setdefault(key, []).append(page)

    findings: list[CannibalisationFinding] = []
    for key, rows in groups.items():
        urls = tuple(
            str(r.get("canonical_url") or r.get("url") or "").strip()
            for r in rows
            if r.get("canonical_url") or r.get("url")
        )
        if len(urls) < 2:
            continue

        ranked = sorted(
            rows,
            key=lambda r: (
                r.get("revenue_attributed_cents")
                if r.get("revenue_attributed_cents") is not None else -1,
                r.get("content_quality_score")
                if r.get("content_quality_score") is not None else -1,
            ),
            reverse=True,
        )
        top = ranked[0]
        top_signal_known = (
            top.get("revenue_attributed_cents") is not None
            or top.get("content_quality_score") is not None
        )
        recommendation = (
            "strengthen_primary_and_differentiate_others"
            if top_signal_known
            else "differentiate_targeting_or_review_merge_canonical_options"
        )
        findings.append(CannibalisationFinding(
            pages=urls,
            overlap_key="|".join(key),
            evidence={
                "target_query": key[0] or None,
                "search_intent": key[1] or None,
                "topic": key[2] or None,
                "observed_page_count": len(urls),
                "candidate_primary_url": (
                    str(top.get("canonical_url") or top.get("url") or "").strip()
                    if top_signal_known else None
                ),
            },
            recommendation=recommendation,
        ))
    return findings
