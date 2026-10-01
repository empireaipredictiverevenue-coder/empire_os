"""Enterprise contact intelligence reconciliation and review-queue sync.

Converts enterprise activation evidence into canonical pending buyer reviews or
durable targeted enrichment retries. It never approves reviews, sends outreach,
accepts terms, moves funds, or recognizes revenue.
"""
from __future__ import annotations

from typing import Any, Mapping
import time
import urllib.parse

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_discovery import (
    build_candidate,
    build_candidate_review_plan,
    classify_decision_role,
    looks_like_person_name,
    rank_site_people,
)
from empire_os.predictive_revenue_enterprise_targets import TARGETS
from empire_os.sb import request_json


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _key(value: Any) -> str:
    return _text(value).casefold()


def _probe_people(probe: Any) -> list[Any]:
    """Normalize the canonical site-probe people contract.

    New/raw site_probe evidence uses 'people'. 'site_people' is accepted only
    as a legacy compatibility key so older persisted review snapshots do not
    lose evidence during rollout.
    """
    if not isinstance(probe, Mapping):
        return []

    if "people" in probe:
        people = probe.get("people")
    else:
        people = probe.get("site_people")

    if not isinstance(people, (list, tuple)):
        return []

    return list(people)


TARGET_BY_NAME = {
    target.account_name: target
    for target in TARGETS
}


