"""Evidence-first longitudinal A2A market decisions, not a purchase predictor.

The decision layer diagnoses source failure, source/product rights, buyer proof,
research change, and value-of-information next tasks. All inputs are existing
read-only owner snapshots; the caller is responsible for authenticating sources.

Never assumes a score, buyer intent, commercial authorisation, or a paid deal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import math

from empire_os.a2a_commercial_signal_miner import AGENT_ID, SCHEMA as MINER_SCHEMA
from empire_os.a2a_data_campaign_release_review import SCHEMA as RELEASE_SCHEMA
from empire_os.data_brokerage_product_catalog import SCHEMA as CATALOGUE_SCHEMA

SCHEMA = "empire.a2a.signal_decision_intelligence.v2"
MAX_SEGMENTS = 100
CURRENCY_CLAIMS = frozenset({"expected_revenue", "profit", "buyer_budget", "price_quote"})

def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(timezone.utc) if t.tzinfo else None

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _signal_basis_fingerprint(signal: Mapping[str, Any]) -> str:
    # Deliberately exclude timestamps and collector metadata: do not recreate
    # an owner's research task merely because a cycle ran again.
    keys = (
        "source_domain", "niche", "metro", "pain_point", "offer_hypothesis",
        "evidence_status", "observed_mentions_unverified",
        "high_intent_mentions_unverified", "supported_by_latest_successful_platforms",
        "research_priority_score_not_probability",
    )
    return _digest({k: signal.get(k) for k in keys})

def _must_miner(packet: Mapping[str, Any], label: str, *, now: datetime) -> datetime:
    if (not isinstance(packet, Mapping)
            or packet.get("schema_version") != MINER_SCHEMA
            or packet.get("agent_id") != AGENT_ID
            or packet.get("execution_authority") != "NONE"
            or packet.get("outbound_sent") is not False
            or packet.get("publishing_performed") is not False
            or packet.get("revenue_verified") is not False
            or packet.get("verified_buyers_discovered") != 0
            or packet.get("network_requests") is not False):
        raise ValueError("UNTRUSTED_" + label.upper() + "_MINER_REPORT")
    timestamp = _dt(packet.get("generated_at"))
    if timestamp is None or timestamp > now + timedelta(minutes=5):
        raise ValueError("INVALID_" + label.upper() + "_TIMESTAMP")
    return timestamp

def _index(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = packet.get("prioritized_research_signals")
    if not isinstance(rows, list) or len(rows) > MAX_SEGMENTS:
        raise ValueError("INVALID_SIGNAL_RECORD_COUNT")
    result: dict[str, Mapping[str, Any]] = {}
    for item in rows:
        if not isinstance(item, Mapping):
            raise ValueError("INVALID_SIGNAL_OBJECT")
        sid = item.get("segment_id")
        if not isinstance(sid, str) or len(sid) != 16 or any(x not in "0123456789abcdef" for x in sid):
            raise ValueError("INVALID_SIGNAL_ID")
        if sid in result:
            raise ValueError("DUPLICATE_SIGNAL_ID")
        score = item.get("research_priority_score_not_probability")
        if (isinstance(score, bool) or not isinstance(score, (float, int))
                or not math.isfinite(score) or not 0 <= score <= 100):
            raise ValueError("INVALID_RESEARCH_PRIORITY")
        if item.get("evidence_status") not in (
                "DISCUSSION_ONLY_NOT_VERIFIED_BUYER",
                "GEO_MARKET_RESEARCH_NOT_BUYER_OR_LICENSE_PROOF"):
            raise ValueError("UNSUPPORTED_RESEARCH_EVIDENCE_CLASS")
        for forbidden in CURRENCY_CLAIMS:
            if forbidden in item:
                raise ValueError("UNVERIFIED_FINANCIAL_CLAIM")
        result[sid] = item
    return result

def _get_products(catalogue: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if (not isinstance(catalogue, Mapping)
            or catalogue.get("schema_version") != CATALOGUE_SCHEMA
            or catalogue.get("mode") != "OBSERVE"
            or catalogue.get("third_party_resale_authorized") is not False
            or catalogue.get("product_publication_authorized") is not False
            or catalogue.get("marketing_outbound_sent") is not False):
        raise ValueError("UNTRUSTED_DATA_BROKERAGE_CATALOGUE")
    rows = catalogue.get("products")
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("UNTRUSTED_PRODUCT_LIST")
    products = {}
    for p in rows:
        if not isinstance(p, Mapping) or not isinstance(p.get("product_id"), str):
            raise ValueError("INVALID_PRODUCT_ROW")
        pid = p["product_id"]
        if pid in products:
            raise ValueError("DUPLICATE_DATA_PRODUCT")
        if (p.get("customer_data_export_ready") is not False or
            p.get("raw_third_party_resale_cleared") is not False or
            p.get("buyer_verified") is not False or
            p.get("product_activation_enabled") is not False):
            raise ValueError("OWNER_CATALOGUE_CLAIM_EXCEEDS_RESEARCH_AUTHORITY")
        products[pid] = p
    return products

def make_decision_intelligence(
    current: Mapping[str, Any],
    releases: Mapping[str, Any],
    catalogue: Mapping[str, Any],
    *,
    previous: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    current_time = _must_miner(current, "current", now=now)
    old_time = _must_miner(previous, "previous", now=now) if previous is not None else None
    if old_time is not None and old_time > current_time:
        raise ValueError("RESEARCH_HISTORY_TIME_REVERSAL")
    if (not isinstance(releases, Mapping)
            or releases.get("schema_version") != RELEASE_SCHEMA
            or releases.get("execution_authority") != "NONE"
            or releases.get("launch_ready_campaign_count") != 0
            or releases.get("actual_commercial_launches") != 0
            or releases.get("messages_sent") is not False):
        raise ValueError("UNTRUSTED_CAMPAIGN_RELEASE_PACKET")
    current_idx = _index(current)
    previous_idx = _index(previous) if previous is not None else {}
    products = _get_products(catalogue)
    catalogue_time = _dt(catalogue.get("generated_at"))
    catalogue_age = ((now - catalogue_time).total_seconds() / 3600
                     if catalogue_time is not None else None)
    catalogue_stale = catalogue_age is None or catalogue_age > 48 or catalogue_age < -5 / 60
    miner_stale = current_time < now - timedelta(hours=48)
    sources = current.get("source_status")
    if not isinstance(sources, Mapping):
        raise ValueError("SOURCE_STATUS_MISSING")
    source_quality = {}
    for name in ("community_intent", "revenue_gps"):
        v = sources.get(name)
        if not isinstance(v, Mapping) or type(v.get("available")) is not bool:
            raise ValueError("SOURCE_HEALTH_SHAPE_INVALID")
        quality = v.get("collection_quality", {})
        if not isinstance(quality, Mapping):
            raise ValueError("COLLECTION_STATUS_INVALID")
        degraded = sorted(k for k, status in quality.items()
                          if status != "LATEST_RETRIEVAL_OK")
        healthy = sorted(k for k, status in quality.items()
                         if status == "LATEST_RETRIEVAL_OK")
        source_quality[name] = {
            "snapshot_accepted_by_upstream_miner": v["available"],
            "source_state": str(v.get("state") or "UNREPORTED"),
            "latest_retrieval_ok": healthy,
            "latest_retrieval_degraded": degraded,
            "per_channel_health_reported": name == "community_intent",
            "all_relevant_channels_healthy": (
                (bool(healthy) and not degraded) if name == "community_intent" else None
            ),
            "freshness_is_not_buying_intent": True,
        }

    campaigns = releases.get("campaigns")
    if not isinstance(campaigns, list) or len(campaigns) > 10:
        raise ValueError("INVALID_RELEASE_CAMPAIGNS")
    release_by_id: dict[str, Mapping[str, Any]] = {}
    for r in campaigns:
        if not isinstance(r, Mapping) or not isinstance(r.get("campaign_id"), str):
            raise ValueError("INVALID_RELEASE_CAMPAIGN")
        if r["campaign_id"] in release_by_id or r.get("live_campaign_authorized") is not False:
            raise ValueError("DUPLICATE_OR_PRIVILEGED_CAMPAIGN")
        release_by_id[r["campaign_id"]] = r

    cards = []
    for sid, item in current_idx.items():
        score = float(item["research_priority_score_not_probability"])
        prev = previous_idx.get(sid)
        old_score = (float(prev["research_priority_score_not_probability"]) if prev else None)
        delta = round(score - old_score, 2) if old_score is not None else None
        current_basis = _signal_basis_fingerprint(item)
        old_basis = _signal_basis_fingerprint(prev) if prev else None
        if prev is None:
            temporal = "NEW_RESEARCH_SIGNAL"
        elif old_basis == current_basis:
            temporal = "UNCHANGED_RESEARCH_SIGNAL"
        elif delta != 0:
            temporal = "PRIORITY_CHANGED_NOT_BUYER_EVIDENCE"
        else:
            temporal = "SOURCE_CONTENT_CHANGED_NOT_BUYER_EVIDENCE"
        duplicate_research = temporal == "UNCHANGED_RESEARCH_SIGNAL"
        product_id = str(item.get("offer_hypothesis") or "")
        product = products.get(product_id)
        # Prioritisation is not an accuracy/confidence estimate.
        evidence = str(item["evidence_status"])
        observed_platforms = item.get("supported_by_latest_successful_platforms", [])
        if not isinstance(observed_platforms, list):
            observed_platforms = []
        reasons = []
        if catalogue_stale:
            reasons.append("PRODUCT_CATALOGUE_NEEDS_FRESH_OWNER_REVIEW")
        if miner_stale:
            reasons.append("RESEARCH_REPORT_STALE")
        if product is None:
            reasons.append("NO_CANONICAL_DATA_PRODUCT_MAPPED")
        else:
            reasons.append("PRODUCT_RIGHTS_AND_DELIVERY_NOT_APPROVED")
        if evidence == "DISCUSSION_ONLY_NOT_VERIFIED_BUYER":
            reasons.append("DISCUSSION_SIGNALS_ARE_NOT_BUYER_INTENT")
            if not observed_platforms:
                reasons.append("NO_SUCCESSFUL_CURRENT_SOCIAL_SOURCE_FOR_THIS_PAIN")
            if item.get("metro") == "not_established":
                reasons.append("NO_VERIFIED_GEO_FOR_MICROTARGETING")
        else:
            reasons.extend(("MARKET_RANK_IS_NOT_PURCHASE_INTENT",
                            "ACTUAL_BUYER_AND_BUDGET_NOT_VERIFIED"))
        relevant_campaigns = [
            x for x in campaigns if
            x.get("sector") == item.get("niche") and x.get("metro") == item.get("metro")
        ]
        if any(x.get("live_campaign_authorized") is not False for x in relevant_campaigns):
            raise ValueError("CAMPAIGN_PRIVILEGE_ESCALATION")
        if not relevant_campaigns:
            reasons.append("NO_SOURCE_GATED_CAMPAIGN_REVIEW_FOR_THIS_MARKET")
        elif any(x.get("hold_reasons") for x in relevant_campaigns):
            reasons.append("CAMPAIGN_RELEASE_GATES_INCOMPLETE")
        if duplicate_research:
            reasons.append("ALREADY_SEEN_SOURCE_EVIDENCE_SUPPRESS_DUPLICATE_TASKS")
        # Quality-aware research triage: a score cannot erase missing rights,
        # weak channels or a lack of confirmed commercial demand.
        if evidence == "DISCUSSION_ONLY_NOT_VERIFIED_BUYER":
            triage_priority = min(score, 30 if observed_platforms else 10)
        else:
            triage_priority = min(score, 55 if product is not None else 20)
        if miner_stale:
            triage_priority = min(triage_priority, 5)
        if catalogue_stale and product is not None:
            triage_priority = min(triage_priority, 45)
        task_names = []
        if product is None:
            task_names.append(("data_brokerage", "MAP_TO_REAL_LICENSABLE_OR_ORIGINAL_PRODUCT"))
        elif catalogue_stale:
            task_names.append(("data_brokerage", "REFRESH_OWNER_APPROVED_PRODUCT_RIGHTS"))
        else:
            task_names.append(("data_brokerage", "AUDIT_SOURCE_FIELD_RIGHTS_AND_DELIVERABILITY"))
        if evidence == "DISCUSSION_ONLY_NOT_VERIFIED_BUYER":
            task_names.append(("community_intent", "INDEPENDENTLY_VALIDATE_MARKET_AND_LOCATION"))
        else:
            task_names.append(("buyer_scout", "VERIFY_REAL_B2B_BUYER_AND_EXPLICIT_USE_CASE"))
        if relevant_campaigns:
            task_names.append(("owned_campaigns", "REVIEW_SOURCE_GATED_CREATIVE_ONLY"))
        # Explicit learning: information gaps are ordered, not automatically resolved.
        cards.append({
            "segment_id": sid, "niche": item.get("niche"), "metro": item.get("metro"),
            "source_class": item.get("source_domain"),
            "product_hypothesis": product_id,
            "prioritisation_score_not_probability": score,
            "quality_adjusted_research_triage_not_probability": round(triage_priority, 2),
            "prior_score": old_score, "score_change_not_buyer_conversion": delta,
            "temporal_status": temporal,
            "current_signal_basis_sha256_not_official_receipt": current_basis,
            "unchanged_evidence_duplicate_tasks_suppressed": duplicate_research,
            "evidence_readiness": "HOLD_UNTIL_BUSINESS_AND_RIGHTS_VERIFICATION",
            "buyer_identity_verified": False, "budget_verified": False,
            "payable_event_verified": False, "campaign_ready": False,
            "independently_calibrated_probability": None,
            "source_rights_and_delivery_confirmed": False,
            "reason_codes": sorted(set(reasons)),
            "next_best_verification_steps": [
                {"owner": owner, "action": action,
                 "state": ("ALREADY_SEEN_NEEDS_OWNER_REVALIDATION" if duplicate_research
                           else "NEW_PROPOSAL_NOT_DISPATCHED"),
                 "external_execution": False}
                for owner, action in task_names[:3]
            ],
        })
    cards.sort(key=lambda x: (-x["quality_adjusted_research_triage_not_probability"],
                              -x["prioritisation_score_not_probability"], x["segment_id"]))
    disappeared = sorted(set(previous_idx) - set(current_idx))
    # Disappearance is a research input change, NOT confirmed lost demand.
    return {
        "schema_version": SCHEMA, "agent_id": AGENT_ID, "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source_timestamps": {
            "current_miner_generated_at": current_time.isoformat(),
            "previous_miner_generated_at": old_time.isoformat() if old_time else None,
            "product_catalogue_generated_at": catalogue_time.isoformat() if catalogue_time else None,
        },
        "provenance_digests_not_official_signatures": {
            "current_report_sha256": _digest(current),
            "release_report_sha256": _digest(releases),
            "product_catalogue_sha256": _digest(catalogue),
        },
        "source_health": source_quality,
        "catalogue_stale": catalogue_stale, "miner_stale": miner_stale,
        "research_candidate_count": len(cards),
        "new_candidate_count": sum(x["temporal_status"] == "NEW_RESEARCH_SIGNAL" for x in cards),
        "repeated_candidate_count": sum(x["temporal_status"] != "NEW_RESEARCH_SIGNAL" for x in cards),
        "unchanged_research_candidate_count": sum(x["unchanged_evidence_duplicate_tasks_suppressed"] for x in cards),
        "changed_or_new_candidate_count": sum(not x["unchanged_evidence_duplicate_tasks_suppressed"] for x in cards),
        "previous_candidates_not_in_latest": disappeared,
        "previous_absence_proves_market_disappeared": False,
        "research_priorities": cards,
        "verification_task_count": sum(len(x["next_best_verification_steps"]) for x in cards),
        "new_owner_task_proposals": sum(len(x["next_best_verification_steps"]) for x in cards
                                        if not x["unchanged_evidence_duplicate_tasks_suppressed"]),
        "duplicate_owner_task_reissues_suppressed": sum(len(x["next_best_verification_steps"]) for x in cards
                                                     if x["unchanged_evidence_duplicate_tasks_suppressed"]),
        "source_repair_recommendations_not_dispatched": [
            {"owner": "community_intent", "channel": k, "action": "CHECK_PROVIDER_OR_SOURCE_HEALTH",
             "external_execution": False}
            for k in source_quality["community_intent"]["latest_retrieval_degraded"]
        ],
        "source_licence_approved": False, "verified_new_buyers": 0,
        "verified_revenue": 0, "automated_message_count": 0,
        "new_paid_api_requests": 0, "financial_transactions": 0,
        "execution_authority": "NONE", "database_writes": False,
        "publications": False, "outbound": False,
        "next_action": "VERIFY_SOURCE_RIGHTS_BUYER_EVIDENCE_AND_PRODUCT_FEASIBILITY",
    }
