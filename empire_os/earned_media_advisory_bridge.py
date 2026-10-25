"""Read-only evidence bridge for existing EmpireOS PR, editorial and consultancy.

Combines first-party review artefacts; does not read Gmail, query EmpireDB,
upsert Smart CRM, send messages, publish content, issue terms or collect money.
No source document supplies execution authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

SCHEMA = "empire.earned_media_advisory.review.v1"
PR_SEND = "docs/commercial/PR_EDITORIAL_GMAIL_SEND_EVIDENCE_20261011.json"
PR_CONTACT = "docs/commercial/PR_EDITORIAL_CONTACT_REVIEW_20261011.json"
PR_PRICES = "docs/commercial/PR_CONSULTANCY_FOUNDER_PRICING_20261011.json"
GROWTH_PITCH = "docs/marketing/GROWTH_001_EDITORIAL_CAMPAIGN_PITCHES_20261016.md"
GROWTH_ARTICLE = "docs/marketing/GROWTH_001_AI_READINESS_ARTICLE_DRAFT_20261016.md"
PROPOSAL = "docs/website/NATIVE_BUYER_PROPOSAL_RELEASE_HANDOFF_20261020.md"
TENDER = "docs/commercial/TENDER_CONSULTANT_AGENT_FOUNDER_HANDOFF_20261024.md"

EXPECTED_PRICES = {
    "consultancy_ai_revenue_opportunity_assessment": (250000, "one_off"),
    "consultancy_predictive_revenue_strategy_blueprint": (750000, "one_off"),
    "consultancy_strategic_ai_revenue_advisory": (300000, "monthly"),
}


class SourceHeld(ValueError):
    """Data is missing/altered/unsafe; never infer authority from a draft."""


def _read(root: Path, relative: str, *, max_bytes: int = 350000) -> tuple[bytes, str]:
    """Only fixed, in-root, regular files; reject symlinks and large payloads."""
    parts = Path(relative).parts
    if not parts or any(p in ("..", ".") for p in parts) or Path(relative).is_absolute():
        raise SourceHeld("INVALID_EVIDENCE_PATH")
    node = root
    if node.is_symlink():
        raise SourceHeld("SYMLINK_SOURCE_ROOT")
    for part in parts:
        node = node / part
        if node.is_symlink():
            raise SourceHeld("SYMLINK_SOURCE")
    if not node.is_file():
        raise SourceHeld("SOURCE_MISSING")
    size = node.stat().st_size
    if size <= 0 or size > max_bytes:
        raise SourceHeld("INVALID_SOURCE_SIZE")
    data = node.read_bytes()
    if len(data) != size:
        raise SourceHeld("UNSTABLE_SOURCE")
    return data, sha256(data).hexdigest()


def _json(root: Path, relative: str) -> tuple[dict[str, Any], str]:
    data, digest = _read(root, relative)
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError) as error:
        raise SourceHeld("MALFORMED_SOURCE_JSON") from error
    if not isinstance(value, dict):
        raise SourceHeld("SOURCE_NOT_OBJECT")
    return value, digest


def _source(health: dict[str, Any], key: str, root: Path, relative: str,
            *, kind: str = "json") -> tuple[Any, bool]:
    try:
        raw, digest = (_json(root, relative) if kind == "json" else _read(root, relative))
    except (SourceHeld, OSError, ValueError):
        health[key] = {"state": "HELD_SOURCE_UNAVAILABLE_OR_INVALID",
                       "reference": relative}
        return None, False
    health[key] = {"state": "EVIDENCE_FILE_READ",
                   "reference": relative, "sha256": digest}
    return raw, True


def _action(lane: str, ref: str, title: str, step: str, *,
            state: str, evidence: str, provider_thread: str | None = None,
            amount_minor: int | None = None, billing: str | None = None) -> dict[str, Any]:
    """Use durable provenance; never invent company/person/tenant binding."""
    identity = sha256((lane + "|" + ref).encode("utf-8")).hexdigest()[:24]
    return {
        "item_id": "earned_" + identity,
        "lane": lane, "label": title, "state": state, "next_review": step,
        "evidence_reference": evidence,
        "source_provider_thread": provider_thread,
        "source_message_id": None,
        "crm_linkage": {
            "state": "UNBOUND_REQUIRES_CANONICAL_IDENTITY_AND_TENANT_REVIEW",
            "canonical_company_id": None,
            "canonical_prospect_id": None,
            "canonical_opportunity_id": None,
        },
        "approved_to_contact": False, "approved_to_publish": False,
        "approved_to_quote": False, "execution_authority": "none",
        "amount_minor": amount_minor, "billing_model": billing,
    }


def review(repo_root: str | Path, *, pr_root: str | Path | None = None,
           distribution_root: str | Path | None = None) -> dict[str, Any]:
    """Pure aggregation with strictly bounded files. No side effects."""
    root = Path(repo_root)
    pr = Path(pr_root) if pr_root else root
    distribution = Path(distribution_root) if distribution_root else root
    sources: dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    seen_threads: set[str] = set()

    messages, ok = _source(sources, "pr_sent_receipts", pr, PR_SEND)
    if ok:
        records = messages.get("records")
        valid = (
            messages.get("schema_version") == "empire.pr_editorial_gmail_submission_evidence.v1"
            and messages.get("mode") == "OBSERVE"
            and messages.get("execution_authority") == "none"
            and messages.get("future_outreach_authorized") is False
            and messages.get("canonical_governed_outbound_activation") is False
            and isinstance(records, list)
            and len(records) == messages.get("submission_count")
            and 0 < len(records) <= 20
        )
        if valid:
            for entry in records:
                if (not isinstance(entry, dict)
                        or not isinstance(entry.get("outlet"), str)
                        or not isinstance(entry.get("thread_id"), str)
                        or not entry["thread_id"].strip()
                        or not isinstance(entry.get("message_id"), str)
                        or not entry["message_id"].strip()
                        or entry.get("receipt_verified") is not True
                        or entry.get("provider_label") != "SENT"
                        or entry["thread_id"] in seen_threads):
                    valid = False
                    break
                seen_threads.add(entry["thread_id"])
        if not valid:
            sources["pr_sent_receipts"]["state"] = "HELD_CONTRADICTORY_SEND_EVIDENCE"
            seen_threads.clear()
        else:
            for entry in records:
                items.append(_action(
                    "pr", entry["thread_id"], entry["outlet"],
                    "Reconcile this exact previously-sent Gmail thread for an actual reply; no repeat pitch",
                    state="SENT_PROVIDER_RECEIPT_REPLY_UNVERIFIED",
                    evidence=PR_SEND, provider_thread=entry["thread_id"],
                ))

    sent_history_valid = sources["pr_sent_receipts"]["state"] == "EVIDENCE_FILE_READ"
    contacts, ok = _source(sources, "pr_outlet_research", pr, PR_CONTACT)
    if ok:
        if contacts.get("mode") != "OBSERVE" or not isinstance(contacts.get("outlets"), list):
            sources["pr_outlet_research"]["state"] = "HELD_CONTACTS_NOT_VERIFIED"
        else:
            sent_names = {item["label"].casefold() for item in items if item["lane"] == "pr"}
            for contact in contacts["outlets"][:25]:
                if not isinstance(contact, dict) or not isinstance(contact.get("outlet"), str):
                    continue
                name = contact["outlet"].strip()
                if not name or name.casefold() in sent_names:
                    continue
                # Contact metadata is not permission to pitch.
                items.append(_action(
                    "pr", name.casefold(), name,
                    ("Verify current newsroom submission policy and exact recipient; founder review required"
                     if sent_history_valid else "Reconcile exact prior Gmail send history before any pitch review"),
                    state=("RESEARCHED_NOT_SENT_BY_THIS_EVIDENCE" if sent_history_valid
                           else "HOLD_PRIOR_SEND_HISTORY_UNVERIFIED"),
                    evidence=PR_CONTACT,
                ))

    growth, ok = _source(sources, "earned_editorial_pitches", root, GROWTH_PITCH, kind="md")
    if ok:
        if b"prepared, NOT sent" not in growth:
            # A named editorial draft is not independent publication proof.
            sources["earned_editorial_pitches"]["state"] = "HELD_UNCLEAR_SUBMISSION_STATE"
        else:
            for outlet in ("Compare the Cloud", "SME Today"):
                items.append(_action(
                    "editorial", outlet.casefold(), outlet,
                    "Review original outlet-specific article/pitch and recheck publisher requirements",
                    state="ORIGINAL_DRAFT_NOT_SUBMITTED",
                    evidence=GROWTH_PITCH,
                ))

    article, ok = _source(sources, "owned_article", root, GROWTH_ARTICLE, kind="md")
    if ok and b"commercial" in article:
        items.append(_action(
            "editorial", "ai-readiness-original", "AI readiness original article",
            "Founder fact-check, rights review and existing ASTRA/SEO publisher release",
            state="DRAFT_NOT_PUBLICATION_EVIDENCE", evidence=GROWTH_ARTICLE,
        ))

    prices, ok = _source(sources, "consultancy_pricing", pr, PR_PRICES)
    if ok:
        approval = prices.get("approval")
        services = prices.get("services")
        valid = (isinstance(approval, dict)
                 and approval.get("decision") == "FOUNDER_APPROVES_PROPOSED_PRICING_ONLY"
                 and isinstance(approval.get("excludes"), list)
                 and {"contracts", "payments", "crm_write", "production_activation"}.issubset(
                     set(x for x in approval["excludes"] if isinstance(x, str)))
                 and isinstance(services, list) and len(services) == len(EXPECTED_PRICES)
                 and {s.get("code") for s in services if isinstance(s, dict)} == set(EXPECTED_PRICES))
        if valid:
            for service in services:
                code = service["code"]
                amount, billing = EXPECTED_PRICES[code]
                if (service.get("amount_minor") != amount
                        or service.get("currency") != "GBP"
                        or service.get("billing_model") != billing
                        or service.get("existing_catalog_product_code") is not None
                        or not isinstance(service.get("name"), str)):
                    valid = False
                    break
        if not valid:
            sources["consultancy_pricing"]["state"] = "HELD_UNVERIFIED_PRICE_OR_AUTHORITY"
        else:
            for service in services:
                items.append(_action(
                    "consultancy", service["code"], service["name"],
                    "Review exact scope, cost, capacity, privacy, terms and canonical CRM intake before an individual quote",
                    state="FOUNDER_PRICING_APPROVED_TERMS_HELD",
                    evidence=PR_PRICES,
                    amount_minor=service["amount_minor"], billing=service["billing_model"],
                ))

    proposal, ok = _source(sources, "proposal_handoff", root, PROPOSAL, kind="md")
    if ok:
        items.append(_action(
            "proposal", "original-website-proposal", "Buyer proposal handoff",
            "Validate offer, named buyer, verified source, personalised SOW and explicit founder sign-off",
            state="REVIEW_HANDOFF_NO_CONTRACT", evidence=PROPOSAL,
        ))

    tender, ok = _source(sources, "tender_consulting", root, TENDER, kind="md")
    if ok:
        items.append(_action(
            "consultancy", "tender-consultant", "Tender consultancy review",
            "Obtain authorised current RFQ and qualified supplier proofs; keep all bids held",
            state="INTERNAL_REVIEW_NO_BID_AUTHORITY", evidence=TENDER,
        ))

    snapshot, ok = _source(sources, "distribution_snapshot", distribution,
                           "runtime/revenue_distribution/latest.json")
    publisher_summary = {"state": "NOT_VERIFIED", "historical_snapshot": True}
    if ok and snapshot.get("mode") == "OBSERVE" and snapshot.get("execution_authority") == "none":
        publishers = snapshot.get("publisher_supply_recruitment", {})
        if isinstance(publishers, dict) and publishers.get("execution_authority") == "none":
            publisher_summary = {
                "state": "HISTORICAL_COMMERCIAL_PUBLISHER_INVENTORY_NOT_PR_PLACEMENT",
                "evidence_observed_date": publishers.get("evidence_observed_date"),
                "candidate_count": publishers.get("candidate_count"),
                "submitted_count": publishers.get("email_submitted_count"),
                "reply_count_verified": None,
                "historical_snapshot": True,
            }
    else:
        sources["distribution_snapshot"]["state"] = "HELD_DISTRIBUTION_NOT_OBSERVE"

    counts = {lane: sum(item["lane"] == lane for item in items)
              for lane in ("pr", "editorial", "consultancy", "proposal")}
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "status": ("REVIEW_CONNECTED_WITH_SOURCE_GAPS"
                   if any(s["state"].startswith("HELD") for s in sources.values())
                   else "REVIEW_CONNECTED_NOT_PRODUCTION_ACTIVATION"),
        "sources": sources,
        "lane_counts": counts,
        "publisher_supply": publisher_summary,
        "handoff_contract": {
            "pr_and_editorial_to_measured_attention": "REQUIRES_REAL_EXTERNAL_PLACEMENT_URL_AND_ATTRIBUTION",
            "measured_attention_to_crm": "REQUIRES_CONSENTED_INBOUND_AND_CANONICAL_TENANT_IDENTITY",
            "consultancy_to_proposal": "REQUIRES_SCOPED_CLIENT_REQUEST_AND_REVIEWED_SOW",
            "proposal_to_contract": "REQUIRES_EXPLICIT_TERMS_AND_FOUNDER_APPROVAL",
            "contract_to_economic_memory": "REQUIRES_FULFILMENT_AND_VERIFIED_SETTLEMENT",
            "editorial_independence": "NO_PAID_EDITORIAL_OR_ASSUMED_BACKLINKS",
        },
        "items": items,
        "smart_crm_writes": False, "empiredb_writes": False,
        "outbound_sent_by_review": False, "new_outbound_authorized": False,
        "publication_authorized": False, "quotes_authorized": False,
        "payment_authorized": False, "revenue_verified_by_review": False,
        "revenue_verification_state": "NOT_QUERIED",
        "next_system_step": "RECONCILE_IN_EXISTING_FOUNDER_REVIEW_AND_CANONICAL_CRM_AFTER_OWNER_APPROVAL",
    }
