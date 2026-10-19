"""Real-source-shape B2B lead-gen research, never unverified buyer activation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.leadgen_revenue_activation_queue import build_leadgen_revenue_queue
from empire_os.founder_lead_supply_api import create_founder_lead_supply_router
from scripts.review_leadgen_revenue_queue_20261019 import main
from tests.test_lead_exchange_live_inventory_20261019 import fixture as inventory_fixture

NOW = datetime(2026, 10, 19, 15, 15, tzinfo=timezone.utc)


def buyer_actions():
    return {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": NOW.isoformat(),
        "outbound_enabled": False, "outbound_sent": False,
        "human_review_required": True, "buyer_conversation_verified": False,
        "contact_verified_for_outbound_count": 0,
        "shortlisted_count": 3, "trusted_founder_review_count": 0,
        "targets": [
            {
                "domain": "acme-roofing-buyers.com",
                "tier": "EVIDENCE_RECOVERY", "founder_priority": 88,
                "verticals": ["roofing", "home_services"],
                "outbound_authorized": False,
                "canonical_contact_or_reply_verified": False,
                "commercial_terms_verified": False,
                "first_party_due_diligence": {"freshness": "CURRENT",
                    "private_contact_details": "SECRET PERSON"},
                "site_corroborated_buyer_role": True,
                "missing_evidence": ["verify_active_buyer_demand",
                                     "verify_compliance_requirements"],
                "recipient_email": "SECRET_EMAIL_NOT_LEAK@example.com",
            },
            {
                "domain": "dental-partners.co.uk",
                "tier": "EVIDENCE_RECOVERY", "founder_priority": 99,
                "verticals": ["dental"],
                "outbound_authorized": False,
                "canonical_contact_or_reply_verified": False,
                "commercial_terms_verified": False,
                "first_party_due_diligence": {"freshness": "CURRENT"},
                "site_corroborated_buyer_role": False,
                "missing_evidence": ["verify_payout_economics"],
            },
            {
                "domain": "roofing-network.com",
                "tier": "EVIDENCE_RECOVERY", "founder_priority": 91,
                "verticals": ["roofing"],
                "outbound_authorized": False,
                "canonical_contact_or_reply_verified": False,
                "commercial_terms_verified": False,
                "first_party_due_diligence": {"freshness": "STALE"},
                "site_corroborated_buyer_role": False,
                "missing_evidence": ["verify_tracking_or_integration"],
            },
        ],
    }


def snapshots():
    inventory = inventory_fixture()
    inventory["observed_at"] = NOW.isoformat()
    return inventory, buyer_actions()


def test_real_research_prioritised_without_buyer_or_stock_promotion():
    exchange, buyers = snapshots()
    result = build_leadgen_revenue_queue(
        exchange=exchange, buyer_actions=buyers, now=NOW
    )
    assert result["state"] == "FOUNDER_RESEARCH_QUEUE_READY"
    assert result["research_target_count"] == 3
    assert result["canonical_selected_inventory_records"] == 4
    assert result["canonical_capacity_waitlist_records"] == 1
    assert result["buyer_research_targets_by_vertical"] == {
        "dental": 1, "roofing": 2,
    }
    assert result["founder_research_queue"][0]["domain"] == "acme-roofing-buyers.com"
    assert result["founder_research_queue"][0]["unverified_vertical_only_supply_overlap"] == {}
    assert result["founder_research_queue"][0]["territory_or_buyer_capacity_match_verified"] is False
    assert result["qualified_buyers"] == 0
    assert result["immediately_sellable_inventory"] == 0
    assert result["ready_for_outbound"] == 0
    assert not result["canonical_empiredb_writes"]
    assert not result["buyer_outreach_authorized"]
    private_dump = json.dumps(result)
    assert "SECRET PERSON" not in private_dump
    assert "SECRET_EMAIL_NOT_LEAK" not in private_dump
    assert "prospect-1" not in private_dump
    assert "Confidential buyer" not in private_dump


def test_exact_same_niche_overlap_explicitly_not_geographic_fit():
    exchange, buyers = snapshots()
    for item in exchange["inventory"]:
        item["niche_family"] = "roofing"
    output = build_leadgen_revenue_queue(exchange=exchange, buyer_actions=buyers, now=NOW)
    assert output["state"] == "FOUNDER_RESEARCH_QUEUE_READY"
    assert output["founder_research_queue"][0]["unverified_vertical_only_supply_overlap"] == {"roofing": 4}
    assert output["territory_matching_performed"] is False
    assert output["verified_buyer_capacity"] == 0


@pytest.mark.parametrize("item_key,value", [
    ("outbound_enabled", True),
    ("outbound_sent", True),
    ("buyer_conversation_verified", True),
    ("human_review_required", False),
    ("contact_verified_for_outbound_count", 1),
])
def test_true_approval_or_contact_claims_are_not_accepted(item_key, value):
    e,b = snapshots()
    b[item_key] = value
    assert build_leadgen_revenue_queue(
        exchange=e, buyer_actions=b, now=NOW
    )["state"] == "HOLD"


def test_duplicate_domain_and_raw_contact_permission_hold():
    e,b = snapshots()
    b["targets"][1]["domain"] = b["targets"][0]["domain"]
    assert build_leadgen_revenue_queue(
        exchange=e,buyer_actions=b,now=NOW
    )["state"] == "HOLD"
    e,b = snapshots()
    b["targets"][0]["outbound_authorized"] = True
    assert build_leadgen_revenue_queue(
        exchange=e,buyer_actions=b,now=NOW
    )["state"] == "HOLD"


def test_unregistered_gap_and_unverified_source_held():
    e,b = snapshots()
    b["targets"][0]["missing_evidence"] = ["private_patient_data"]
    assert build_leadgen_revenue_queue(
        exchange=e,buyer_actions=b,now=NOW
    )["state"] == "HOLD"
    e,b = snapshots()
    bad = {
        "schema_version": "empire.official_source_canonical_preflight.v1",
        "mode": "OFFICIAL_TO_CANONICAL_REVIEW_ONLY",
        "source_rows_observed": 41,
        "company_source_rows_prepared_not_ingested": 16,
        "held_source_rows": 25,
        "canonical_empiredb_writes": True,
        "outbound_authorized": False,
        "verified_net_new_empiredb_prospects": 0,
        "exchange_inventory_added": 0,
    }
    assert build_leadgen_revenue_queue(
        exchange=e,buyer_actions=b,source_preflight=bad,now=NOW
    )["state"] == "HOLD"
    bad["canonical_empiredb_writes"] = False
    result=build_leadgen_revenue_queue(
        exchange=e,buyer_actions=b,source_preflight=bad,now=NOW
    )
    assert result["source_research"]["businesses_prepared_for_review_not_ingested"] == 16
    assert result["canonical_selected_inventory_records"] == 4


def test_stale_buyers_or_exchange_held():
    e,b=snapshots()
    b["generated_at"]=(NOW-timedelta(hours=7)).isoformat()
    assert build_leadgen_revenue_queue(
        exchange=e,buyer_actions=b,now=NOW
    )["state"]=="HOLD"
    e,b=snapshots()
    e["observed_at"]=(NOW-timedelta(hours=7)).isoformat()
    assert build_leadgen_revenue_queue(
        exchange=e,buyer_actions=b,now=NOW
    )["state"]=="HOLD"


def test_cli_readonly_includes_real_shapes(tmp_path,capsys):
    exchange,buyers=snapshots()
    exchange["observed_at"]=datetime.now(timezone.utc).isoformat()
    buyers["generated_at"]=datetime.now(timezone.utc).isoformat()
    e=tmp_path/"exchange.json"
    b=tmp_path/"buyers.json"
    e.write_text(json.dumps(exchange))
    b.write_text(json.dumps(buyers))
    assert main(["--read-only", "--exchange",str(e),
                 "--buyer-actions",str(b),"--max-visible","2"]) == 0
    out=json.loads(capsys.readouterr().out)
    assert len(out["founder_research_queue"])==2
    assert out["queue_rows_hidden_for_preview_limit"]==1
    assert out["ready_for_outbound"]==0
    assert e.read_text()==json.dumps(exchange)


def test_founder_private_api_leadgen_route_read_only(tmp_path):
    exchange,buyers=snapshots()
    exchange["observed_at"]=datetime.now(timezone.utc).isoformat()
    buyers["generated_at"]=datetime.now(timezone.utc).isoformat()
    e=tmp_path/"exchange.json"
    b=tmp_path/"buyers.json"
    e.write_text(json.dumps(exchange))
    b.write_text(json.dumps(buyers))
    app=FastAPI()
    app.include_router(create_founder_lead_supply_router(
        report_path=tmp_path/"missing-report.json",
        exchange_path=e,
        buyer_actions_path=b,
    ))
    resp=TestClient(app).get("/v1/founder-lead-supply/leadgen")
    assert resp.status_code==200
    assert resp.json()["available"] is True
    assert resp.json()["research_target_count"]==3
    assert "SECRET PERSON" not in resp.text
    assert resp.json()["buyer_outreach_authorized"] is False
    assert e.read_text()==json.dumps(exchange)
    assert b.read_text()==json.dumps(buyers)


def test_founder_leadgen_links_retain_only_bounded_first_party_https():
    exchange, buyers = snapshots()
    buyers["targets"][0]["existing_first_party_source_urls"] = [
        "https://acme-roofing-buyers.com/contact",
        "https://www.acme-roofing-buyers.com/partners",
        "http://acme-roofing-buyers.com/old",
        "https://acme-roofing-buyers.com.evil.example/capture",
        "https://evil.example@acme-roofing-buyers.com/review",
        "https://acme-roofing-buyers.com:443/port",
        "https://acme-roofing-buyers.com/contact",
    ]
    report = build_leadgen_revenue_queue(
        exchange=exchange, buyer_actions=buyers, now=NOW
    )
    links=report["founder_research_queue"][0]["first_party_research_links_for_manual_review"]
    assert links == [
        "https://acme-roofing-buyers.com/contact",
        "https://www.acme-roofing-buyers.com/partners",
    ]
    checks=report["founder_research_queue"][0]["evidence_checklist"]
    assert len(checks)==2
    assert all(item["verified"] is False for item in checks)
    assert all("required_proof" in item for item in checks)
    assert report["buyer_outreach_authorized"] is False


def test_manual_private_report_has_restricted_permissions(tmp_path, monkeypatch, capsys):
    import scripts.review_leadgen_revenue_queue_20261019 as script
    exchange, buyers = snapshots()
    exchange["observed_at"] = datetime.now(timezone.utc).isoformat()
    buyers["generated_at"] = datetime.now(timezone.utc).isoformat()
    e = tmp_path / "exchange.json"
    b = tmp_path / "buyers.json"
    e.write_text(json.dumps(exchange))
    b.write_text(json.dumps(buyers))
    folder = tmp_path / "private-leadgen"
    monkeypatch.setattr(script, "PRIVATE_DIR", folder)
    monkeypatch.setattr(script, "PRIVATE_REPORT", folder / "research_queue_latest.json")
    assert script.main(["--read-only", "--write-private",
                        "--exchange", str(e), "--buyer-actions", str(b)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "FOUNDER_RESEARCH_QUEUE_READY"
    saved = json.loads(script.PRIVATE_REPORT.read_text())
    assert saved["research_target_count"] == 3
    assert saved["ready_for_outbound"] == 0
    assert saved["canonical_empiredb_writes"] is False
    assert folder.stat().st_mode & 0o777 == 0o700
    assert script.PRIVATE_REPORT.stat().st_mode & 0o777 == 0o600


def test_stale_input_cannot_overwrite_private_report(tmp_path, monkeypatch, capsys):
    import scripts.review_leadgen_revenue_queue_20261019 as script
    exchange, buyers = snapshots()
    exchange["observed_at"] = datetime.now(timezone.utc).isoformat()
    buyers["generated_at"] = (datetime.now(timezone.utc)-timedelta(hours=7)).isoformat()
    e = tmp_path / "exchange.json"
    b = tmp_path / "buyers.json"
    e.write_text(json.dumps(exchange))
    b.write_text(json.dumps(buyers))
    folder = tmp_path / "private-leadgen"
    folder.mkdir()
    before = folder / "research_queue_latest.json"
    before.write_text('{"sentinel":true}')
    monkeypatch.setattr(script, "PRIVATE_DIR", folder)
    monkeypatch.setattr(script, "PRIVATE_REPORT", before)
    assert script.main(["--read-only", "--write-private",
                        "--exchange", str(e), "--buyer-actions", str(b)]) == 2
    assert before.read_text() == '{"sentinel":true}'
    assert json.loads(capsys.readouterr().out)["state"] == "HOLD"
