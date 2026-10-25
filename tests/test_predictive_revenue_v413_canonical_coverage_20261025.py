"""V4.13 recognition vs cash, original canonical event reader, and fail-closed tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import base64
import json
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_revenue_v413_canonical_coverage import (
    MAX_EVENTS, review_v413_canonical_evidence_coverage_held,
)
from empire_os.predictive_revenue_v412_scenario_twin import (
    RevenueResearchScenario, simulate_revenue_twin_held,
)
from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership

TENANT="00000000-0000-0000-0000-000000000101"
OTHER="00000000-0000-0000-0000-000000000102"
SOURCE="a"*64
NOW=1800000000
DATE=datetime(2026,10,25,tzinfo=timezone.utc)
EVENT_ID="00000000-0000-0000-0000-000000000201"


def b64(raw:bytes)->str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class FakeCursor:
    def __init__(self):
        self.rows=iter([
            ("empire_predictive_rights_login",),
            ("CANDIDATE_REVIEW_HELD",TENANT,SOURCE,
             "PRIVATE_PREDICTIVE_RESEARCH_ONLY",False,False,False,"none"),
            None,
        ])
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def execute(self,*_):pass
    def fetchone(self):return next(self.rows)


class FakeConnection:
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return FakeCursor()


def credentials(*,member=True,build_twin=True):
    key=Ed25519PrivateKey.generate()
    verifier=SignedCrmTenantVerifier(
        {"original-fixture":key.public_key()},
        load_membership=lambda user,tenant: TenantMembership(
            tenant_id=TENANT,user_id=user,role="owner",
            status="active" if member else "disabled"),
        now=lambda:NOW,
    )
    head=b64(json.dumps({"alg":"EdDSA","typ":"JWT","kid":"original-fixture"}).encode())
    claim=b64(json.dumps({
        "iss":"empire-os","aud":"empire-revenue-crm","sub":"founder-1",
        "tenant_id":TENANT,"scope":"crm:read","iat":NOW-4,
        "nbf":NOW-4,"exp":NOW+120,"jti":"research-v413-event-00001",
    }).encode())
    message=head+"."+claim
    token=message+"."+b64(key.sign(message.encode()))
    reader=EmpireDbHeldSourceRightsReader(
        "isolated-fixture",connect_factory=lambda _: FakeConnection()
    )
    scenario=RevenueResearchScenario(
        source_evidence_digest=SOURCE,sector="roofing",
        intent_velocity_score=85,economic_capacity_score=70,
        observed_need_score=95,timing_alignment_score=75,
        cohort_opportunities=120,prior_observed_opportunities=45,
        prior_observed_wins=4,deal_value_cents=350000,
        fulfilment_cost_per_win_cents=150000,currency_code="GBP",
        median_days_to_cash=42.0,iterations=2000,seed=42,
    )
    twin=(simulate_revenue_twin_held(
        scenario,signed_crm_bearer=token,
        crm_verifier=verifier,source_rights_reader=reader,
    ) if build_twin else None)
    return twin,token,verifier


@pytest.fixture
def env():
    return credentials()


def invoke(env, *, ids=(), event_reader=None, twin=None, verifier=None,token=None,as_of=DATE):
    observed,bearer,auth=env
    args=dict(
        research_twin=twin if twin is not None else observed,
        candidate_event_ids=ids,
        signed_crm_bearer=token if token is not None else bearer,
        crm_verifier=verifier if verifier is not None else auth,
        dedicated_revenue_dsn="owner-supplied-restricted-secret",
        as_of=as_of,
    )
    if event_reader is not None:args["event_reader"]=event_reader
    return review_v413_canonical_evidence_coverage_held(**args)


def fixture_event(*,event_id=EVENT_ID,amount=350000):
    return {
        "schema_version":"empire.predictive_revenue.verified_event_read.v1",
        "status":"SINGLE_REVENUE_EVENT_VERIFIED",
        "canonical_event_ref":"canonical:commercial_events:"+event_id,
        "order_bound":True,"tenant_lineage_matched":True,
        "product_and_price_matched":True,
        "single_event_not_daily_aggregate":True,
        "daily_revenue_census_verified":False,
        "forecast_source_verified":False,
        "revenue_recognition_performed":False,
        "execution_authority":"none","amount_cents":amount,
    }


def test_v413_zero_candidates_unknown_not_zero_revenue(env):
    report=invoke(env)
    assert report["status"]=="NO_EVENT_CANDIDATES_CENSUS_UNKNOWN_HELD"
    assert report["candidate_ids_supplied"]==0
    assert report["actual_revenue_total_cents"] is None
    assert report["cash_collected_total_cents"] is None
    assert report["complete_30_60_90_cohort_census_verified"] is False
    assert report["unverified_events_are_not_zero_revenue"] is True
    assert report["reader_independently_original"] is True


def test_v413_injected_positive_event_never_claims_real_evidence(env):
    report=invoke(
        env,ids=(EVENT_ID,),
        event_reader=lambda **kwargs:fixture_event(),
    )
    assert report["single_event_reads_verified"]==0
    assert report["reader_independently_original"] is False
    assert report["event_ref_fingerprints"]==()
    assert report["revenue_forecast_calibration_eligible"] is False
    assert report["simulated_currency"]=="GBP"
    assert report["observed_canonical_event_currency"] is None
    assert report["recognition_vs_cash_metric_mismatch"] is True


def test_v413_missing_or_unavailable_source_not_mistaken_for_zero(env):
    def missing(**_):
        raise RuntimeError("sensitive production DSN")
    report=invoke(env,ids=(EVENT_ID,),event_reader=missing)
    assert report["status"]=="EVENT_COVERAGE_UNAVAILABLE_HELD"
    assert report["sanitized_rejected_or_missing_count"]==1
    assert "sensitive" not in str(report)
    assert report["actual_revenue_total_cents"] is None


@pytest.mark.parametrize("change", [
    {"schema_version":"noncanonical"},
    {"mode":"EXECUTE"},
    {"simulation_only":False},
    {"execution_authority":"trade"},
    {"licensed_source_admitted":True},
    {"forecast_empirically_calibrated":True},
    {"approved_commercial_forecast":True},
    {"revenue_recognised_cents":0},
    {"currency_code":"UNKNOWN"},
    {"canonical_tenant_id":OTHER},
])
def test_v413_forged_twin_contract_rejected_or_tenant_mismatch(env,change):
    twin=deepcopy(env[0]);twin.update(change)
    with pytest.raises(ValueError):
        invoke(env,twin=twin)


@pytest.mark.parametrize("ids",[
    [EVENT_ID],(EVENT_ID,EVENT_ID),("not-an-id",),
    ("00000000-0000-0000-0000-000000000000",),
    tuple(str(uuid.uuid5(uuid.NAMESPACE_DNS,str(i))) for i in range(MAX_EVENTS+1)),
])
def test_v413_event_scoping_enforces_bounded_unique_known_ids(env,ids):
    with pytest.raises(ValueError,match="BOUNDED_UNIQUE_EVENT"):
        invoke(env,ids=ids)


def test_v413_revoked_original_crm_membership_denied_before_event_reads():
    twin=credentials()[0]
    _,token,verifier=credentials(member=False,build_twin=False)
    invoked=[]
    def forbidden(**kwargs):
        invoked.append(kwargs)
        return fixture_event()
    with pytest.raises(ValueError,match="ACTIVE_CRM"):
        invoke((twin,token,verifier),ids=(EVENT_ID,),event_reader=forbidden)
    assert invoked==[]


def test_v413_no_secret_or_execution_capabilities():
    source=(Path(__file__).resolve().parents[1]/
            "empire_os/predictive_revenue_v413_canonical_coverage.py").read_text()
    for forbidden in (
        "create_engine(", "create_all(", "psycopg.connect(",
        "commit(", "systemctl", "send_message(", "send_email(",
        "redis.Redis(", "router.post(", "include_router(",
        "execute_payment(", "recognize_revenue(", "subprocess.run(",
    ):
        assert forbidden not in source
    assert "read_recognized_revenue_event" in source


def test_v413_no_currency_or_cohort_aggregate_can_be_asserted_from_rev051(env):
    fake=fixture_event(amount=10**15)
    report=invoke(env,ids=(EVENT_ID,),event_reader=lambda **_:fake)
    assert report["observed_metric"]=="single_revenue_recognition_event"
    assert report["forecast_metric"]=="simulated_gross_collectible_cash"
    assert report["complete_30_60_90_cohort_census_verified"] is False
    assert report["revenue_cohort_coverage_verified"] is False
    assert report["revenue_forecast_calibration_eligible"] is False
    assert report["forecast_model_updated"] is False
