"""Enterprise contact intelligence reconciliation and review-queue sync.

Converts enterprise activation evidence into canonical pending buyer reviews or
durable targeted enrichment retries. It never approves reviews, sends outreach,
accepts terms, moves funds, or recognizes revenue.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping
import urllib.parse

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_discovery import (
    build_candidate,
    build_candidate_review_plan,
    classify_decision_role,
    looks_like_person_name,
)
from empire_os.predictive_revenue_enterprise_targets import TARGETS
from empire_os.qualification_worker_v2 import request_json


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _key(value: Any) -> str:
    return _text(value).casefold()


TARGET_BY_NAME = {
    target.account_name: target
    for target in TARGETS
}


def reconcile_verified_enterprise_contact(
    row: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return a verified person contact reconciled to current target evidence."""
    if row.get("person_contact_verified") is not True:
        return None

    probe = row.get("probe")
    if not isinstance(probe, Mapping):
        return None
    if (
        probe.get("review_ready") is not True
        or probe.get("outreach_ready") is not True
        or probe.get("person_bound") is not True
    ):
        return None

    email = _text(probe.get("preferred_email")).lower()
    decision = probe.get("decision_maker")
    if not email or not isinstance(decision, Mapping):
        return None

    name = _text(decision.get("name"))
    if not looks_like_person_name(name):
        return None

    target = TARGET_BY_NAME.get(_text(row.get("account_name")))
    if target is None:
        return None

    observed = next(
        (
            dict(person)
            for person in target.observed_people
            if _key(person.get("name")) == _key(name)
        ),
        None,
    )

    if observed is not None:
        title = _text(observed.get("title"))
        role, score = classify_decision_role(title)
        return {
            "name": name,
            "title": title,
            "email": email,
            "decision_role": role,
            "decision_score": score,
            "source": "enterprise_target_reconciled",
            "probe_source": _text(decision.get("source")) or None,
            "role_reconciled": True,
            "target_evidence_urls": list(target.evidence_urls),
        }

    # A new person may enter only when the probe itself has strong first-party
    # person evidence. Generated patterns alone cannot invent the executive.
    strong_sources = {
        "website_structured_data",
        "official_site_current",
        "hunter_confirmed_first_party",
    }
    source = _text(decision.get("source"))
    verified_contacts = [
        item
        for item in (probe.get("verified_contacts") or [])
        if isinstance(item, Mapping)
        and _text(item.get("email")).lower() == email
    ]
    first_party = any(
        _text(item.get("source")) in {
            "official_site",
            "person_structured_data",
        }
        for item in verified_contacts
    )
    if source not in strong_sources or not first_party:
        return None

    title = _text(decision.get("title"))
    role, score = classify_decision_role(title)
    if not title or score < 0.5:
        return None
    return {
        "name": name,
        "title": title,
        "email": email,
        "decision_role": role,
        "decision_score": score,
        "source": "enterprise_first_party_new_person",
        "probe_source": source,
        "role_reconciled": False,
        "target_evidence_urls": list(target.evidence_urls),
    }


def _fetch_prospect(prospect_id: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "select": (
            "id,business_name,niche,metro,phone,website,address,"
            "buy_signal_score,status,notes,contact_name,contact_title,"
            "contact_source,contacted_status,created_at"
        ),
        "id": f"eq.{prospect_id}",
        "limit": 1,
    })
    rows = request_json("GET", f"/rest/v1/prospects?{params}") or []
    if not rows or not isinstance(rows[0], dict):
        raise RuntimeError(f"canonical prospect missing:{prospect_id}")
    return rows[0]


