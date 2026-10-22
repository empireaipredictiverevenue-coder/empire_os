"""Pinned, read-only commercial SEO portfolio summary (NO source URLs).

Only the private materialised proposal contains original owned URL paths.
This reader makes zero network/model calls and grants zero action authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .jev_seo_deployment_queue import (
    JevDeploymentQueueHeld, safe_deployment_portfolio_summary,
)

RECEIPT=Path(
    "/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021/"
    "jev_seo_evidence_to_deployment_queue_20261022.json"
)
SHA256="ad234309362cc012c5ba3ed73d0639926a28b1b522796c462a97e5493286ec00"


class JevDeploymentReceiptHeld(ValueError):
    pass


def read_deployment_summary(path: Path=RECEIPT, expected_sha256: str=SHA256) -> dict[str,Any]:
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_mode & 0o077
            or not 1500 <= path.stat().st_size <= 260000):
        raise JevDeploymentReceiptHeld("PRIVATE_DEPLOYMENT_RECEIPT_UNAVAILABLE")
    payload=path.read_bytes()
    if sha256(payload).hexdigest()!=expected_sha256:
        raise JevDeploymentReceiptHeld("PRIVATE_DEPLOYMENT_RECEIPT_HASH_MISMATCH")
    try:
        data=json.loads(payload)
        summary=safe_deployment_portfolio_summary(data)
    except (UnicodeError,ValueError,TypeError,JevDeploymentQueueHeld) as exc:
        raise JevDeploymentReceiptHeld("PRIVATE_DEPLOYMENT_RECEIPT_INVALID") from exc
    rows=data.get("private_work_queue")
    if (not isinstance(rows,list) or len(rows)!=30
            or len({r.get("case_id") for r in rows})!=30
            or len({r.get("first_party_path") for r in rows})!=30
            or any(r.get("automatic_website_change_authorized") is not False
                   or r.get("published_or_redirected") is not False
                   or r.get("qualified_buyer_enquiry_verified") is not False
                   or r.get("revenue_recognised") is not False
                   or r.get("historical_page_text_recovered") is not False
                   or r.get("source_to_related_page_equivalence_verified") is not False
                   or r.get("model_recommended_work")!="SOURCE_AUDIT"
                   for r in rows)):
        raise JevDeploymentReceiptHeld("UNVERIFIED_DEPLOYMENT_WORK_STATUS")
    return {
        **summary,
        "validated_private_receipt_sha256":expected_sha256,
        "per_case_urls_exposed":False,
        "research_owner":"EXISTING_SEO_DEPARTMENT",
        "proposed_deployment_scope":"ORIGINAL_EDUCATIONAL_CONTENT_ONLY",
        "publication_approval_required":True,
        "redirect_approval_required":True,
        "automated_model_retraining":False,
        "new_calls_or_billing_triggered":0,
        "execution_authority":"NONE",
    }
