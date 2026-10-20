"""Contract regression for NYC commercial evidence gate; test fixtures never enter sales."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import pytest

from empire_os.a2a_nyc_commercial_evidence_gate import inspect_nyc_pilot

NOW = datetime(2026, 10, 20, 11, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def inputs():
    report = {
        "schema": "empire.permit_property_three_agency_evidence.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "permit_event_count": 3,
        "event_level_join_status_counts": {
            "TRI_AGENCY_BIN_AND_LOT_MATCH": 2, "DCP_LOT_ONLY_BIN_UNCONFIRMED": 1,
        },
        "event_level_landuse_category_counts": {"COMMERCIAL_OFFICE": 2, "UNKNOWN": 1},
        "source_datasets": {
            "dob_now_filings": "w9ak-ipjd", "dob_now_initial_permits": "rbx6-tga4",
            "dcp_pluto": "64uk-42ks", "oti_building_footprints": "5zhs-2jue",
        },
        "source_rights_not_granted_by_derived_evidence": True,
        "customer_facing_distributable": False,
    }
    prov = {
        "schema": "empire.original_derived_three_agency_receipt.v1",
        "derived_evidence_sha256": DIGEST,
        "no_buyer_or_property_owner_verified": True,
        "source_rights_review_required": True,
        "captured_at_utc": NOW.isoformat(),
    }
    catalog = {
        "schema_version": "empire.data_brokerage.internal_product_catalog.v1",
        "product_publication_authorized": False,
        "third_party_resale_authorized": False,
        "products": [{
            "product_id": "nyc_permit_project_verification",
            "customer_data_export_ready": False,
            "raw_third_party_resale_cleared": False,
            "customer_claim_release_ready": False,
            "fulfilment_verified": False,
        }],
    }
    gps = {
        "schema_version": "empire.market_sweep_revenue_gps.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "buyer_intent_inferred": False, "revenue_inferred": False,
        "markets": [{
            "niche": "general_contractor", "metro": "nyc",
            "approved_buyer_count": 0, "commercial_demand_evidence_count": 0,
            "commercial_terms_count": 0, "commercial_reply_count": 0,
            "research_priority_score": 80,
        }],
    }
    return dict(report=report, report_sha256=DIGEST,
                provenance=prov, catalogue=catalog, revenue_gps=gps, now=NOW)


def test_counts_are_event_counts_not_buildings_or_buyers():
    result = inspect_nyc_pilot(**inputs())
    assert result["source"]["event_count_from_existing_report"] == 3
    assert result["source"]["distinct_verified_buildings"] is None
    assert result["source"]["digest_matches"]
    assert result["source"]["independent_legal_reuse_attestation_present"] is False
    assert result["market"]["approved_buyers_reported_by_source"] == 0
    assert not result["commercial_pilot_ready"]
    assert not result["data_licence_to_resell_verified"]
    assert not result["outbound_sent"] and result["spend"] == 0
    assert "NO_APPROVED_NYC_BUYERS_IN_SOURCE_SNAPSHOT" in result["hold_reasons"]


def test_hash_tamper_detected_and_held():
    data = inputs()
    data["report_sha256"] = "b" * 64
    result = inspect_nyc_pilot(**data)
    assert not result["source"]["digest_matches"]
    assert "SOURCE_INTEGRITY_OR_CONTRACT_REVIEW" in result["hold_reasons"]
    assert not result["commercial_pilot_ready"]


def test_fake_catalogue_rights_cannot_self_authorise_distribution():
    data = inputs()
    data["catalogue"]["product_publication_authorized"] = True
    data["catalogue"]["third_party_resale_authorized"] = True
    data["catalogue"]["products"][0].update({
        "customer_data_export_ready": True,
        "raw_third_party_resale_cleared": True,
        "customer_claim_release_ready": True,
        "fulfilment_verified": True,
    })
    data["revenue_gps"]["markets"][0]["approved_buyer_count"] = 5
    data["revenue_gps"]["markets"][0]["commercial_terms_count"] = 3
    result = inspect_nyc_pilot(**data)
    assert result["source"]["reported_catalogue_flags_all_true"]
    assert not result["rights_cleared"]
    assert not result["commercial_pilot_ready"]
    assert not result["verified_customer_or_buyer"]


def test_invalid_event_count_and_authority_rejected():
    data = inputs()
    data["report"]["event_level_join_status_counts"]["TRI_AGENCY_BIN_AND_LOT_MATCH"] = 4
    with pytest.raises(ValueError, match="inconsistent"):
        inspect_nyc_pilot(**data)
    data = inputs()
    data["revenue_gps"]["revenue_inferred"] = True
    with pytest.raises(ValueError, match="untrusted_market"):
        inspect_nyc_pilot(**data)


def test_duplicate_target_market_rejected_for_commercial_conclusion():
    data = inputs()
    data["revenue_gps"]["markets"].append(deepcopy(data["revenue_gps"]["markets"][0]))
    result = inspect_nyc_pilot(**data)
    assert "NYC_BUYER_MARKET_NOT_RESOLVED_UNIQUELY" in result["hold_reasons"]
    assert not result["commercial_pilot_ready"]


def test_optional_real_snapshot_inspection_no_commercial_promotion():
    p = Path("/srv/empire_os/runtime/data_brokerage")
    gps = Path("/srv/empire_os/runtime/market_sweeps/revenue_gps_latest.json")
    files = (
        p / "nyc_dobnow_property_three_agency_latest.json",
        p / "nyc_dobnow_property_three_agency_latest.provenance.json",
        p / "internal_product_catalog_latest.json", gps,
    )
    if not all(f.is_file() for f in files):
        pytest.skip("owner-issued runtime evidence unavailable outside EmpireOS")
    report_bytes = files[0].read_bytes()
    result = inspect_nyc_pilot(
        report=json.loads(report_bytes),
        report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        provenance=json.loads(files[1].read_bytes()),
        catalogue=json.loads(files[2].read_bytes()),
        revenue_gps=json.loads(files[3].read_bytes()),
        now=datetime.now(timezone.utc),
    )
    assert result["product_id"] == "nyc_permit_project_verification"
    assert not result["commercial_pilot_ready"]
    assert not result["data_licence_to_resell_verified"]
