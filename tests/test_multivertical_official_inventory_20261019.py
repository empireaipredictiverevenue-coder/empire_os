"""Cross-source registry and private research totals never become sold leads."""
from datetime import datetime, timezone
import json

import pytest

from scripts.review_multivertical_source_inventory_20261019 import (
    build_coverage, main,
)
from tests.test_lead_exchange_live_inventory_20261019 import fixture
from empire_os.source_intelligence import SOURCES

NOW = datetime(2026, 10, 19, 14, 40, tzinfo=timezone.utc)


def samples():
    recc = {
        "schema_version": "empire.recc_solar_supply_sweep.v1",
        "source_id": "gb_recc_solar", "state": "COMPLETED",
        "unique_research_observations": 16, "observed_at": NOW.isoformat(),
        "commercial_exchange_inventory_added": 0,
        "canonical_empiredb_writes": False, "outbound_authorized": False,
    }
    nppes = {
        "schema_version": "empire.cms_nppes_dental_org_sweep.v1",
        "source_id": "us_cms_nppes_dental_npi2", "state": "COMPLETED",
        "unique_private_organization_observations": 16,
        "observed_at": NOW.isoformat(),
        "commercial_exchange_inventory_additions": 0,
        "canonical_empiredb_writes": False, "outbound_authorized": False,
    }
    return recc, nppes


def test_observed_sources_must_remain_research_not_exchange_stock():
    solar, dental = samples()
    result = build_coverage(fixture(), solar, dental)
    assert result["canonical_exchange_selected_inventory"] == 4
    assert result["source_observation_total_no_cross_source_dedup_claim"] == 32
    assert len(result["separate_research_pools"]) == 2
    assert all(p["canonical_additions"] == 0 for p in result["separate_research_pools"])
    assert result["canonical_exchange_delivery_ready"] == 0
    assert result["official_source_packs_registered"] == 8
    assert result["execution_authority"] == "none"


@pytest.mark.parametrize("name,key,value", [
    ("recc", "commercial_exchange_inventory_added", 1),
    ("recc", "outbound_authorized", True),
    ("nppes", "commercial_exchange_inventory_additions", 2),
    ("nppes", "canonical_empiredb_writes", True),
    ("nppes", "unique_private_organization_observations", 10000),
])
def test_false_inventory_promotion_claims_fail_closed(name, key, value):
    s,d = samples()
    target = s if name == "recc" else d
    target[key] = value
    with pytest.raises(ValueError):
        build_coverage(fixture(), s, d)


def test_canonical_source_registry_not_accidentally_activated():
    for name in (
        "us_cms_nppes_dental_npi2", "us_cslb_official_contractor_csv",
        "gb_sra_firm_api", "gb_fca_insurance_firm_api",
        "us_naic_carrier_lookup", "us_state_bar_firms",
        "us_nyc_dcwp_home_improvement_companies",
        "us_nyserda_solar_participants",
    ):
        item = SOURCES[name]
        assert item.production_status == "research"
        assert "internal_acquisition" not in item.allowed_uses
        assert item.raw_resale_allowed is False


def test_readonly_cli_aggregates_only_local_files(tmp_path, capsys):
    e = fixture()
    e["observed_at"] = datetime.now(timezone.utc).isoformat()
    s,d = samples()
    files = []
    for name, v in (("exchange", e), ("recc", s), ("nppes", d)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(v))
        files.append(path)
    assert main(["--read-only", "--exchange", str(files[0]),
                 "--recc", str(files[1]), "--nppes", str(files[2])]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source_observation_total_no_cross_source_dedup_claim"] == 32
    assert result["canonical_exchange_selected_inventory"] == 4
    assert "prospect-1" not in json.dumps(result)


def test_three_distinct_official_research_pools_remain_separate():
    solar, dental = samples()
    nyc = {
        "schema_version": "empire.us_nyc_home_improvement_company_pilot.v1",
        "source_id": "us_nyc_dcwp_home_improvement_companies",
        "state": "COMPLETED", "observed_at": NOW.isoformat(),
        "corporate_business_licences_observed": 9,
        "commercial_exchange_inventory_additions": 0,
        "canonical_empiredb_writes": False,
        "outbound_authorized": False,
    }
    report = build_coverage(fixture(), solar, dental, nyc)
    assert report["canonical_exchange_selected_inventory"] == 4
    assert report["source_observation_total_no_cross_source_dedup_claim"] == 41
    assert len(report["separate_research_pools"]) == 3
    assert report["separate_research_pools"][2]["specific_trade_verified"] is False
    assert all(x["canonical_additions"] == 0
               for x in report["separate_research_pools"])
    assert report["official_source_packs_registered"] == 8
    nyc["commercial_exchange_inventory_additions"] = 9
    with pytest.raises(ValueError):
        build_coverage(fixture(), solar, dental, nyc)
