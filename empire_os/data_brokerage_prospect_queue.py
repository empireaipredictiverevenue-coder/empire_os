"""Original-owner, data-driven brokerage prospect discovery (NOT a CRM promotion).

Recover research prospects suppressed by the former four-advert-only search
strategy. Derive only non-personal public organization evidence from the
already operating Source Intelligence / website verifier / relationship
registry. No new scraping, contact, paid provider, publication or new daemon.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from hashlib import sha256
from collections import Counter
from collections.abc import Mapping
from typing import Any
import json
import re

SCHEMA = "empire.data_brokerage.dynamic_prospect_queue.v1"
QUALIFIED = Path("runtime/data_brokerage/qualified_domain_intelligence_latest.json")
VERIFIED_SITES = Path("runtime/buyer_network_intelligence/direct_site_verification_latest.json")
REGISTRY = Path("runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
BUYER_OWNER = Path("runtime/buyer_network_intelligence/founder_qualification_actions_latest.json")
RELEVANT = frozenset({"roofing", "hvac", "home_services", "solar", "restoration"})
PUBLIC_EMAILS_EXCLUDED = True


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, str) or len(v) > 70:
        return None
    try:
        out = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return out.astimezone(timezone.utc) if out.utcoffset() is not None else None
    except (ValueError, OverflowError, TypeError):
        return None


def _read(root: Path, path: Path, limit: int) -> tuple[dict[str, Any], str] | None:
    f = root / path
    try:
        if f.is_symlink() or not f.is_file() or not 0 < f.stat().st_size <= limit:
            return None
        raw = f.read_bytes()
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return None
        return obj, sha256(raw).hexdigest()
    except (ValueError, OSError, TypeError, UnicodeError):
        return None


def _public_page(page: Any, domain: str) -> str | None:
    if not isinstance(page, Mapping) or page.get("status") != "PASS" or page.get("http_status") != 200:
        return None
    url = page.get("url")
    if not isinstance(url, str) or len(url) > 410:
        return None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.hostname.lower() not in {domain, "www."+domain}
                or parsed.username or parsed.password or parsed.port not in (None,443)):
            return None
        return parsed._replace(query="", fragment="").geturl()
    except ValueError:
        return None


def build_brokerage_prospect_queue(root: Path, *, now: datetime, limit: int = 25) -> dict[str, Any]:
    """Returns all-stage counts, and top evidence-backed orgs for research.

    Critical distinction: research prospects are useful search RESULTS;
    they are not genuine paying customers or permission to send messages.
    """
    if now.utcoffset() is None or type(limit) is not int or not 1 <= limit <= 40:
        raise ValueError("INVALID_BROKERAGE_PROSPECT_QUERY")
    clock = now.astimezone(timezone.utc)
    sources = (_read(root, QUALIFIED, 2_000_000),
               _read(root, VERIFIED_SITES, 3_000_000),
               _read(root, REGISTRY, 2_000_000),
               _read(root, BUYER_OWNER, 3_000_000))
    if not all(sources):
        return _hold("SOURCE_OWNER_READBACK_UNAVAILABLE")
    (qualified, q_hash), (site, s_hash), (registry, r_hash), (buyer_owner, b_hash) = sources
    qrows, srows, relationships = (qualified.get("records"),
                                  site.get("results"), registry.get("relationships"))
    buyer_targets = buyer_owner.get("targets")
    if (qualified.get("schema_version") != "empire.data_brokerage.domain_qualification.v1"
            or qualified.get("contracts_or_revenue_verified") is not False
            or qualified.get("source_rights_represented_as_verified") is not False
            or site.get("schema_version") != "buyer-direct-site-verification-v1"
            or site.get("authority") != "OBSERVE"
            or registry.get("schema_version") != "empire.commercial_relationship_registry.v1"
            or registry.get("mode") != "OBSERVE"
            or registry.get("outbound_authorized") is not False
            or registry.get("execution_authority") not in ("NONE", "none")
            or buyer_owner.get("schema_version") != "empire.buyer_qualification_actions.v1"
            or buyer_owner.get("mode") != "OBSERVE"
            or buyer_owner.get("execution_authority") not in ("NONE", "none")
            or buyer_owner.get("outbound_enabled") is not False
            or buyer_owner.get("outbound_sent") is not False
            or not isinstance(buyer_targets, list) or len(buyer_targets) > 3000
            or not isinstance(qrows, list) or len(qrows) > 1800
            or not isinstance(srows, list) or len(srows) > 7000
            or not isinstance(relationships, list) or len(relationships) > 2500):
        return _hold("ORIGINAL_OWNER_RESEARCH_CONTRACT_INVALID")
    timestamps = [_utc(qualified.get("generated_at_utc")),
                  _utc(site.get("generated_at")),
                  _utc(registry.get("generated_at")),
                  _utc(buyer_owner.get("generated_at"))]
    if any(t is None or not timedelta(0) <= clock-t <= timedelta(days=7) for t in timestamps):
        return _hold("ORIGINAL_OWNER_SNAPSHOT_NOT_CURRENT")
    governance = site.get("governance")
    if not isinstance(governance, Mapping) or any(
        governance.get(k) is not False for k in
        ("commercial_terms","db_write","forms","funds","logins","outbound","traffic_activation")
    ):
        return _hold("ORIGINAL_SITE_OWNER_ACCESS_AUTHORITY_NOT_VERIFIED")

    sites = {x.get("domain"): x for x in srows
             if isinstance(x, Mapping) and isinstance(x.get("domain"), str)}
    if len(sites) != len([x for x in srows if isinstance(x, Mapping)
                         and isinstance(x.get("domain"), str)]):
        return _hold("DUPLICATE_SITE_OWNER_IDENTITY")
    relationships_by_name = {}
    for rel in relationships:
        if not isinstance(rel, Mapping):
            continue
        company = rel.get("company")
        if isinstance(company, str):
            relationships_by_name[company.casefold()] = rel
        for identifier in (rel.get("identity_domains") or [])[:15]:
            if isinstance(identifier, str):
                relationships_by_name.setdefault(identifier.casefold(), rel)
    buyer_by_domain = {x.get("domain"): x for x in buyer_targets
                       if isinstance(x, Mapping) and isinstance(x.get("domain"), str)}
    if len(buyer_by_domain) != len([x for x in buyer_targets
                                    if isinstance(x, Mapping) and isinstance(x.get("domain"), str)]):
        return _hold("DUPLICATE_CANONICAL_BUYER_IDENTITY")
    founder_recorded = {x.get("domain", "").casefold() for x in
                        registry.get("founder_reported_external_contact_queue", [])[:120]
                        if isinstance(x, Mapping) and isinstance(x.get("domain"), str)}

    audit = Counter()
    ranked = []
    visited = set()
    for row in qrows:
        if not isinstance(row, Mapping):
            continue
        domain = row.get("domain")
        if (not isinstance(domain, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,235}", domain)
                or domain in visited):
            continue
        visited.add(domain)
        audit["total_historical_organizations"] += 1
        if row.get("site_corrob") is not True or row.get("verification_stage") != "DIRECT_SITE_CORROBORATED":
            continue
        audit["first_party_corrob"] += 1
        if row.get("role_signal_present_not_buyer_contract") is not True:
            continue
        audit["role_text_evidence"] += 1
        observed = _utc(row.get("site_observed_at"))
        site_rec = sites.get(domain)
        if (observed is None or not timedelta(0) <= clock-observed <= timedelta(days=7)
                or not isinstance(site_rec, Mapping)
                or site_rec.get("observed_at") != row.get("site_observed_at")
                or site_rec.get("corroborated") is not True):
            audit["stale_or_missing_site_proof"] += 1
            continue
        audit["fresh_verified_site"] += 1
        passed = [u for raw in site_rec.get("pages", [])[:25]
                  if (u:=_public_page(raw,domain))]
        if not passed:
            audit["no_successful_first_party_page"] += 1
            continue
        if row.get("prior_communication_observed") is True or domain in founder_recorded:
            audit["previous_communication_suppressed"] += 1
            continue
        audit["no_prior_communication_observed"] += 1
        if row.get("do_not_pursue") is True:
            audit["do_not_pursue"] += 1
            continue
        relation = relationships_by_name.get(domain)
        if relation:
            if (relation.get("last_outbound_at")
                    or relation.get("last_inbound_at")
                    or relation.get("do_not_pursue") is True
                    or relation.get("stage") not in ("RESEARCH_ONLY", None)
                    or relation.get("bounced_addresses")):
                audit["existing_contact_or_hold"] += 1
                continue
        # The original Buyer Acquisition Team owns prior-send and delivery
        # states. Brokerage registry alone is NOT sufficient suppression.
        buyer_record = buyer_by_domain.get(domain)
        if buyer_record is None:
            audit["canonical_buyer_owner_missing"] += 1
            continue
        buyer_contact_state = buyer_record.get("contact_history_state")
        if (buyer_contact_state != "DISCOVERED_NO_CONFIRMED_CONTACT"
                or buyer_record.get("commercial_next_action") in (
                    "NO_NEW_SEND_RECONCILE_SUPPRESSION_OR_DELIVERY",
                    "REVIEW_PRIOR_THREAD_FOR_RESPONSE_NO_DUPLICATE_FIRST_TOUCH"
                ) or buyer_record.get("contact_history_last_outbound_at") is not None
                or buyer_record.get("contact_history_last_inbound_at") is not None):
            audit["canonical_buyer_owner_prior_contact_or_hold"] += 1
            continue
        audit["canonical_buyer_owner_no_confirmed_contact"] += 1
        sectors = set(row.get("site_vertical_evidence") or ())
        if not sectors.intersection(RELEVANT):
            audit["not_relevant_to_current_home_services_research"] += 1
            continue
        audit["sector_evidence_match"] += 1
        if row.get("source_rights_state") != "INTERNAL_RESEARCH_HOLD":
            audit["source_rights_contract_unknown"] += 1
            continue
        site_evidence = site_rec.get("evidence")
        site_evidence = site_evidence if isinstance(site_evidence, Mapping) else {}
        has_publisher_programme = site_evidence.get("publisher_program") is True
        if has_publisher_programme:
            first_party_commercial_role = "PUBLIC_PUBLISHER_OR_AFFILIATE_PROGRAMME"
            specific_gap = "NO_DIRECT_REQUEST_TO_PURCHASE_MARKET_INTELLIGENCE"
        elif site_evidence.get("active_demand") is True:
            first_party_commercial_role = "PUBLIC_LEAD_MARKETING_OR_SERVICE_OFFER"
            specific_gap = "LEAD_SERVICE_OFFER_NOT_PROOF_OF_BUYING_RESEARCH"
        else:
            first_party_commercial_role = "PUBLIC_ROLE_NEEDS_MANUAL_QUALIFICATION"
            specific_gap = "CURRENT_DATA_BUYER_NEED_NOT_EVIDENCED"
        # A generic /partners page can conceal a concrete /publishers
        # programme. Select the most specific verified first-party page,
        # not simply the first URL that happens to contain "partner".
        best_page = (
            sorted(
                passed,
                key=lambda u: (
                    -int(any(term in u.casefold() for term in
                             ("/publishers", "/for-affiliates", "/affiliate",
                              "/publisher-programme", "/publisher-application"))),
                    -int(any(term in u.casefold() for term in
                             ("/publisher", "/partner", "/network"))),
                    u,
                ),
            )[0] if has_publisher_programme else passed[0]
        )
        score = min(98, 48+min(15,5*len(sectors.intersection(RELEVANT)))
                    +(15 if has_publisher_programme else 0)
                    +(10 if "roofing" in sectors else 0)
                    +(7 if (clock-observed).total_seconds() < 172800 else 0))
        tier = "PROGRAMME_LANDSCAPE_RESEARCH_PROSPECT" if has_publisher_programme else "SECTOR_LANDSCAPE_RESEARCH_PROSPECT"
        ranked.append({
            "domain": domain,
            "source_first_party_page": best_page,
            "original_site_observed_at": observed.isoformat(),
            "observed_industry_keywords": sorted(sectors.intersection(RELEVANT)),
            "public_publisher_programme_signal": has_publisher_programme,
            "first_party_commercial_role": first_party_commercial_role,
            "specific_buyer_research_gap": specific_gap,
            "original_buyer_team_next_action": buyer_record.get("commercial_next_action"),
            "buyers_of_leads_are_not_automatically_buyers_of_reports": True,
            "report_purchasing_need_first_party_verified": False,
            "tier": tier, "research_relevance_score_not_purchase_probability": score,
            "commercial_buying_request_verified": False,
            "customer_research_order_verified": False,
            "source_website_does_not_prove_willingness_to_pay": True,
            "existing_registry_relationship": bool(relation),
            "canonical_buyer_owner_contact_state": buyer_contact_state,
            "canonical_buyer_owner_verified_for_research_only": True,
            "prior_outbound_evidence_found": False,
            "canonical_tenant_crm_suppression_verified": False,
            "buyer_specific_report_scope_unconfirmed": True,
            "recommended_action": "REVIEW_EXISTING_ORIGINAL_AGENCY_INTELLIGENCE_FIT",
            "contact_authorized": False,
        })
    ranked.sort(key=lambda x: (-x["research_relevance_score_not_purchase_probability"],
                               not x["public_publisher_programme_signal"],
                               x["domain"]))
    audit["sourced_research_prospects"] = len(ranked)
    return {
        "schema_version": SCHEMA, "status": "ORIGINAL_SOURCE_PROSPECTS_RECOVERED",
        "evaluated_at": clock.isoformat(), "scope": "EXISTING_AGENCY_PUBLISHER_HOME_SERVICES",
        "source_sha256": {
            "original_brokerage_domains": q_hash,
            "original_first_party_verifier": s_hash,
            "existing_commercial_relationships": r_hash,
            "original_buyer_acquisition_owner": b_hash,
        },
        "input_stages": dict(audit),
        "total_research_prospects": len(ranked),
        "returned_research_prospects": min(limit, len(ranked)),
        "ranked_research_prospects": ranked[:limit],
        "buying_intent_confirmed": 0, "buyers_contacted": 0,
        "paid_buyers_verified": 0, "revenue_verified": False,
        "customer_contact_permission": False, "crm_changes": False,
        "raw_external_page_content_redistributed": False,
        "execution_authority": "none",
    }


def _hold(status: str) -> dict[str, Any]:
    return {"schema_version": SCHEMA, "status": status,
            "total_research_prospects": 0, "ranked_research_prospects": [],
            "buying_intent_confirmed": 0, "buyers_contacted": 0,
            "paid_buyers_verified": 0, "revenue_verified": False,
            "customer_contact_permission": False, "crm_changes": False,
            "raw_external_page_content_redistributed": False,
            "execution_authority": "none"}


def validate_prospect_queue(report: Any) -> bool:
    if (not isinstance(report, Mapping) or report.get("schema_version") != SCHEMA
            or report.get("buying_intent_confirmed") != 0
            or report.get("buyers_contacted") != 0
            or report.get("paid_buyers_verified") != 0
            or report.get("revenue_verified") is not False
            or report.get("customer_contact_permission") is not False
            or report.get("crm_changes") is not False
            or report.get("raw_external_page_content_redistributed") is not False
            or report.get("execution_authority") != "none"):
        return False
    if report.get("status") != "ORIGINAL_SOURCE_PROSPECTS_RECOVERED":
        return report.get("total_research_prospects") == 0 and report.get("ranked_research_prospects") == []
    if (not isinstance(report.get("input_stages"), Mapping)
            or not isinstance(report.get("source_sha256"), Mapping)
            or not isinstance(report.get("ranked_research_prospects"), list)
            or not 0 <= len(report["ranked_research_prospects"]) <= 40
            or report.get("returned_research_prospects") != len(report["ranked_research_prospects"])
            or type(report.get("total_research_prospects")) is not int
            or report["total_research_prospects"] < report["returned_research_prospects"]
            or _utc(report.get("evaluated_at")) is None
            or any(not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}",v)
                   for v in report["source_sha256"].values())):
        return False
    owner_sourced = "original_buyer_acquisition_owner" in report.get("source_sha256", {})
    seen=set()
    for item in report["ranked_research_prospects"]:
        if (not isinstance(item, Mapping)
                or not isinstance(item.get("domain"), str)
                or item["domain"] in seen
                or not isinstance(item.get("source_first_party_page"), str)
                or not item["source_first_party_page"].startswith("https://")
                or item.get("public_publisher_programme_signal") not in (True, False)
                or (owner_sourced and item.get("first_party_commercial_role") not in (
                    "PUBLIC_PUBLISHER_OR_AFFILIATE_PROGRAMME",
                    "PUBLIC_LEAD_MARKETING_OR_SERVICE_OFFER",
                    "PUBLIC_ROLE_NEEDS_MANUAL_QUALIFICATION"))
                or (owner_sourced and item.get("specific_buyer_research_gap") not in (
                    "NO_DIRECT_REQUEST_TO_PURCHASE_MARKET_INTELLIGENCE",
                    "LEAD_SERVICE_OFFER_NOT_PROOF_OF_BUYING_RESEARCH",
                    "CURRENT_DATA_BUYER_NEED_NOT_EVIDENCED"))
                or (owner_sourced and item.get("buyers_of_leads_are_not_automatically_buyers_of_reports") is not True)
                or (owner_sourced and item.get("report_purchasing_need_first_party_verified") is not False)
                or (owner_sourced and not isinstance(item.get("original_buyer_team_next_action"), str))
                or item.get("commercial_buying_request_verified") is not False
                or item.get("customer_research_order_verified") is not False
                or (owner_sourced and item.get("canonical_buyer_owner_contact_state") != "DISCOVERED_NO_CONFIRMED_CONTACT")
                or (owner_sourced and item.get("canonical_buyer_owner_verified_for_research_only") is not True)
                or item.get("buyer_specific_report_scope_unconfirmed") is not True
                or item.get("canonical_tenant_crm_suppression_verified") is not False
                or item.get("contact_authorized") is not False
                or item.get("source_website_does_not_prove_willingness_to_pay") is not True
                or item.get("tier") not in (
                    "PROGRAMME_LANDSCAPE_RESEARCH_PROSPECT",
                    "SECTOR_LANDSCAPE_RESEARCH_PROSPECT")
                or type(item.get("research_relevance_score_not_purchase_probability")) is not int
                or not 0 <= item["research_relevance_score_not_purchase_probability"] <= 98):
            return False
        seen.add(item["domain"])
    return True
