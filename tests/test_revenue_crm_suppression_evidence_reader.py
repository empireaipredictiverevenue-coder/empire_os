"""Contract tests for restricted CRM suppression hit reader: no actual DB."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from empire_os.revenue_crm_suppression_evidence_reader import (
    ChannelEvidenceSourceUnavailable,
    PostgresCrmSuppressionEvidenceReader,
    SUPPRESSION_SQL,
)
from empire_os.revenue_crm_channel_evidence import review_channel_evidence

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
PID = "00000000-0000-0000-0000-000000000201"


class FakeCursor:
    def __init__(self, data):
        self.data = data
        self.pending = None
    def __enter__(self): return self
    def __exit__(self, *unused): return False
    def execute(self, sql, params=None):
        self.data["queries"].append((sql, params))
        if "pg_catalog.pg_has_role(session_user" in sql:
            self.pending = self.data.get("authority", (True, False, False, False))
        elif sql == "SELECT public.empire_current_tenant_id()":
            self.pending = (self.data.get("tenant", TENANT),)
        elif "SELECT p.prosecdef,p.provolatile,r.rolname" in sql:
            assert params == ("public.empire_crm_prospect_suppression_hit(uuid,text)",)
            self.pending = self.data.get("owner", (True, "s", "empiredb_migrator"))
        elif "to_regprocedure" in sql:
            assert params == ("public.empire_crm_prospect_suppression_hit(uuid,text)",)
            self.pending = (
                "public.empire_crm_prospect_suppression_hit(uuid,text)"
                if self.data.get("function", True) else None,
            )
        elif sql == SUPPRESSION_SQL:
            assert params == (PID, "sms")
            self.pending = (self.data.get("value", "UNKNOWN"),)
        else:
            assert sql.startswith("SET "), sql
    def fetchone(self):
        return self.pending


class FakeConnection:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *unused): return False
    def cursor(self): return FakeCursor(self.data)


def reader(data):
    return PostgresCrmSuppressionEvidenceReader(
        "FAKE_DSN_NO_NETWORK", tenant_id=TENANT,
        connect_factory=lambda _: FakeConnection(data),
    )


def check(proof):
    return review_channel_evidence(
        {"tenant_id": TENANT, "prospect_id": PID, "prospect_status": "new"},
        channel=proof.channel,
        evidence=proof,
        now=datetime.now(timezone.utc),
    )


def test_verified_suppression_hit_blocks_sms_without_exposing_phone():
    db = {"queries": [], "value": "SUPPRESSED"}
    proof = reader(db).suppression_proof(prospect_id=PID, channel="sms")
    assert proof.suppression_state == "suppressed"
    assert proof.consent_state == "unknown"
    assert proof.identity_bound is False
    result = check(proof)
    assert result["review_status"] == "BLOCKED_BY_EVIDENCE"
    assert "CANONICAL_SUPPRESSION_MATCH" in result["blockers"]
    assert result["send_authorized"] is False
    assert "contact" not in str(proof.suppression_evidence_ref)
    assert "phone" not in str(result)
    statements = [sql for sql, _ in db["queries"]]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert SUPPRESSION_SQL in statements
    assert not any("SELECT normalized_contact" in q for q in statements)
    assert not any("outbound_suppressions" in q for q in statements)
    assert not any("INSERT " in q or "UPDATE " in q or "DELETE " in q for q in statements)


def test_unknown_hit_never_proves_suppression_clearance():
    db = {"queries": [], "value": "UNKNOWN"}
    proof = reader(db).suppression_proof(prospect_id=PID, channel="sms")
    result = check(proof)
    assert proof.suppression_state == "unknown"
    assert result["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert "CANONICAL_SUPPRESSION_UNKNOWN" in result["blockers"]
    assert result["send_authorized"] is False


@pytest.mark.parametrize("state", ["NOT_FOUND", "CLEAR", "ALLOWED", True, False, None, ""])
def test_no_other_response_can_claim_eligibility(state):
    db = {"queries": [], "value": state}
    with pytest.raises(ChannelEvidenceSourceUnavailable):
        reader(db).suppression_proof(prospect_id=PID, channel="sms")


def test_other_channels_do_not_query_db_and_remain_unknown():
    db = {"queries": []}
    for channel in ("email", "web_push"):
        proof = reader(db).suppression_proof(prospect_id=PID, channel=channel)
        assert proof.suppression_state == "unknown"
        assert check(proof)["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert db["queries"] == []


@pytest.mark.parametrize("overrides", [
    {"tenant": OTHER},
    {"authority": (False, False, False, False)},
    {"authority": (True, True, False, False)},
    {"authority": (True, False, True, False)},
    {"authority": (True, False, False, True)},
    {"function": False},
    {"owner": (False, "s", "empiredb_migrator")},
    {"owner": (True, "v", "empiredb_migrator")},
    {"owner": (True, "s", "untrusted_owner")},
])
def test_wrong_login_tenant_or_unprovisioned_function_fails_closed(overrides):
    db = {"queries": [], **overrides}
    with pytest.raises(ChannelEvidenceSourceUnavailable):
        reader(db).suppression_proof(prospect_id=PID, channel="sms")
    assert not any(sql == SUPPRESSION_SQL for sql, _ in db["queries"])


def test_reader_rejects_missing_dsn_invalid_uuid_or_unsupported_channel():
    with pytest.raises(ChannelEvidenceSourceUnavailable):
        PostgresCrmSuppressionEvidenceReader("", tenant_id=TENANT)
    with pytest.raises(ChannelEvidenceSourceUnavailable):
        PostgresCrmSuppressionEvidenceReader("fake", tenant_id="not-uuid",
                                            connect_factory=lambda *_: None)
    db = {"queries": []}
    with pytest.raises(ChannelEvidenceSourceUnavailable):
        reader(db).suppression_proof(prospect_id="raw-phone", channel="sms")
    with pytest.raises(ChannelEvidenceSourceUnavailable):
        reader(db).suppression_proof(prospect_id=PID, channel="voice")
    assert db["queries"] == []


def test_driver_error_sanitised():
    def fail(_):
        raise RuntimeError("SECRET_RAW_CONNECTION_STRING")
    repo = PostgresCrmSuppressionEvidenceReader(
        "SECRET_RAW_CONNECTION_STRING", tenant_id=TENANT,
        connect_factory=fail,
    )
    with pytest.raises(ChannelEvidenceSourceUnavailable) as err:
        repo.suppression_proof(prospect_id=PID, channel="sms")
    assert "SECRET_RAW_CONNECTION_STRING" not in str(err.value)


def test_existing_crm_api_integration_reports_hit_without_live_activation():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.revenue_crm_api import (
        AuthenticatedRevenueCrmRead, create_revenue_crm_router,
    )
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    repo = PostgresRevenueCrmRepository(
        "TEST_DSN_NO_NETWORK", tenant_id=TENANT,
        connect_factory=lambda *_: None,
    )
    repo.prospect = lambda p: (
        {"tenant_id": TENANT, "prospect_id": PID, "prospect_status": "new"}
        if p == PID else None
    )
    app = FastAPI()
    db = {"queries": [], "value": "SUPPRESSED"}
    access = AuthenticatedRevenueCrmRead(tenant_id=TENANT, repository=repo)
    evidence_reader = reader(db)
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=lambda request: access,
        resolve_authenticated_channel_evidence=lambda request, p, channel:
            evidence_reader.suppression_proof(prospect_id=p, channel=channel),
    ))
    r = TestClient(app).get(
        f"/v1/revenue-crm/prospects/{PID}/channel-evidence-preview",
        headers={"X-Consent":"true","X-Suppression-Cleared":"true"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["channels"]["sms"]["review_status"] == "BLOCKED_BY_EVIDENCE"
    assert body["channels"]["email"]["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert body["channels"]["web_push"]["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert all(x["send_authorized"] is False for x in body["channels"].values())
    assert body["send_authorized"] is False
    assert "@" not in r.text
    assert sum(sql == SUPPRESSION_SQL for sql, _ in db["queries"]) == 1


def test_missing_db_function_yields_503_without_allowing_contact():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.revenue_crm_api import (
        AuthenticatedRevenueCrmRead, create_revenue_crm_router,
    )
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    repo = PostgresRevenueCrmRepository(
        "TEST_DSN_NO_NETWORK", tenant_id=TENANT,
        connect_factory=lambda *_: None,
    )
    repo.prospect = lambda p: (
        {"tenant_id": TENANT, "prospect_id": PID, "prospect_status": "new"}
        if p == PID else None
    )
    db = {"queries": [], "function": False}
    evidence_reader = reader(db)
    app = FastAPI()
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=lambda request: AuthenticatedRevenueCrmRead(
            tenant_id=TENANT, repository=repo,
        ),
        resolve_authenticated_channel_evidence=lambda request, p, channel:
            evidence_reader.suppression_proof(prospect_id=p, channel=channel),
    ))
    r = TestClient(app).get(
        f"/v1/revenue-crm/prospects/{PID}/channel-evidence-preview"
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "crm_channel_reader_unavailable"
    assert not any(sql == SUPPRESSION_SQL for sql, _ in db["queries"])
