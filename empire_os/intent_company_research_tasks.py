"""Bounded intent → company research tasks inside EmpireOS commercial registry.

Tasks are read-only evidence reviews, not CRM contacts or outreach.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence

ELIGIBLE = frozenset({
    "EXPLICIT_REQUEST_UNVERIFIED", "OPERATOR_PROBLEM_SELF_REPORTED",
})
MAX_TASKS = 12


def task_id(url: str) -> str:
    return "intent-research:" + sha256(url.encode()).hexdigest()[:20]


def build_tasks(
    observations: Sequence[Mapping[str, Any]], *,
    now: datetime | None = None,
    previous_tasks: Sequence[Mapping[str, Any]] = (),
    public_affiliation_evidence: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    previous = {
        str(x.get("task_id")): x for x in previous_tasks
        if isinstance(x, Mapping) and x.get("task_id")
    }
    validated_notes = {
        str(r["source_post_url"]): dict(r)
        for r in public_affiliation_evidence
    }
    seen: set[str] = set()
    candidates = []
    class_counts = Counter()
    for item in observations:
        detail = item.get("icp_relevance")
        if not isinstance(detail, Mapping):
            continue
        category = str(detail.get("intent_class") or "")
        class_counts[category] += 1
        if category not in ELIGIBLE:
            continue
        score = int(item.get("reported_intent_score") or 0)
        if (category == "OPERATOR_PROBLEM_SELF_REPORTED" and score < 45
                and not item.get("potential_company_matches")):
            continue
        url = item.get("public_post_url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            continue
        key = task_id(url)
        if key in seen:
            continue
        seen.add(key)
        matches = item.get("potential_company_matches") or []
        affiliation = validated_notes.get(url)
        has_evidence = bool(matches) or bool(affiliation)
        # Raw signal score is a tiebreaker, not proof of buying intent.
        priority = (
            (2 if category == "EXPLICIT_REQUEST_UNVERIFIED" else 1),
            (1 if has_evidence else 0),
            int(item.get("reported_intent_score") or 0),
        )
        prior = previous.get(key) or {}
        # Preserve first observation across refreshes, never inherit
        # approval, contact, terms or execution authority from old records.
        first_seen = prior.get("first_seen_at") or now.isoformat()
        tasks = {
            "task_id": key,
            "first_seen_at": first_seen,
            "last_evaluated_at": now.isoformat(),
            "source_url": url,
            "source": item.get("channel"),
            "observed_at": item.get("observed_at"),
            "niche": item.get("niche"),
            "intent_class": category,
            "reported_intent_score": item.get("reported_intent_score"),
            "candidate_offer_hypotheses": list(
                detail.get("candidate_offer_hypotheses") or []
            )[:4],
            "potential_company_matches": list(matches)[:4],
            "public_affiliation_evidence": dict(affiliation) if affiliation else None,
            "task_status": (
                "FIRST_PARTY_AFFILIATION_REVIEW" if affiliation
                else "EVIDENCE_LINK_REVIEW" if matches
                else "INDEPENDENT_COMPANY_IDENTITY_RESEARCH"
            ),
            "requirements": [
                "INDEPENDENT_COMPANY_IDENTITY_EVIDENCE",
                "POSTER_COMPANY_CONNECTION",
                "CURRENT_PURCHASING_NEED",
                "COMMERCIAL_AUTHORITY_AND_CONTACT_RULES",
            ],
            "source_attribution_proven": False,
            "verified_buyer_intent": False,
            "person_contact_verified": False,
            "founder_outreach_authorized": False,
            "commercial_outcome_verified": False,
            "execution_authority": "NONE",
        }
        candidates.append((priority, key, tasks))
    # Fairness: max half from either platform while both have candidates.
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    reddit = [x for x in candidates if x[2]["source"] == "reddit"]
    linkedin = [x for x in candidates if x[2]["source"] == "linkedin"]
    chosen = reddit[:MAX_TASKS // 2] + linkedin[:MAX_TASKS // 2]
    if len(chosen) < MAX_TASKS:
        used = {x[1] for x in chosen}
        chosen += [x for x in candidates if x[1] not in used][
            :MAX_TASKS-len(chosen)]
    chosen.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return {
        "schema_version": "empire.intent_company_research_tasks.v1",
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "eligible_intent_observations": sum(
            val for cls, val in class_counts.items() if cls in ELIGIBLE
        ),
        "excluded_unsupported_observations": sum(
            val for cls, val in class_counts.items() if cls not in ELIGIBLE
        ),
        "created_or_preserved_task_count": len(chosen),
        "review_backlog_truncated": len(chosen) < len(candidates),
        "identity_review_tasks": [x[2] for x in chosen],
        "first_party_affiliation_evidence_tasks": sum(
            x[2]["task_status"] == "FIRST_PARTY_AFFILIATION_REVIEW"
            for x in chosen
        ),
        "verified_buyer_count": 0,
        "outbound_authorized": False,
        "new_prospects_written": 0,
        "execution_authority": "NONE",
    }
