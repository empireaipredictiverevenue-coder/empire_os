"""Founder JEV research status and manual operator probe regression."""
import json

import pytest
from fastapi.testclient import TestClient

from empire_os.founder_dashboard_service import build_founder_dashboard_service
from scripts.probe_jev_evidence_research_v2 import (
    _synthetic_decision, execute_fixture_smoke, main,
)


def test_offline_fixture_probe_never_opens_network_or_database():
    packet = execute_fixture_smoke()
    assert packet["status"] == "OFFLINE_SYNTHETIC_PIPELINE_PASSED"
    assert packet["network_access"] is False
    assert packet["network_calls"] == 0
    assert packet["db_reads"] == 0
    assert packet["actual_revenue"] is False
    assert packet["original_buyer_reply_verified"] is False
    assert packet["research_receipt"]["inspected_source_count"] == 1
    assert packet["research_receipt"]["sources"][0]["claim_accuracy_verified"] is False
    assert packet["decision_attachment"]["buyer_intent_verified"] is False


def test_fixture_smoke_cli_returns_valid_json_without_secrets(capsys):
    assert main(["--fixture-smoke"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "OFFLINE_SYNTHETIC_PIPELINE_PASSED"
    assert data["execution_authority"] == "none"
    assert "Fictional Only Ltd" not in json.dumps(data)


def test_manual_local_json_plan_remains_untrusted(tmp_path,capsys):
    target = tmp_path / "decision.json"
    target.write_text(json.dumps(_synthetic_decision()), encoding="utf8")
    assert main([
        "--decision-json", str(target), "--public-niche", "roofing",
        "--public-market", "Manchester",
    ]) == 0
    packet = json.loads(capsys.readouterr().out)
    assert packet["status"] == "OFFLINE_UNAUTHENTICATED_PLAN_ONLY"
    assert packet["input_authentication"] == "LOCAL_JSON_NOT_CANONICAL"
    assert packet["network_access"] is False
    assert packet["execution_authority"] == "none"
    assert packet["plan"]["status"] == "PLANNED_PUBLIC_RESEARCH"


def test_local_invalid_file_does_not_fabricate_identity(tmp_path):
    p = tmp_path / "untrusted.json"
    p.write_text('{"schema_version":"madeup"}',encoding="utf8")
    with pytest.raises(ValueError, match="trusted shape"):
        main([
            "--decision-json",str(p),
            "--public-niche","roofing","--public-market","Manchester",
        ])


def test_founder_api_research_truth_and_safe_default():
    app = build_founder_dashboard_service()
    response = TestClient(app).get("/v1/founder-jev/status")
    assert response.status_code == 200
    truth = response.json()
    assert truth["shared_vane_openmanus_research_core_integrated"] is True
    assert truth["jev_evidence_gap_plan_available"] is True
    assert truth["jev_public_research_execution_activated"] is False
    assert truth["jev_research_source_validation_completed_live"] is False
    assert truth["jev_official_primary_continuity_implemented"] is True
    assert truth["jev_official_primary_continuity_production_enabled"] is False
    assert truth["jev_research_spend_gbp"] == 0
    assert truth["buyers_identified"] is None
    assert truth["verified_revenue"] is None
    assert truth["send_authorized"] is False
    assert truth["production_activated"] is False
    assert not any(
        path.startswith("/v1/founder-jev/execute")
        for path in app.openapi()["paths"]
    )


def test_operator_official_source_smoke_explicit_only_and_no_search(monkeypatch,capsys):
    import scripts.probe_jev_evidence_research_v2 as operator

    selected = []
    def one_source(decision, *, public_niche, public_market, official_source_urls, country):
        selected.append((public_niche, public_market, official_source_urls, country))
        return {
            "pages_considered": 1, "inspected_source_count": 1,
            "sources": [{
                "inspection_status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
                "content_sha256": "a"*64,
            }],
        }

    monkeypatch.setattr(operator, "run_jev_official_source_review", one_source)
    assert operator.main([
        "--official-source-smoke",
        "--official-source-url", "https://www.ons.gov.uk/construction",
        "--public-niche", "roofing", "--public-market", "Manchester",
    ]) == 0
    outcome = json.loads(capsys.readouterr().out)
    assert selected == [(
        "roofing", "Manchester",
        ("https://www.ons.gov.uk/construction",), "GB",
    )]
    assert outcome["status"] == "PUBLIC_OFFICIAL_SOURCE_SMOKE"
    assert outcome["search_provider_calls"] == 0
    assert outcome["inspected_count"] == 1
    assert outcome["content_fingerprint_present"] is True
    assert outcome["actual_revenue"] is False
    assert outcome["buyer_intent_verified"] is False
    assert outcome["execution_authority"] == "none"


def test_operator_rejects_official_source_smoke_without_public_scope():
    with pytest.raises(SystemExit):
        main(["--official-source-smoke",
              "--official-source-url", "https://www.ons.gov.uk/construction"])
