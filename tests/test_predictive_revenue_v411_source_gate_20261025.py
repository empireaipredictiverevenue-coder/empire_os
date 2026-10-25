"""Predictive Revenue V4.11: native signed CRM -> held source custody tests.

No production keys, live DB logins, source grants or revenue claims.
"""
from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.predictive_revenue_v411_source_gate import (
    PredictiveRevenueSourceHold, SCHEMA, review_revenue_source_candidate_held,
)
from empire_os.predictive_cloud_v410_rights_reader import (
    EmpireDbHeldSourceRightsReader,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership

TENANT = "00000000-0000-0000-0000-000000000101"
SOURCE = "a" * 64
NOW = 1800000000


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def jwt(key: Ed25519PrivateKey, tenant: str = TENANT) -> str:
    head = b64(json.dumps({"alg": "EdDSA", "typ": "JWT", "kid": "fixture"}).encode())
    claims = b64(json.dumps({
        "iss": "empire-os", "aud": "empire-revenue-crm", "sub": "founder-1",
        "tenant_id": tenant, "scope": "crm:read", "iat": NOW - 2,
        "nbf": NOW - 2, "exp": NOW + 200,
        "jti": "research-v411-jti-000001",
    }).encode())
    unsigned = head + "." + claims
    return unsigned + "." + b64(key.sign(unsigned.encode()))


def verifier(*, membership="active", key: Ed25519PrivateKey | None = None):
    key = key or Ed25519PrivateKey.generate()
    v = SignedCrmTenantVerifier(
        {"fixture": key.public_key()},
        load_membership=lambda _sub, _tenant: (
            TenantMembership(
                tenant_id=TENANT, user_id="founder-1",
                role="owner", status=membership,
            )
        ),
        now=lambda: NOW,
    )
    return v, jwt(key)


class Cursor:
    def __init__(self, row, *, login="empire_predictive_rights_login"):
        self.values = iter([(login,), row, None])
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchone(self):
        return next(self.values)


class Connection:
    def __init__(self, cursor):
        self.cur = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cur


def original_reader(row=None, *, login="empire_predictive_rights_login",
                    unavailable=False):
    if row is None:
        row = ("CANDIDATE_REVIEW_HELD", TENANT, SOURCE,
               "PRIVATE_PREDICTIVE_RESEARCH_ONLY",
               False, False, False, "none")
    def connect(_dsn):
        if unavailable:
            raise RuntimeError("fake: no production 066 migration")
        return Connection(Cursor(row, login=login))
    return EmpireDbHeldSourceRightsReader("fixture-dsn", connect_factory=connect)


def invoke(v=None, token=None, reader=None, digest=SOURCE):
    if v is None or token is None:
        v, token = verifier()
    return review_revenue_source_candidate_held(
        crm_bearer=token,
        crm_verifier=v,
        source_rights_reader=reader if reader is not None else original_reader(),
        source_evidence_digest=digest,
    )


def test_v411_native_crm_membership_and_rights_candidate_still_held():
    record = invoke()
    assert record["schema_version"] == SCHEMA
    assert record["mode"] == "OBSERVE"
    assert record["canonical_tenant_id"] == TENANT
    assert record["original_signed_crm_membership_verified"] is True
    assert record["restricted_empiredb_rights_reader_checked"] is True
    assert record["rights_decision"] == "CANDIDATE_REVIEW_HELD"
    for flag in (
        "real_source_rights_independently_verified", "revenue_opportunity_admitted",
        "customer_forecast_verified", "commercial_offer_authorized",
        "buyer_outreach_authorized", "lead_delivery_authorized",
        "redis_publish_authorized", "economic_memory_write_authorized",
        "paid_traffic_authorized", "trading_authorized",
        "funds_movement_authorized",
    ):
        assert record[flag] is False
    assert record["recognised_revenue_cents"] is None
    assert record["execution_authority"] == "none"


def test_v411_unavailable_real_rights_schema_stays_held():
    record = invoke(reader=original_reader(unavailable=True))
    assert record["rights_decision"] == "SOURCE_RIGHTS_READER_UNAVAILABLE_HELD"
    assert record["restricted_empiredb_rights_reader_checked"] is False
    assert record["revenue_opportunity_admitted"] is False


@pytest.mark.parametrize("state,revoked", [
    ("NO_SOURCE_RIGHTS_HELD", False),
    ("PENDING_HELD", False),
    ("CANDIDATE_REVIEW_HELD", False),
    ("EXPIRED_HELD", False),
    ("FUTURE_EVIDENCE_HELD", False),
    ("REVOKED_HELD", True),
])
def test_v411_all_valid_source_states_block_commercial_admission(state, revoked):
    row = (state, TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY",
           revoked, False, False, "none")
    result = invoke(reader=original_reader(row))
    assert result["rights_decision"] == state
    assert result["revenue_opportunity_admitted"] is False
    assert result["commercial_offer_authorized"] is False


@pytest.mark.parametrize("row", [
    ("APPROVED", TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY", False, False, False, "none"),
    ("CANDIDATE_REVIEW_HELD", TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY", False, True, False, "none"),
    ("CANDIDATE_REVIEW_HELD", TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY", False, False, True, "none"),
    ("CANDIDATE_REVIEW_HELD", TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY", False, False, False, "trading"),
    ("REVOKED_HELD", TENANT, SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY", False, False, False, "none"),
    ("CANDIDATE_REVIEW_HELD", "00000000-0000-0000-0000-000000000102", SOURCE, "PRIVATE_PREDICTIVE_RESEARCH_ONLY", False, False, False, "none"),
    ("CANDIDATE_REVIEW_HELD", TENANT, SOURCE, "OUTBOUND_MARKETING", False, False, False, "none"),
])
def test_v411_inconsistent_or_promoting_database_reply_fails_closed(row):
    result = invoke(reader=original_reader(row))
    assert result["rights_decision"] == "SOURCE_RIGHTS_READER_UNAVAILABLE_HELD"
    assert result["revenue_opportunity_admitted"] is False


def test_v411_untrusted_rights_login_returns_unavailable_held():
    report = invoke(reader=original_reader(login="postgres"))
    assert report["rights_decision"] == "SOURCE_RIGHTS_READER_UNAVAILABLE_HELD"


@pytest.mark.parametrize("digest", ["not-a-digest", "F"*64, "", None])
def test_v411_invalid_source_digest_rejected_before_crm_or_db(digest):
    with pytest.raises(PredictiveRevenueSourceHold, match="source_digest_invalid"):
        invoke(digest=digest)


def test_v411_reject_untrusted_crm_verifier_or_rights_reader():
    v, token = verifier()
    with pytest.raises(PredictiveRevenueSourceHold, match="original_crm"):
        review_revenue_source_candidate_held(
            crm_bearer=token, crm_verifier=object(),
            source_rights_reader=original_reader(),
            source_evidence_digest=SOURCE,
        )
    with pytest.raises(PredictiveRevenueSourceHold, match="original_empiredb"):
        review_revenue_source_candidate_held(
            crm_bearer=token, crm_verifier=v,
            source_rights_reader=object(),
            source_evidence_digest=SOURCE,
        )


def test_v411_requires_real_crm_signed_bearer_and_active_membership():
    v, token = verifier(membership="disabled")
    with pytest.raises(PredictiveRevenueSourceHold, match="crm_identity"):
        invoke(v=v, token=token)
    v, token = verifier()
    with pytest.raises(PredictiveRevenueSourceHold, match="crm_identity"):
        invoke(v=v, token=token[:-3] + "abc")
    with pytest.raises(PredictiveRevenueSourceHold, match="signed_crm"):
        review_revenue_source_candidate_held(
            crm_bearer="", crm_verifier=v,
            source_rights_reader=original_reader(),
            source_evidence_digest=SOURCE,
        )


def test_v411_cannot_spoof_a_different_tenant():
    v, token = verifier()
    forged = jwt(Ed25519PrivateKey.generate(),
                 tenant="00000000-0000-0000-0000-000000000102")
    with pytest.raises(PredictiveRevenueSourceHold, match="crm_identity"):
        invoke(v=v, token=forged)


def test_v411_no_credentials_or_network_or_mutating_routes():
    source = (__import__("pathlib").Path(__file__).resolve().parents[1]
              / "empire_os/predictive_revenue_v411_source_gate.py").read_text()
    for forbidden in (
        "os.environ", "create_engine(", "create_all(", "router.post(",
        "app.include_router(", "send_message(", "requests.post(", "redis.Redis(",
        "psycopg.connect(", "commit(", "execute_payment(", "trade_order(",
    ):
        assert forbidden not in source
