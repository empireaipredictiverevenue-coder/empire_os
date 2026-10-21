"""Allowlisted aggregate status from immutable private Jev GSC URL intake.

Never expose URL paths or customer/query material over the internal API.
Pinned file digest prevents accidental overwritten 'reviewed' label claims.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .jev_evidence_intake import intake_summary_only, JevEvidenceIntakeHeld

RECEIPT_PATH = Path(
    "/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021/"
    "jev_original_page_review_intake_20261022.json"
)
EXPECTED_SHA256 = "f4e224ba92bf00e7c36da857ee96e09d6c9f13233d19d7db192b55b5afe52c26"


class JevIntakeReceiptUnavailable(ValueError):
    pass


def read_verified_original_page_summary(
    path: Path = RECEIPT_PATH,
    expected_digest: str = EXPECTED_SHA256,
) -> dict[str, Any]:
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_mode & 0o077
            or path.stat().st_size > 150_000
            or path.stat().st_size < 500):
        raise JevIntakeReceiptUnavailable("PRIVATE_CASE_RECEIPT_MISSING_OR_UNSAFE")
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != expected_digest:
        raise JevIntakeReceiptUnavailable("PRIVATE_CASE_RECEIPT_DIGEST_MISMATCH")
    try:
        intake = json.loads(payload)
    except (UnicodeError, ValueError) as exc:
        raise JevIntakeReceiptUnavailable("PRIVATE_CASE_RECEIPT_UNREADABLE") from exc
    try:
        summary = intake_summary_only(intake)
    except (JevEvidenceIntakeHeld, AttributeError) as exc:
        raise JevIntakeReceiptUnavailable("PRIVATE_CASE_RECEIPT_CONTRACT_CHANGED") from exc
    cases = intake.get("deduplicated_original_cases")
    if (not isinstance(cases, list)
            or len(cases) != summary["observed_url_case_count"]
            or len({c["case_id"] for c in cases}) != len(cases)
            or sum(c["observed_page_dimension_impressions"] for c in cases)
                 != summary["observed_impressions_from_sample"]
            or any(c["human_label_verified"] is not False
                   or c["proposed_human_review_label"] is not None
                   or c["independent_jev_case_evaluation_ready"] is not False
                   for c in cases)):
        raise JevIntakeReceiptUnavailable("PRIVATE_CASE_LABEL_STATUS_CONTRADICTORY")
    return {
        **summary,
        "private_receipt_sha256": expected_digest,
        "case_details_exposed": False,
        "proposed_jev_model_outputs": 0,
        "current_review_state": "PENDING_ORIGINAL_PAGE_AND_AUTHENTICATED_HUMAN_REVIEW",
        "provider_inference_from_status_read": False,
        "automatic_model_evaluation_enabled": False,
        "external_requests_performed": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }
