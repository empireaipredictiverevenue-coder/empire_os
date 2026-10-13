"""Attach founder-supplied EmpireDB domain history to an internal review.

An operator-pasted readback is evidence of a bounded historical domain query,
not an independently re-run query, recipient verification or permission to send.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


FLAGS = (
    "prior_canonical_intent_observed",
    "canonical_send_or_reply_event_observed",
    "any_suppression_on_domain_observed",
)


def apply_operator_domain_readback(
    review: Mapping[str, Any],
    readback: Mapping[str, Any],
    *,
    expected_domains: list[str],
) -> dict[str, Any]:
    """Validate complete cohort and annotate packets without clearing any gates."""
    if (review.get("mode") != "OBSERVE"
            or review.get("outreach_authorized") is not False
            or readback.get("schema_version") != "empire.enterprise-domain-history-readonly.v1"
            or readback.get("source") != "CANONICAL_EMPIREDB"
            or readback.get("mode") != "OBSERVE"
            or readback.get("database_transaction") != "READ_ONLY"
            or readback.get("database_writes") is not False
            or readback.get("outbound_sent") is not False
            or readback.get("founder_send_authorized") is not False
            or readback.get("individual_recipient_suppression_cleared") is not False):
        raise ValueError("UNTRUSTED_ENTERPRISE_DOMAIN_ATTESTATION")
    results = readback.get("domain_results")
    if (not isinstance(results, dict)
            or type(readback.get("domain_count")) is not int
            or readback["domain_count"] != len(results)
            or sorted(results) != sorted(expected_domains)
            or not isinstance(review.get("packets"), list)):
        raise ValueError("STALE_OR_INCOMPLETE_DOMAIN_ATTESTATION")
    for domain, item in results.items():
        if (not isinstance(item, Mapping)
                or any(type(item.get(flag)) is not bool for flag in FLAGS)
                or item.get("outreach_authorized") is not False
                or item.get("individual_recipient_suppression_cleared") is not False
                or item.get("recipient_identity_verified") is not False):
            raise ValueError("INVALID_DOMAIN_ATTESTATION_FLAGS")
        if item.get("domain_contact_history_state") != (
            "PRIOR_HISTORY_OBSERVED" if (
                item["prior_canonical_intent_observed"]
                or item["canonical_send_or_reply_event_observed"]
            ) else "NO_DOMAIN_HISTORY_OBSERVED_NOT_SEND_CLEARANCE"
        ):
            raise ValueError("INCONSISTENT_DOMAIN_HISTORY_STATE")
    updated = deepcopy(dict(review))
    for packet in updated["packets"]:
        domain = packet.get("domain")
        if domain not in results or packet.get("outreach_authorized") is not False:
            raise ValueError("UNMATCHED_DOMAIN_REVIEW_PACKET")
        entry = results[domain]
        # A website domain is not necessarily the published recipient's email domain.
        # Domain-history evidence cannot silently extend to a different mailbox domain.
        routes = (packet.get("market_role_review") or {}).get("public_contact_routes_for_review_only") or []
        uninspected = set()
        if not isinstance(routes, (list, tuple)):
            raise ValueError("INVALID_PUBLISHED_CONTACT_ROUTES")
        for route in routes:
            if not isinstance(route, Mapping):
                raise ValueError("INVALID_PUBLISHED_CONTACT_ROUTE")
            address = str(route.get("published_email") or "").strip().lower()
            if address:
                if address.count("@") != 1:
                    raise ValueError("INVALID_PUBLISHED_CONTACT_ADDRESS")
                contact_domain = address.rsplit("@", 1)[-1]
                if contact_domain not in results:
                    uninspected.add(contact_domain)
        packet["uninspected_published_contact_domains"] = sorted(uninspected)
        if uninspected:
            packet["blockers"].append("PUBLISHED_CONTACT_DOMAIN_HISTORY_UNCHECKED")
        packet["domain_history_observation"] = {
            "source": "FOUNDER_PASTED_CANONICAL_READBACK",
            "scope": "DOMAIN_ONLY",
            "history_state": entry["domain_contact_history_state"],
            "prior_intent_observed": entry["prior_canonical_intent_observed"],
            "send_or_reply_event_observed": entry["canonical_send_or_reply_event_observed"],
            "suppression_on_domain_observed": entry["any_suppression_on_domain_observed"],
            "individual_recipient_suppression_cleared": False,
            "outreach_authorized": False,
        }
        # Deliberately preserve the original recipient/contact blockers.
        if packet.get("prior_contact_status") != "UNKNOWN_RECHECK_REQUIRED":
            raise ValueError("RECIPIENT_HISTORY_IMPROPERLY_PRECLEARED")
        if packet.get("suppression_status") != "UNKNOWN_SEND_TIME_CHECK_REQUIRED":
            raise ValueError("RECIPIENT_SUPPRESSION_IMPROPERLY_PRECLEARED")
    updated["founder_operator_domain_history_observed"] = True
    updated["domain_history_observation_count"] = len(results)
    updated["domain_history_readback_is_send_clearance"] = False
    updated["individual_recipient_suppression_cleared"] = False
    updated["outreach_authorized"] = False
    updated["database_write_performed"] = False
    updated["outbound_sent"] = False
    return updated
