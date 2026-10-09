"""Fail-closed, read-only correlation between canonical prospects and Scout sites.

A canonical prospect ID is *not* inferred from a company name or search URL.
This adapter only supplies a domain context to an existing Astra research task
when two independently collected data lanes agree on the exact prospect.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping
from urllib.parse import urlsplit


UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.I,
)
HOST = re.compile(r"[a-z0-9](?:[a-z0-9.-]{1,251})[a-z0-9]\Z")
ELIGIBLE_ACTIONS = {"verify_decision_maker", "enrich_identity", "prepare_buyer_review"}


def _when(raw: object) -> datetime | None:
    try:
        timestamp = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
        return timestamp.astimezone(timezone.utc) if timestamp.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _fresh(raw: object, now: datetime, max_age: timedelta) -> bool:
    observed = _when(raw)
    return bool(observed and timedelta(minutes=-5) <= now - observed <= max_age)


def _host(raw: object) -> str:
    if not isinstance(raw, str) or len(raw) > 500:
        return ""
    try:
        u = urlsplit(raw)
        if (
            u.scheme not in {"http", "https"}
            or u.username or u.password or u.query or u.fragment
            or u.port not in {None, 80, 443}
        ):
            return ""
        domain = (u.hostname or "").casefold().rstrip(".").removeprefix("www.")
        if (
            not HOST.fullmatch(domain) or ".." in domain
            or "." not in domain or domain.startswith(".")
        ):
            return ""
        return domain
    except ValueError:
        return ""


def _name(raw: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(raw or "").casefold()))


def _qualified_scout_row(row: Mapping[str, Any]) -> dict[str, str] | None:
    """Require canonical source AND separately observed first-party identity."""
    prospect_id = row.get("canonical_seed_prospect_id")
    if not isinstance(prospect_id, str) or not UUID.fullmatch(prospect_id):
        return None
    website = row.get("website")
    domain = _host(website)
    recorded_domain = _host(row.get("canonical_seed_website"))
    declared = row.get("domain")
    if not (
        domain and recorded_domain == domain
        and isinstance(declared, str)
        and declared.casefold().rstrip(".").removeprefix("www.") == domain
        and row.get("canonical_identity_verified") is True
        and row.get("canonical_seed_identity_corroborated") is True
        and row.get("discovery_source") == "canonical_prospect_seed"
        and row.get("business_name_source") == "canonical_seed_corroborated_by_site"
    ):
        return None
    name = _name(row.get("business_name"))
    observed = row.get("site_business_names")
    if not (
        name and len(name) >= 5 and isinstance(observed, list)
        and any(_name(value) == name for value in observed if isinstance(value, str))
    ):
        return None
    return {
        "prospect_id": prospect_id.lower(),
        "company_domain": domain,
        "company_name_key": name,
        "source": "canonical_seed_correlated_with_first_party_site",
    }


def resolve_company_bindings(
    next_best_actions: Mapping[str, Any],
    scout: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_age_minutes: int = 120,
) -> dict[str, Any]:
    """Bind only exact prospect identities from fresh first-party corroboration.

    Returns a lookup keyed by *Astra NBA entity_id*, not company name.
    Unsupported inputs do not create company identities or permissions.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now_requires_timezone")
    current = current.astimezone(timezone.utc)
    result: dict[str, Any] = {
        "schema_version": "empire.astra.canonical_company_binding.v1",
        "status": "no_trusted_match",
        "mode": "OBSERVE",
        "bindings": {},
        "candidate_count": 0,
        "matched_count": 0,
        "blocked_reason_counts": {},
        "execution_authority": "none",
        "outbound_authorized": False,
    }
    reasons: Counter[str] = Counter()
    horizon = timedelta(minutes=max(1, min(max_age_minutes, 180)))
    if not (
        _fresh(next_best_actions.get("generated_at"), current, horizon)
        and _fresh(scout.get("generated_at"), current, horizon)
    ):
        return {
            **result,
            "status": "stale_or_missing_source_receipt",
            "blocked_reason_counts": {"source_freshness_unproven": 1},
        }

    candidate_index: dict[str, list[dict[str, str]]] = {}
    scout_rows = scout.get("candidates")
    if not isinstance(scout_rows, list):
        return {**result, "status": "invalid_scout_source"}
    for row in scout_rows[:200]:
        if not isinstance(row, Mapping):
            continue
        result["candidate_count"] += 1
        candidate = _qualified_scout_row(row)
        if candidate is None:
            reasons["canonical_first_party_identity_unverified"] += 1
            continue
        candidate_index.setdefault(candidate["prospect_id"], []).append(candidate)

    nba_rows = next_best_actions.get("actions")
    duplicate_entity_ids: set[str] = set()
    if not isinstance(nba_rows, list):
        return {**result, "status": "invalid_nba_source"}
    for action in nba_rows[:200]:
        if not isinstance(action, Mapping):
            continue
        action_name = str(action.get("recommended_action") or "")
        if (
            action_name not in ELIGIBLE_ACTIONS
            or action.get("authority") not in {"observe", "internal_write"}
            or action.get("founder_gate_required") is True
            or action.get("waiting_external") is True
        ):
            continue
        entity_id = action.get("entity_id")
        prospect_id = action.get("prospect_id")
        if not (
            isinstance(entity_id, str) and UUID.fullmatch(entity_id)
            and isinstance(prospect_id, str) and UUID.fullmatch(prospect_id)
        ):
            reasons["nba_canonical_entity_or_prospect_id_missing"] += 1
            continue
        matches = candidate_index.get(prospect_id.lower(), [])
        if len(matches) != 1:
            reasons[
                "canonical_prospect_collision" if len(matches) > 1
                else "canonical_prospect_not_correlated"
            ] += 1
            continue
        match = matches[0]
        if _name(action.get("company_name")) != match["company_name_key"]:
            reasons["canonical_company_name_mismatch"] += 1
            continue
        if entity_id in duplicate_entity_ids or entity_id in result["bindings"]:
            result["bindings"].pop(entity_id, None)
            duplicate_entity_ids.add(entity_id)
            reasons["duplicate_entity_action_identity"] += 1
            continue
        result["bindings"][entity_id] = {
            "company_domain": match["company_domain"],
            "canonical_prospect_id": prospect_id.lower(),
            "identity_source": match["source"],
            "identity_scope": "research_only",
            "execution_authority": "none",
        }

    result["matched_count"] = len(result["bindings"])
    result["status"] = "matched" if result["bindings"] else "no_trusted_match"
    result["blocked_reason_counts"] = dict(sorted(reasons.items()))
    return result
