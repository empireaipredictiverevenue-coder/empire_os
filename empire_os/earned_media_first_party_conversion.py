"""Original owned guide -> existing consented commercial enquiry, read-only.

Inspects staged code + editorial owner evidence. Never treats a browser entry
hint as a session, published article, search click, actual enquiry or settlement.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Mapping

from empire_os.earned_media_advisory_bridge import _json, _read, SourceHeld

SCHEMA = "empire.earned_media.first_party_conversion_review.v1"
ARTICLE_BRIEF = "docs/marketing/GROWTH_001_AI_READINESS_ARTICLE_BRIEF_20261016.json"
ARTICLE_DRAFT = "docs/marketing/GROWTH_001_AI_READINESS_ARTICLE_DRAFT_20261016.md"
PAGE = "apps/empire-public-site/src/app/predictive-revenue/page.tsx"
GUIDE = "apps/empire-public-site/src/components/SaaSRevenueLeakageGuide.tsx"
FRONT_ALLOWLIST = "apps/empire-public-site/src/lib/commercial-entry-review.ts"
BACK_ALLOWLIST = "empire_os/first_party_sales_interest.py"
COMMERCIAL_PAGE = "apps/empire-public-site/src/app/commercial/page.tsx"
EXPECTED_PATHS = frozenset((
    "/", "/commercial", "/predictive-revenue",
    "/industries/roofing", "/industries/solar",
    "/industries/hvac", "/industries/property",
))
ENTRY = "/predictive-revenue"
CTA = "/commercial?entry=%2Fpredictive-revenue#commercial-enquiry"


def _reviewed_browser_paths(raw: str) -> set[str]:
    m = re.search(
        r'const REVIEWED_ENTRY_PATHS = new Set\(\[(.*?)\]\);',
        raw, flags=re.DOTALL,
    )
    if not m:
        raise ValueError("BROWSER_ENTRY_ALLOWLIST_NOT_PRESENT")
    values = json.loads("[" + m.group(1).strip().rstrip(",") + "]")
    if (not isinstance(values, list) or not values
            or any(not isinstance(v, str) for v in values)
            or len(values) != len(set(values))):
        raise ValueError("BROWSER_ENTRY_ALLOWLIST_INVALID")
    return set(values)


def _reviewed_backend_paths(raw: str) -> set[str]:
    tree = ast.parse(raw)
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name)
                        and target.id == "REVIEWED_ENTRY_PATHS"
                        for target in node.targets)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "frozenset"
                and len(node.value.args) == 1):
            parsed = ast.literal_eval(node.value.args[0])
            if isinstance(parsed, set) and all(isinstance(v, str) for v in parsed):
                return parsed
    raise ValueError("BACKEND_ENTRY_ALLOWLIST_NOT_PRESENT")


def _held(reason: str, sources: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "execution_authority": "none",
        "state": "HELD_SOURCE_OR_CONSENT_CONTRACT", "reason_code": reason,
        "sources": dict(sources or {}), "reviewed_entry_page": None,
        "proposed_cta": None, "owned_guide_state": "UNVERIFIED",
        "article_publication_state": "NOT_AUTHORIZED",
        "source_code_readiness": False, "founder_site_release_authorized": False,
        "source_click_verified": False, "consented_enquiry_verified": False,
        "actual_client_acceptance_verified": False, "realised_revenue_verified": False,
        "attributable_enquiries": None, "attributable_revenue": None,
        "smart_crm_reads": False, "smart_crm_writes": False,
        "message_sent": False, "publication_executed": False,
        "payment_executed": False,
    }


def review_owned_guide_enquiry(
    packet: Mapping[str, Any], *, repo_root: str | Path,
) -> dict[str, Any]:
    if (packet.get("schema_version") != "empire.earned_media_advisory.review.v1"
            or packet.get("mode") != "OBSERVE"
            or packet.get("execution_authority") != "none"
            or packet.get("smart_crm_writes") is not False
            or packet.get("publication_authorized") is not False
            or packet.get("new_outbound_authorized") is not False):
        return _held("EARNED_MEDIA_REVIEW_PACKET_INVALID")
    sources = packet.get("sources")
    if (not isinstance(sources, Mapping)
            or not isinstance(sources.get("owned_article"), Mapping)
            or sources["owned_article"].get("state") != "EVIDENCE_FILE_READ"):
        return _held("ORIGINAL_ARTICLE_NOT_VERIFIED")
    root = Path(repo_root)
    refs = (
        ARTICLE_BRIEF, ARTICLE_DRAFT,
        PAGE, GUIDE, FRONT_ALLOWLIST, BACK_ALLOWLIST, COMMERCIAL_PAGE,
    )
    data: dict[str, bytes] = {}
    hashes: dict[str, dict[str, str]] = {}
    try:
        for relative in refs:
            data[relative], digest = _read(root, relative, max_bytes=145000)
            hashes[relative] = {"sha256": digest, "state": "STAGED_CODE_OR_DRAFT_READ"}
        brief = json.loads(data[ARTICLE_BRIEF])
        if not isinstance(brief, dict):
            raise ValueError("INVALID_ARTICLE_BRIEF")
        front = data[FRONT_ALLOWLIST].decode("utf-8")
        back = data[BACK_ALLOWLIST].decode("utf-8")
        paths = _reviewed_browser_paths(front)
        if paths != EXPECTED_PATHS or _reviewed_backend_paths(back) != paths:
            return _held("BROWSER_BACKEND_ENTRY_ALLOWLIST_DRIFT", hashes)
    except (OSError, SourceHeld, UnicodeError, ValueError, SyntaxError,
            TypeError, json.JSONDecodeError):
        return _held("MISSING_OR_UNSAFE_SOURCE_ARTIFACT", hashes)

    try:
        content = {k: data[k].decode("utf-8") for k in refs}
    except UnicodeError:
        return _held("SOURCE_TEXT_INVALID_ENCODING", hashes)
    if (sources["owned_article"].get("sha256") != hashes[ARTICLE_DRAFT]["sha256"]
            or brief.get("status") != "DRAFT_ONLY"
            or brief.get("publication_authorized") is not False
            or brief.get("new_page_proposal_authorized") is not False
            or brief.get("intended_live_route") != "https://empire-ai.co.uk/commercial"
            or "INTERNAL EDITORIAL NOTES — NOT PUBLIC COPY" not in content[ARTICLE_DRAFT]):
        return _held("ARTICLE_DRAFT_PUBLICATION_AUTHORITY_UNVERIFIED", hashes)
    if (not all(token in content[PAGE] for token in (
                    "SaaSRevenueLeakageGuide", "<SaaSRevenueLeakageGuide />"))
            or "export default function SaaSRevenueLeakageGuide" not in content[GUIDE]
            or 'href={ownedRevenueGuideProposalHref()}' not in content[GUIDE]
            or 'import { ownedRevenueGuideProposalHref }' not in content[GUIDE]
            or 'return "/commercial?entry=" + encodeURIComponent(path) + "#commercial-enquiry"' not in front
            or 'const path = "/predictive-revenue"' not in front
            or "function claimedEntryForReview" not in front
            or 'claimed_entry_page: claimedEntryForReview(window.location.search)' not in content[COMMERCIAL_PAGE]
            or 'result?.decision === "commercial_enquiry_recorded"' not in content[COMMERCIAL_PAGE]
            or 'contact_consent: consent' not in content[COMMERCIAL_PAGE]
            or 'reuseCommercialInterestAttempt(' not in content[COMMERCIAL_PAGE]
            or '"/v1/checkout/commercial/interests"' not in content[COMMERCIAL_PAGE]
            or '"source": "UNVERIFIED_BROWSER_SUBMITTED"' not in back
            or '"organic_search_attributed": False' not in back
            or 'if contact_consent is not True:' not in back):
        return _held("OWNED_GUIDE_OR_CONSENT_CAPTURE_UNVERIFIED", hashes)

    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "execution_authority": "none",
        "state": "STAGED_EXISTING_GUIDE_TO_EXISTING_INTAKE_NOT_LIVE_VERIFIED",
        "sources": hashes, "reviewed_entry_page": ENTRY,
        "proposed_cta": CTA, "offer_preselection": None,
        "entry_hint_class": "UNVERIFIED_BROWSER_SUBMITTED_PATH_ONLY",
        "owned_guide_state": "SOURCE_CODE_PRESENT_DEPLOYMENT_NOT_VERIFIED",
        "article_publication_state": "SEPARATE_AI_READINESS_ARTICLE_DRAFT_NOT_AUTHORIZED",
        "source_code_readiness": True,
        "source_click_verified": False, "source_visit_verified": False,
        "consented_enquiry_verified": False,
        "public_page_deployment_verified": False,
        "founder_site_release_authorized": False,
        "original_article_publication_authorized": False,
        "unimplemented_insights_route_used": False,
        "source_attribution_kind": "BROWSER_HINT_NOT_ANALYTICS_OR_REFERRER",
        "ready_for_release": False,
        "review_step": (
            "ASTRA website owner to review source-only CTA and original "
            "article independently; test actual production ingress/consent "
            "before any measurement or publication"
        ),
        "revenue_gates": (
            "REAL_CONSENTED_ENQUIRY_NOT_READ",
            "CANONICAL_TENANT_PROSPECT_IDENTITY_NOT_RECONCILED",
            "ACCEPTED_TERMS_AND_SCOPE_NOT_VERIFIED",
            "BANK_SETTLED_REVENUE_NOT_QUERIED",
        ),
        "attributable_enquiries": None, "attributable_revenue": None,
        "actual_client_acceptance_verified": False, "realised_revenue_verified": False,
        "smart_crm_reads": False, "smart_crm_writes": False,
        "message_sent": False, "publication_executed": False,
        "payment_executed": False,
    }
