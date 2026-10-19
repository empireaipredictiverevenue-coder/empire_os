"""Buyer Scout cross-snapshot commercial memory: read-only, fail-closed.

Reports only B2B-domain research priorities (no contacts, mail, person names,
raw discovery texts, message bodies, prices or buyer IDs). Unifies exact
domain evidence with already-maintained authoritative relationships, including
aliases only when those identity domains belong to the SAME existing
relationship row. Identical business names alone NEVER cause a merge.

Does not replace the Buyer Scout, CRM, Search Fabric or buyer qualification
owner. No new crawling, scoring-as-revenue, outreach or database writes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone, timedelta
import re
from urllib.parse import urlsplit

SCHEMA = "empire.buyer_scout_commercial_awareness.v1"
SCOUT_SCHEMA = "empire.buyer_acquisition_scout.v1"
ACTIONS_SCHEMA = "empire.buyer_qualification_actions.v1"
RELATIONSHIP_SCHEMA = "empire.commercial_relationship_registry.v1"
DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
MAX_SCOUT = 100
MAX_ACTIONS = 150
MAX_RELATIONSHIPS = 3000
MAX_DOMAINS_PER_RELATIONSHIP = 30
MAX_ROWS = 150
MAX_STALENESS = timedelta(hours=6)


def _time(v: object, *, now: datetime) -> datetime:
    try:
        moment = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("timestamp_malformed") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("timezone_aware_snapshot_required")
    if moment > now + timedelta(minutes=5) or now - moment > MAX_STALENESS:
        raise ValueError("snapshot_stale_or_future")
    return moment.astimezone(timezone.utc)


def _domain(value: object) -> str:
    if not isinstance(value, str):
        return ""
    raw = value.strip().lower().rstrip(".")
    if "://" in raw:
        p = urlsplit(raw)
        if (p.scheme not in ("https", "http") or p.username or p.password
                or p.port is not None or not p.hostname):
            return ""
        raw = p.hostname.lower().rstrip(".")
    if raw.startswith("www."):
        raw = raw[4:]
    if not DOMAIN.fullmatch(raw):
        return ""
    return raw


def _checked_rows(snapshot: Mapping, key: str, limit: int) -> list:
    rows = snapshot.get(key)
    if not isinstance(rows, list) or len(rows) > limit or any(
        not isinstance(v, Mapping) for v in rows
    ):
        raise ValueError("source_rows_invalid")
    return rows


def _source_timestamp(snapshot: Mapping, schema: str, now: datetime,
                      *, registry: bool = False) -> datetime:
    if not isinstance(snapshot, Mapping) or snapshot.get("schema_version") != schema:
        raise ValueError("source_schema_mismatch")
    if (str(snapshot.get("execution_authority") or "").lower() != "none"
            or snapshot.get("outbound_sent") is not False):
        raise ValueError("source_has_execution_authority")
    if registry:
        if snapshot.get("mode") != "OBSERVE" or snapshot.get("outbound_authorized") is not False:
            raise ValueError("relationship_authority_invalid")
    elif snapshot.get("mode") != "OBSERVE":
        raise ValueError("source_mode_invalid")
    if schema == ACTIONS_SCHEMA and snapshot.get("outbound_enabled") is not False:
        raise ValueError("qualification_outbound_gate_invalid")
    return _time(snapshot.get("generated_at"), now=now)


def _next_research(sc: Mapping, action: Mapping, *, prior: bool,
                   suppressed: bool, conflicts: bool, identity_collision: bool,
                   stale_gmail: bool) -> tuple[str, str, int]:
    """Returns a research task, role and deterministic evidence priority.

    Priority is research urgency, NOT an inferred conversion probability.
    """
    if suppressed:
        return ("SUPPRESSION_REVIEW_ONLY", "SUPPRESSED", 0)
    if identity_collision:
        return ("RESOLVE_IDENTITY_ALIAS_CONFLICT", "UNKNOWN", 90)
    if conflicts:
        return ("RESOLVE_SCOUT_AND_FOUNDER_ROLE_CONFLICT", "UNKNOWN", 85)
    if prior and stale_gmail:
        return ("REFRESH_EXISTING_THREAD_BEFORE_ANY_CONTACT", "EXISTING_RELATIONSHIP", 95)
    if prior:
        return ("REVIEW_EXISTING_THREAD_NO_DUPLICATE_INTRO", "EXISTING_RELATIONSHIP", 95)
    if action.get("manual_hold_reason") or action.get("automated_hold_reason"):
        return ("RESOLVE_FOUNDING_COMMERCIAL_HOLD", "RESEARCH_ONLY", 25)
    relationship = sc.get("buyer_relationship")
    icp = sc.get("icp_intelligence")
    icp = icp if isinstance(icp, Mapping) else {}
    direct = (sc.get("explicit_direct_buyer_evidence") is True
              and isinstance(sc.get("buyer_claim_provenance"), Mapping)
              and sc["buyer_claim_provenance"].get("explicit_direct_purchase_observed") is True)
    if relationship == "intermediary_or_marketplace" and not direct:
        return ("VERIFY_INTERMEDIARY_OWN_SPEND_VS_PUBLISHER_RECRUITMENT", "INTERMEDIARY_OR_PUBLISHER", 40)
    if not direct:
        return ("VERIFY_FIRST_PARTY_DIRECT_BUYBOX_AND_DEMAND", "UNVERIFIED_BUYER_ROLE", 55)
    if sc.get("canonical_identity_verified") is not True:
        return ("RECONCILE_CANONICAL_BUSINESS_IDENTITY_WITH_CRM", "DIRECT_BUYER_CLAIM_UNVERIFIED_IDENTITY", 65)
    if sc.get("budget_verified") is not True or icp.get("budget_verified") is not True:
        return ("VERIFY_BUDGET_AND_PURCHASING_AUTHORITY", "DIRECT_BUYER_EVIDENCE_INCOMPLETE", 70)
    if sc.get("commercial_terms_verified") is not True or icp.get("commercial_terms_verified") is not True:
        return ("VERIFY_BUYBOX_PRICE_TERMS_AND_PAYMENT_PATH", "DIRECT_BUYER_EVIDENCE_INCOMPLETE", 75)
    return ("REVIEW_BUYER_CAPACITY_AND_PILOT_RISK_WITH_OWNER", "EVIDENCE_REVIEW_ONLY", 80)


def review_buyer_scout_awareness(
    scout: Mapping, actions: Mapping, relationships: Mapping, *,
    as_of: datetime, prior_scout: Mapping | None = None,
) -> dict:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("timezone_aware_review_required")
    now = as_of.astimezone(timezone.utc)
    stamp = {
        "scout": _source_timestamp(scout, SCOUT_SCHEMA, now),
        "founder_actions": _source_timestamp(actions, ACTIONS_SCHEMA, now),
        "relationship_registry": _source_timestamp(
            relationships, RELATIONSHIP_SCHEMA, now, registry=True),
    }
    candidates = _checked_rows(scout, "candidates", MAX_SCOUT)
    qualified = _checked_rows(actions, "targets", MAX_ACTIONS)
    known = _checked_rows(relationships, "relationships", MAX_RELATIONSHIPS)
    # A stale snapshot may contribute positive prior-contact evidence but
    # NEVER clears permission for outreach, even when Gmail says fresh.
    gmail_fresh = relationships.get("gmail_snapshot_fresh") is True
    by_action = defaultdict(list)
    for row in qualified:
        domain = _domain(row.get("domain"))
        if domain:
            by_action[domain].append(row)
    identity_domains = defaultdict(list)
    for index, row in enumerate(known):
        ids = row.get("identity_domains")
        if not isinstance(ids, list) or len(ids) > MAX_DOMAINS_PER_RELATIONSHIP:
            raise ValueError("relationship_identity_domains_invalid")
        for raw in ids:
            domain = _domain(raw)
            if domain:
                identity_domains[domain].append(index)
    prior_domains = set()
    if prior_scout is not None:
        _source_timestamp(prior_scout, SCOUT_SCHEMA, now)
        for row in _checked_rows(prior_scout, "candidates", MAX_SCOUT):
            domain = _domain(row.get("domain"))
            if domain:
                prior_domains.add(domain)
    grouped = defaultdict(list)
    for candidate in candidates:
        domain = _domain(candidate.get("domain"))
        if domain:
            grouped[domain].append(candidate)
    if len(grouped) > MAX_ROWS:
        raise ValueError("too_many_candidate_domains")
    result = []
    duplicate_evidence = 0
    missing_action = 0
    positive_prior = 0
    suppressed_count = 0
    unknown_buyer = 0
    for domain in sorted(grouped):
        rows = grouped[domain]
        if len(rows) > 1:
            duplicate_evidence += len(rows)-1
        # A discovery row is never trusted to grant identity/terms by itself.
        sc = rows[0]
        ars = by_action.get(domain, [])
        if not ars:
            missing_action += 1
        action = ars[0] if len(ars) == 1 else {}
        matched_indices = identity_domains.get(domain, [])
        identity_collision = len(set(matched_indices)) > 1 or len(ars) > 1
        historical = [known[index] for index in set(matched_indices)]
        suppressed = any(
            r.get("do_not_pursue") is True or
            bool(r.get("bounced_addresses")) for r in historical
        )
        prior = any(
            r.get("last_outbound_at") or r.get("last_inbound_at")
            or r.get("gmail_thread_ids") for r in historical
        )
        if suppressed:
            suppressed_count += 1
        if prior:
            positive_prior += 1
        # Never treat publisher/intermediary as a direct paying buyer.
        conflicts = any(
            (row.get("buyer_relationship") != sc.get("buyer_relationship"))
            or (row.get("explicit_direct_buyer_evidence") != sc.get("explicit_direct_buyer_evidence"))
            for row in rows[1:]
        )
        if action.get("site_corroborated_buyer_role") is False and sc.get("explicit_direct_buyer_evidence") is True:
            conflicts = True
        task, role, priority = _next_research(
            sc, action, prior=prior, suppressed=suppressed,
            conflicts=conflicts, identity_collision=identity_collision,
            stale_gmail=not gmail_fresh)
        if "UNVERIFIED" in role or role == "INTERMEDIARY_OR_PUBLISHER":
            unknown_buyer += 1
        # Research cooldown: do not reprobe identical discovered domains
        # merely because an hourly fallback rotated through them again.
        # New inbound or a verified demand/terms receipt can override that.
        new_signal = bool(
            action.get("canonical_contact_or_reply_verified") is True
            or (sc.get("explicit_direct_buyer_evidence") is True
                and sc.get("commercial_terms_verified") is True
                and sc.get("budget_verified") is True))
        duplicate_research = (domain in prior_domains and not new_signal)
        if duplicate_research and task in (
            "VERIFY_FIRST_PARTY_DIRECT_BUYBOX_AND_DEMAND",
            "VERIFY_INTERMEDIARY_OWN_SPEND_VS_PUBLISHER_RECRUITMENT",
        ):
            task = "COOLDOWN_RESEARCH_REUSE_EXISTING_FIRST_PARTY_EVIDENCE"
            priority = 10
        result.append({
            "domain": domain,
            "duplicate_scout_rows": max(0, len(rows)-1),
            "prior_cycle_candidate": domain in prior_domains,
            "research_cooldown_recommended": duplicate_research,
            "founder_review_target_present": bool(ars),
            "known_relationship_count": len(historical),
            "prior_contact_or_thread_evidence": bool(prior),
            "suppression_or_bounce_hold": bool(suppressed),
            "identity_alias_conflict": bool(identity_collision),
            "buyer_role_for_review": role,
            "research_priority_not_conversion_probability": priority,
            "next_evidence_task": task,
            "buyer_budget_authenticated": False,
            "buyer_specific_buybox_authenticated": False,
            "buyer_payment_terms_authenticated": False,
            "contact_or_outbound_authorized": False,
        })
    result.sort(key=lambda row: (-row["research_priority_not_conversion_probability"],
                                 row["domain"]))
    tasks = Counter(row["next_evidence_task"] for row in result)
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "snapshots": {key: value.isoformat() for key, value in stamp.items()},
        "gmail_snapshot_fresh": gmail_fresh,
        "source_candidate_rows": len(candidates),
        "unique_exact_business_domains": len(result),
        "duplicate_scout_rows": duplicate_evidence,
        "previously_contacted_or_engaged_domains": positive_prior,
        "suppressed_or_bounced_domains": suppressed_count,
        "unknown_or_intermediary_buyer_role_count": unknown_buyer,
        "founder_research_target_missing_count": missing_action,
        "research_cooldown_recommendations": sum(r["research_cooldown_recommended"] for r in result),
        "research_task_counts": dict(sorted(tasks.items())),
        "review_queue": result,
        "same_name_different_domain_not_automatically_merged": True,
        "parent_company_merges_require_explicit_canonical_evidence": True,
        "no_reprobe_execution": True, "new_search_queries": 0,
        "no_unverified_direct_payer_claims": True,
        "canonical_crm_writes": False, "emails_sent": False,
        "outbound_authorized": False, "buyer_activation_authorized": False,
        "execution_authority": "none",
    }
