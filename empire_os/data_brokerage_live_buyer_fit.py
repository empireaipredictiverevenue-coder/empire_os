"""Bounded first-party qualification of existing brokerage buyer hypotheses.

No contacts, logins, form submissions, CRM writes or vendor spend. Uses the
original Search Fabric public-site fetch, not another search platform.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
import os
import stat
import json
from typing import Any, Callable
from urllib.parse import urlsplit
import re

from bs4 import BeautifulSoup

from empire_os.data_brokerage_prospect_queue import (
    build_brokerage_prospect_queue, validate_prospect_queue,
)
from empire_os.search_fabric.site_probe import _fetch, _public_url_allowed

SCHEMA = "empire.data_brokerage.first_party_buyer_fit.v1"
ORIGINAL_PRODUCT = "founder_original_intelligence_reports"
NON_BUYER_STATES = frozenset({
    "PUBLIC_PUBLISHER_NETWORK", "HOME_SERVICES_MARKETING_AGENCY",
    "B2B_APPOINTMENT_AGENCY", "LEAD_SELLER_TO_CONTRACTORS",
    "INBOUND_CALL_MARKETPLACE", "CONTENT_PUBLISHER",
    "PUBLISHER_SEO_AGENCY", "OTHER_OR_NOT_DETERMINED",
    "SOURCE_FETCH_FAILED", "INSUFFICIENT_SITE_EVIDENCE",
})
RESEARCH_IDEAS = {
    "PUBLIC_PUBLISHER_NETWORK": "PUBLISHER_PROGRAMME_BENCHMARK_HYPOTHESIS",
    "HOME_SERVICES_MARKETING_AGENCY": "CONTRACTOR_COMPETITOR_BENCHMARK_HYPOTHESIS",
    "B2B_APPOINTMENT_AGENCY": "OUTSIDE_CURRENT_HOME_SERVICES_REPORT_SCOPE",
    "LEAD_SELLER_TO_CONTRACTORS": "BUYER_OF_LEADS_NOT_RESEARCH_ORDER",
    "INBOUND_CALL_MARKETPLACE": "SUPPLY_MARKETPLACE_NOT_RESEARCH_ORDER",
    "CONTENT_PUBLISHER": "CONTENT_PUBLISHER_NOT_AGENCY_MARKET_BUYER",
    "PUBLISHER_SEO_AGENCY": "SEO_SERVICE_NOT_AFFILIATE_PUBLISHER_NETWORK",
    "OTHER_OR_NOT_DETERMINED": "HOLD_INSUFFICIENT_PURCHASE_EVIDENCE",
    "SOURCE_FETCH_FAILED": "HOLD_NEW_SOURCE_NOT_VERIFIED",
    "INSUFFICIENT_SITE_EVIDENCE": "HOLD_PAGE_INTENT_NOT_READABLE",
}


def classify_first_party_purpose(title: str, description: str, body: str) -> str:
    """Title and short description dominate, avoiding navigation keyword drift."""
    heading = (title + " " + description).casefold()[:1100]
    text = body.casefold()[:5500]
    if re.search(r"publisher seo|seo for publishers|seo for newsrooms", heading):
        return "PUBLISHER_SEO_AGENCY"
    if re.search(r"b2b appointment setting|b2b lead generation agency|b2b appointment", heading):
        return "B2B_APPOINTMENT_AGENCY"
    if (re.search(r"home.*living|inspired home|home.*design ideas", heading)
            and not re.search(r"leads|pay per call|marketing agency", heading)):
        return "CONTENT_PUBLISHER"
    if (re.search(r"buy and sell inbound calls|pay.per.call marketplace|inbound call marketplace", heading)
            or ("marketplace" in heading and "calls" in heading)):
        return "INBOUND_CALL_MARKETPLACE"
    if (re.search(r"affiliate network|for affiliates|affiliate contact|pay per call.*affiliate", heading)
            and re.search(r"pay.per.call|calls|publishers|affiliate", text + " " + heading)):
        return "PUBLIC_PUBLISHER_NETWORK"
    if (re.search(r"join our (?:partner|publisher|affiliate) network|apply as publisher|apply as an affiliate|apply to become a .*publisher partner", text)
            and re.search(r"calls|traffic|performance|lead", heading + " " + text)):
        return "PUBLIC_PUBLISHER_NETWORK"
    if ("publisher" in heading and "publisher partner" in text
            and any(term in text for term in ("campaign", "payout", "get paid", "traffic"))):
        return "PUBLIC_PUBLISHER_NETWORK"
    if re.search(r"contractor marketing|local seo|google ads|marketing for roofers|google seo.*facebook ads", heading):
        return "HOME_SERVICES_MARKETING_AGENCY"
    if re.search(r"buy (?:solar|hvac|roofing|exclusive|home service) leads|lead.*for.*installers|pay per qualified call|exclusive (?:inbound|home service) leads", heading):
        return "LEAD_SELLER_TO_CONTRACTORS"
    if re.search(r"lead generation|contractor.*leads", heading):
        return "HOME_SERVICES_MARKETING_AGENCY"
    return "OTHER_OR_NOT_DETERMINED"


def _extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html[:1_000_000], "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    return " ".join(main.stripped_strings)[:12_000]


def _fetch_first_party(url: str) -> Any:
    import requests
    with requests.Session() as session:
        return _fetch(session, url, timeout=5.0, public_only=True)


def classify_existing_brokerage_buyers(
    root: Path, *, now: datetime, fetch: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """One bounded source check of every research-only, uncontacted prospect."""
    if now.utcoffset() is None:
        raise ValueError("UTC_AWARE_BROKERAGE_AUDIT_REQUIRED")
    queue = build_brokerage_prospect_queue(root, now=now, limit=40)
    if not validate_prospect_queue(queue):
        raise ValueError("ORIGINAL_BUYER_OWNER_PROSPECTS_UNVERIFIED")
    if queue.get("status") != "ORIGINAL_SOURCE_PROSPECTS_RECOVERED":
        return {
            "schema_version": SCHEMA,
            "status": "ORIGINAL_PROSPECT_OWNER_NOT_CURRENT",
            "evaluated_at": now.astimezone(timezone.utc).isoformat(),
            "classification": [], "total_organisations": 0,
            "source_requests": 0,
            "research_purchase_requests_verified": 0,
            "outbound_authorized": False, "crm_writes": False,
            "revenue_verified": False, "execution_authority": "none",
        }
    selected = queue["ranked_research_prospects"]
    request = fetch or _fetch_first_party

    def inspect(row: Mapping[str, Any]) -> dict[str, Any]:
        domain = row["domain"]
        url = row["source_first_party_page"]
        record = {
            "domain": domain,
            "original_first_party_url": url,
            "canonical_buyer_contact_state": row["canonical_buyer_owner_contact_state"],
            "original_buyer_next_action": row["original_buyer_team_next_action"],
            "original_product": ORIGINAL_PRODUCT,
            "first_party_observed_at": now.astimezone(timezone.utc).isoformat(),
            "source_fetch_succeeded": False,
            "source_content_sha256": None,
            "first_party_purpose": "SOURCE_FETCH_FAILED",
            "research_product_idea": RESEARCH_IDEAS["SOURCE_FETCH_FAILED"],
            "direct_report_purchase_request_verified": False,
            "specific_research_budget_verified": False,
            "customer_delivery_approved": False,
            "previous_outbound_suppression_preserved": True,
            "contact_authorized": False,
        }
        if not _public_url_allowed(url):
            return record
        try:
            document = request(url)
            if document is None:
                return record
            final = str(getattr(document, "url", "") or "")
            parsed = urlsplit(final)
            if (parsed.scheme != "https"
                    or (parsed.hostname or "").lower() not in {domain, "www."+domain}):
                return record
            raw = str(getattr(document, "text", "") or "")
            if len(raw) < 120 or len(raw) > 2_000_000:
                return record
            title = str(getattr(document, "title", "") or "")[:190]
            desc = str(getattr(document, "description", "") or "")[:300]
            body = _extract_main_text(raw)
            if len(body) < 90 and len(title+" "+desc) < 90:
                purpose = "INSUFFICIENT_SITE_EVIDENCE"
            else:
                purpose = classify_first_party_purpose(title, desc, body)
            record.update({
                "source_fetch_succeeded": True,
                "source_content_sha256": sha256(raw.encode("utf-8")).hexdigest(),
                "first_party_final_url": final[:400],
                "first_party_page_title": title,
                "first_party_page_description": desc,
                "first_party_purpose": purpose,
                "research_product_idea": RESEARCH_IDEAS[purpose],
            })
        except (OSError, ValueError, TypeError, TimeoutError):
            pass
        return record

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(inspect, selected))
    counts = dict(sorted(Counter(row["first_party_purpose"] for row in results).items()))
    return {
        "schema_version": SCHEMA,
        "status": "FIRST_PARTY_COMMERCIAL_PURPOSES_REVIEWED",
        "evaluated_at": now.astimezone(timezone.utc).isoformat(),
        "original_prospect_source_hash": queue["source_sha256"],
        "total_organisations": len(results),
        "source_requests": len(results),
        "roles": counts,
        "classification": results,
        "research_purchase_requests_verified": 0,
        "marketing_uses_not_purchase_requests": True,
        "outbound_authorized": False, "crm_writes": False,
        "revenue_verified": False, "execution_authority": "none",
    }


def validate_brokerage_first_party_roles(obj: Any) -> bool:
    if not isinstance(obj, Mapping) or obj.get("schema_version") != SCHEMA:
        return False
    if (obj.get("research_purchase_requests_verified") != 0
            or obj.get("outbound_authorized") is not False
            or obj.get("crm_writes") is not False
            or obj.get("revenue_verified") is not False
            or obj.get("execution_authority") != "none"):
        return False
    if obj.get("status") != "FIRST_PARTY_COMMERCIAL_PURPOSES_REVIEWED":
        return obj.get("status") == "ORIGINAL_PROSPECT_OWNER_NOT_CURRENT" and obj.get("classification") == []
    entries = obj.get("classification")
    if (not isinstance(entries, list) or not 0 < len(entries) <= 40
            or obj.get("total_organisations") != len(entries)
            or obj.get("source_requests") != len(entries)
            or obj.get("marketing_uses_not_purchase_requests") is not True):
        return False
    actual = Counter()
    seen = set()
    for row in entries:
        if not isinstance(row, Mapping):
            return False
        dom, status = row.get("domain"), row.get("first_party_purpose")
        if (not isinstance(dom, str) or dom in seen
                or status not in NON_BUYER_STATES
                or row.get("research_product_idea") != RESEARCH_IDEAS[status]
                or row.get("canonical_buyer_contact_state") != "DISCOVERED_NO_CONFIRMED_CONTACT"
                or row.get("direct_report_purchase_request_verified") is not False
                or row.get("specific_research_budget_verified") is not False
                or row.get("customer_delivery_approved") is not False
                or row.get("contact_authorized") is not False
                or row.get("previous_outbound_suppression_preserved") is not True):
            return False
        seen.add(dom)
        actual[status] += 1
    if dict(sorted(actual.items())) != obj.get("roles"):
        return False
    for row in entries:
        source = row.get("source_content_sha256")
        if row.get("source_fetch_succeeded") is True:
            if (not isinstance(source, str)
                    or not re.fullmatch(r"[a-f0-9]{64}", source)
                    or row.get("first_party_purpose") == "SOURCE_FETCH_FAILED"):
                return False
        elif row.get("source_fetch_succeeded") is False:
            if row.get("first_party_purpose") != "SOURCE_FETCH_FAILED" or source is not None:
                return False
        else:
            return False
    return True


PRIVATE_EVIDENCE = Path("runtime/data_brokerage/first_party_buyer_fit_latest.json")


def persist_first_party_fit(root: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    """Persist one original-owner-only, derived, source-linked evidence receipt."""
    if not validate_brokerage_first_party_roles(report):
        raise ValueError("UNTRUSTED_BROKERAGE_FIRST_PARTY_BUYER_FIT")
    target = root / PRIVATE_EVIDENCE
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError("PRIVATE_EVIDENCE_SYMLINK_REFUSED")
    data = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if len(data) > 55_000:
        raise ValueError("FIRST_PARTY_BUYER_FIT_OUTPUT_NOT_BOUNDED")
    digest = sha256(data).hexdigest()
    with NamedTemporaryFile(dir=target.parent, prefix=".firstparty-buyer-", delete=False) as handle:
        temp = Path(handle.name)
        try:
            os.chmod(temp, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, target)
    if target.is_symlink() or stat.S_IMODE(target.stat().st_mode) != 0o600:
        raise ValueError("BROKERAGE_BUYER_FIT_PRIVATE_FILE_MODE_HOLD")
    if sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("BROKERAGE_BUYER_FIT_READBACK_INTEGRITY_HOLD")
    return {
        "status": report["status"],
        "verified_private_receipt": str(PRIVATE_EVIDENCE),
        "verified_report_sha256": digest,
        "first_party_organisations_checked": report["total_organisations"],
        "first_party_role_counts": report.get("roles", {}),
        "intelligence_purchase_requests_verified": 0,
        "customer_delivery_authorized": False,
        "crm_writes": False,
        "contact_authorized": False,
    }


def validate_first_party_fit_summary(obj: Any) -> bool:
    if not isinstance(obj, Mapping):
        return False
    if (obj.get("status") != "FIRST_PARTY_COMMERCIAL_PURPOSES_REVIEWED"
            or obj.get("verified_private_receipt") != str(PRIVATE_EVIDENCE)
            or not isinstance(obj.get("verified_report_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", obj["verified_report_sha256"])
            or type(obj.get("first_party_organisations_checked")) is not int
            or not 1 <= obj["first_party_organisations_checked"] <= 40
            or not isinstance(obj.get("first_party_role_counts"), Mapping)
            or sum(obj["first_party_role_counts"].values()) != obj["first_party_organisations_checked"]
            or any(k not in NON_BUYER_STATES or type(v) is not int or v < 0
                   for k,v in obj["first_party_role_counts"].items())
            or obj.get("intelligence_purchase_requests_verified") != 0
            or obj.get("customer_delivery_authorized") is not False
            or obj.get("crm_writes") is not False
            or obj.get("contact_authorized") is not False):
        return False
    return True
