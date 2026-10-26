"""Exact original EmpireDB proof gates. All rows are fixture-only."""
from datetime import datetime, timezone, timedelta

import pytest

from empire_os.canonical_prospect_tenant_handoff import (
    review_existing_prospect_entity_tenant, ProspectHandoffHold,
)

TENANT = "11111111-1111-4111-8111-111111111111"
ENTITY = "22222222-2222-4222-8222-222222222222"
PROSPECT = "33333333-3333-4333-8333-333333333333"
NOW = datetime(2026, 10, 26, 11, 0, tzinfo=timezone.utc)

class FakeReadOnlyCursor:
    def __init__(self, *, link=None, conflicts=None, bindings=None):
        self.link = [(PROSPECT, ENTITY, "verified_source_identity",
                      {"source_ref": "empiredb:prospects:" + PROSPECT}, True)] if link is None else link
        self.conflicts = [] if conflicts is None else conflicts
        self.bindings = [
            (TENANT, ENTITY, "prospect", "crm:authenticated-owner",
             NOW - timedelta(days=1), None)
        ] if bindings is None else bindings
        self.queries = []
    def execute(self, statement, params):
        lowered = " ".join(statement.lower().split())
        assert lowered.startswith("select ")
        assert "%s" in statement
        assert not any(word in lowered for word in ("insert ", "delete ", "update ", "truncate ", "create "))
        self.queries.append((statement, params))
    def fetchall(self):
        query=self.queries[-1][0].lower()
        if "prospect_entity_links" in query:
            return self.link
        if "business_entity_conflicts" in query:
            return self.conflicts
        if "tenant_business_entity_bindings" in query:
            return self.bindings
        raise AssertionError("unexpected table")

def test_valid_exact_source_entity_and_tenant_binding_returns_scoped_report_not_sale():
    c=FakeReadOnlyCursor()
    r=review_existing_prospect_entity_tenant(
        c, prospect_id=PROSPECT, entity_id=ENTITY,
        authenticated_tenant_id=TENANT, as_of=NOW,
    )
    assert len(c.queries)==3
    assert all("WHERE" in q[0] for q in c.queries)
    assert r["prospect_id"]==PROSPECT
    assert r["tenant_id"]==TENANT
    assert r["identity_conflict_absent_at_query_time"] is True
    assert r["tenant_entity_binding_ref"].startswith("empiredb:tenant_business_entity_bindings:")
    assert not r["gtm_opportunity_link_verified"]
    assert not r["buyer_acceptance_verified"]
    assert not r["authenticated_reader_session_attested_by_this_module"]
    assert not r["outbound_authorized"]
    assert not r["database_writes"]

@pytest.mark.parametrize("kwargs,error", [
    ({"link":[]}, "EXACT_ACTIVE_PROSPECT_ENTITY_LINK_REQUIRED"),
    ({"link":[(PROSPECT,ENTITY,"score_only",{"source_ref":"x"},True)]}, "PROSPECT_ENTITY_SOURCE_MATCH_NOT_VERIFIED"),
    ({"link":[(PROSPECT,ENTITY,"verified_source_identity",{},True)]}, "PROSPECT_ENTITY_SOURCE_MATCH_NOT_VERIFIED"),
    ({"link":[(PROSPECT,ENTITY,"verified_source_identity",{"source_ref":"x"},False)]}, "PROSPECT_ENTITY_SOURCE_MATCH_NOT_VERIFIED"),
    ({"conflicts":[("uuid-conflict",)]}, "OPEN_IDENTITY_CONFLICT_HOLD"),
    ({"bindings":[]}, "ACTIVE_TENANT_BUSINESS_BINDING_REQUIRED"),
    ({"bindings":[(TENANT,ENTITY,"prospect","x",NOW,None),(TENANT,ENTITY,"customer","y",NOW,None)]}, "ACTIVE_TENANT_BUSINESS_BINDING_REQUIRED"),
])
def test_identity_and_scope_fail_closed(kwargs,error):
    c=FakeReadOnlyCursor(**kwargs)
    with pytest.raises(ProspectHandoffHold,match=error):
        review_existing_prospect_entity_tenant(
            c, prospect_id=PROSPECT, entity_id=ENTITY,
            authenticated_tenant_id=TENANT, as_of=NOW,
        )

def test_untrusted_ids_and_clock_rejected_before_database_read():
    cases=[{"prospect_id":"not-uuid"}, {"entity_id":"bad"},
           {"authenticated_tenant_id":""}, {"as_of":datetime(2026,10,26)}]
    for override in cases:
        c=FakeReadOnlyCursor()
        kw=dict(prospect_id=PROSPECT, entity_id=ENTITY,
                authenticated_tenant_id=TENANT, as_of=NOW)
        kw.update(override)
        with pytest.raises(ProspectHandoffHold):
            review_existing_prospect_entity_tenant(c,**kw)
        assert c.queries==[]

def test_one_row_prospect_binding_does_not_confirm_any_order_or_buyer():
    r=review_existing_prospect_entity_tenant(
        FakeReadOnlyCursor(), prospect_id=PROSPECT, entity_id=ENTITY,
        authenticated_tenant_id=TENANT, as_of=NOW,
    )
    assert r["payment_authorized"] is False
    assert r["commercial_terms_authorized"] is False
    assert r["execution_authority"] == "NONE"
    assert r["gtm_opportunity_link_verified"] is False


