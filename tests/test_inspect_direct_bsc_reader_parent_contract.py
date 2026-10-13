"""Catalog-only parent RLS probe — no customer, payment or fingerprint rows."""
from scripts import inspect_direct_bsc_reader_parent_contract as parent
import inspect
import pytest


def rows():
    return [
        {"table_name":name,"owner":"empiredb_migrator",
         "rls_enabled":name=="direct_bsc_buyer_capabilities",
         "rls_forced":name=="direct_bsc_buyer_capabilities",
         "rls_policy_count":0,"policy_metadata":[]}
        for name in parent.TABLE_NAMES
    ]


def test_canonical_catalog_exists_only_observation_not_approval():
    report=parent.classify(rows(), [{
        "role":"empiredb_migrator_login","can_login":True,
        "inherit_option":True,"set_option":True,"admin_option":False,
    }],[])
    assert report["status"]=="CATALOG_OBSERVED_REVIEW_REQUIRED"
    assert report["mode"]=="READ_ONLY"
    assert report["production_changes"] is False
    assert report["migration_049_applied"] is False
    assert report["payment_execution"] is False
    assert report["migrator_incoming_memberships"][0]["role"]=="empiredb_migrator_login"


@pytest.mark.parametrize("bad", (
    [], rows()[:3], rows() + rows()[:1],
    [{**r,"table_name":"unknown"} for r in rows()],
))
def test_incomplete_duplicate_or_wrong_parent_catalog_holds(bad):
    assert parent.classify(bad,[],[])["status"]=="HELD_PARENT_CATALOG_MISSING"


def test_requires_exact_readonly_flag(capsys):
    assert parent.main([])==3
    assert parent.main(["--apply"])==3
    assert "HELD_READONLY_FLAG_REQUIRED" in capsys.readouterr().out


def test_catalog_only_query_uses_readonly_transaction_and_no_private_data():
    src=inspect.getsource(parent)
    for required in ("SET TRANSACTION READ ONLY","pg_catalog.pg_policy",
       "pg_catalog.pg_auth_members","pg_catalog.pg_default_acl",
       "pg_catalog.pg_get_expr","pg_catalog.unnest(p.polroles)"):
        assert required in src
    for forbidden in ("FROM public.buyers","FROM public.fulfilment_orders",
        "FROM public.bsc_payment_requests","SELECT * FROM public.",
        "ALTER ROLE ","GRANT SELECT ","REVOKE ","INSERT INTO public.",
        "COMMIT;","CREATE POLICY ","CREATE ROLE ","token_fingerprint"):
        assert forbidden not in src


class FakeCursor:
    def __init__(self):
        self.sql=[]
        self.idx=0
    def __enter__(self): return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):
        self.sql.append((sql,params))
    def fetchone(self):
        return ("empiredb","postgres",False)
    def fetchall(self):
        self.idx+=1
        if self.idx==1: return [
            (name,"empiredb_migrator",name=="direct_bsc_buyer_capabilities",
             name=="direct_bsc_buyer_capabilities",0)
            for name in parent.TABLE_NAMES
        ]
        if self.idx==2:
            return [("bsc_payment_requests","tenant_limit",True,"r",
                     ["PUBLIC"],"(tenant_id = empire_current_tenant_id())")]
        if self.idx==3: return [
            ("empiredb_migrator_login",True,True,True,False)]
        if self.idx==4: return [
            ("public","empiredb_app","SELECT")]
        raise AssertionError("unexpected fetchall")


class FakeConn:
    def __init__(self): self.cur=FakeCursor();self.rollbacks=0
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def cursor(self): return self.cur
    def rollback(self): self.rollbacks+=1


def test_exact_private_policy_metadata_retained_and_no_data_queries(monkeypatch):
    import psycopg
    fake=FakeConn()
    monkeypatch.setattr(psycopg,"connect",lambda *a,**k:fake)
    result=parent.inspect()
    assert result["status"]=="CATALOG_OBSERVED_REVIEW_REQUIRED"
    row=next(x for x in result["parent_table_security"]
             if x["table_name"]=="bsc_payment_requests")
    assert row["policy_metadata"][0]["target_roles"]==["PUBLIC"]
    assert row["policy_metadata"][0]["select_scope_expression"]==(
        "(tenant_id = empire_current_tenant_id())"
    )
    assert len(fake.cur.sql)==7
    assert fake.cur.sql[0][0]=="SET TRANSACTION READ ONLY"
    assert fake.rollbacks==1
