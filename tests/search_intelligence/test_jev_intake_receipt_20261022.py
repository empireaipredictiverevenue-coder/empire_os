"""Pinned real URL intake status, no personal paths in API."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from empire_os.search_intelligence.jev_evidence_intake import build_original_page_review_intake
from empire_os.search_intelligence.jev_intake_receipt import (
    JevIntakeReceiptUnavailable, read_verified_original_page_summary,
)
from empire_os.search_intelligence.service import build_search_intelligence_service
from tests.search_intelligence.test_jev_evidence_intake_20261022 import source_fixture


def file_for(tmp_path):
    content = build_original_page_review_intake(source_fixture())
    path = tmp_path/"review.json"
    path.write_text(json.dumps(content))
    path.chmod(0o600)
    from hashlib import sha256
    return path, sha256(path.read_bytes()).hexdigest()


def test_pinned_file_contract_returns_only_summary(tmp_path):
    path, digest = file_for(tmp_path)
    d = read_verified_original_page_summary(path, digest)
    assert d["observed_url_case_count"] == 2
    assert d["reviewed_human_labels"] == d["benchmark_ready_cases"] == 0
    assert d["case_details_exposed"] is False
    assert d["automatic_model_evaluation_enabled"] is False
    assert d["provider_inference_from_status_read"] is False
    assert d["execution_authority"] == "NONE"
    assert "/aeo/" not in str(d)
    assert "ai_lead_gen" not in str(d)


def test_digest_mismatch_is_held(tmp_path):
    path, digest = file_for(tmp_path)
    with pytest.raises(JevIntakeReceiptUnavailable, match="DIGEST_MISMATCH"):
        read_verified_original_page_summary(path, "0"*64)
    path.chmod(0o644)
    with pytest.raises(JevIntakeReceiptUnavailable, match="UNSAFE"):
        read_verified_original_page_summary(path, digest)
    path.chmod(0o600)
    link=tmp_path/"symlink.json"
    link.symlink_to(path)
    with pytest.raises(JevIntakeReceiptUnavailable):
        read_verified_original_page_summary(link, digest)


def test_http_summary_requires_verified_receipt(monkeypatch, tmp_path):
    import empire_os.search_intelligence.api as api
    path, digest = file_for(tmp_path)
    monkeypatch.setattr(api, "read_verified_original_page_summary",
                        lambda: read_verified_original_page_summary(path,digest))
    client=TestClient(build_search_intelligence_service())
    response=client.get("/v1/search/jev/evidence/summary")
    assert response.status_code==200
    assert response.headers["cache-control"]=="no-store"
    assert response.headers["x-content-type-options"]=="nosniff"
    assert response.json()["observed_url_case_count"]==2
    assert "/aeo/" not in response.text
    monkeypatch.setattr(api, "read_verified_original_page_summary",
                        lambda: (_ for _ in ()).throw(
                            JevIntakeReceiptUnavailable("sensitive source path")))
    bad=client.get("/v1/search/jev/evidence/summary")
    assert bad.status_code==503
    assert bad.json()["detail"]=="jev_original_page_evidence_unavailable"
    assert "sensitive" not in bad.text
