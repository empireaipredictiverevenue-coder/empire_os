"""Read-only owned-campaign preflight. This module cannot publish or activate."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import re
from typing import Any


EVENT_FIELDS = frozenset({
    "event_id", "campaign_id", "asset_id", "source", "channel", "occurred_at",
})
REQUIRED_EVENTS = (
    "campaign_page_view", "campaign_cta_click", "campaign_enquiry_started",
    "campaign_enquiry_submitted",
)
INFRASTRUCTURE_GATES = (
    "owned_destination", "privacy_review",
    "governed_enquiry_endpoint", "first_party_event_collector",
    "canonical_intake_schema", "public_route_prepared", "site_build",
)
CAMPAIGN_ID = re.compile(r"campaign_[0-9a-f]{24}\Z")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode()).hexdigest()


def lookup_campaign(marketing: dict, campaign_id: str) -> dict:
    if not isinstance(campaign_id, str) or not CAMPAIGN_ID.fullmatch(campaign_id):
        raise ValueError("invalid campaign ID")
    matches = [c for c in marketing.get("campaigns", [])
               if c.get("campaign_id") == campaign_id]
    if len(matches) != 1:
        raise ValueError("campaign missing or ambiguous")
    return deepcopy(matches[0])


def _landing(campaign: dict) -> dict:
    assets = [a for a in campaign.get("assets", [])
              if a.get("asset_type") == "landing_page"]
    return assets[0] if len(assets) == 1 else {}


def inspect_campaigns(marketing: dict, infrastructure: dict) -> dict:
    """Reviews are evidence inputs, never execution permissions.

    Infrastructure review entries require status PASS and evidence_refs. Content
    publication review must be bound to the exact landing asset digest. Passing
    this preflight still does not establish deployment or authorize a transition.
    """
    from empire_os.owned_campaign_content import public_owner_scope, render_asset, PRIVACY

    campaigns = marketing.get("campaigns")
    if not isinstance(campaigns, list):
        raise ValueError("canonical campaigns list required")
    sections = Counter(digest(_landing(c).get("sections")) for c in campaigns)
    results = []
    for c in campaigns:
        cid = c.get("campaign_id")
        gates: dict[str, bool] = {}
        try:
            lookup_campaign(marketing, cid)
            gates["campaign_identity"] = True
        except ValueError:
            gates["campaign_identity"] = False
        a = _landing(c)
        conversion = c.get("conversion_plan") or {}
        attribution = c.get("attribution_plan") or {}
        claim_review = c.get("claim_review") or {}
        product = c.get("product_code")
        expected_cta = ("Discuss product fit" if product == "managed_service"
                        else "Enquire about the research")
        gates.update({
            "ready_stage": c.get("current_stage") == "READY_FOR_OWNED_ACTIVATION",
            "execution_authority_none": c.get("execution_authority") == "none",
            "internal_account_only": c.get("account_label") == "Empire AI"
                and not c.get("tenant_scope", {}).get("customer_access_authorized"),
            "opportunity_provenance": bool(c.get("opportunity_key")
                and c.get("opportunity_evidence_refs")),
            "usable_draft": bool(a.get("h1") and a.get("thesis")
                and a.get("asset_id") == f"{cid}:landing"
                and a.get("campaign_id") == cid),
            "claim_scope": (c.get("owned_publication_review") or {}).get("claim_verification_result", {}).get("status") == "PASS",
            "public_owner_scope": public_owner_scope(c)["status"] == "PUBLIC_OWNER_SCOPE_RESOLVED",
            "privacy_notice": a.get("privacy_notice") == PRIVACY,
            "no_outbound": c.get("outbound_authorized", False) is False
                and c.get("automatic_followup", False) is False,
            "conversion_objective": bool(conversion.get("conversion_objective")),
            "product_and_cta": product in (None, "managed_service")
                and conversion.get("primary_cta") == expected_cta
                and a.get("cta") == expected_cta
                and (bool(c.get("product_id") and c.get("product_evidence_refs"))
                     if product == "managed_service" else (
                    c.get("product_id") is None and not a.get("product_refs")
                    and c.get("campaign_objective") == "research_enquiry")),
            "event_contract": EVENT_FIELDS.issubset(set(
                attribution.get("event_contract", {}).get("required", [])))
                and attribution.get("campaign_id") == cid
                and a.get("asset_id") in attribution.get("asset_ids", [])
                and attribution.get("source") == "owned_site"
                and attribution.get("medium") == "organic",
            "unique_metadata": bool(a.get("seo_title") and a.get("meta_description"))
                and sum(_landing(other).get("seo_title") == a.get("seo_title")
                        for other in campaigns) == 1
                and sum(_landing(other).get("meta_description") == a.get("meta_description")
                        for other in campaigns) == 1,
            "stable_route": conversion.get("landing_path") == f"/research/{cid}",
            "zero_paid_spend": c.get("paid_media_spend_cents") == 0,
        })
        review = c.get("owned_publication_review") or {}
        try:
            html_digest = hashlib.sha256(render_asset(a).encode()).hexdigest()
        except (KeyError, TypeError, ValueError):
            html_digest = None
        gates["useful_content_review"] = (
            review.get("status") == "PASS" and html_digest is not None
            and review.get("campaign_id") == cid
            and review.get("asset_id") == a.get("asset_id")
            and review.get("asset_sha256") == html_digest
            and review.get("asset_contract_sha256") == digest(a)
            and review.get("claim_inventory") == a.get("claims")
            and review.get("evidence_refs") == a.get("evidence_refs")
            and bool(review.get("evidence_refs"))
            and review.get("independent_visitor_value") is True
            and review.get("limitations_present") is True
            and review.get("privacy_surface_present") is True
            and sections[digest(a.get("sections"))] == 1
        )
        for key in INFRASTRUCTURE_GATES:
            evidence = infrastructure.get(key) or {}
            gates[key] = evidence.get("status") == "PASS" and bool(evidence.get("evidence_refs"))
        blockers = [name for name, passed in gates.items() if not passed]
        results.append({
            "campaign_id": cid, "current_stage": c.get("current_stage"),
            "preflight_status": "BLOCKED" if blockers else "PASS",
            "gates": gates, "blockers": blockers,
            "asset_sha256": digest(a),
            "repeated_landing_sections": sections[digest(a.get("sections"))] > 1,
            "public_route": f"https://empire-ai.co.uk/research/{cid}" if gates["campaign_identity"] else None,
            "primary_cta": expected_cta,
            "account_label": c.get("account_label"),
            "account_id": c.get("account_id"), "tenant_id": c.get("tenant_id"),
            "prediction_status": c.get("predictive_revenue_status"),
        })
    return {
        "schema_version": "empire.owned_campaign_preflight.v2",
        "canonical_campaigns_sha256": digest(campaigns),
        "campaigns_requested": len(results),
        "campaigns_preflight_passed": sum(r["preflight_status"] == "PASS" for r in results),
        "campaigns_blocked": sum(r["preflight_status"] == "BLOCKED" for r in results),
        "campaigns": results, "infrastructure_review": deepcopy(infrastructure),
        "required_events": list(REQUIRED_EVENTS),
        "execution_authority": "none", "campaign_state_mutated": False,
        "publication_performed": False,
    }
