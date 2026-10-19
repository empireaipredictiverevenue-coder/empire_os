"""Optional, read-only Scout research section for the existing recovery desk.

The independently-owned deferred-enrichment queue retains all its original
priority packets. This reader NEVER admits, merges or promotes Scout research
into that canonical queue or authorizes a contact.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit, urlunsplit
from typing import Any, Mapping
from empire_os.buyer_publisher_program_evidence import (
    read_public_program_claims, PublicProgrammeHold,
)

SCHEMA = "empire.buyer_recovery_scout_observer.v1"
INPUT = Path("runtime/buyer_network_intelligence/scout_network_review_handoff_latest_20261019.json")
ALLOWED_SOURCE_FILES = {
    "scout": "runtime/buyer_acquisition/scout_latest.json",
    "registry": "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json",
    "network": "runtime/buyer_network_intelligence/candidate_queue_latest.json",
    "qualification": "runtime/buyer_network_intelligence/founder_qualification_actions_latest.json",
}
REVIEW_LANES = frozenset({
    "HELD_SOURCE_NOT_ELIGIBLE_FOR_NETWORK_ADMISSION",
    "NOT_IN_NETWORK_INDEPENDENT_RESEARCH_HANDOFF_REQUIRED",
    "NETWORK_DISCOVERY_EXISTS_QUALIFICATION_ACTION_NOT_PRESENT",
    "EXISTING_FOUNDER_QUALIFICATION_NOT_YET_PURCHASE_PROOF",
})
MAX_BYTES = 50_000
DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\.[a-z]{2,24}$")

class ScoutConsumerHold(ValueError):
    pass

def _read_source(path: Path, *, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ScoutConsumerHold("missing_source")
    meta = path.stat()
    if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= limit:
        raise ScoutConsumerHold("invalid_source_type_or_size")
    content = path.read_bytes()
    if not content or len(content) > limit:
        raise ScoutConsumerHold("invalid_source_size")
    return content

def _same_host(url: Any, domain: str) -> str | None:
    if not isinstance(url, str) or not 10 <= len(url) <= 2048:
        return None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in ("https", "http")
            or parsed.username or parsed.password or not parsed.hostname
            or parsed.hostname.lower().removeprefix("www.") != domain):
            return None
    except ValueError:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))

def _signal_url(url: Any) -> str | None:
    if url is None:
        return None
    if not isinstance(url, str) or not 10 <= len(url) <= 2048:
        raise ScoutConsumerHold("signal_url_bad_type")
    try:
        parts = urlsplit(url)
        if (parts.scheme not in ("https", "http") or
            not parts.hostname or parts.username or parts.password):
            raise ScoutConsumerHold("signal_url_untrusted")
    except ValueError as exc:
        raise ScoutConsumerHold("signal_url_malformed") from exc
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))

def read_scout_review(root: Path) -> dict[str, Any]:
    root = Path(root)
    filepath = root / INPUT
    if not filepath.exists():
        return {
            "schema_version": SCHEMA, "status": "NOT_INSTALLED",
            "review_tasks": [], "review_task_count": 0,
            "commercial_authority": "NONE",
        }
    raw = _read_source(filepath, limit=MAX_BYTES)
    if stat.S_IMODE(filepath.stat().st_mode) & 0o077:
        raise ScoutConsumerHold("source_permission_not_private")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ScoutConsumerHold("malformed_review_document") from exc
    if (not isinstance(data, Mapping)
        or data.get("schema_version") != "empire.scout_network_private_review_handoff.v1"
        or data.get("mode") != "PRIVATE_REVIEW_ONLY"
        or data.get("outbound_sent") is not False
        or data.get("db_writes") is not False
        or data.get("approved_buyer_admissions") != 0
        or data.get("crm_contacts_created") != 0
        or data.get("execution_authority") != "NONE"
        or not isinstance(data.get("source_sha256"), Mapping)
        or data.get("source_scopes") != {
            "scout_snapshot": ALLOWED_SOURCE_FILES["scout"],
            "buyer_network_discovery_snapshot": ALLOWED_SOURCE_FILES["network"],
            "founder_qualification_snapshot": ALLOWED_SOURCE_FILES["qualification"],
            "social_identity_research_snapshot": ALLOWED_SOURCE_FILES["registry"],
        }
        or not isinstance(data.get("review_tasks"), list)
        or not 0 <= len(data["review_tasks"]) <= 100
        or data.get("review_task_count") != len(data["review_tasks"])):
        raise ScoutConsumerHold("review_authority_or_schema_untrusted")
    seen = set()
    held = 0
    preview = []
    for row in data["review_tasks"]:
        if not isinstance(row, Mapping):
            raise ScoutConsumerHold("bad_review_task")
        domain = row.get("domain")
        lane = row.get("review_lane")
        if (not isinstance(domain,str) or not DOMAIN.fullmatch(domain)
            or domain in seen or lane not in REVIEW_LANES
            or row.get("outreach_authorized") is not False
            or row.get("contact_identity_promoted") is not False
            or row.get("independent_buyer_purchase_receipt_verified") is not False
            or row.get("accepting_buy_box_verified") is not False
            or row.get("payout_terms_verified") is not False
            or row.get("available_capacity_verified") is not False
            or row.get("verified_decision_maker_contact") is not False):
            raise ScoutConsumerHold("review_identity_or_buyer_gate_changed")
        seen.add(domain)
        if lane == "HELD_SOURCE_NOT_ELIGIBLE_FOR_NETWORK_ADMISSION":
            held += 1
        company_url = row.get("first_party_company_site_to_review")
        source_url = row.get("original_signal_page_review_url")
        if lane != "HELD_SOURCE_NOT_ELIGIBLE_FOR_NETWORK_ADMISSION":
            if _same_host(company_url, domain) is None:
                raise ScoutConsumerHold("review_company_source_drift")
        elif company_url is not None:
            raise ScoutConsumerHold("held_source_reintroduced")
        source_url = _signal_url(source_url)
        tasks = row.get("next_evidence_tasks")
        if (not isinstance(tasks, list) or not 1 <= len(tasks) <= 25
            or not all(isinstance(x,str) and 2 <= len(x) <= 180 for x in tasks)):
            raise ScoutConsumerHold("review_tasks_untrusted")
        preview.append({
            "company_domain": domain, "review_lane": lane,
            "first_party_website_for_research": company_url,
            "original_evidence_url": source_url,
            "next_evidence_tasks": tasks,
            "buyer_qualification_verified": False,
            "founder_outreach_authorized": False,
            "may_be_sent_to_outbound": False,
        })
    if data.get("review_held_count") != held:
        raise ScoutConsumerHold("held_count_untrusted")
    checked_digests = {}
    for key, path in ALLOWED_SOURCE_FILES.items():
        expected=data["source_sha256"].get(key)
        if not isinstance(expected,str) or not re.fullmatch(r"[a-f0-9]{64}",expected):
            raise ScoutConsumerHold("invalid_source_digest")
        actual_digest=sha256(_read_source(root / path, limit=6_000_000)).hexdigest()
        checked_digests[key]=actual_digest
        if actual_digest != expected:
            return {
                "schema_version": SCHEMA, "status": "STALE_SOURCE_REBUILD_REQUIRED",
                "review_tasks": [], "review_task_count": 0,
                "commercial_authority": "NONE",
            }
    for key, path in ALLOWED_SOURCE_FILES.items():
        if sha256(_read_source(root / path, limit=6_000_000)).hexdigest() != checked_digests[key]:
            raise ScoutConsumerHold("source_changed_during_read")
    # Repeat consistency check: a live observer may swap inputs concurrently.
    if sha256(_read_source(filepath,limit=MAX_BYTES)).hexdigest() != sha256(raw).hexdigest():
        raise ScoutConsumerHold("review_changed_during_analysis")
    try:
        programme_catalog=read_public_program_claims(root)
    except (PublicProgrammeHold, OSError, UnicodeError, TypeError, KeyError):
        programme_catalog={"status":"PUBLIC_CLAIM_CATALOG_HELD","programmes":{}}
    for entry in preview:
        evidence=programme_catalog["programmes"].get(entry["company_domain"])
        if evidence is not None:
            entry["public_publisher_programme_review"]=evidence
    return {
        "public_programme_evidence_status":programme_catalog["status"],
        "programme_claim_rows_matched":sum(
            "public_publisher_programme_review" in entry for entry in preview
        ),
        "schema_version": SCHEMA, "status": "SOURCE_LINKED_RESEARCH_ONLY",
        "review_task_count": len(preview), "held_source_count": held,
        "independently_verified_buyer_count": 0,
        "review_tasks": preview,
        "commercial_authority": "NONE",
        "buyer_network_admission_executed": False,
        "outbound_sent": False,
    }
