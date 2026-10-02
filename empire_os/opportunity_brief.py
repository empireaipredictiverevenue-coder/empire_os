"""Evidence-backed one-page opportunity briefs for governed conversations."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import json
import re


OUTPUT = Path("runtime/opportunity_briefs/latest.json")
OUTPUT_DIR = Path("runtime/opportunity_briefs/accounts")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: Iterable[Any]) -> list[str]:
    rows: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in rows:
            rows.append(text)
    return rows


def _supported_claims(account: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for raw in account.get("claims") or []:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("verdict") != "SUPPORTED":
            continue
        refs = _unique(raw.get("source_refs") or [])
        text = _text(raw.get("text"))
        if not text or not refs or raw.get("observed") is not True:
            continue
        claims.append({
            "claim_type": _text(raw.get("claim_type")) or None,
            "text": text,
            "source_refs": refs,
            "observed": True,
        })
    return claims


def _hypotheses(account: Mapping[str, Any]) -> list[dict[str, Any]]:
    company = _text(account.get("company_name")) or "the company"
    return [
        {
            "hypothesis": (
                f"Validate whether {company} has an addressable demand gap "
                "that Empire can measure from current market/search evidence."
            ),
            "status": "UNVERIFIED_HYPOTHESIS",
            "test": "measure current high-intent demand and evidence coverage",
        },
        {
            "hypothesis": (
                "Test whether observed competitive overlap exposes a practical "
                "positioning or acquisition opportunity."
            ),
            "status": "UNVERIFIED_HYPOTHESIS",
            "test": (
                "compare observed competitor presence against "
                "first-party presence"
            ),
        },
    ]


def build_opportunity_brief(
    account: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    if account.get("mode") != "OBSERVE":
        raise ValueError("account intelligence must remain OBSERVE")
    if account.get("execution_authority") not in {None, "none"}:
        raise ValueError("account intelligence carries execution authority")
    if (
        account.get("buyer_intent") is True
        or account.get("commercial_intent") is True
    ):
        raise ValueError("unsupported commercial intent promotion")

    company = _text(account.get("company_name"))
    entity_id = _text(account.get("entity_id"))
    if not company or not entity_id:
        raise ValueError("canonical company identity required")

    claims = _supported_claims(account)
    critic = (
        dict(account.get("claim_critic") or {})
        if isinstance(account.get("claim_critic"), Mapping)
        else {}
    )
    blocked = int(critic.get("blocked_count") or 0)
    first_party = [
        claim
        for claim in claims
        if claim.get("claim_type") == "first_party_web_presence_observed"
    ]
    review_ready = bool(claims and first_party and blocked == 0)

    source_refs = _unique(
        ref
        for claim in claims
        for ref in claim.get("source_refs") or []
    )
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("generated_at must include timezone")

    unknowns = [
        "buyer_intent",
        "commercial_demand",
        "territory",
        "buyer_capacity",
        "delivery_route",
        "pricing",
        "commercial_terms",
        "customer_outcome",
        "actual_revenue",
    ]
    return {
        "schema_version": "empire.evidence-opportunity-brief.v1",
        "mode": "REVIEW_ONLY",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "entity_id": entity_id,
        "company_name": company,
        "company_website": _text(account.get("company_website")) or None,
        "observed_facts": claims,
        "supported_fact_count": len(claims),
        "evidence_quality": {
            "canonical_evidence_count": int(
                account.get("canonical_evidence_count") or 0
            ),
            "research_observation_count": int(
                account.get("research_observation_count") or 0
            ),
            "claim_critic_blocked_count": blocked,
            "all_published_claims_supported": blocked == 0,
        },
        "opportunity_hypotheses": _hypotheses(account),
        "first_test": {
            "name": "evidence_backed_market_gap_validation",
            "objective": (
                "Measure current demand, search and competitive evidence "
                "before making any commercial or revenue claim."
            ),
            "execution_authority": "none",
        },
        "unknowns": unknowns,
        "source_refs": source_refs,
        "review_ready": review_ready,
        "send_approved": False,
        "external_send_allowed": False,
        "buyer_intent_inferred": False,
        "commercial_demand_inferred": False,
        "pricing_inferred": False,
        "capacity_inferred": False,
        "results_inferred": False,
        "revenue_inferred": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def render_opportunity_brief_markdown(payload: Mapping[str, Any]) -> str:
    facts = payload.get("observed_facts") or []
    hypotheses = payload.get("opportunity_hypotheses") or []
    unknowns = payload.get("unknowns") or []
    sources = payload.get("source_refs") or []

    lines = [
        f"# {_text(payload.get('company_name'))} - Evidence Opportunity Brief",
        "",
        "## Observed evidence",
    ]
    if facts:
        for fact in facts:
            lines.append(f"- {_text(fact.get('text'))}")
    else:
        lines.append("- No publishable observed facts yet.")

    lines.extend(["", "## Opportunities to test"])
    for item in hypotheses:
        lines.append(
            f"- Hypothesis: {_text(item.get('hypothesis'))} "
            f"Test: {_text(item.get('test'))}"
        )

    first_test = payload.get("first_test") or {}
    lines.extend([
        "",
        "## First test",
        _text(first_test.get("objective")),
        "",
        "## Still unknown",
        ", ".join(_text(value) for value in unknowns if _text(value)),
        "",
        "## Evidence sources",
    ])
    for ref in sources:
        lines.append(f"- {ref}")

    lines.extend([
        "",
        "Internal review brief only. Buyer intent, pricing, capacity, "
        "commercial terms and revenue are not inferred.",
        "",
    ])
    return "\n".join(lines)


def materialize_opportunity_briefs(
    source: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in source.get("briefs") or []
        if isinstance(row, Mapping)
    ]
    briefs = [
        build_opportunity_brief(row, generated_at=generated_at)
        for row in rows
    ]
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("generated_at must include timezone")
    return {
        "schema_version": "empire.evidence-opportunity-brief-batch.v1",
        "mode": "REVIEW_ONLY",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "brief_count": len(briefs),
        "review_ready_count": sum(
            brief.get("review_ready") is True for brief in briefs
        ),
        "briefs": briefs,
        "external_send_allowed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def write_opportunity_briefs(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> list[Path]:
    root = Path(repo_root).resolve()
    latest = root / OUTPUT
    account_dir = root / OUTPUT_DIR
    latest.parent.mkdir(parents=True, exist_ok=True)
    account_dir.mkdir(parents=True, exist_ok=True)

    tmp = latest.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(latest)

    written = [latest]
    for brief in payload.get("briefs") or []:
        if not isinstance(brief, Mapping):
            continue
        entity = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            _text(brief.get("entity_id")),
        )
        if not entity:
            continue
        path = account_dir / f"{entity}.md"
        path.write_text(
            render_opportunity_brief_markdown(brief),
            encoding="utf-8",
        )
        written.append(path)
    return written