class FakeAuthCursor(FakeReadOnlyCursor):
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def __init__(self, *, bound_tenant=TENANT, allowed_login=True, **kw):
        super().__init__(**kw)
        self.bound_tenant=bound_tenant
        self.allowed_login=allowed_login
    def execute(self, statement, params=None):
        self.queries.append((statement, params))
        if "prospect_entity_links" in statement or "business_entity_conflicts" in statement or "tenant_business_entity_bindings" in statement:
            assert params
            assert statement.lstrip().lower().startswith("select")
        elif not (
            statement.startswith("SET ") or
            statement.lstrip().startswith("SELECT " )
        ):
            raise AssertionError("mutation attempted")
    def fetchone(self):
        latest=self.queries[-1][0]
        if "pg_catalog.pg_has_role" in latest:
            return (True,False,False,False) if self.allowed_login else (False,False,False,False)
        if "empire_current_tenant_id" in latest:
            return (self.bound_tenant,)
        raise AssertionError("unexpected scalar")

class FakeConnection:
    def __init__(self,cursor):
        self._cursor=cursor
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def cursor(self): return self._cursor

def test_real_signed_crm_membership_and_original_db_role_handoff_fixture(monkeypatch):
    from empire_os import revenue_crm_transport
    # TEST-ONLY fake of the still-unreleased original CRM login contract.
    # Production without the published constant MUST fail closed.
    monkeypatch.delattr(revenue_crm_transport, 'CRM_LOGIN_AUTHORITY_SQL', raising=False)
    monkeypatch.setattr(revenue_crm_transport, 'CRM_LOGIN_AUTHORITY_SQL',
                        'SELECT pg_catalog.pg_has_role(session_user, test_role)', raising=False)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
    from tests.test_revenue_crm_signed_auth import token, NOW as AUTH_NOW, live_membership
    from empire_os.canonical_prospect_tenant_handoff import review_signed_crm_prospect_tenant
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    verifier=SignedCrmTenantVerifier({"issuer-1":public},
       load_membership=live_membership, now=lambda:AUTH_NOW)
    cursor=FakeAuthCursor()
    def factory(dsn, *, connect_timeout):
        assert dsn=="TEST_DSN_NOT_A_REAL_CONNECTION"
        assert connect_timeout==5
        return FakeConnection(cursor)
    result=review_signed_crm_prospect_tenant(
        signed_crm_bearer=token(key,claims={"tenant_id":TENANT}),
        crm_verifier=verifier,
        dedicated_crm_dsn="TEST_DSN_NOT_A_REAL_CONNECTION",
        prospect_id=PROSPECT, entity_id=ENTITY, as_of=NOW,
        connect_factory=factory,
    )
    assert result["signed_crm_active_membership_verified"] is True
    assert result["restricted_db_session_role_and_tenant_checked"] is True
    assert result["real_database_connector_independently_attested"] is False
    assert result["status"]=="INJECTED_CONNECTOR_RESEARCH_ONLY"
    assert not result["gtm_opportunity_link_verified"]
    assert not result["payment_authorized"]
    assert all(not q.lstrip().lower().startswith(("delete ","update ","insert ")) for q,_ in cursor.queries)
    for bound in ("99999999-9999-4999-8999-999999999999",None):
        with pytest.raises(ProspectHandoffHold,match="CRM_SESSION_TENANT_SCOPE_MISMATCH"):
            review_signed_crm_prospect_tenant(
                signed_crm_bearer=token(key,claims={"tenant_id":TENANT}),
                crm_verifier=verifier,
                dedicated_crm_dsn="TEST_DSN_NOT_A_REAL_CONNECTION",
                prospect_id=PROSPECT, entity_id=ENTITY, as_of=NOW,
                connect_factory=lambda *a,**kw: FakeConnection(FakeAuthCursor(bound_tenant=bound)),
            )
    with pytest.raises(ProspectHandoffHold,match="SIGNED_CRM_MEMBERSHIP_NOT_VERIFIED"):
        review_signed_crm_prospect_tenant(
            signed_crm_bearer="unsigned-token",
            crm_verifier=verifier,
            dedicated_crm_dsn="TEST_DSN_NOT_A_REAL_CONNECTION",
            prospect_id=PROSPECT, entity_id=ENTITY, as_of=NOW,
            connect_factory=factory,
        )
    with pytest.raises(ProspectHandoffHold,match="RESTRICTED_CRM_READER_ROLE_NOT_ATTESTED"):
        review_signed_crm_prospect_tenant(
            signed_crm_bearer=token(key,claims={"tenant_id":TENANT}),
            crm_verifier=verifier,
            dedicated_crm_dsn="TEST_DSN_NOT_A_REAL_CONNECTION",
            prospect_id=PROSPECT, entity_id=ENTITY, as_of=NOW,
            connect_factory=lambda *a,**kw: FakeConnection(FakeAuthCursor(allowed_login=False)),
        )


def test_original_crm_reader_login_check_unreleased_is_hard_hold(monkeypatch):
    from empire_os import revenue_crm_transport
    from empire_os.canonical_prospect_tenant_handoff import review_signed_crm_prospect_tenant
    monkeypatch.delattr(revenue_crm_transport, "CRM_LOGIN_AUTHORITY_SQL", raising=False)
    # No credential is consulted; a missing original role attestation
    # means the adapter itself must not open a database connection.
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_CRM_LOGIN_ATTESTATION_UNRELEASED"):
        review_signed_crm_prospect_tenant(
            signed_crm_bearer="not-a-real-token", crm_verifier=object(),
            dedicated_crm_dsn="TEST_DSN_NOT_A_REAL_CONNECTION",
            prospect_id=PROSPECT, entity_id=ENTITY, as_of=NOW,
            connect_factory=lambda *a,**k: (_ for _ in ()).throw(AssertionError("no connection permitted")),
        )