def sync_enterprise_activation(
    activation: Mapping[str, Any],
    *,
    request=request_json,
    queue: BuyerDeferredEnrichmentQueue | None = None,
) -> dict[str, Any]:
    queue = queue or BuyerDeferredEnrichmentQueue()
    proposed = queued = skipped = 0
    errors: list[dict[str, str]] = []
    outcomes: list[dict[str, Any]] = []

    for row in activation.get("targets") or []:
        if not isinstance(row, Mapping):
            continue
        account_name = _text(row.get("account_name"))
        target = TARGET_BY_NAME.get(account_name)
        prospect_id = _text(row.get("prospect_id"))
        if target is None or not prospect_id:
            skipped += 1
            continue

        offer_key = (
            target.target_product_codes[0]
            if target.target_product_codes
            else "predictive_revenue_diagnostic"
        )
        reconciled = reconcile_verified_enterprise_contact(row)

        try:
            if reconciled is not None:
                prospect = _fetch_prospect(prospect_id)
                candidate = build_candidate(
                    prospect,
                    entity_id=prospect.get("entity_id") or None,
                    entity_linked=bool(prospect.get("entity_id")),
                )
                probe = row.get("probe") or {}
                plan = build_candidate_review_plan(
                    candidate,
                    {
                        "review_ready": True,
                        "outreach_ready": True,
                        "preferred_email": reconciled["email"],
                        "decision_maker": reconciled,
                        "verified_contacts": (
                            probe.get("verified_contacts") or []
                        ),
                        "contact_route": probe.get("contact_route"),
                        "person_bound": True,
                        "routing_name": probe.get("routing_name"),
                        "routing_title": probe.get("routing_title"),
                        "offer_key": offer_key,
                    },
                    idempotency_key=(
                        f"enterprise-review:{target.account_key}:"
                        f"{reconciled['email']}:v1"
                    ),
                )
                plan["params"]["p_evidence"].update({
                    "source": "enterprise_contact_intelligence.v1",
                    "account_key": target.account_key,
                    "wave": target.wave,
                    "target_product_codes": list(
                        target.target_product_codes
                    ),
                    "target_evidence_urls": list(target.evidence_urls),
                    "role_reconciled": bool(
                        reconciled["role_reconciled"]
                    ),
                    "live_outbound_send": False,
                    "actual_revenue": False,
                })
                response = request(
                    "POST",
                    "/rest/v1/rpc/propose_buyer_candidate_review",
                    payload=plan["params"],
                )
                review_id = (
                    response.get("review_id")
                    if isinstance(response, Mapping)
                    else None
                )
                if not review_id:
                    raise RuntimeError("review proposal returned no review_id")
                proposed += 1
                queue.resolve(
                    prospect_id,
                    outcome="enterprise_buyer_review_proposed",
                )
                outcomes.append({
                    "account_name": account_name,
                    "prospect_id": prospect_id,
                    "outcome": "buyer_review_proposed",
                    "review_id": str(review_id),
                    "contact_name": reconciled["name"],
                    "contact_title": reconciled["title"],
                    "contact_email": reconciled["email"],
                    "offer_key": offer_key,
                })
                continue

            probe = row.get("probe")
            reason = (
                _text(
                    probe.get("rejection_reason")
                    if isinstance(probe, Mapping)
                    else ""
                )
                or "contact_not_ready"
            )
            enqueued = queue.enqueue({
                "prospect_id": prospect_id,
                "business_name": account_name,
                "website": _text(row.get("canonical_website")),
                "reason": reason,
                "account_key": target.account_key,
                "wave": target.wave,
                "offer_key": offer_key,
                "target_people": [
                    dict(person)
                    for person in target.observed_people
                ],
                "target_product_codes": list(
                    target.target_product_codes
                ),
            })
            if enqueued:
                queued += 1
                outcomes.append({
                    "account_name": account_name,
                    "prospect_id": prospect_id,
                    "outcome": "targeted_enrichment_queued",
                    "reason": reason,
                    "target_people": [
                        dict(person)
                        for person in target.observed_people
                    ],
                    "offer_key": offer_key,
                })
            else:
                skipped += 1
        except Exception as exc:
            errors.append({
                "account_name": account_name,
                "prospect_id": prospect_id,
                "error": f"{type(exc).__name__}:{str(exc)[:300]}",
            })

    return {
        "schema_version": "empire.enterprise-contact-intelligence.v1",
        "proposed_review_count": proposed,
        "targeted_retry_queued_count": queued,
        "skipped_count": skipped,
        "error_count": len(errors),
        "errors": errors,
        "outcomes": outcomes,
        "live_outbound_send": False,
        "reviews_approved": 0,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "internal_write",
    }
