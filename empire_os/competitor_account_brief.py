"""Account Intelligence Brief + Claim Critic for competitor research.

Builds founder-facing briefs only from canonical competitor evidence and bounded
public research observations. Claims require explicit provenance. Search-result
content never becomes a verified fact merely because it was retrieved.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/competitor_account_briefs_latest.json"
)

_BLOCKED_CLAIM_TERMS = (
    "buyer intent",
    "commercial intent",
    "ready to buy",
    "wants to buy",
    "revenue",
    "market share",
    "customer of",
    "switching from",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _source_refs(values: Iterable[Any]) -> list[str]:
    refs = []
    for value in values:
        ref = _clean(value)
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def critique_claim(claim: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless a claim is explicit, observed, and sourced."""
    text = _clean(claim.get("text"))
    claim_type = _clean(claim.get("claim_type"))
    source_refs = _source_refs(claim.get("source_refs", []) or [])
    observed = claim.get("observed") is True
    blockers: list[str] = []

    if not text:
        blockers.append("claim_text_required")
    if not claim_type:
        blockers.append("claim_type_required")
    if not source_refs:
        blockers.append("claim_source_required")
    if not observed:
        blockers.append("claim_must_be_observed")

    lowered = text.lower()
    if any(term in lowered for term in _BLOCKED_CLAIM_TERMS):
        blockers.append("unsupported_commercial_or_market_inference")

    return {
        "claim_type": claim_type or None,
        "text": text or None,
        "source_refs": source_refs,
        "observed": observed,
        "verdict": "SUPPORTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "execution_authority": "none",
    }


