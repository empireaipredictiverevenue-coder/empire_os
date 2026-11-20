"""PDF page evidence -> existing Knowledge Factory intake, research only.

Caller supplies page text from an approved reader. Does not fetch, run OCR,
write a database, approve canonical truth or grant distribution rights.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from empire_os.knowledge_factory_intake import admit_intake_capture

MAX_PAGE_CHARS = 150_000


def review_pdf_page(*, source_ref: str, page: int, page_text: str,
                    document_sha256: str, tenant_id: str, namespace: str,
                    rights_status: str = "unverified") -> dict[str, Any]:
    """Build provenance-linked, noncanonical intake from a single PDF page."""
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise ValueError("positive PDF page number required")
    if not isinstance(page_text, str) or not page_text.strip() or len(page_text) > MAX_PAGE_CHARS:
        raise ValueError("nonempty bounded extracted page text required")
    if not isinstance(document_sha256, str) or len(document_sha256) != 64 or any(c not in "0123456789abcdef" for c in document_sha256):
        raise ValueError("verified document SHA256 required")
    if rights_status not in ("unverified", "restricted", "public_research", "licensed"):
        raise ValueError("unsupported rights status")
    if not isinstance(source_ref, str) or not source_ref.strip() or len(source_ref) > 900:
        raise ValueError("document source required")
    source = f"{source_ref.strip()}#page={page}"
    page_digest = sha256(page_text.encode("utf-8")).hexdigest()
    intake = admit_intake_capture({
        "source_kind": "research", "source_ref": source,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id, "namespace": namespace,
        "summary": "PDF page extracted for evidence review; content not independently verified",
        "raw_evidence_ref": f"pdf:sha256:{document_sha256}:page:{page}:text:sha256:{page_digest}",
        "source_digest": page_digest,
    }, tenant_id=tenant_id)
    return {**intake, "document_sha256": document_sha256,
            "page_number": page, "page_text_sha256": page_digest,
            "rights_status": rights_status, "commercial_reuse_authorized": False,
            "extracted_text_chars": len(page_text), "tables_verified": False,
            "research_only": True, "raw_page_text_stored": False}
