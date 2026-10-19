"""User-supplied v49 shadow fixtures reproduced without contacting anyone."""
import json

import pytest

from empire_os.flagship_legacy_v49_shadow import (
    review_v49_matching_counterfactual as shadow,
    WEIGHTS, SCHEMA,
)

LEAD = {
    "tenant_id": "synthetic_tenant",
    "metro": "Dallas",
    "specialties": ["roofing"],
    "approved_adjacent_metros": ["Plano"],
}


def contractor(**kwargs):
    row = {
        "tenant_id": "synthetic_tenant", "metro": "Dallas",
        "specialties": ["roofing"], "active": True,
        "trust_score": 8, "days_since_dispatch": 7,
        "active_dispatches": 1, "max_concurrent": 3,
        "territory_verified": True, "specialty_verified": True,
        "license_verified": True, "capacity_verified": True,
        "source_rights_verified": True, "trust_score_verified": True,
        "dispatch_history_verified": True, "suppressed": False,
        "private_contact_email": "private-fixture@example.com",
    }
    row.update(kwargs)
    return row


def run(*items, lead=LEAD):
    return shadow(lead=lead, contractor_fixtures=list(items))


def test_zip_synthetic_four_candidate_report_exact_reference_values():
    report = run(
        contractor(),
        contractor(metro="Los Angeles"),
        contractor(specialties=["solar"]),
        contractor(capacity_verified=False),
    )
    assert report["schema_version"] == SCHEMA
    assert WEIGHTS == (.40, .25, .15, .10, .10)
    assert report["historical_mean_rank_score"] == .725
    assert report["fixture_mean_research_score"] == .887
    assert report["legacy_ranked_count"] == 4
    assert report["fixture_research_eligible_count"] == 1
    assert report["evidence_hold_count"] == 3
    assert report["legacy_wrong_geography_count"] == 1
    assert report["legacy_wrong_specialty_count"] == 1
    assert report["evidence_hold_reason_counts"] == {
        "capacity_verified": 1, "geography": 1, "specialty": 1,
    }
    assert "private-fixture@example.com" not in json.dumps(report)
    assert "synthetic_tenant" not in json.dumps(report)
    for field in (
        "historical_score_is_calibrated_conversion_probability",
        "supplied_evidence_flags_independently_authenticated",
        "verified_buyer_capacity", "real_world_matching_accuracy_measured",
        "training_eligible", "commercial_allocations_authorized",
        "outbound_authorized", "production_empiredb_accessed",
        "database_writes", "funds_moved",
    ):
        assert report[field] is False


def test_wrong_market_even_when_niche_matches_is_not_research_eligible():
    result = run(contractor(metro="Los Angeles", trust_score=10))
    assert result["legacy_ranked_count"] == 1
    assert result["fixture_research_eligible_count"] == 0
    assert result["evidence_hold_reason_counts"]["geography"] == 1


def test_wrong_niche_even_when_city_matches_is_not_research_eligible():
    result = run(contractor(specialties=["dental"]))
    assert result["legacy_ranked_count"] == 1
    assert result["fixture_research_eligible_count"] == 0
    assert result["evidence_hold_reason_counts"]["specialty"] == 1


def test_adjacent_metro_only_research_eligible_under_all_asserted_gates():
    result = run(contractor(metro="Plano"))
    assert result["fixture_research_eligible_count"] == 1
    assert result["commercial_allocations_authorized"] is False


@pytest.mark.parametrize("change, reason", [
    ({"tenant_id": "another"}, "tenant_scope"),
    ({"suppressed": True}, "suppression_unknown_or_present"),
    ({"suppressed": None}, "suppression_unknown_or_present"),
    ({"license_verified": False}, "license_verified"),
    ({"source_rights_verified": None}, "source_rights_verified"),
    ({"territory_verified": False}, "territory_verified"),
    ({"capacity_verified": False}, "capacity_verified"),
    ({"trust_score": None}, "unknown_trust_or_dispatch_history"),
    ({"days_since_dispatch": None}, "unknown_trust_or_dispatch_history"),
    ({"active_dispatches": 3}, "capacity_exhausted"),
    ({"active": False}, "inactive"),
])
def test_historical_rank_never_overrides_evidence_gate(change, reason):
    result = run(contractor(**change))
    assert result["fixture_research_eligible_count"] == 0
    assert result["evidence_hold_reason_counts"][reason] == 1


def test_original_zero_trust_midpoint_bug_is_reported_but_not_proof():
    report = run(contractor(trust_score=0))
    assert report["legacy_ranked_count"] == 1
    assert report["legacy_zero_trust_bonus_count"] == 1
    assert report["supplied_evidence_flags_independently_authenticated"] is False


@pytest.mark.parametrize("change", [
    {"active": 1}, {"trust_score": float("nan")},
    {"trust_score": float("inf")}, {"active_dispatches": -1},
    {"max_concurrent": 0}, {"days_since_dispatch": -2},
    {"max_concurrent": True}, {"metro": None},
    {"specialties": [" "]},
])
def test_unsafe_type_or_numeric_range_rejected(change):
    with pytest.raises(ValueError):
        run(contractor(**change))


def test_empty_specialty_unsafe_even_if_no_candidate():
    with pytest.raises(ValueError, match="original trade required"):
        run(lead={**LEAD, "specialties": []})


def test_more_than_one_hundred_candidates_held_without_scoring():
    with pytest.raises(ValueError, match="bounded"):
        run(*[contractor()] * 101)


def test_absent_contractors_only_reports_unknown_not_negative():
    report = run()
    assert report["tested_synthetic_count"] == 0
    assert report["historical_mean_rank_score"] is None
    assert report["fixture_mean_research_score"] is None
    assert report["real_world_matching_accuracy_measured"] is False
