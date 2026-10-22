"""SEO deployment queue uses real Jev and GSC records without inventing revenue."""
from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from empire_os.search_intelligence.jev_seo_deployment_queue import (
    JevDeploymentQueueHeld, prepare_jev_seo_deployment_queue,
    safe_deployment_portfolio_summary,
)
from empire_os.search_intelligence.jev_deployment_receipt import (
    JevDeploymentReceiptHeld, read_deployment_summary, RECEIPT,
)
from empire_os.search_intelligence.service import build_search_intelligence_service


def test_thirty_real_case_evidence_becomes_four_research_portfolios():
    packet=prepare_jev_seo_deployment_queue()
    summary=safe_deployment_portfolio_summary(packet)
    assert packet["original_case_count"]==30
    assert packet["jev_actual_case_predictions"]==30
    assert packet["core_topic_research_case_count"]==15
    assert packet["off_core_hold_case_count"]==15
    assert packet["sample_total_impressions"]==44
    assert packet["sample_total_clicks"]==0
    assert [x["case_count"] for x in packet["research_portfolios"]]==[11,3,1,15]
    assert [x["total_gsc_sample_impressions"] for x in packet["research_portfolios"]]==[14,4,1,25]
    assert all(r["model_recommended_work"]=="SOURCE_AUDIT" for r in packet["private_work_queue"])
    assert all(r["automatic_website_change_authorized"] is False for r in packet["private_work_queue"])
    assert all(r["published_or_redirected"] is False for r in packet["private_work_queue"])
    assert all(r["qualified_buyer_enquiry_verified"] is False for r in packet["private_work_queue"])
    assert summary["website_changes_live"] is False
    assert summary["first_party_source_content_verified"] is False
    assert summary["seo_traffic_lift_verified"] is False
    assert summary["realised_revenue_verified"] is False
    assert summary["model_calls_during_summary"] == 0
    assert summary["execution_authority"]=="NONE"


def test_no_auto_redirect_even_if_current_owned_page_exists():
    packet=prepare_jev_seo_deployment_queue()
    for c in packet["private_work_queue"]:
        assert c["source_to_related_page_equivalence_verified"] is False
        assert c["original_publisher_rights_verified"] is False
        assert c["historical_page_text_recovered"] is False
        if c["work_type"]=="EDITORIAL_EVIDENCE_RESEARCH_ONLY":
            assert c["related_page_evidence_status"]=="RELATED_PAGE_ONLY_NOT_HISTORICAL_EQUIVALENCE"
            assert c["existing_asset_sha256"].startswith("repo-sha256:")
        else:
            assert c["work_type"]=="RETAIN_404_AND_MONITOR"
            assert c["related_owned_page_for_context"] is None
            assert c["existing_original_asset_for_review"] is None


def test_missing_or_unmatched_evidence_fails_closed():
    source=prepare_jev_seo_deployment_queue()
    originals=deepcopy(source["private_work_queue"])
    # Input adapter is stricter than private output, use known trusted real cohort.
    from empire_os.search_intelligence.ai_first_seo_review import validated_cases
    cases=validated_cases()
    from empire_os.search_intelligence.jev_case_receipts import ROOT,PINNED_SHA256
    import json
    model_rows=[]
    for i in range(6):
        d=json.loads((ROOT/f"jev_page_batch_{i}_20261022.json").read_text())
        model_rows+=d["case_reviews"]
    mutated=deepcopy(model_rows)
    mutated[0]["source_ref"]="gsc-page-origin-sha256:"+"0"*64
    with pytest.raises(JevDeploymentQueueHeld,match="PROVENANCE"):
        prepare_jev_seo_deployment_queue(cases=cases, provider_records=mutated)
    mutated=deepcopy(model_rows)
    mutated[0]["publish_authority"]=True
    with pytest.raises(JevDeploymentQueueHeld,match="AUTHORITY"):
        prepare_jev_seo_deployment_queue(cases=cases, provider_records=mutated)


def test_private_receipt_pinned_and_never_leaks_original_paths():
    packet=read_deployment_summary()
    assert packet["original_url_observations"]==30
    assert packet["per_case_urls_exposed"] is False
    assert packet["personal_data_or_paths_disclosed"] is False
    assert packet["publication_approval_required"] is True
    assert packet["new_calls_or_billing_triggered"]==0
    assert "/aeo/" not in str(packet)
    assert "ai_lead_gen" not in str(packet)


def test_tamper_hash_and_permissions_are_rejected(tmp_path):
    path=tmp_path/"private.json"
    path.write_bytes(RECEIPT.read_bytes())
    path.chmod(0o600)
    with pytest.raises(JevDeploymentReceiptHeld, match="HASH_MISMATCH"):
        read_deployment_summary(path, "0"*64)
    path.chmod(0o644)
    with pytest.raises(JevDeploymentReceiptHeld, match="UNAVAILABLE"):
        read_deployment_summary(path)
    path.chmod(0o600)
    path.write_bytes(path.read_bytes()+b"\n")
    with pytest.raises(JevDeploymentReceiptHeld):
        read_deployment_summary(path)


def test_private_api_never_calls_jev_or_releases_raw_cases(monkeypatch):
    client=TestClient(build_search_intelligence_service())
    response=client.get("/v1/search/jev/deployment/summary")
    assert response.status_code==200
    assert response.headers["cache-control"]=="no-store"
    assert response.headers["x-content-type-options"]=="nosniff"
    assert response.json()["core_topic_research_observations"]==15
    assert "/aeo/" not in response.text
    assert response.json()["model_calls_during_summary"]==0
    import empire_os.search_intelligence.api as module
    monkeypatch.setattr(module,"read_deployment_summary",lambda: (_ for _ in ()).throw(JevDeploymentReceiptHeld("secret path")))
    fail=client.get("/v1/search/jev/deployment/summary")
    assert fail.status_code==503
    assert fail.json()["detail"]=="jev_deployment_queue_unavailable"
    assert "secret path" not in fail.text
