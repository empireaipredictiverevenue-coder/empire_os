"""Scoped CRM lineage. All DB cursors are mock; migration is HELD."""
from __future__ import annotations
from pathlib import Path
import pytest

from empire_os.crm_scoped_lineage_reader import (
    review_signed_scoped_lineage, FUNCTION_SIGNATURE, READ_SQL,
)
from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from tests.test_canonical_prospect_tenant_handoff_20261026 import (
    TENANT, ENTITY, PROSPECT, NOW, FakeConnection,
)
from tests.test_canonical_order_lineage_review_20261026 import OPPORTUNITY, EVENT, ORDER

class ScopedCursor:
    def __init__(self, *, bound_tenant=TENANT, auth=(True,False,False,False),
                 rpc_available=True, rpc_provenance=(True,"s","empiredb_migrator",True),
                 result=None):
        self.bound_tenant=bound_tenant
        self.auth=auth
        self.rpc_available=rpc_available
        self.rpc_provenance=rpc_provenance
        self.result=(PROSPECT,ENTITY,TENANT,OPPORTUNITY,EVENT,"event") if result is None else result
        self.calls=[]
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def execute(self,statement,params=None):
        assert statement.lstrip().startswith("SELECT p.prosecdef,") or statement in (
            "SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout = '4000ms'",
            "SET LOCAL ROLE empire_revenue_crm_reader",
            "SELECT public.empire_current_tenant_id()",
            READ_SQL,
            "SELECT pg_catalog.pg_has_role(session_user, fake_role)"
        )
        if statement==READ_SQL:
            assert params==(PROSPECT,OPPORTUNITY,EVENT,"event")
        self.calls.append((statement,params))
    def fetchone(self):
        stmt=self.calls[-1][0]
        if "pg_has_role" in stmt:return self.auth
        if "empire_current_tenant_id" in stmt:return (self.bound_tenant,)
        raise AssertionError("unexpected fetchone")
    def fetchall(self):
        if "SELECT p.prosecdef," in self.calls[-1][0]:
            return [self.rpc_provenance] if self.rpc_available else []
        assert self.calls[-1][0] == READ_SQL
        return [self.result] if self.result is not False else []

