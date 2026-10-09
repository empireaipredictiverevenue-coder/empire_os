"""Evidence-gated review readiness for buyer scout holding candidates."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
import re
import urllib.parse


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


_CORPORATE_SUFFIXES = frozenset({
    "llc", "inc", "incorporated", "ltd", "limited", "corp",
    "corporation", "pllc", "llp", "lp", "company", "co",
})


def _legal_identity_key(value: Any) -> tuple[str, ...]:
    tokens = re.findall(r"[a-z0-9]+", str(value or "").casefold())
    while tokens and tokens[-1] in _CORPORATE_SUFFIXES:
        tokens.pop()
    return tuple(tokens)


def _official_source_identity_matches(
    query_evidence: list[Any],
    site: Mapping[str, Any],
    business_name: str,
) -> bool:
    """Never equate a registry result with an unrelated search-hit domain."""
    observed_names = list(site.get("site_business_names") or [])
    if site.get("business_name_source") in {
        "first_party_site_identity", "canonical_seed_corroborated_by_site",
    }:
        observed_names.append(business_name)
    observed = {_legal_identity_key(name) for name in observed_names}
    observed.discard(())

    for item in query_evidence:
        if not isinstance(item, Mapping):
            continue
        refs = item.get("source_refs") or []
        if not isinstance(refs, (list, tuple)) or not any(
            str(ref).startswith("official:") for ref in refs
        ):
            continue
        # Official licence searches use a leading quoted registered name.
        # No quoted name or no exact first-party corroboration => blocked.
        match = re.match(r'^\s*["“]([^"”]+)["”]', str(item.get("query") or ""))
        if not match or _legal_identity_key(match.group(1)) not in observed:
            return False
    return True


def quarantine_stale_official_readiness(
    rows: list[Mapping[str, Any]],
    *,
    patch_call: PatchCall | None = None,
) -> dict[str, Any]:
    """Quarantine only unpromoted false-ready official registry/site joins.

    This operation never creates prospects, sends messages or changes terms.
    An empty/ambiguous PATCH response fails closed: no success is claimed.
    """
    mismatches: list[str] = []
    quarantined = 0
    for raw in rows[:200]:
        row = dict(raw)
        if (
            row.get("review_state") != "review_ready"
            or row.get("reconciliation_state") != "REVIEW_READY"
            or row.get("canonical_prospect_id")
            or row.get("canonical_buyer_id")
        ):
            continue
        if _official_source_identity_matches(
            row.get("query_evidence") or [],
            row.get("site_evidence") or {},
            str(row.get("business_name") or ""),
        ):
            continue
        identifier = str(row.get("id") or "").strip()
        if not identifier:
            raise ValueError("stale ready candidate missing identity")
        mismatches.append(identifier)
        if patch_call is None:
            continue
        query = urllib.parse.urlencode({
            "id": "eq." + identifier,
            "review_state": "eq.review_ready",
            "reconciliation_state": "eq.REVIEW_READY",
            "canonical_prospect_id": "is.null",
            "canonical_buyer_id": "is.null",
        })
        response = patch_call(
            "PATCH", "/rest/v1/buyer_scout_candidates?" + query,
            {
                "review_state": "discovered",
                "reconciliation_state": "NEW_EXTERNAL_BUYER_CANDIDATE",
                "reviewed_at": None,
                "reviewed_by": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if (
            not isinstance(response, list)
            or len(response) != 1
            or response[0].get("id") != identifier
        ):
            raise RuntimeError("stale_ready_quarantine_unconfirmed:" + identifier)
        quarantined += 1
    return {
        "review_ready_audited_count": min(len(rows), 200),
        "mismatch_ids": mismatches,
        "quarantined_count": quarantined,
        "database_write_performed": bool(quarantined),
        "outbound_sent": False,
        "execution_authority": "holding_repair_only" if patch_call else "none",
    }


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
    if not _official_source_identity_matches(query_evidence, site, business_name):
        return False, "official_registry_identity_mismatch"

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

    products = {
        str(value)
        for value in (row.get("target_product_codes") or [])
        if str(value).strip()
    }
    if "permit_intelligence" in products:
        if site.get("permit_territory_state") != (
            "NYC_FIRST_PARTY_EVIDENCE"
        ):
            return False, "permit_territory_not_verified"
        if (
            site.get("business_name_source") == "canonical_prospect_seed"
            and site.get("canonical_seed_identity_corroborated") is not True
        ):
            return False, "permit_business_identity_unconfirmed"

    pools = {
        str(value)
        for value in (row.get("target_buyer_pools") or [])
        if str(value).strip()
    }
    direct_pool = "direct_demand_buyers" in pools
    if direct_pool and row.get("explicit_direct_buyer_evidence") is not True:
        # Independently sourced product research can qualify the organisation
        # for holding review. It cannot qualify it as a direct inventory buyer.
        non_direct_product_evidence = any(
            isinstance(item, Mapping)
            and item.get("buyer_pool") in pools.intersection({
                "local_and_smb_buyers", "end_service_buyers",
                "agency_and_reseller_buyers", "enterprise_and_data_buyers",
                "software_and_advisory_buyers",
            })
            and str(item.get("query") or "").strip()
            and item.get("product_code") in products
            for item in query_evidence
        )
        if not non_direct_product_evidence:
            return False, "direct_buyer_evidence_missing"

    return True, "review_ready"


def materialize_review_readiness(
    rows: list[Mapping[str, Any]],
    *,
    patch_call: PatchCall | None = None,
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

        compare_query = urllib.parse.urlencode({
            "id": "eq." + candidate_id,
            "review_state": "eq." + str(row.get("review_state")),
            "reconciliation_state": "eq.NEW_EXTERNAL_BUYER_CANDIDATE",
            "canonical_prospect_id": "is.null",
            "canonical_buyer_id": "is.null",
        })
        response = patch_call(
            "PATCH",
            "/rest/v1/buyer_scout_candidates?" + compare_query,
            {
                "review_state": "review_ready",
                "reconciliation_state": "REVIEW_READY",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": "empire_buyer_scout_review_gate",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        ) if patch_call is not None else None
        if patch_call is not None and (
            not isinstance(response, list)
            or len(response) != 1
            or not isinstance(response[0], Mapping)
            or str(response[0].get("id") or "") != candidate_id
            or response[0].get("review_state") != "review_ready"
        ):
            blocked["review_transition_unconfirmed"] = (
                blocked.get("review_transition_unconfirmed", 0) + 1
            )
            continue
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
        "database_write_performed": patch_call is not None and bool(updates),
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
