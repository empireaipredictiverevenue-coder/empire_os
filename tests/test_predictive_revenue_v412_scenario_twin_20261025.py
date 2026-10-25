"""V4.12 Predictive Revenue scenario twin and original CRM integration tests."""
from __future__ import annotations

import base64
import json
import math
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_revenue_v412_scenario_twin import (
    RevenueResearchScenario, HORIZONS, _cash_cdf,
    score_opportunity_for_review, simulate_revenue_twin_held,
    review_cash_twin_drift_held,
)
from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership

TENANT = "00000000-0000-0000-0000-000000000101"
SOURCE = "a" * 64
NOW = 1800000000


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class Cursor:
    def __init__(self, unavailable=False, *, decision="CANDIDATE_REVIEW_HELD"):
        self.items = iter([
            ("empire_predictive_rights_login",),
            (decision, TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY",
             decision == "REVOKED_HELD", False, False, "none"), None,
        ])
        self.unavailable = unavailable

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        if self.unavailable:
            raise RuntimeError("synthetic unavailable DB")

    def fetchone(self):
        return next(self.items)


class Connection:
    def __init__(self, unavailable=False, *, decision="CANDIDATE_REVIEW_HELD"):
        self.cursor_obj = Cursor(unavailable, decision=decision)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_obj


def fixture_credentials(*, active=True, rights="CANDIDATE_REVIEW_HELD"):
    key = Ed25519PrivateKey.generate()
    verifier = SignedCrmTenantVerifier(
        {"fixture-v412": key.public_key()},
        load_membership=lambda user, tenant: TenantMembership(
            tenant_id=TENANT, user_id=user, role="owner",
            status="active" if active else "disabled",
        ),
        now=lambda: NOW,
    )
    header = b64(json.dumps({"alg":"EdDSA","typ":"JWT","kid":"fixture-v412"}).encode())
    claim = b64(json.dumps({
        "iss":"empire-os","aud":"empire-revenue-crm","sub":"founder-1",
        "tenant_id":TENANT,"scope":"crm:read",
        "iat":NOW-10,"nbf":NOW-10,"exp":NOW+120,
        "jti":"v412-synthetic-revenue-0001",
    }).encode())
    signed = header+"."+claim
    bearer = signed+"."+b64(key.sign(signed.encode()))
    reader = EmpireDbHeldSourceRightsReader(
        "fixture",
        connect_factory=lambda _: Connection(
            unavailable=rights=="MISSING", decision=rights
        ),
    )
    return {"signed_crm_bearer":bearer,
            "crm_verifier":verifier, "source_rights_reader":reader}


def scenario(**overrides):
    data = dict(
        source_evidence_digest=SOURCE, sector="roofing",
        intent_velocity_score=85, economic_capacity_score=70,
        observed_need_score=95, timing_alignment_score=75,
        cohort_opportunities=120, prior_observed_opportunities=45,
        prior_observed_wins=4,
        deal_value_cents=350000, fulfilment_cost_per_win_cents=150000,
        research_overhead_cents=15000,
        median_days_to_cash=42.0, cash_lag_log_sigma=.6,
        iterations=2000, seed=42,
    )
    return RevenueResearchScenario(**(data | overrides))


def test_v412_score_35_25_25_15_with_three_nonexecuting_tiers():
    priority = score_opportunity_for_review(scenario())
    assert priority["score"] == 82.25
    assert priority["tier"] == "TIER_2_RESEARCH_REVIEW"
    assert priority["opportunity_commercially_qualified"] is False
    assert score_opportunity_for_review(scenario(
        intent_velocity_score=100, economic_capacity_score=100,
        observed_need_score=100, timing_alignment_score=100,
    ))["tier"] == "TIER_1_FOUNDER_REVIEW"
    assert score_opportunity_for_review(scenario(
        intent_velocity_score=0, economic_capacity_score=0,
        observed_need_score=0, timing_alignment_score=0,
    ))["tier"] == "TIER_3_RESEARCH_NURTURE"


