import hashlib
import pytest
from empire_os.knowledge_factory_pdf_bridge import review_pdf_page

DIGEST = hashlib.sha256(b"example-pdf").hexdigest()
ARGS = dict(source_ref="https://example.org/report.pdf", page=2,
            page_text="Revenue increased by 10%.", document_sha256=DIGEST,
            tenant_id="tenant-a", namespace="document-research")


def test_pdf_page_stays_research_only_and_cites_page():
    record = review_pdf_page(**ARGS)
    assert record["source_kind"] == "research"
    assert record["source_ref"] == "https://example.org/report.pdf#page=2"
    assert record["raw_evidence_ref"].startswith(f"pdf:sha256:{DIGEST}:page:2:")
    assert record["stage"] == "raw" and record["verified_as_canon"] is False
    assert record["execution_authority"] == "none"
    assert record["commercial_reuse_authorized"] is False
    assert record["raw_page_text_stored"] is False
    assert record["tables_verified"] is False


def test_deterministic_identity_and_tenant_separation():
    a = review_pdf_page(**ARGS)
    assert a["intake_ref"] == review_pdf_page(**ARGS)["intake_ref"]
    assert a["intake_ref"] != review_pdf_page(**{**ARGS, "tenant_id": "tenant-b"})["intake_ref"]
    assert a["intake_ref"] != review_pdf_page(**{**ARGS, "page_text": "Different"})["intake_ref"]


@pytest.mark.parametrize("override", [
    {"page": 0}, {"page": True}, {"page_text": " "},
    {"page_text": "a" * 150001}, {"document_sha256": "bad"},
    {"rights_status": "resale_approved"}, {"tenant_id": "wrong "},
])
def test_fails_closed(override):
    with pytest.raises(ValueError):
        review_pdf_page(**{**ARGS, **override})
