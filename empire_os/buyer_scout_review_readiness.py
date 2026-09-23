"""Evidence-gated review readiness for buyer scout holding candidates."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
import re


OUTPUT = Path("runtime/buyer_acquisition/review_readiness_latest.json")
PatchCall = Callable[[str, str, dict[str, Any]], Any]


GENERIC_BUSINESS_NAMES = frozenset({
    "home",
    "about",
    "about us",
    "contact",
    "contact us",
    "services",
    "our services",
    "welcome",
    "homepage",
    "index",
    "learn more",
    "read more",
    "click here",
    "get started",
    "step 1",
    "step 2",
    "step 3",
})


def reliable_business_name(
    name: str,
    *,
    source: str | None = None,
) -> bool:
    text = re.sub(r"\s+", " ", str(name or "")).strip()
    if not text:
        return False

    lowered = text.lower().strip(" -|:")
    if lowered in GENERIC_BUSINESS_NAMES:
        return False

    if re.match(
        r"^(home|about(?: us)?|contact(?: us)?|services?|step\s+\d+)\s*[-|:]",
        lowered,
    ):
        return False
    if re.fullmatch(r"step\s+\d+", lowered):
        return False

    return True


def review_readiness(row: Mapping[str, Any]) -> tuple[bool, str]:
    if str(row.get("reconciliation_state") or "") != (
        "NEW_EXTERNAL_BUYER_CANDIDATE"
    ):
        return False, "not_new_external_candidate"
    if str(row.get("review_state") or "") not in {"discovered", "reconciled"}:
        return False, "review_state_not_eligible"

    business_name = str(row.get("business_name") or "").strip()
    website = str(row.get("website") or "").strip()
    domain = str(row.get("domain") or "").strip()
    if not business_name or not website or not domain:
        return False, "business_identity_incomplete"
    site = (
        dict(row.get("site_evidence"))
        if isinstance(row.get("site_evidence"), Mapping)
        else {}
    )
    if not reliable_business_name(
        business_name,
        source=site.get("business_name_source"),
    ):
        return False, "business_name_not_verified"

    query_evidence = row.get("query_evidence")
    if not isinstance(query_evidence, list) or not query_evidence:
        return False, "query_evidence_missing"

    site = (
        dict(row.get("site_evidence"))
        if isinstance(row.get("site_evidence"), Mapping)
        else {}
    )
    try:
        site_score = float(site.get("site_evidence_score") or 0.0)
    except (TypeError, ValueError):
        site_score = 0.0

    contact_count = 0
    for key in (
        "first_party_email_count",
        "first_party_phone_count",
        "people_count",
    ):
        try:
            contact_count += max(int(site.get(key) or 0), 0)
        except (TypeError, ValueError):
            pass

    if site_score < 0.50:
        return False, "site_evidence_below_floor"
    if contact_count <= 0:
        return False, "first_party_contact_path_missing"

    pools = {
        str(value)
        for value in (row.get("target_buyer_pools") or [])
        if str(value).strip()
    }
    direct_pool = "direct_demand_buyers" in pools
    if direct_pool and row.get("explicit_direct_buyer_evidence") is not True:
        return False, "direct_buyer_evidence_missing"

    return True, "review_ready"


def materialize_review_readiness(
    rows: list[Mapping[str, Any]],
    *,
    patch_call: PatchCall,
) -> dict[str, Any]:
    ready = 0
    blocked: dict[str, int] = {}
    updates: list[dict[str, Any]] = []

    for raw in rows:
        row = dict(raw)
        allowed, reason = review_readiness(row)
        if not allowed:
            blocked[reason] = blocked.get(reason, 0) + 1
            continue

        candidate_id = str(row.get("id") or "").strip()
        if not candidate_id:
            blocked["candidate_id_missing"] = (
                blocked.get("candidate_id_missing", 0) + 1
            )
            continue

        response = patch_call(
            "PATCH",
            (
                "/rest/v1/buyer_scout_candidates"
                f"?id=eq.{candidate_id}"
            ),
            {
                "review_state": "review_ready",
                "reconciliation_state": "REVIEW_READY",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": "empire_buyer_scout_review_gate",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ready += 1
        updates.append({
            "candidate_id": candidate_id,
            "reason": reason,
            "response": response,
        })

    return {
        "schema_version": "empire.buyer_scout_review_readiness.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(rows),
        "review_ready_count": ready,
        "blocked_count": len(rows) - ready,
        "blocked_reason_counts": dict(sorted(blocked.items())),
        "updates": updates,
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "terms_accepted": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def write_review_readiness(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