def test_v412_2000_simulations_30_60_90_cash_non_decreasing_and_reproducible():
    c = fixture_credentials()
    first = simulate_revenue_twin_held(scenario(), **c)
    second = simulate_revenue_twin_held(scenario(), **c)
    assert first == second
    assert first["source_rights_decision"] == "CANDIDATE_REVIEW_HELD"
    assert first["mode"] == "SIMULATION"
    assert first["scenario_assumptions"]["channel"] == "ORGANIC_ONLY"
    assert first["scenario_assumptions"]["iterations"] == 2000
    assert first["roas"] is None
    assert first["revenue_recognised_cents"] is None
    for metric in ("gross_cash_cents", "contribution_cents"):
        for percentile in ("p10", "p50", "p90"):
            values = [first["forecast_horizons"][str(t)][f"{percentile}_{metric}"]
                      for t in HORIZONS]
            assert values == sorted(values)
        for t in HORIZONS:
            rec = first["forecast_horizons"][str(t)]
            assert rec[f"p10_{metric}"] <= rec[f"p50_{metric}"] <= rec[f"p90_{metric}"]
    for flag in ("licensed_source_admitted", "causal_identification_verified",
                 "forecast_empirically_calibrated", "confidence_intervals_empirically_validated",
                 "approved_commercial_forecast", "capital_deployment_authorized",
                 "buyer_outreach_authorized", "lead_delivery_authorized",
                 "economic_memory_write_authorized", "redis_publish_authorized"):
        assert first[flag] is False


def test_v412_zero_opportunities_cannot_manufacture_a_buyer():
    result = simulate_revenue_twin_held(scenario(
        cohort_opportunities=0, research_overhead_cents=0
    ), **fixture_credentials())
    for rec in result["forecast_horizons"].values():
        assert rec["p90_gross_cash_cents"] == 0
        assert rec["p10_contribution_cents"] == 0


def test_v412_low_lag_moves_cash_earlier_without_changing_forecast_auth():
    earlier = simulate_revenue_twin_held(
        scenario(median_days_to_cash=5), **fixture_credentials())
    later = simulate_revenue_twin_held(
        scenario(median_days_to_cash=180), **fixture_credentials())
    assert (earlier["forecast_horizons"]["30"]["p50_gross_cash_cents"]
            > later["forecast_horizons"]["30"]["p50_gross_cash_cents"])
    assert earlier["approved_commercial_forecast"] is False


def test_v412_missing_or_revoked_source_still_simulation_only():
    for rights in ("MISSING", "REVOKED_HELD"):
        rec = simulate_revenue_twin_held(scenario(), **fixture_credentials(rights=rights))
        assert rec["source_rights_decision"].endswith("_HELD")
        assert rec["licensed_source_admitted"] is False
        assert rec["execution_authority"] == "none"


@pytest.mark.parametrize("field,value", [
    ("source_evidence_digest", "not-a-digest"),
    ("sector", ""),
    ("intent_velocity_score", -1),
    ("intent_velocity_score", 101),
    ("intent_velocity_score", math.nan),
    ("economic_capacity_score", math.inf),
    ("observed_need_score", True),
    ("cohort_opportunities", -1),
    ("cohort_opportunities", 100001),
    ("cohort_opportunities", True),
    ("prior_observed_opportunities", 3),
    ("deal_value_cents", 0),
    ("fulfilment_cost_per_win_cents", 9999999),
    ("research_overhead_cents", -1),
    ("median_days_to_cash", 0),
    ("cash_lag_log_sigma", 0),
    ("cash_lag_log_sigma", math.inf),
    ("iterations", 1999),
    ("iterations", 10001),
    ("seed", -1),
    ("acquisition_channel", "PAID"),
    ("paid_media_budget_cents", 1),
])
def test_v412_invalid_scenario_assumption_rejected(field, value):
    with pytest.raises(ValueError):
        scenario(**{field:value}).validate()


