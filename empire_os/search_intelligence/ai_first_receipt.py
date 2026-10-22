"""Verify one private AI-first local SEO sweep, expose aggregate status only.

An AI suggestion is not a verified label, not historical page copy, and not an
execution permission. No inference occurs in any request-serving code.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .ai_first_seo_review import (
    SCHEMA, SeoAiFirstHeld, public_safe_ai_summary,
)
from .jev_intake_receipt import EXPECTED_SHA256 as SOURCE_DIGEST

RECEIPT = Path(
    "/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021/"
    "seo_local_ai_first_30_20261022.json"
)
PINNED_DIGEST = "7b4758b90f5aa46e1625c100cde3be582fa076a08c711949c8083542b3103bd8"


class AiFirstReceiptHeld(ValueError):
    pass


def read_ai_first_summary(
    path: Path = RECEIPT,
    expected_digest: str = PINNED_DIGEST,
) -> dict[str, Any]:
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_mode & 0o077
            or not 1500 <= path.stat().st_size <= 180000):
        raise AiFirstReceiptHeld("PRIVATE_AI_RECEIPT_UNAVAILABLE")
    data = path.read_bytes()
    if sha256(data).hexdigest() != expected_digest:
        raise AiFirstReceiptHeld("PRIVATE_AI_RECEIPT_HASH_MISMATCH")
    try:
        packet = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise AiFirstReceiptHeld("PRIVATE_AI_RECEIPT_NOT_JSON") from exc
    if (packet.get("schema_version") != SCHEMA
            or packet.get("source_receipt_sha256") != SOURCE_DIGEST
            or packet.get("estimated_external_inference_cost_usd") != 0
            or packet.get("local_inference_only") is not True
            or packet.get("original_page_copy_recovered") is not False
            or packet.get("automated_source_research_complete") is not False
            or packet.get("publication_or_redirect_authorized") is not False
            or packet.get("database_writes") is not False):
        raise AiFirstReceiptHeld("PRIVATE_AI_RECEIPT_CONTRACT_CHANGED")
    try:
        summary = public_safe_ai_summary(packet)
    except (SeoAiFirstHeld, AttributeError, TypeError, KeyError) as exc:
        raise AiFirstReceiptHeld("PRIVATE_AI_RECEIPT_REVIEW_FAILED") from exc
    return {
        **summary,
        "shadow_model": "convaiinnovations/laya:onnx",
        "provider": "existing_local_laya_http",
        "model_output_status": "UNVERIFIED_RESEARCH_CANDIDATES",
        "source_receipt_pinned": True,
        "receipt_read_calls_to_model": 0,
        "original_404_content_recovery_required": True,
        "review_recommended_to_ai_research_desk": True,
        "customer_identifiers_disclosed": False,
        "execution_authority": "NONE",
    }
