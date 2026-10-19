"""Existing buyer partner pilot gates are not sale or activation evidence."""
from datetime import datetime, timezone
from empire_os.buyer_specification_readiness import build_buyer_specification_readiness
from tests.test_lead_exchange_live_inventory_20261019 import fixture as exchange_fixture

NOW = datetime(2026, 10, 19, 16, 35, tzinfo=timezone.utc)


def registry():
    return {
        "schema_version": "empire.commercial_relationship_registry.v1",
        "execution_authority": "NONE", "outbound_authorized": False,
        "outbound_sent": False,
        "gmail_snapshot_fresh": False,
        "partner_inbound_requirements": {
            "schema_version": "empire.partner_inbound_requirements_review.v1",
            "commercial_activation_authorized": False,
            "outbound_authorized": False,
            "current_review_count": 0, "historical_hold_count": 1,
        },
        "partner_pilot_readiness_queue": [
            {
                "entity_key": "leadbank", "company": "LeadBank",
                "activation_gates": {
                    g: False for g in (
                        "buyer_buybox_received_and_verified",
                        "current_target_geography_verified",
                        "buyer_source_approved",
                        "buyer_landing_approved",
                        "partner_specific_tracking_verified",
                        "partner_specific_routing_verified",
                        "buyer_payable_event_and_terms_verified",
                        "contract_and_compliance_approved",
                        "founder_live_traffic_authorized",
                    )
                },
                "gate_count_total": 9, "gate_count_verified": 0,
                "live_traffic_authorized": False,
                "outbound_authorized": False,
                "lead_smart_route_and_terms_reused": False,
                "tracking_or_route_mutation_performed": False,
                "inbound_requirement_review_status": "HISTORICAL_REPORTED_REQUIREMENTS_HOLD",
                "inbound_requirement_field_count": 1,
                "two_way_gmail_thread_observed": True,
                "mailbox_snapshot_fresh": False,
                "relationship_stage": "AWAITING_BUYER",
                "activation_stage": "WAITING_BUYER_BUYBOX",
                "proposed_corridor_not_buyer_approved": "US_ROOFING_REVIEW",
            }
        ],
    }


def test_nine_missing_gates_not_promoted_into_buyer_capacity():
    e = exchange_fixture()
    e["observed_at"] = NOW.isoformat()
    r = build_buyer_specification_readiness(relationships=registry(), exchange=e, now=NOW)
    assert r["state"] == "FOUNDER_PARTNER_GAP_BOARD_READY"
    assert r["partner_pilots_reviewed"] == 1
    assert r["verified_buyer_specifications"] == 0
    assert r["verified_buyer_capacity"] == 0
    assert r["canonical_exchange_selected_records"] == 4
    assert r["allocatable_inventory"] == 0
    assert r["outbound_authorized"] is False
    p = r["partner_readiness"][0]
    assert p["gate_verified_count"] == 0
    assert len(p["missing_evidence"]) == 9
    assert p["next_verification"] == "buyer_buybox_received_and_verified"
    assert p["reported_fields_unverified"] == 1
    assert p["buyer_buybox_verified"] is False


def test_mutated_gate_count_and_execution_authority_hold():
    e = exchange_fixture()
    e["observed_at"] = NOW.isoformat()
    r = registry()
    r["partner_pilot_readiness_queue"][0]["gate_count_verified"] = 1
    assert build_buyer_specification_readiness(
        relationships=r, exchange=e, now=NOW
    )["state"] == "HOLD"
    r = registry()
    r["outbound_authorized"] = True
    assert build_buyer_specification_readiness(
        relationships=r, exchange=e, now=NOW
    )["state"] == "HOLD"


def test_private_founder_buyer_specifications_route(tmp_path):
    import json
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.founder_lead_supply_api import create_founder_lead_supply_router
    e=exchange_fixture()
    e["observed_at"]=datetime.now(timezone.utc).isoformat()
    a=tmp_path/"exchange.json"
    b=tmp_path/"relationships.json"
    a.write_text(json.dumps(e))
    b.write_text(json.dumps(registry()))
    app=FastAPI()
    app.include_router(create_founder_lead_supply_router(
        report_path=tmp_path/"missing.json",
        exchange_path=a,
        relationship_path=b,
    ))
    result=TestClient(app).get("/v1/founder-lead-supply/buyer-specifications")
    assert result.status_code == 200
    data=result.json()
    assert data["available"] is True
    assert data["partner_pilots_reviewed"] == 1
    assert data["verified_buyer_specifications"] == 0
    assert data["commercial_activation_authorized"] is False
    assert data["outbound_authorized"] is False


def test_missing_registry_fails_closed_on_founder_route(tmp_path):
    from empire_os.founder_lead_supply_api import read_buyer_specification_gap_board
    result=read_buyer_specification_gap_board(
        tmp_path/"unknown-exchange.json",tmp_path/"unknown-buyer.json"
    )
    assert result["available"] is False
    assert result["canonical_empiredb_writes"] is False