def test_v412_untrusted_identity_rejected_even_for_synthetic_scenario():
    with pytest.raises(ValueError, match="crm_identity"):
        simulate_revenue_twin_held(scenario(), **fixture_credentials(active=False))


def test_v412_require_canonical_scenario_type():
    with pytest.raises(TypeError):
        simulate_revenue_twin_held({}, **fixture_credentials())


def test_v412_cash_lag_cdf_bounded_and_increasing():
    observed = [_cash_cdf(t, 38., 0.5) for t in HORIZONS]
    assert observed == sorted(observed)
    assert all(0 <= x <= 1 for x in observed)


def test_v412_no_new_services_db_routes_money_or_real_outbound():
    module = (Path(__file__).resolve().parents[1] /
              "empire_os/predictive_revenue_v412_scenario_twin.py").read_text()
    for forbidden in (
        "create_engine(", "create_all(", "psycopg.connect(",
        "app.include_router(", "router.post(", "send_message(",
        "redis.Redis(", "systemctl", "execute_payment(", "send_email(",
        "request.post(", "ApplicationBuilder(", "capital_execute(",
    ):
        assert forbidden not in module


def test_v412_reflector_flags_large_variance_without_learning_or_money_actions():
    forecast = simulate_revenue_twin_held(scenario(), **fixture_credentials())
    p50 = forecast["forecast_horizons"]["60"]["p50_gross_cash_cents"]
    assert p50 > 0
    report = review_cash_twin_drift_held(
        forecast, horizon_days=60, observed_cash_cents=p50 * 2,
        observation_evidence_digest="b" * 64,
    )
    assert report["status"] == "RECALIBRATION_RESEARCH_REVIEW_HELD"
    assert report["research_threshold_12_percent_exceeded"] is True
    assert report["variance_ratio"] == 1.0
    for key in ("actual_receipt_independently_verified", "causal_effect_identified",
                "automatic_retraining", "auto_dag_reweight",
                "outreach_authorized", "capital_allocation_authorized",
                "forecast_promoted_to_commercial"):
        assert report[key] is False


def test_v412_reflector_zero_forecast_never_divides_or_claims_drift():
    forecast = simulate_revenue_twin_held(scenario(
        cohort_opportunities=0
    ), **fixture_credentials())
    report = review_cash_twin_drift_held(
        forecast, horizon_days=30, observed_cash_cents=50000,
        observation_evidence_digest="b" * 64,
    )
    assert report["variance_ratio"] is None
    assert report["research_threshold_12_percent_exceeded"] is False
    assert report["status"] == "ZERO_SYNTHETIC_P50_NOT_COMPARABLE_HELD"


@pytest.mark.parametrize("field,value", [
    ("horizon_days", 31),
    ("horizon_days", True),
    ("observed_cash_cents", -1),
    ("observed_cash_cents", True),
    ("observation_evidence_digest", "external-receipt"),
])
def test_v412_reflector_rejects_noncanonical_observation(field, value):
    forecast = simulate_revenue_twin_held(scenario(), **fixture_credentials())
    args = {"horizon_days":60, "observed_cash_cents":100000,
            "observation_evidence_digest":"c"*64}
    args[field] = value
    with pytest.raises(ValueError):
        review_cash_twin_drift_held(forecast, **args)


def test_v412_reflector_refuses_promoted_forecast_forced_by_caller():
    forecast = simulate_revenue_twin_held(scenario(), **fixture_credentials())
    forecast["approved_commercial_forecast"] = True
    with pytest.raises(ValueError, match="UNTRUSTED"):
        review_cash_twin_drift_held(
            forecast, horizon_days=90, observed_cash_cents=1000,
            observation_evidence_digest="d" * 64,
        )
