"""Regression: existing running scout evidence -> governed sniper review only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.revenue_sniper_scanner_review import (
    review_existing_scout_snapshot, SCOUT_SCHEMA,
)
from scripts.review_existing_scanners_and_snipers_20261019 import main

NOW = datetime(2026, 10, 19, 12, 15, tzinfo=timezone.utc)


def candidate(**overrides):
    result = {
        "domain": "acme-roofing.example",
        "business_name": "Acme Roofing",
        "continuous_commercial_lane": "home_service_growth",
        "discovery_source": "canonical_prospect_seed",
        "candidate_state": "RESEARCH_EVIDENCE_ONLY",
        "buyer_type": "direct_buyer",
        "canonical_identity_verified": False,
        "decision_maker_state": "OBSERVED_ROLE_MATCH",
        "economic_capacity_state": "OBSERVED_PROXY",
        "observed_buying_triggers": ["public project"],
        "direct_buyer_score": 0,
        "budget_verified": False,
        "commercial_terms_verified": False,
        "outreach_authorized": False,
        "continuous_lane_fit_score": 78,
        "first_party_people": [
            {"name": "PRIVATE PERSON", "email": "private@example.test"}
        ],
        "first_party_emails": ["private@example.test"],
    }
    result.update(overrides)
    return result


def snapshot(*rows):
    return {
        "schema_version": SCOUT_SCHEMA,
        "mode": "OBSERVE",
        "database_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
        "generated_at": NOW.isoformat(),
        "queries": [],
        "candidates": list(rows),
    }


def test_existing_live_scout_b2b_ranks_research_not_verified_buyer():
    result = review_existing_scout_snapshot(snapshot(candidate()), now=NOW)
    assert result["scanner_rows_observed"] == 1
    assert result["research_rank_counts"] == {"PRIORITY_RESEARCH": 1}
    assert result["commercially_verified_buyers"] == 0
    item = result["research_candidates"][0]
    assert item["research_priority_points"] == 7
    assert item["buyer_capacity_verified"] is False
    assert item["outbound_authorized"] is False
    assert item["sniper_execution_authorized"] is False
    assert "PRIVATE PERSON" not in json.dumps(result)
    assert "private@example.test" not in json.dumps(result)


def test_regulated_insurance_and_mass_tort_are_specialist_hold():
    result = review_existing_scout_snapshot(snapshot(
        candidate(domain="insure.example", continuous_commercial_lane="insurance",
                  buyer_type="insurance_broker"),
        candidate(domain="law.example", continuous_commercial_lane="legal_mass_tort",
                  buyer_type="law_firm"),
    ), now=NOW)
    assert result["research_rank_counts"] == {"REGULATED_HOLD": 2}
    assert all(not row["lead_sellable"] for row in result["research_candidates"])
    assert all("regulated_firm_only_jurisdiction_review_required" in row["blocking_reasons"]
               for row in result["research_candidates"])


def test_unknown_mass_tort_firm_is_not_assumed_law_buyer():
    result = review_existing_scout_snapshot(snapshot(
        candidate(domain="law.example", continuous_commercial_lane="legal_mass_tort",
                  buyer_type="unknown"),
    ), now=NOW)
    assert result["research_candidates"][0]["research_rank"] == "REGULATED_HOLD"
    assert "law_firm_identity_not_proven" in result["research_candidates"][0]["blocking_reasons"]


@pytest.mark.parametrize("bad_domain", [
    "https://127.0.0.1/", "http://example.com", "https://localhost/",
    "http://internal.local", "10.2.0.1", "https://foo.example:443/",
    "",
])
def test_network_or_untrusted_domains_fail_closed(bad_domain):
    result = review_existing_scout_snapshot(snapshot(candidate(domain=bad_domain)), now=NOW)
    assert result["research_rank_counts"] == {"SOURCE_HOLD": 1}
    assert not result["research_candidates"][0]["outbound_authorized"]


@pytest.mark.parametrize("tampering", [
    {"outreach_authorized": True},
    {"candidate_state": "READY_TO_BUY"},
    {"buyer_type": "consumer_claimant"},
    {"continuous_commercial_lane": "crypto_trading"},
    {"discovery_source": "unverified_vendor"},
])
def test_untrusted_actions_sources_and_subjects_hold(tampering):
    result = review_existing_scout_snapshot(snapshot(candidate(**tampering)), now=NOW)
    assert result["research_candidates"][0]["research_rank"] == "SOURCE_HOLD"
    assert result["execution_authority"] == "none"


def test_duplicates_collapse_for_review_not_sales_counts():
    result = review_existing_scout_snapshot(snapshot(
        candidate(), candidate(discovery_source="search_fabric")
    ), now=NOW)
    assert result["scanner_rows_observed"] == 2
    assert result["distinct_business_lane_keys"] == 1
    assert result["duplicate_company_lane_observations"] == 1
    assert result["research_rank_counts"] == {"SOURCE_HOLD": 1}
    assert "duplicate_company_lane_requires_reconciliation" in result["research_candidates"][0]["blocking_reasons"]
    assert result["commercially_verified_buyers"] == 0


def test_old_snapshot_is_not_prioritised_as_current():
    old = snapshot(candidate())
    old["generated_at"] = (NOW - timedelta(days=3)).isoformat()
    result = review_existing_scout_snapshot(old, now=NOW)
    assert result["source_snapshot_fresh_under_24h"] is False
    assert result["research_rank_counts"] == {"SOURCE_HOLD": 1}


def test_false_outbound_or_write_flag_rejects_snapshot():
    for key in ["database_write_performed", "outbound_sent"]:
        s = snapshot(candidate())
        s[key] = True
        with pytest.raises(ValueError, match="untrusted_or_unbounded"):
            review_existing_scout_snapshot(s, now=NOW)


def test_max_candidates_and_invalid_schema_rejected():
    with pytest.raises(ValueError):
        review_existing_scout_snapshot(snapshot(*[candidate(domain=f"firm{i}.example") for i in range(101)]), now=NOW)
    s = snapshot()
    s["schema_version"] = "spoofed"
    with pytest.raises(ValueError):
        review_existing_scout_snapshot(s, now=NOW)


def test_probe_failures_are_diagnostics_not_sold_leads():
    s = snapshot()
    s["probe_failure_counts"] = {"homepage_fetch_failed": 5}
    result = review_existing_scout_snapshot(s, now=NOW)
    assert result["source_failure_counts"]["homepage_fetch_failed"] == 5
    assert result["commercially_verified_buyers"] == 0


def test_readonly_cli_runs_existing_snapshot_without_writing(tmp_path, capsys):
    s = snapshot(candidate())
    s["generated_at"] = datetime.now(timezone.utc).isoformat()
    p = tmp_path / "scout_latest.json"
    p.write_text(json.dumps(s))
    assert main(["--read-only", "--scout-snapshot", str(p)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["research_rank_counts"] == {"PRIORITY_RESEARCH": 1}
    assert out["canonical_database_writes"] is False
    assert out["live_outreach"] is False
    assert p.read_text() == json.dumps(s)


def test_cli_bad_json_does_not_echo_content(tmp_path, capsys):
    p = tmp_path / "scout_latest.json"
    p.write_text("confidential applicant data")
    assert main(["--read-only", "--scout-snapshot", str(p)]) == 2
    value = capsys.readouterr().out
    assert "confidential applicant" not in value
    assert json.loads(value)["execution_authority"] == "none"
