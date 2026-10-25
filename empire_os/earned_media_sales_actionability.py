"""Source-actionability barrier: research priority != a permitted sales action.

This companion reader has no connectors or rights to change commercial evidence.
It will not turn listing visibility, source hints, scores, emails, or canonical
UUIDs into verified buyers, quotes, authorised outreach or booked revenue.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Mapping
from pathlib import Path

from empire_os.earned_media_leadgen_review import REQUESTS, _key

SCHEMA = "empire.earned_media.sales_actionability_review.v1"
SOURCE_SCHEMA = "empire.earned_media.public_request_observation.v1"
MAX_LEADS = 200
MAX_OBSERVATIONS = 10
PUBLIC_PROBE_DOC = "docs/commercial/PR_CONSULTANCY_MARKETPLACE_PUBLIC_OBSERVATION_20261025.json"

COMMON_GATES = (
    "ORIGINAL_SOURCE_CURRENT_AND_ALLOWED",
    "BUYER_PROBLEM_AND_INTENT_INDEPENDENTLY_VERIFIED",
    "LAWFUL_CONTACT_CHANNEL_AND_PURPOSE_VERIFIED",
    "CURRENT_SUPPRESSION_AND_PRIOR_HISTORY_RECONCILED",
    "DELIVERY_CAPABILITY_AND_CAPACITY_VERIFIED",
    "TENANT_BOUND_CRM_COMMERCIAL_AUTHORITY_VERIFIED",
)


def _public_probe(
    snapshot: Any, *, as_of: datetime,
) -> tuple[dict[str, str], str]:
    """Search discovery never establishes authenticated listing availability."""
    if not isinstance(snapshot, Mapping):
        return {}, "NO_PUBLIC_PROBE"
    entries = snapshot.get("observations")
    if (snapshot.get("schema_version") != SOURCE_SCHEMA
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "none"
            or not isinstance(entries, list)
            or len(entries) > MAX_OBSERVATIONS):
        return {}, "INVALID_PUBLIC_PROBE"
    expected = {spec["url"] for spec in REQUESTS}
    observed: dict[str, str] = {}
    for item in entries:
        if not isinstance(item, Mapping):
            return {}, "INVALID_PUBLIC_PROBE"
        url = item.get("source_url")
        raw_date = item.get("observed_date")
        if (url not in expected or url in observed
                or item.get("discovery_channel") != "PUBLIC_SEARCH_RESULT"
                or item.get("authenticated_listing_available") is not False
                or item.get("identified_buying_organisation") is not False
                or item.get("supplier_eligibility_verified") is not False
                or item.get("outreach_authorized") is not False
                or not isinstance(raw_date, str)):
            return {}, "INVALID_PUBLIC_PROBE"
        try:
            observed_date = date.fromisoformat(raw_date)
        except ValueError:
            return {}, "INVALID_PUBLIC_PROBE"
        age = as_of.date() - observed_date
        if age.days < 0:
            return {}, "FUTURE_DATED_PUBLIC_PROBE"
        observed[url] = (
            "DISCOVERABLE_PUBLIC_INDEX_SNAPSHOT_NOT_LIVE_APPLICATION_PROOF"
            if age.days <= 2 else "STALE_PUBLIC_INDEX_SNAPSHOT"
        )
    return observed, "PUBLIC_INDEX_OBSERVATIONS_REVIEWED"


def review_sales_actionability(
    leadgen: Mapping[str, Any], *, as_of: datetime,
    public_observations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("OFFSET_AWARE_CLOCK_REQUIRED")
    if (leadgen.get("schema_version") != "empire.earned_media.lead_generation_review.v1"
            or leadgen.get("status") != "RESEARCH_PRIORITY_QUEUE_NOT_BUYER_PIPELINE"
            or leadgen.get("mode") != "OBSERVE"
            or leadgen.get("execution_authority") != "none"
            or leadgen.get("outbound_authorized") is not False
            or leadgen.get("crm_writes") is not False
            or leadgen.get("qualified_buyers_verified") != 0):
        raise ValueError("LEAD_REVIEW_AUTHORITY_INVALID")
    opportunities = leadgen.get("opportunities")
    if not isinstance(opportunities, list) or len(opportunities) > MAX_LEADS:
        raise ValueError("LEAD_REVIEW_UNBOUNDED")
    observed, probe_status = _public_probe(
        public_observations, as_of=as_of.astimezone(timezone.utc)
    )
    # Invalid source evidence is not silently allowed to grant a positive state.
    if probe_status in {"INVALID_PUBLIC_PROBE", "FUTURE_DATED_PUBLIC_PROBE"}:
        observed = {}
    rows: list[dict[str, Any]] = []
    seen = set()
    for lead in opportunities:
        if not isinstance(lead, Mapping):
            raise ValueError("INVALID_LEAD_ROW")
        identifier = lead.get("opportunity_id")
        if not isinstance(identifier, str) or identifier in seen:
            raise ValueError("DUPLICATE_OR_MISSING_LEAD_ID")
        seen.add(identifier)
        stage, channel = lead.get("lead_stage"), lead.get("channel")
        if (lead.get("verified_buyer_identity") is not False
                or lead.get("verified_procurement_intent") is not False
                or lead.get("outbound_authorized") is not False
                or lead.get("quote_authorized") is not False
                or lead.get("verified_revenue") is not False):
            raise ValueError("UNSUPPORTED_CLAIMED_COMMERCIAL_AUTHORITY")
        if stage == "SOURCE_SIGNAL_ONLY" and channel == "PUBLIC_PROCUREMENT_REQUEST":
            source_url = lead.get("source_url")
            if (identifier, source_url) not in {
                (_key("public_request", spec["url"]), spec["url"])
                for spec in REQUESTS
            }:
                raise ValueError("PUBLIC_REQUEST_SOURCE_MISMATCH")
            public_state = observed.get(source_url, "NOT_RECHECKED")
            if source_url == REQUESTS[2]["url"]:
                category = "HOLD_BROKERED_BUYER_ORIGINAL_SOURCE"
                next_check = "Verify original commissioning company and true primary procurement source, then delivery scope"
            else:
                category = "HOLD_MARKETPLACE_ELIGIBILITY_AND_DELIVERY"
                next_check = "Check original Upwork listing within authorised account, zero-spend eligibility and specialist credentials"
            open_gates = [*COMMON_GATES, "AUTHENTICATED_MARKETPLACE_ELIGIBILITY",
                          "BUYER_APPLICATION_REQUIREMENTS_AND_TERMS"]
            known = ["HISTORICAL_PUBLIC_SERVICE_REQUEST_OBSERVED"]
            if public_state.startswith("DISCOVERABLE"):
                known.append("PUBLIC_SEARCH_INDEX_RESULT_OBSERVED_NOT_PLATFORM_LOGIN")
        elif stage == "RESEARCHED_ACCOUNT_NOT_BUYER" and channel == "CANONICAL_REVENUE_DISTRIBUTION_RESEARCH":
            if not lead.get("existing_canonical_prospect_id"):
                raise ValueError("CLAIMED_CANONICAL_ACCOUNT_WITHOUT_ID")
            category = "RESEARCH_ONLY_CANONICAL_ID_NOT_BUYER_INTENT"
            public_state = "NOT_APPLICABLE"
            next_check = "Verify fresh company-specific need and lawful exact contact channel before separate CRM review"
            open_gates = list(COMMON_GATES)
            known = ["HISTORICAL_CANONICAL_PROSPECT_ID_PRESENT_NOT_TENANT_PROOF"]
        elif stage == "RESEARCHED_ACCOUNT_UNBOUND" and channel == "CANONICAL_REVENUE_DISTRIBUTION_RESEARCH":
            if lead.get("existing_canonical_prospect_id") is not None:
                raise ValueError("CLAIMED_UNBOUND_ACCOUNT_WITH_ID")
            category = "RESEARCH_ONLY_COMPANY_IDENTITY_UNBOUND"
            public_state = "NOT_APPLICABLE"
            next_check = "Verify original company/domain identity and real need; do not create phantom CRM lead"
            open_gates = [*COMMON_GATES, "CANONICAL_COMPANY_AND_PROSPECT_ID_VERIFIED"]
            known = ["HISTORICAL_RESEARCH_ACCOUNT_OBSERVED"]
        else:
            raise ValueError("UNEXPECTED_LEAD_STAGE_OR_CHANNEL")
        rows.append({
            "opportunity_id": identifier,
            "label": lead.get("label"),
            "lead_stage": stage,
            "original_review_priority_not_sales_probability": lead.get("priority_score"),
            "source_index_check": public_state,
            "actionability": category,
            "historically_observed_evidence": known,
            "required_before_sale": open_gates,
            "review_gates_passed": 0,
            "next_evidence_step": next_check,
            "eligible_for_outreach": False,
            "eligible_for_individual_quote": False,
            "client_acceptance_verified": False,
            "buyer_conversation_verified": False,
            "booked_pipeline_gbp_minor": None,
            "realised_revenue_gbp_minor": None,
        })
    categories = Counter(row["actionability"] for row in rows)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "none",
        "status": "REVIEW_PRIORITIES_NOT_EXECUTABLE_SALES_PIPELINE",
        "source_probe_state": probe_status,
        "source_proof": ("SEARCH_INDEX_ONLY_NO_PLATFORM_SESSION"
                         if observed else "UNVERIFIED_OR_UNAVAILABLE"),
        "total_observations": len(rows),
        "actionability_counts": dict(sorted(categories.items())),
        "ready_for_contact": 0, "ready_for_proposal": 0,
        "verified_buyer_conversations": 0, "accepted_clients": 0,
        "actual_sales": 0, "recognised_revenue": None,
        "records": rows,
        "first_party_opt_in_path": "/commercial#commercial-enquiry",
        "first_party_path_note": (
            "Existing consent-specific nonbinding commercial enquiry, not"
            " evidence it has received a buyer or approved a consultancy product."
        ),
        "sender_authority": False, "crm_write_authority": False,
        "payment_authority": False,
    }


def review_sales_from_source_file(
    leadgen: Mapping[str, Any], *, repo_root: str | Path, as_of: datetime,
) -> dict[str, Any]:
    """Prefer actual bounded provenance file, never client-provided listings."""
    from empire_os.earned_media_advisory_bridge import _json, SourceHeld

    if leadgen.get("status") != "RESEARCH_PRIORITY_QUEUE_NOT_BUYER_PIPELINE":
        return {
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "status": "HELD_LEADGEN_UPSTREAM",
            "execution_authority": "none", "total_observations": 0,
            "records": [], "actionability_counts": {},
            "ready_for_contact": 0, "ready_for_proposal": 0,
            "verified_buyer_conversations": 0, "accepted_clients": 0,
            "recognised_revenue": None, "sender_authority": False,
            "crm_write_authority": False, "payment_authority": False,
            "source_probe_state": "NOT_READ_UPSTREAM_HELD",
        }
    source = None
    integrity = "NO_PROBE_FILE"
    try:
        source, digest = _json(Path(repo_root), PUBLIC_PROBE_DOC)
        integrity = "SOURCE_FILE_READ_BOUNDED"
    except (OSError, ValueError, SourceHeld):
        digest = None
    result = review_sales_actionability(
        leadgen, as_of=as_of, public_observations=source,
    )
    result["observation_source"] = {
        "reference": PUBLIC_PROBE_DOC, "integrity": integrity,
        "sha256": digest,
    }
    return result