def _canonical_claims(company: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []

    evidence = [
        item
        for item in company.get("evidence", []) or []
        if isinstance(item, Mapping)
    ]
    competitor_sources: dict[str, list[str]] = {}
    for item in evidence:
        competitor_key = _clean(item.get("competitor_key"))
        source_ref = _clean(item.get("source_ref"))
        if competitor_key and source_ref:
            competitor_sources.setdefault(competitor_key, []).append(source_ref)

    company_name = _clean(company.get("company_name"))
    for competitor_key, refs in sorted(competitor_sources.items()):
        unique_refs = _source_refs(refs)
        claims.append({
            "claim_type": "competitor_colisting_observed",
            "text": (
                f"{company_name} was observed on {len(unique_refs)} public "
                f"source(s) that also referenced competitor "
                f"{competitor_key}."
            ),
            "source_refs": unique_refs,
            "observed": True,
        })

    return claims


def _research_claims(research: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    company_name = _clean(research.get("company_name"))
    company_domain = _clean(research.get("company_domain"))

    first_party_refs = _source_refs(
        row.get("url")
        for row in research.get("observations", []) or []
        if isinstance(row, Mapping)
        and row.get("first_party_domain_match") is True
        and _clean(row.get("url"))
    )
    if first_party_refs and company_domain:
        claims.append({
            "claim_type": "first_party_web_presence_observed",
            "text": (
                f"{company_name} first-party web presence was observed at "
                f"{company_domain}."
            ),
            "source_refs": first_party_refs,
            "observed": True,
        })

    reobserved_refs = _source_refs(
        row.get("url")
        for row in research.get("observations", []) or []
        if isinstance(row, Mapping)
        and row.get("existing_evidence_source") is True
        and _clean(row.get("url"))
    )
    if reobserved_refs:
        claims.append({
            "claim_type": "canonical_evidence_reobserved",
            "text": (
                f"{company_name} was re-observed on "
                f"{len(reobserved_refs)} previously known public evidence "
                "source(s)."
            ),
            "source_refs": reobserved_refs,
            "observed": True,
        })

    return claims


def build_account_intelligence_brief(
    company: Mapping[str, Any],
    research: Mapping[str, Any],
) -> dict[str, Any]:
    entity_id = _clean(company.get("entity_id") or research.get("entity_id"))
    company_name = _clean(
        company.get("company_name") or research.get("company_name")
    )

    raw_claims = [
        *_canonical_claims(company),
        *_research_claims(research),
    ]
    reviewed_claims = [critique_claim(claim) for claim in raw_claims]
    supported_claims = [
        claim for claim in reviewed_claims
        if claim["verdict"] == "SUPPORTED"
    ]
    blocked_claims = [
        claim for claim in reviewed_claims
        if claim["verdict"] == "BLOCKED"
    ]

    observations = [
        row
        for row in research.get("observations", []) or []
        if isinstance(row, Mapping)
    ]
    unverified_search_observations = [
        {
            "title": _clean(row.get("title")),
            "url": _clean(row.get("url")),
            "domain": _clean(row.get("domain")) or None,
        }
        for row in observations
        if row.get("observation_type") == "public_search_result"
        and row.get("verified_fact") is not True
    ]

    priority = company.get("research_priority")
    if not isinstance(priority, Mapping):
        priority = {}

    return {
        "schema_version": "empire.account_intelligence_brief.v1",
        "mode": "OBSERVE",
        "entity_id": entity_id,
        "company_name": company_name,
        "company_website": _clean(company.get("company_website")) or None,
        "research_rank": research.get("research_rank"),
        "research_priority_score": priority.get("research_priority_score"),
        "stack_state": priority.get("stack_state"),
        "requested_action": research.get("requested_action"),
        "research_next_step": research.get("next_step"),
        "canonical_evidence_count": int(
            company.get("unique_evidence_count") or 0
        ),
        "research_observation_count": int(
            research.get("observation_count") or 0
        ),
        "claims": supported_claims,
        "claim_critic": {
            "reviewed_count": len(reviewed_claims),
            "supported_count": len(supported_claims),
            "blocked_count": len(blocked_claims),
            "blocked_claims": blocked_claims,
            "all_published_claims_supported": not blocked_claims,
        },
        "unverified_search_observations": unverified_search_observations,
        "unverified_search_observation_count": len(
            unverified_search_observations
        ),
        "buyer_intent": False,
        "commercial_intent": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def build_account_brief_batch(
    audience_snapshot: Mapping[str, Any],
    research_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    companies = {
        _clean(row.get("entity_id")): row
        for row in audience_snapshot.get("companies", []) or []
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    }
    research = {
        _clean(row.get("entity_id")): row
        for row in research_snapshot.get("actions", []) or []
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    }

    briefs = []
    for entity_id, company in companies.items():
        action = research.get(entity_id)
        if action is None:
            continue
        briefs.append(build_account_intelligence_brief(company, action))

    briefs.sort(
        key=lambda row: (
            int(row.get("research_rank") or 999999),
            row.get("company_name") or "",
        )
    )

    return {
        "schema_version": "empire.account_intelligence_brief_batch.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brief_count": len(briefs),
        "supported_claim_count": sum(
            int(row["claim_critic"]["supported_count"]) for row in briefs
        ),
        "blocked_claim_count": sum(
            int(row["claim_critic"]["blocked_count"]) for row in briefs
        ),
        "all_published_claims_supported": all(
            row["claim_critic"]["all_published_claims_supported"]
            for row in briefs
        ),
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "actual_revenue": False,
        "execution_authority": "none",
        "briefs": briefs,
    }


def write_account_brief_snapshot(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def build_account_brief_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.account_intelligence_brief_batch.v1",
            "mode": "OBSERVE",
            "brief_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "actual_revenue": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Account Intelligence Briefs with Claim Critic"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    if not args.build:
        print(json.dumps(
            build_account_brief_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    base = repo_root / "runtime/competitive_intelligence"
    audience = json.loads(
        (base / "competitor_audience_latest.json").read_text(
            encoding="utf-8"
        )
    )
    research = json.loads(
        (base / "competitor_account_research_latest.json").read_text(
            encoding="utf-8"
        )
    )
    payload = build_account_brief_batch(audience, research)
    write_account_brief_snapshot(repo_root, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
