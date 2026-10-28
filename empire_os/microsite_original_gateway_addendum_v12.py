"""Proposed single-route original gateway extension — owner must adopt separately.

No publishing script, alternate gateway or authorisation writer exists here.
A release becomes readable only after owner-custodied SEO/brand/site approvals,
an unchanged original five-release manifest and exact site-export bytes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Any

from empire_os.owned_campaign_release import load_release, released_paths

ORIGINAL_PREVIEW_SHA = "3ee2f8d08d12d306ab3842b3cb5b041d34fb340f2f6a8d8a898821b2200293a0"
CANDIDATE = "microsite_c4c5a13b626d293fe15c"
CAMPAIGN_ID = "campaign_" + hashlib.sha256(
    (CANDIDATE + ":" + ORIGINAL_PREVIEW_SHA).encode()
).hexdigest()[:24]
SCHEMA = "empire.original_website.one_microsite_addendum.v1"
APPROVAL_SCHEMA = "empire.original_website.scoped_owner_approval.v1"
_ORIGINAL_RELEASE = Path("runtime/astra/owned_campaign_deployed_release.json")
_ADDENDUM = Path("runtime/public_website/one_chicago_research_release.json")
_ROLE_FILE = {
    "seo": Path("runtime/public_website/approvals/chicago_research_seo.json"),
    "brand": Path("runtime/public_website/approvals/chicago_research_brand.json"),
    "website": Path("runtime/public_website/approvals/chicago_research_website.json"),
}
_CAMPAIGN = re.compile(r"campaign_[0-9a-f]{24}\Z")


def _regular_bytes(path: Path, max_bytes: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Required original-owner file missing or symlinked")
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes:
        raise ValueError("Original-owner file outside bounded size limit")
    return raw


def _read(path: Path) -> dict[str, Any]:
    doc = json.loads(_regular_bytes(path, 40000).decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("Owner document must be a JSON object")
    return doc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _owner_approved(root: Path, role: str, source_hash: str, deployed_hash: str) -> bool:
    doc = _read(root / _ROLE_FILE[role])
    return (
        doc.get("schema_version") == APPROVAL_SCHEMA
        and doc.get("review_lane") == role
        and doc.get("independently_approved") is True
        and isinstance(doc.get("owner_ref"), str)
        and bool(doc["owner_ref"].strip())
        and doc.get("candidate_id") == CANDIDATE
        and doc.get("source_preview_sha256") == source_hash
        and doc.get("deployed_html_sha256") == deployed_hash
        and doc.get("approval_scope") == "single_chicago_citywide_research"
    )


def original_owner_chicago_html(
    campaign_id: str,
    *,
    root: Path = Path("/srv/empire_os"),
    existing_release_reader: Callable[[Path], Any] = load_release,
    existing_paths_reader: Callable[[Path], list[str]] = released_paths,
) -> str | None:
    """Return one original-site reviewed page or None. No mutation or rollout.

    The serving gate checks independent owner-controlled approvals and a
    byte-verified local staged export. First publication is possible *before*
    external HTTP readback; the original site owner must then perform and log
    independent live URL, hash and rollback checks immediately afterwards.
    CAUTION: this checks receipt contents, not owner cryptographic signatures.
    """
    if campaign_id != CAMPAIGN_ID or not _CAMPAIGN.fullmatch(campaign_id):
        return None
    root = Path(root)
    try:
        original = existing_release_reader(root)
        paths = existing_paths_reader(root)
        if (not isinstance(original, dict)
                or len(original.get("campaigns", [])) != 5
                or not isinstance(paths, list) or len(paths) != 5
                or len(set(paths)) != 5
                or f"/research/{campaign_id}" in paths):
            return None
        original_receipt_sha = _sha(_regular_bytes(root / _ORIGINAL_RELEASE, 350000))
        receipt = _read(root / _ADDENDUM)
        source_hash = receipt.get("source_preview_sha256")
        deploy_hash = receipt.get("deployed_html_sha256")
        if (receipt.get("schema_version") != SCHEMA
                or receipt.get("candidate_id") != CANDIDATE
                or receipt.get("campaign_id") != CAMPAIGN_ID
                or source_hash != ORIGINAL_PREVIEW_SHA
                or not isinstance(deploy_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", deploy_hash)
                or receipt.get("original_five_release_sha256") != original_receipt_sha
                or receipt.get("zero_paid_media") is not True
                or receipt.get("indexation_enabled") is not False
                or receipt.get("lead_form_enabled") is not False
                or receipt.get("outbound_authorized") is not False
                or receipt.get("execution_authority") != "none"
                # A FIRST publication cannot already have an external live
                # readback: that proof can only be collected after serving.
                # Require the original owner's exact staged export SHA instead.
                or receipt.get("original_site_owner_staged_export_verified") is not True
                or receipt.get("staged_export_sha256") != deploy_hash
                or receipt.get("original_site_owner_release_approved") is not True
                or receipt.get("url") !=
                f"https://empire-ai.co.uk/research/{CAMPAIGN_ID}"):
            return None
        for role in _ROLE_FILE:
            if not _owner_approved(root, role, source_hash, deploy_hash):
                return None
        # Original ASTRA build export only, not a caller-nominated arbitrary path.
        deployed = (root / "apps/empire-public-site/out/research" /
                    f"{CAMPAIGN_ID}.html")
        raw = _regular_bytes(deployed, 8500000)
        if _sha(raw) != deploy_hash:
            return None
        html = raw.decode("utf-8")
        if (not re.search(
                r'<meta\s+name="robots"\s+content="noindex,nofollow,noarchive"',
                html, re.I
            )
            or "<form" in html.lower() or "<script" in html.lower()
            or "data:image/png;base64," not in html):
            return None
        return html
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def original_owner_extension_patch() -> str:
    """Instructions for ORIGINAL owner review; not executed by this module."""
    return (
        "In existing empire_os.owned_campaign_release.released_html() only, "
        "after the original five lookup fails, call "
        "empire_os.microsite_original_gateway_addendum_v12."
        "original_owner_chicago_html(campaign_id, root=root). "
        "Leave load_release() exactly-five invariant and public_gateway route intact."
    )
