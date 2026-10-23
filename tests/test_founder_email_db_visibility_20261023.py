"""Pure safety proofs: denied RLS views never turn zero counts into clearance."""
from scripts.audit_founder_email_db_visibility_20261023 import policy_all_rows_visible


def test_unrestricted_role_select_policy_is_full_visibility():
    assert policy_all_rows_visible(True,True,[("r",True,"true",[123])],123)


def test_no_rls_full_visibility_if_rls_disabled():
    assert policy_all_rows_visible(False,False,[],123)


def test_rls_filters_or_absence_fail_closed():
    assert not policy_all_rows_visible(True,True,[],123)
    assert not policy_all_rows_visible(True,False,[("r",True,"true",[123])],123)
    assert not policy_all_rows_visible(True,True,[("r",True,"tenant_id = 1",[123])],123)
    assert not policy_all_rows_visible(True,True,[("r",True,"true",[999])],123)
    assert not policy_all_rows_visible(True,True,[("r",False,"tenant_id = 1",[999]),
                                                ("r",True,"true",[123])],123)


def test_public_unrestricted_policy_and_irrelevant_insert_policy():
    assert policy_all_rows_visible(True,True,[("*",True,None,[0]),
                                               ("a",False,"false",[123])],123)


class FakeCursor:
    def __init__(self, *, restricted=False):
        self.restricted=restricted
        self.last_query=""
        self.calls=[]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query, params=None):
        self.last_query=query
        self.calls.append((query,params))
    def fetchone(self):
        q=self.last_query
        if "FROM pg_catalog.pg_roles" in q:
            return ("empire_outbound_sender","on",123,False,False)
        if "has_table_privilege" in q:
            return (True,)
        if "FROM pg_catalog.pg_class" in q:
            return (True,False,True)
        if "FROM public.outbound_suppressions" in q:
            return (0,)
        if "FROM public.outbound_intents" in q:
            return (0,)
        raise AssertionError("unexpected query")
    def fetchall(self):
        assert "FROM pg_catalog.pg_policy" in self.last_query
        return [("r",True,"tenant_id = 1" if self.restricted else "true",[123])]


class FakeConnection:
    def __init__(self,*,restricted=False):
        self.cur=FakeCursor(restricted=restricted)
        self.rolled_back=False
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def cursor(self):
        return self.cur
    def rollback(self):
        self.rolled_back=True


def test_nine_original_account_counts_are_redacted_and_never_approved(tmp_path,monkeypatch):
    from scripts import audit_founder_email_db_visibility_20261023 as audit
    monkeypatch.setattr(audit,"load_ledger",lambda root:{
        "anchors":[(f"Firm {i}",f"private{i}@example.net",f"gmail{i}") for i in range(9)],
    })
    secret=tmp_path/"outbound.env"
    secret.write_text('EMPIRE_OUTBOUND_SENDER_DSN="postgres://secret-owner@example.net/db"\n')
    secret.chmod(0o600)
    con=FakeConnection()
    report=audit.run(root=tmp_path,env=secret,connect=lambda *args,**kw:con)
    assert report["status"]=="CANONICAL_READ_ONLY_COUNTS_OBSERVED_NOT_SEND_CLEARANCE"
    assert report["database_login_verified"] is True
    assert report["full_rls_visibility_verified"] is True
    assert len(report["checked"])==9
    assert all(x["canonical_intent_matches"]==0 for x in report["checked"])
    assert not report["new_send_authorized"] and not report["outbound_sent"]
    assert not report["database_writes"]
    assert "private0@" not in str(report)
    assert "secret-owner" not in str(report)
    assert con.rolled_back
    assert len([q for q,p in con.cur.calls if "FROM public.outbound_intents" in q])==9


def test_rls_restriction_prevents_any_recipient_count_queries(tmp_path,monkeypatch):
    from scripts import audit_founder_email_db_visibility_20261023 as audit
    monkeypatch.setattr(audit,"load_ledger",lambda root:{
        "anchors":[(f"Firm {i}",f"private{i}@example.net",f"gmail{i}") for i in range(9)],
    })
    secret=tmp_path/"outbound.env"
    secret.write_text('EMPIRE_OUTBOUND_SENDER_DSN="postgres://safe"\n')
    secret.chmod(0o600)
    con=FakeConnection(restricted=True)
    result=audit.run(root=tmp_path,env=secret,connect=lambda *args,**kw:con)
    assert result["status"]=="HELD_CANONICAL_VISIBILITY_UNVERIFIED"
    assert result["historical_email_clearance"]=="NOT_VERIFIED"
    assert "checked" not in result
    assert not any("FROM public.outbound_suppressions" in q for q,p in con.cur.calls)
    assert not result["outbound_sent"] and not result["new_send_authorized"]