@pytest.fixture
def signed_auth(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from empire_os import revenue_crm_transport
    from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
    from tests.test_revenue_crm_signed_auth import token, NOW as AUTH_NOW, live_membership
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    monkeypatch.setattr(revenue_crm_transport,"CRM_LOGIN_AUTHORITY_SQL",
                        "SELECT pg_catalog.pg_has_role(session_user, fake_role)",
                        raising=False)
    verifier=SignedCrmTenantVerifier({"issuer-1":public},
                                    load_membership=live_membership,now=lambda:AUTH_NOW)
    return verifier,token(key,claims={"tenant_id":TENANT})

def run(signed_auth,cursor,**changes):
    verifier,signed=signed_auth
    kwargs={
        "signed_crm_bearer":signed,
        "crm_verifier":verifier,
        "dedicated_crm_dsn":"TEST_ONLY",
        "prospect_id":PROSPECT,
        "opportunity_id":OPPORTUNITY,
        "evidence_id":EVENT,
        "evidence_kind":"event",
        "as_of":NOW,
        "connect_factory":lambda *a,**kw:FakeConnection(cursor)
    }
    kwargs.update(changes)
    return review_signed_scoped_lineage(**kwargs)

def test_tenant_scoped_rpc_only_no_raw_tables(signed_auth):
    c=ScopedCursor()
    r=run(signed_auth,c)
    assert r["status"]=="INJECTED_SCOPED_RPC_TEST_ONLY"
    assert r["entity_id"]==ENTITY
    assert r["receipt_kind"]=="event"
    assert r["source_rights_verified"] is False
    assert r["buyer_capacity_verified"] is False
    assert r["outbound_authorized"] is False
    assert r["settlement_verified"] is False
    assert r["database_writes"] is False
    assert c.calls[-1][0]==READ_SQL
    assert len(c.calls)==7
    for sql,_ in c.calls:
        assert "FROM public.prospect_entity_links" not in sql
        assert "FROM public.tenant_business_entity_bindings" not in sql
        assert "FROM public.commercial_events" not in sql
        assert "FROM public.fulfilment_orders" not in sql

@pytest.mark.parametrize("settings,error",[
    ({"rpc_available":False},"ORIGINAL_TENANT_SCOPED_RPC_NOT_RELEASED"),
    ({"rpc_provenance":(False,"s","empiredb_migrator",True)},"UNTRUSTED_TENANT_SCOPED_RPC_PROVENANCE"),
    ({"rpc_provenance":(True,"s","unsafe_owner",True)},"UNTRUSTED_TENANT_SCOPED_RPC_PROVENANCE"),
    ({"rpc_provenance":(True,"s","empiredb_migrator",False)},"UNTRUSTED_TENANT_SCOPED_RPC_PROVENANCE"),
    ({"result":False},"ONE_EXACT_AUTHORIZED_LINEAGE_RECEIPT_REQUIRED"),
    ({"bound_tenant":"99999999-9999-4999-8999-999999999999"},"CRM_SESSION_TENANT_SCOPE_MISMATCH"),
    ({"auth":(False,False,False,False)},"RESTRICTED_CRM_READER_ROLE_NOT_ATTESTED"),
    ({"result":(PROSPECT,ENTITY,"99999999-9999-4999-8999-999999999999",OPPORTUNITY,EVENT,"event")},"SCOPED_LINEAGE_RECEIPT_MISMATCH"),
    ({"result":(PROSPECT,ENTITY,TENANT,OPPORTUNITY,EVENT,"order")},"SCOPED_LINEAGE_RECEIPT_MISMATCH"),
])
def test_scoped_rpc_missing_cross_tenant_unsafe_held(signed_auth,settings,error):
    with pytest.raises(ProspectHandoffHold,match=error):
        run(signed_auth,ScopedCursor(**settings))

def test_bad_kind_and_bad_input_uuid_rejected_before_database(signed_auth):
    cur=ScopedCursor()
    with pytest.raises(ProspectHandoffHold,match="UNSUPPORTED_EXACT_LINEAGE_RECEIPT_KIND"):
        run(signed_auth,cur,evidence_kind="payment")
    with pytest.raises(ProspectHandoffHold,match="INVALID_PROSPECT_ID"):
        run(signed_auth,cur,prospect_id="research_review:arbitrary")
    assert cur.calls==[]

def test_owner_held_migration_never_grants_global_raw_read():
    sql=Path(__file__).resolve().parents[1].joinpath(
        "docs/architecture/CRM_SCOPED_LINEAGE_RPC_HELD_20261026.sql"
    ).read_text()
    assert "DO NOT RUN/APPLY" in sql
    assert "SECURITY DEFINER" in sql
    assert "SET search_path = ''" in sql
    assert "public.empire_current_tenant_id()" in sql
    assert "pg_catalog.pg_has_role" in sql
    assert "REVOKE ALL ON FUNCTION public.empire_crm_exact_lineage" in sql
    assert "GRANT EXECUTE ON FUNCTION public.empire_crm_exact_lineage" in sql
    assert "GRANT SELECT ON public.prospect_entity_links" not in sql
    assert "GRANT SELECT ON public.tenant_business_entity_bindings" not in sql
    assert "CREATE ROLE" not in sql

def test_raw_crm_legacy_path_cannot_connect_to_production(signed_auth):
    from empire_os.canonical_prospect_tenant_handoff import review_signed_crm_prospect_tenant
    verifier,signed=signed_auth
    with pytest.raises(ProspectHandoffHold,match="CRM_RAW_LINEAGE_READ_FORBIDDEN_USE_SCOPED_RPC"):
        review_signed_crm_prospect_tenant(
            signed_crm_bearer=signed,crm_verifier=verifier,
            dedicated_crm_dsn="TEST_ONLY",
            prospect_id=PROSPECT,entity_id=ENTITY,as_of=NOW,
            event_id=EVENT,opportunity_id=OPPORTUNITY,
        )
