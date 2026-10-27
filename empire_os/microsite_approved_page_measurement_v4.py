"""Post-release per-page measurement adapter.

Every source is a trusted *original owner* reader callback, not a browser claim.
This module never activates collectors, publishes pages, or reads personal rows.
Production use remains unavailable until canonical owners expose the readers.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit

from empire_os.predictive_microsite_factory import build_candidate


def _count(value: Any, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 100000000:
        raise ValueError(f"{name} count invalid")
    return value


def _owner_row(value: Any, *, source: str, cid: str, url: str, sha: str) -> Mapping[str, Any]:
    if (not isinstance(value, Mapping)
            or value.get("source_owner") != source
            or value.get("candidate_id") != cid
            or value.get("public_url") != url
            or value.get("asset_sha256") != sha
            or not isinstance(value.get("source_evidence_ref"), str)
            or not value["source_evidence_ref"].strip()):
        raise ValueError(f"{source} original release/source binding invalid")
    return value


def review_deployed_microsite(
    spec: Mapping[str, Any], *,
    original_site_owner_reader: Callable[[str], Mapping[str, Any]] | None = None,
    original_gsc_reader: Callable[[str], Mapping[str, Any]] | None = None,
    original_first_party_reader: Callable[[str], Mapping[str, Any]] | None = None,
    original_crm_reader: Callable[[str], Mapping[str, Any]] | None = None,
    original_settlement_reader: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Use only explicit evidence-backed releases, not the new factory's flags."""
    candidate, html = build_candidate(spec)
    cid, digest = candidate["id"], sha256(html.encode()).hexdigest()
    result = {
        "schema_version": "empire.microsite.per_page_verified_join.v4",
        "candidate_id": cid, "mode": "READ_ONLY",
        "state": "UNRELEASED_OR_RELEASE_NOT_PROVEN",
        "public_url": None,
        "source_asset_sha256": digest,
        "organic_search_impressions": None,
        "organic_search_clicks": None,
        "consent_verified_sessions": None,
        "consented_enquiries": None,
        "qualified_enquiries": None,
        "buyer_accepted_events": None,
        "settled_revenue_minor": None,
        "settled_currency": None,
        "attributed_revenue_verified": False,
        "source_receipts": {},
        "execution_authority": "none", "no_publishing": True,
    }
    if original_site_owner_reader is None:
        return result
    release = original_site_owner_reader(cid)
    if release is None:
        return result
    if not isinstance(release, Mapping) or release.get("status") != "ORIGINAL_OWNER_DEPLOYMENT_READBACK_VERIFIED":
        raise ValueError("unverified site-owner deployment")
    url = release.get("public_url")
    if not isinstance(url, str):
        raise ValueError("site owner URL missing")
    loc = urlsplit(url)
    if (loc.scheme != "https" or loc.hostname != "empire-ai.co.uk"
            or loc.username or loc.password or loc.query or loc.fragment
            or not loc.path.startswith("/research/")):
        raise ValueError("unapproved owned-route origin")
    _owner_row(release, source="original_empire_website_owner", cid=cid, url=url, sha=digest)
    result["state"] = "OWNER_DEPLOYMENT_VERIFIED_MEASUREMENT_PENDING"
    result["public_url"] = url
    result["source_receipts"]["site_owner"] = release["source_evidence_ref"]

    def source_row(reader, owner):
        if reader is None:
            return None
        row = reader(url)
        if row is None:
            return None
        return _owner_row(row, source=owner, cid=cid, url=url, sha=digest)

    gsc = source_row(original_gsc_reader, "original_seo_first_party_gsc")
    if gsc is not None:
        if (gsc.get("dimension") != "page"
                or gsc.get("status") != "MEASURED_PAGE_METRICS"):
            raise ValueError("GSC not exact page-measured")
        impressions = _count(gsc.get("impressions"), "impressions")
        clicks = _count(gsc.get("clicks"), "clicks")
        if clicks > impressions:
            raise ValueError("GSC impossible click count")
        result["organic_search_impressions"] = impressions
        result["organic_search_clicks"] = clicks
        result["source_receipts"]["gsc"] = gsc["source_evidence_ref"]

    events = source_row(original_first_party_reader, "original_website_consent_and_event_owner")
    if events is not None:
        if (events.get("lawful_website_analytics_consent_verified") is not True
                or events.get("server_side_event_collection_verified") is not True):
            raise ValueError("first-party event admission not verified")
        result["consent_verified_sessions"] = _count(events.get("sessions"), "sessions")
        result["source_receipts"]["events"] = events["source_evidence_ref"]

    crm = source_row(original_crm_reader, "original_empire_crm_owner")
    if crm is not None:
        if (crm.get("source_to_enquiry_identity_join_verified") is not True
                or crm.get("consent_and_suppression_verified") is not True):
            raise ValueError("CRM source/consent join missing")
        enquiries = _count(crm.get("consented_enquiries"), "consented enquiries")
        qualified = _count(crm.get("qualified_enquiries"), "qualified enquiries")
        accepted = _count(crm.get("buyer_accepted_events"), "buyer accepted events")
        if not accepted <= qualified <= enquiries:
            raise ValueError("CRM canonical lifecycle counts inconsistent")
        result.update(
            consented_enquiries=enquiries, qualified_enquiries=qualified,
            buyer_accepted_events=accepted)
        result["source_receipts"]["crm"] = crm["source_evidence_ref"]

    settled = source_row(original_settlement_reader, "original_empire_verified_settlement_owner")
    if settled is not None:
        if (crm is None or result["buyer_accepted_events"] is None
                or settled.get("original_accepted_event_to_settlement_join_verified") is not True
                or settled.get("cash_settled_independently_verified") is not True):
            raise ValueError("settlement not joined to accepted original event")
        minor = _count(settled.get("settled_revenue_minor"), "settled revenue minor")
        if minor > 0 and result["buyer_accepted_events"] == 0:
            raise ValueError("positive settlement with no accepted original event")
        if settled.get("currency") not in ("GBP", "USD"):
            raise ValueError("settlement currency not verified")
        result.update(
            settled_revenue_minor=minor,
            settled_currency=settled["currency"],
            attributed_revenue_verified=True)
        result["source_receipts"]["settlement"] = settled["source_evidence_ref"]

    return result