def _target_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve enterprise metadata from the activation row first.

    Curated targets may enrich the original seed accounts, but rolling accounts
    remain first-class and must not depend on TARGETS membership.
    """
    account_name = _text(row.get("account_name"))
    target = TARGET_BY_NAME.get(account_name)

    account_key = _text(row.get("account_key"))
    if not account_key and target is not None:
        account_key = _text(target.account_key)

    wave = _text(row.get("wave"))
    if not wave and target is not None:
        wave = _text(target.wave)

    raw_codes = row.get("target_product_codes")
    product_codes = [
        _text(value)
        for value in (raw_codes if isinstance(raw_codes, (list, tuple)) else [])
        if _text(value)
    ]
    if not product_codes and target is not None:
        product_codes = [
            _text(value)
            for value in target.target_product_codes
            if _text(value)
        ]

    urls: list[str] = []
    for key in ("target_evidence_urls", "evidence_urls"):
        raw_urls = row.get(key)
        if isinstance(raw_urls, (list, tuple)):
            urls.extend(_text(value) for value in raw_urls if _text(value))
    if target is not None:
        urls.extend(_text(value) for value in target.evidence_urls if _text(value))
    canonical_website = _text(row.get("canonical_website"))
    if canonical_website:
        urls.append(canonical_website)
    for route in row.get("company_contact_routes") or []:
        if isinstance(route, Mapping):
            evidence_url = _text(route.get("evidence_url"))
            if evidence_url:
                urls.append(evidence_url)
    for person in _probe_people(row.get("probe")):
        if isinstance(person, Mapping):
            evidence_url = _text(person.get("url")) or _text(person.get("page_url"))
            if evidence_url:
                urls.append(evidence_url)

    return {
        "target": target,
        "account_key": account_key,
        "wave": wave,
        "target_product_codes": list(dict.fromkeys(product_codes)),
        "target_evidence_urls": list(dict.fromkeys(urls)),
    }


def _request_with_retry(
    request,
    method: str,
    path: str,
    *,
    payload: Any | None = None,
    attempts: int = 3,
    base_delay_seconds: float = 0.35,
):
    last_error: Exception | None = None
    for attempt in range(1, max(1, int(attempts)) + 1):
        try:
            return request(
                method,
                path,
                payload=payload,
            )
        except (RuntimeError, OSError, TimeoutError) as exc:
            last_error = exc
            if attempt >= attempts:
                break
            time.sleep(
                max(0.0, float(base_delay_seconds))
                * (2 ** (attempt - 1))
            )
    assert last_error is not None
    raise last_error


def _leadership_evidence_url(target) -> str | None:
    urls = [
        _text(url)
        for url in target.evidence_urls
        if _text(url)
    ]
    for url in urls:
        lowered = url.lower()
        if any(
            token in lowered
            for token in (
                "/leadership",
                "/team",
                "/people",
                "/management",
                "/who-we-are",
            )
        ):
            return url
    return urls[0] if urls else None


def current_target_people(
    row: Mapping[str, Any],
) -> list[dict[str, Any]]:
    account_name = _text(row.get("account_name"))
    target = TARGET_BY_NAME.get(account_name)

    evidence: list[dict[str, Any]] = []

    probe = row.get("probe")
    for person in _probe_people(probe):
        if not isinstance(person, Mapping):
            continue
        name = _text(person.get("name"))
        title = _text(person.get("title"))
        if not looks_like_person_name(name) or not title:
            continue
        evidence.append({
            "name": name,
            "title": title,
            "email": _text(person.get("email")),
            "url": (
                _text(person.get("url"))
                or _text(person.get("page_url"))
            ),
            "source_kind": _text(person.get("source_kind")),
        })

    for person in row.get("observed_people") or []:
        if not isinstance(person, Mapping):
            continue
        name = _text(person.get("name"))
        title = _text(person.get("title"))
        if not looks_like_person_name(name) or not title:
            continue
        evidence.append({
            "name": name,
            "title": title,
            "email": _text(person.get("email")),
            "url": _text(person.get("url")) or _text(person.get("page_url")),
            "source_kind": _text(person.get("source_kind")) or "activation_observed",
        })

    if target is not None:
        curated_url = _leadership_evidence_url(target)
        for person in target.observed_people:
            name = _text(person.get("name"))
            title = _text(person.get("title"))
            if not name or not title:
                continue
            evidence.append({
                "name": name,
                "title": title,
                "email": "",
                "url": curated_url or "",
                "source_kind": "curated_first_party",
            })

    ranked = rank_site_people(evidence)
    return [
        {
            **person,
            "source": (
                "first_party_site_current"
                if person.get("source_kind") == "visible_text"
                else (
                    "curated_public_evidence"
                    if person.get("source_kind") == "curated_first_party"
                    else "first_party_site_observed"
                )
            ),
            "evidence_url": person.get("url") or None,
        }
        for person in ranked[:8]
    ]

def _verified_decision_email(
    probe: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> str:
    """Return only an email verified for the same named decision maker."""
    email = _text(decision.get("email")).lower()
    name = _text(decision.get("name"))
    if not email or not looks_like_person_name(name):
        return ""

    verified = next(
        (
            item
            for item in (probe.get("verified_contacts") or [])
            if isinstance(item, Mapping)
            and _text(item.get("email")).lower() == email
            and item.get("is_valid") is True
            and item.get("bound_to_decision_maker") is True
        ),
        None,
    )
    if verified is None:
        return ""

    first_party_sources = {
        "official_site",
        "person_structured_data",
        "first_party_schema_person",
        "hunter_confirmed_first_party",
    }
    if _text(verified.get("source")) in first_party_sources:
        return email

    hunter_match = any(
        isinstance(item, Mapping)
        and _text(item.get("email")).lower() == email
        and _key(item.get("person_name")) == _key(name)
        and item.get("person_bound") is True
        and item.get("first_party") is True
        and _text(item.get("state")).lower() == "confirmed"
        and item.get("bounced_evidence") is not True
        for item in (probe.get("hunter_confirmed_contacts") or [])
    )
    return email if hunter_match else ""


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

    decision = probe.get("decision_maker")
    if not isinstance(decision, Mapping):
        return None
    email = _verified_decision_email(probe, decision)
    if not email:
        return None

    name = _text(decision.get("name"))
    if not looks_like_person_name(name):
        return None

    metadata = _target_metadata(row)
    target = metadata["target"]

    observed = next(
        (
            dict(person)
            for person in current_target_people(row)
            if _key(person.get("name")) == _key(name)
        ),
        None,
    )

    site_title_conflicts: list[dict[str, Any]] = []
    curated_match = next(
        (
            person
            for person in target.observed_people
            if _key(person.get("name")) == _key(name)
        ),
        None,
    ) if target is not None else None
    if curated_match is not None:
        curated_title = _text(curated_match.get("title"))
        for person in _probe_people(probe):
            if not isinstance(person, Mapping):
                continue
            if _key(person.get("name")) != _key(name):
                continue
            candidate_title = _text(person.get("title"))
            if (
                candidate_title
                and _key(candidate_title) != _key(curated_title)
            ):
                site_title_conflicts.append({
                    "title": candidate_title,
                    "source_kind": _text(person.get("source_kind")) or None,
                    "url": (
                        _text(person.get("url"))
                        or _text(person.get("page_url"))
                        or None
                    ),
                })

    if curated_match is not None:
        title = _text(curated_match.get("title"))
        role, score = classify_decision_role(title)
        return {
            "name": name,
            "title": title,
            "email": email,
            "decision_role": role,
            "decision_score": score,
            "source": "enterprise_target_reconciled",
            "probe_source": _text(decision.get("source")) or None,
            "leadership_source": "curated_public_evidence",
            "leadership_evidence_url": _leadership_evidence_url(target),
            "role_reconciled": True,
            "site_title_conflict": bool(site_title_conflicts),
            "site_title_conflicts": site_title_conflicts,
            "target_evidence_urls": list(metadata["target_evidence_urls"]),
        }

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
            "leadership_source": observed.get("source"),
            "leadership_evidence_url": observed.get("evidence_url"),
            "role_reconciled": True,
            "site_title_conflict": bool(site_title_conflicts),
            "site_title_conflicts": site_title_conflicts,
            "target_evidence_urls": list(metadata["target_evidence_urls"]),
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
        "target_evidence_urls": list(metadata["target_evidence_urls"]),
    }


def _pending_review_for_prospect(
    prospect_id: str,
    *,
    request=request_json,
) -> dict[str, Any] | None:
    prospect_id = _text(prospect_id)
    if not prospect_id:
        return None
    params = urllib.parse.urlencode({
        "select": (
            "id,status,prospect_id,contact_name,contact_title,contact_email,"
            "decision_score,evidence,created_at"
        ),
        "prospect_id": f"eq.{prospect_id}",
        "status": "eq.pending",
        "order": "created_at.desc",
        "limit": 2,
    })
    rows = _request_with_retry(
        request,
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{params}",
    ) or []
    pending = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and _text(row.get("status")).lower() == "pending"
        and _text(row.get("prospect_id")) == prospect_id
        and _text(row.get("id"))
    ]
    if len(pending) > 1:
        raise RuntimeError(
            f"multiple_pending_buyer_reviews:{prospect_id}"
        )
    return pending[0] if pending else None


def _refresh_pending_review(
    review_id: str,
    *,
    contact_name: str,
    contact_title: str,
    contact_email: str,
    decision_score: float,
    evidence: Mapping[str, Any],
    request=request_json,
) -> bool:
    review_id = _text(review_id)
    if not review_id:
        return False

    params = urllib.parse.urlencode({
        "select": (
            "id,status,contact_name,contact_title,contact_email,"
            "decision_score,evidence"
        ),
        "id": f"eq.{review_id}",
        "limit": 1,
    })
    rows = _request_with_retry(
        request,
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{params}",
    ) or []
    if not isinstance(rows, list) or not rows:
        return False

    current = rows[0] if isinstance(rows[0], Mapping) else {}
    if _text(current.get("status")).lower() != "pending":
        return False

    desired_email = _text(contact_email).lower()
    desired_title = _text(contact_title)
    desired_name = _text(contact_name)
    current_email = _text(current.get("contact_email")).lower()
    current_title = _text(current.get("contact_title"))
    current_name = _text(current.get("contact_name"))

    if (
        current_email == desired_email
        and current_title == desired_title
        and current_name == desired_name
    ):
        return False

    response = _request_with_retry(
        request,
        "POST",
        "/rest/v1/rpc/refresh_pending_buyer_candidate_review",
        payload={
            "p_review_id": review_id,
            "p_contact_name": desired_name,
            "p_contact_title": desired_title,
            "p_contact_email": desired_email,
            "p_decision_score": float(decision_score),
            "p_evidence": dict(evidence),
        },
    )
    decision = (
        _text(response.get("decision")).lower()
        if isinstance(response, Mapping)
        else ""
    )
    if decision == "not_pending":
        return False
    if decision not in {"updated", "no_change"}:
        raise RuntimeError(
            "pending review refresh rpc returned unexpected decision"
        )

    verify = _request_with_retry(
        request,
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{params}",
    ) or []
    if not isinstance(verify, list) or not verify:
        raise RuntimeError("pending review reconciliation verification missing")
    row = verify[0] if isinstance(verify[0], Mapping) else {}
    if (
        _text(row.get("status")).lower() != "pending"
        or _text(row.get("contact_name")) != desired_name
        or _text(row.get("contact_title")) != desired_title
        or _text(row.get("contact_email")).lower() != desired_email
    ):
        raise RuntimeError("pending review reconciliation did not persist")
    return True


def _fetch_prospect(
    prospect_id: str,
    *,
    request=request_json,
) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "select": (
            "id,business_name,niche,metro,phone,website,address,"
            "buy_signal_score,status,notes,contact_name,contact_title,"
            "contact_source,contacted_status,created_at"
        ),
        "id": f"eq.{prospect_id}",
        "limit": 1,
    })
    rows = _request_with_retry(
        request,
        "GET",
        f"/rest/v1/prospects?{params}",
    ) or []
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
    proposed = reconciled_existing = queued = skipped = 0
    errors: list[dict[str, str]] = []
    outcomes: list[dict[str, Any]] = []

    for row in activation.get("targets") or []:
        if not isinstance(row, Mapping):
            continue
        account_name = _text(row.get("account_name"))
        metadata = _target_metadata(row)
        prospect_id = _text(row.get("prospect_id"))
        account_key = _text(metadata.get("account_key"))
        wave = _text(metadata.get("wave"))
        target_product_codes = list(
            metadata.get("target_product_codes") or []
        )
        target_evidence_urls = list(
            metadata.get("target_evidence_urls") or []
        )
        if not prospect_id or not account_key:
            skipped += 1
            continue

        offer_key = (
            target_product_codes[0]
            if target_product_codes
            else "predictive_revenue_diagnostic"
        )
        reconciled = reconcile_verified_enterprise_contact(row)

        try:
            if reconciled is not None:
                prospect = _fetch_prospect(
                    prospect_id,
                    request=request,
                )
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
                        f"enterprise-review:{account_key}:"
                        f"{reconciled['email']}:v1"
                    ),
                )
                plan["params"]["p_evidence"].update({
                    "source": "enterprise_contact_intelligence.v1",
                    "account_key": account_key,
                    "wave": wave,
                    "target_product_codes": target_product_codes,
                    "target_evidence_urls": list(metadata["target_evidence_urls"]),
                    "company_contact_routes": [
                        dict(route)
                        for route in (
                            row.get("company_contact_routes") or []
                        )
                        if isinstance(route, Mapping)
                    ],
                    "role_reconciled": bool(
                        reconciled["role_reconciled"]
                    ),
                    "live_outbound_send": False,
                    "actual_revenue": False,
                })
                pending_review = _pending_review_for_prospect(
                    prospect_id,
                    request=request,
                )
                review_refreshed = False
                review_outcome = "buyer_review_proposed"
                queue_outcome = "enterprise_buyer_review_proposed"
                if pending_review is not None:
                    review_id = str(pending_review["id"])
                    review_refreshed = _refresh_pending_review(
                        review_id,
                        contact_name=reconciled["name"],
                        contact_title=reconciled["title"],
                        contact_email=reconciled["email"],
                        decision_score=float(
                            plan["params"]["p_decision_score"]
                        ),
                        evidence=plan["params"]["p_evidence"],
                        request=request,
                    )
                    reconciled_existing += 1
                    review_outcome = "buyer_review_reconciled"
                    queue_outcome = "enterprise_buyer_review_reconciled"
                else:
                    response = _request_with_retry(
                        request,
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
                        raise RuntimeError(
                            "review proposal returned no review_id"
                        )
                    if (
                        isinstance(response, Mapping)
                        and _text(response.get("decision")).lower()
                        == "existing"
                    ):
                        review_refreshed = _refresh_pending_review(
                            str(review_id),
                            contact_name=reconciled["name"],
                            contact_title=reconciled["title"],
                            contact_email=reconciled["email"],
                            decision_score=float(
                                plan["params"]["p_decision_score"]
                            ),
                            evidence=plan["params"]["p_evidence"],
                            request=request,
                        )
                    else:
                        proposed += 1
                queue.resolve(
                    prospect_id,
                    outcome=queue_outcome,
                )
                outcomes.append({
                    "account_name": account_name,
                    "prospect_id": prospect_id,
                    "outcome": review_outcome,
                    "review_id": str(review_id),
                    "contact_name": reconciled["name"],
                    "contact_title": reconciled["title"],
                    "contact_email": reconciled["email"],
                    "offer_key": offer_key,
                    "pending_review_refreshed": review_refreshed,
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
            company_routes = [
                dict(route)
                for route in (row.get("company_contact_routes") or [])
                if isinstance(route, Mapping)
                and route.get("verified") is True
                and _text(route.get("value"))
            ]
            voice_route = next(
                (
                    route
                    for route in company_routes
                    if _text(route.get("channel")).lower() == "voice"
                    and route.get("person_bound") is not True
                ),
                None,
            )
            enqueued = queue.enqueue({
                "prospect_id": prospect_id,
                "business_name": account_name,
                "website": _text(row.get("canonical_website")),
                "phone": (
                    _text(voice_route.get("value"))
                    if isinstance(voice_route, Mapping)
                    else ""
                ),
                "reason": reason,
                "priority_score": (
                    95 if wave == "rolling_enterprise" else 90
                ),
                "priority_reason": "enterprise_contact_convergence",
                "account_key": account_key,
                "wave": wave,
                "offer_key": offer_key,
                "target_people": current_target_people(row),
                "target_product_codes": target_product_codes,
                "company_contact_routes": company_routes,
            })
            if enqueued:
                queued += 1
                outcomes.append({
                    "account_name": account_name,
                    "prospect_id": prospect_id,
                    "outcome": "targeted_enrichment_queued",
                    "reason": reason,
                    "target_people": current_target_people(row),
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
        "reconciled_existing_review_count": reconciled_existing,
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
