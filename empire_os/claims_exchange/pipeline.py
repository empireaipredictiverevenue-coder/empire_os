"""Bounded deterministic V2 research pipeline.

Commercial observations only, not allocations, actual claims, license checks,
outreach eligibility, contract execution or measured revenue.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import date
from hashlib import sha256
import json

from .controls import (candidate_readiness, classify_signal, offer_compliance,
                       reject_sensitive_input, safe_https_source)
from .engine import match_capacity

SCHEMA = "empire.claims_exchange.snapshot_v2"
MAX_CANDIDATES = 500
MAX_SIGNALS = 1000
MAX_OFFERS = 100
MAX_DEMANDS = 200


def _bounded(value: object, name: str, maximum: int) -> list:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{name}_invalid_or_over_limit")
    return value


def _key(record: Mapping) -> tuple[str, str]:
    raw_id, raw_jur = record.get("entity_id"), record.get("jurisdiction")
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError("canonical_entity_id_required")
    if not isinstance(raw_jur, str) or not raw_jur.strip():
        raise ValueError("jurisdiction_required")
    return raw_id.casefold().strip(), raw_jur.casefold().strip()


def _same_identity(a: Mapping, b: Mapping) -> bool:
    # Do not hide collisions among buyer/carrier/contractor identities.
    keys = ("kind", "public_domain", "company_name")
    return all(str(a.get(k, "")).casefold().strip() ==
               str(b.get(k, "")).casefold().strip() for k in keys)


def triage_priority(record: Mapping) -> int:
    """Manual research ordering only, not evidence strength or contact authority."""
    source = record.get("research_source")
    if source == "dfw_storm_cohort":
        return 60
    if source == "official_network_program":
        return 45
    if source == "buyer_network":
        base = 28 if record.get("source_status") == "VERIFY_REQUIREMENTS" else 8
        verticals = record.get("discovery_verticals", [])
        if isinstance(verticals, list):
            if "roofing" in verticals:
                base += 12
            if "restoration" in verticals:
                base += 10
        return min(60, base)
    return 0


def build_snapshot(payload: Mapping, *, as_of: date) -> dict:
    if not isinstance(payload, Mapping):
        raise ValueError("input_requires_json_object")
    reject_sensitive_input(payload)
    candidates = _bounded(payload.get("candidates", []), "candidates", MAX_CANDIDATES)
    signals = _bounded(payload.get("signals", []), "signals", MAX_SIGNALS)
    offers = _bounded(payload.get("offers", []), "offers", MAX_OFFERS)
    demands = _bounded(payload.get("demands", []), "demands", MAX_DEMANDS)
    unique: dict[tuple[str, str], Mapping] = {}
    collisions = set()
    exact_duplicates = 0
    for row in candidates:
        if not isinstance(row, Mapping):
            raise ValueError("candidate_invalid")
        key = _key(row)
        if key in unique:
            if not _same_identity(unique[key], row):
                collisions.add(key)
            else:
                exact_duplicates += 1
        else:
            unique[key] = row
    # Two different canonical IDs sharing a confirmed site and territory
    # are ambiguous; never automatically merge them or contact both.
    domains = {}
    for key, row in unique.items():
        domain = str(row.get("public_domain", "")).casefold().strip().removeprefix("www.")
        if not domain:
            continue
        dkey = (domain, key[1])
        previous = domains.get(dkey)
        if previous is not None and previous != key:
            collisions.update((previous, key))
        else:
            domains[dkey] = key
    for key in collisions:
        unique.pop(key, None)

    reviewed = {
        key: candidate_readiness(row, as_of=as_of)
        for key, row in unique.items()
    }
    contextual = []
    signal_scores = Counter()
    signal_ids = set()
    for signal in signals:
        if not isinstance(signal, Mapping):
            raise ValueError("signal_invalid")
        result = classify_signal(signal, as_of=as_of)
        contextual.append(result)
        if result["status"] != "CONTEXT_ONLY":
            continue
        entity_id = result["entity_id"]
        jurisdiction = signal.get("jurisdiction")
        if not isinstance(jurisdiction, str):
            continue
        if not isinstance(entity_id, str) or not entity_id.strip():
            continue
        key = (entity_id.casefold().strip(), jurisdiction.casefold().strip())
        source_id = (key, result["source_url"], result["kind"])
        if key in reviewed and source_id not in signal_ids:
            signal_ids.add(source_id)
            signal_scores[key] = min(25, signal_scores[key] + result["points"])

    queue = []
    for key, entry in reviewed.items():
        context_points = signal_scores[key]
        queue.append({
            "entity_id": entry["entity_id"],
            "company_name": entry["company_name"],
            "kind": entry["kind"],
            "jurisdiction": entry["jurisdiction"],
            "review_state": entry["review_state"],
            "evidence_confidence": entry["confidence"],
            "context_score": context_points,
            "research_priority": min(100, entry["confidence"] + context_points),
            "triage_priority": triage_priority(unique[key]),
            "research_source": unique[key].get("research_source", "unattributed"),
            "missing_evidence": entry["missing_evidence"],
            "evidence_rejections": entry["evidence"]["rejected_reasons"],
            "evidence_links": entry["evidence"]["provenance"],
            "founder_review_only": True,
            "outbound_authorized": False,
            "execution_authority": "none",
        })
    queue.sort(key=lambda r: (-r["triage_priority"], -r["research_priority"], r["entity_id"].casefold()))

    offers_out = []
    for offer in offers:
        if not isinstance(offer, Mapping):
            raise ValueError("offer_invalid")
        offers_out.append(offer_compliance(offer))

    pairings = []
    for item in demands:
        if not isinstance(item, Mapping):
            raise ValueError("demand_invalid")
        c_id, b_id, jur = item.get("contractor_id"), item.get("buyer_id"), item.get("jurisdiction")
        if not all(isinstance(x, str) and x.strip() for x in (c_id, b_id, jur)):
            pairings.append({"state": "RESEARCH_ONLY", "reasons": ["missing_canonical_binding"],
                             "execution_authority": "none"})
            continue
        c_key, b_key = (c_id.casefold().strip(), jur.casefold().strip()), (b_id.casefold().strip(), jur.casefold().strip())
        c, b = unique.get(c_key), unique.get(b_key)
        if c is None or b is None:
            pairings.append({"state": "RESEARCH_ONLY", "reasons": ["unresolved_identity"],
                             "execution_authority": "none"})
            continue
        if (reviewed[c_key]["review_state"] != "FOUNDER_REVIEW_READY"
                or reviewed[b_key]["review_state"] != "FOUNDER_REVIEW_READY"):
            pairings.append({"state": "RESEARCH_ONLY", "reasons": ["incomplete_independent_evidence"],
                             "execution_authority": "none"})
            continue
        result = match_capacity(c, b, item)
        pairings.append(result)

    summary = {
        "input_candidates": len(candidates), "unique_candidates": len(unique),
        "exact_duplicates": exact_duplicates,
        "conflicting_identity_groups_quarantined": len(collisions),
        "founder_review_ready": sum(x["review_state"] == "FOUNDER_REVIEW_READY" for x in queue),
        "needs_research": sum(x["review_state"] == "RESEARCH_ONLY" for x in queue),
        "signals_context_only": sum(x["status"] == "CONTEXT_ONLY" for x in contextual),
        "signals_rejected": sum(x["status"] == "REJECTED" for x in contextual),
        "matches_for_founder_review": sum(x["state"] == "MATCH_FOR_FOUNDER_REVIEW" for x in pairings),
        "regulated_offers_blocked": sum(x["quote_state"].startswith("BLOCKED") for x in offers_out),
        "actual_revenue": 0, "settlement_commissions": 0, "outbound_sent": 0,
    }
    digest_data = {
        "as_of": as_of.isoformat(), "queue": queue, "offers": offers_out,
        "pairings": pairings, "summary": summary,
    }
    digest = sha256(json.dumps(digest_data, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return {
        "schema": SCHEMA, "mode": "OBSERVE", "as_of": as_of.isoformat(),
        "snapshot_sha256": digest,
        "summary": summary, "research_queue": queue,
        "offer_reviews": offers_out,
        "buyer_matches": pairings,
        "quarantine": {"conflicting_identity_count": len(collisions)},
        "outbound_authorized": False, "public_api_activation_authorized": False,
        "claim_handling_authorized": False, "payment_authorized": False,
        "execution_authority": "none",
    }
