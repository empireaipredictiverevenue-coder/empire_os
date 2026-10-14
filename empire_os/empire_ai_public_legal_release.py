"""Separate, fail-closed Empire AI public legal-document admission.

This module does NOT publish, write a receipt, change the shared gateway, or
imply that any founder/legal review is complete. It must be integrated only
after ASTRA's website hand-off and an independently approved deployment.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re

LEGAL_ROOT = Path("/srv/empire_os/runtime/public_legal/approved")
RELEASE_RECEIPT = LEGAL_ROOT / "release.json"
LEGAL_PAGES = {"privacy": "privacy.html", "terms": "terms.html"}
SCHEMA = "empire.public-legal-release.v1"
NOTICE_SCHEMA = "empire.public-legal-notice.v1"
SOURCE_LANE = "OWNED_EMPIRE_AI_PUBLIC_LEGAL"
BLOCKED_DRAFT_MARKERS = (
    "FOUNDER / LEGAL REVIEW DRAFT",
    "NOT EFFECTIVE OR PUBLISHED",
    "NOT YET LIVE",
    "[RELEASE GATE:",
    "[CONFIRM ",
    "[VERIFIED ",
    "[SET ONLY AFTER",
    "Status: PROPOSED",
    "final review copy",
    "Lorem ipsum",
)
REQUIRED_EVIDENCE = (
    "founder_publication_authorized",
    "legal_review_complete",
    "privacy_rights_workflow_verified",
    "privacy_retention_and_deletion_verified",
    "youtube_revocation_and_deletion_verified",
)
REQUIRED_REFERENCES = (
    "founder_approval_ref",
    "legal_review_ref",
    "privacy_rights_evidence_ref",
    "retention_evidence_ref",
    "youtube_revocation_evidence_ref",
)


def checked_legal_path(route: str, *, root: Path = LEGAL_ROOT,
                       receipt_path: Path | None = None) -> Path | None:
    """Read-only admission. No receipt is ever generated here.

    Both policies must be present and unchanged even when requesting one.
    Independent from the existing US homeowner/Lead Smart approval gate.
    """
    if route not in LEGAL_PAGES:
        return None
    receipt_path = receipt_path or (root / "release.json")
    try:
        if root.is_symlink() or receipt_path.is_symlink():
            return None
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            return None
        if (receipt.get("source_lane") != SOURCE_LANE
            or receipt.get("execution_authority") != "none"
            or receipt.get("money_movement_authorized") is not False
            or receipt.get("marketing_or_outbound_authorized") is not False):
            return None
        if receipt.get("schema_version") == NOTICE_SCHEMA:
            # Public information disclosure only. This route does NOT certify
            # private-data handling or authorise Google data collection, storage,
            # outbound, payments or uploads. Do not falsify verification flags.
            if (receipt.get("notice_only") is not True
                or receipt.get("founder_publication_authorized") is not True
                or receipt.get("founder_approval_ref")
                   != "founder-chat-20261014-exact-two-pages"
                or receipt.get("notice_publication_review_ref")
                   != "empire-google-oauth-notice-review-20261014"
                or receipt.get("active_youtube_data_storage_authorized") is not False
                or receipt.get("youtube_upload_authorized") is not False
                or any(receipt.get(key) is not False
                       for key in ("legal_review_complete",
                                   "privacy_rights_workflow_verified",
                                   "privacy_retention_and_deletion_verified",
                                   "youtube_revocation_and_deletion_verified"))):
                return None
        elif receipt.get("schema_version") == SCHEMA:
            if any(receipt.get(key) is not True for key in REQUIRED_EVIDENCE):
                return None
            if any(not isinstance(receipt.get(key), str)
                   or not receipt[key].strip()
                   or receipt[key].startswith("TEST_")
                   for key in REQUIRED_REFERENCES):
                return None
        else:
            return None
        effective = receipt.get("effective_date")
        if not isinstance(effective, str):
            return None
        parsed = date.fromisoformat(effective)
        if parsed > date.today() or parsed < date(2020, 1, 1):
            return None
        digests = receipt.get("approved_page_sha256")
        if not isinstance(digests, dict) or set(digests) != set(LEGAL_PAGES):
            return None
        for page, filename in LEGAL_PAGES.items():
            file = root / filename
            if file.is_symlink() or not file.is_file():
                return None
            expected = digests.get(page)
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                return None
            data = file.read_bytes()
            if len(data) > 512_000 or len(data) < 100:
                return None
            if hashlib.sha256(data).hexdigest() != expected:
                return None
            html = data.decode("utf-8")
            lowered = html.lower()
            if (any(marker.lower() in lowered for marker in BLOCKED_DRAFT_MARKERS)
                or "<html" not in lowered or "</html>" not in lowered
                or "<title" not in lowered
                or "empire ai" not in lowered
                or "68 wentbridge road" not in lowered
                or "founder@empire-ai.co.uk" not in lowered
                or "<script" in lowered or "<iframe" in lowered):
                return None
            if page == "privacy" and (
                "youtube api services" not in lowered
                or "policies.google.com/privacy" not in lowered
                or "myaccount.google.com/permissions" not in lowered
                or "security.google.com/settings/security/permissions" not in lowered
                or "youtube.readonly" not in lowered
                or "yt-analytics.readonly" not in lowered
            ):
                return None
            if page == "terms" and (
                "youtube.com/t/terms" not in lowered
                or "/privacy" not in lowered
            ):
                return None
        return root / LEGAL_PAGES[route]
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return None
