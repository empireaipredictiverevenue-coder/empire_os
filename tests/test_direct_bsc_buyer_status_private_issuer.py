"""Isolated issuance tests: bearer only after commit, never in persisted data."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import pytest

from empire_os.direct_bsc_buyer_status import (
    BuyerAccessDenied, fingerprint,
)
from empire_os.direct_bsc_buyer_status_private_issuer import (
    mint_private_buyer_access, PrivateBuyerIssuerPostgresWriter,
    ISSUER_ROLE,ISSUER_SQL,
)

NOW=datetime(2026,10,13,19,30,tzinfo=timezone.utc)
KEY=bytes(range(32))
ORDER=str(uuid4())
REQUEST=str(uuid4())
BASE={
    "id": REQUEST, "fulfilment_order_id":ORDER,
    "settlement_mode":"direct","status":"pending",
    "created_at":NOW-timedelta(minutes=5),
    "expires_at":NOW+timedelta(minutes=65),
}


def mint(request=None,persist=None,**kw):
    return mint_private_buyer_access(
        approved_order_id=ORDER, approved_request_id=REQUEST,
        hmac_key=KEY, payment_request=BASE if request is None else request,
        persist=persist if persist is not None else
          lambda p: {"decision":"created",
                     "token_fingerprint":p["token_fingerprint"]},
        now=NOW,**kw,
    )


def test_issue_one_time_bearer_never_sent_to_db():
    recorded=[]
    def save(p):
        recorded.append(dict(p))
        return {"decision":"created",
                "token_fingerprint":p["token_fingerprint"]}
    token=mint(persist=save)
    assert token.startswith("ecs1_") and len(token)==48
    assert len(recorded)==1
    assert set(recorded[0])=={
        "token_fingerprint","fulfilment_order_id","request_id",
        "issued_at","expires_at",
    }
    assert recorded[0]["token_fingerprint"]==fingerprint(token,KEY)
    assert token not in repr(recorded)
    assert recorded[0]["expires_at"]==NOW+timedelta(minutes=65)


def test_new_token_random_each_time():
    first=mint()
    second=mint()
    assert first != second
    assert fingerprint(first,KEY)!=fingerprint(second,KEY)


@pytest.mark.parametrize("mutation",[
    lambda r:r.update(id=str(uuid4())),
    lambda r:r.update(fulfilment_order_id=str(uuid4())),
    lambda r:r.update(status="approved"),
    lambda r:r.update(status="cancelled"),
    lambda r:r.update(settlement_mode="escrow"),
    lambda r:r.update(created_at=NOW+timedelta(seconds=1)),
    lambda r:r.update(expires_at=NOW),
    lambda r:r.update(expires_at="garbled"),
    lambda r:r.update(created_at=NOW.replace(tzinfo=None)),
])
def test_bad_request_cannot_issue_or_hit_writer(mutation):
    row=deepcopy(BASE);mutation(row)
    calls=[]
    with pytest.raises(BuyerAccessDenied,match="payment_status_unavailable"):
        mint(request=row,persist=lambda p:calls.append(p))
    assert not calls


@pytest.mark.parametrize("ttl",[
    timedelta(0),timedelta(seconds=-1),timedelta(hours=3), 3600,
])
def test_bad_ttl_rejected(ttl):
    calls=[]
    with pytest.raises(BuyerAccessDenied):
        mint(ttl=ttl,persist=lambda p:calls.append(p))
    assert not calls


def test_db_failure_discards_bearer_without_logging_secrets():
    def fail(payload):
        raise RuntimeError("sensitive-db-connection=PASSWORD")
    with pytest.raises(BuyerAccessDenied,match="payment_status_unavailable") as exc:
        mint(persist=fail)
    assert exc.value.__cause__ is None


@pytest.mark.parametrize("response",[
    None,{},{"decision":"existing"},{"decision":"created"},
    {"decision":"created","token_fingerprint":"0"*64},
    {"decision":"created","token_fingerprint":"secret"},
])
def test_insert_denial_duplicate_wrong_digest_or_missing_result_fails_closed(response):
    with pytest.raises(BuyerAccessDenied):
        mint(persist=lambda p:response)


class Cursor:
    def __init__(self,row=None,fail=False):
        self.row=row
        self.fail=fail
        self.executed=[]
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def execute(self,statement,params=None):
        self.executed.append((statement,params))
        if self.fail and statement==ISSUER_SQL:
            raise RuntimeError("password=PRIVATE")
    def fetchone(self):return self.row


class Conn:
    def __init__(self,cursor,fail_commit=False):
        self.cursor_obj=cursor
        self.fail_commit=fail_commit
    def cursor(self):return self.cursor_obj
    def __enter__(self):return self
    def __exit__(self,*a):
        if self.fail_commit:
            raise RuntimeError("transaction not committed")
        return False


def test_dedicated_writer_role_and_fixed_sql_only(monkeypatch):
    monkeypatch.setenv("EMPIREDB_DSN","postgres://app")
    cur=Cursor(({"decision":"created","token_fingerprint":"a"*64},))
    writer=PrivateBuyerIssuerPostgresWriter(
        "postgres://issuer",connect_factory=lambda dsn:Conn(cur))
    data={"token_fingerprint":"a"*64,"fulfilment_order_id":ORDER,
          "request_id":REQUEST,"issued_at":NOW,
          "expires_at":NOW+timedelta(minutes=45)}
    assert writer(data)["decision"]=="created"
    assert [c[0] for c in cur.executed]==[
        "SET LOCAL statement_timeout='2500ms'",
        "SET LOCAL ROLE "+ISSUER_ROLE,
        ISSUER_SQL,
    ]
    assert cur.executed[-1][1]==(
        "a"*64,ORDER,REQUEST,NOW,NOW+timedelta(minutes=45))
    assert not any("ecs1_" in str(c) for c in cur.executed)


def test_writer_rejects_app_dsn_and_empty(monkeypatch):
    monkeypatch.setenv("EMPIREDB_DSN","postgres://app")
    for dsn in ("","postgres://app"):
        with pytest.raises(BuyerAccessDenied):
            PrivateBuyerIssuerPostgresWriter(dsn,connect_factory=lambda s:None)


@pytest.mark.parametrize("result",[
    None,(),(1,2),
])
def test_writer_missing_or_bad_shape_denies(result):
    writer=PrivateBuyerIssuerPostgresWriter(
        "postgres://issuer",
        connect_factory=lambda s:Conn(Cursor(result)))
    with pytest.raises(BuyerAccessDenied):
        writer({
            "token_fingerprint":"a"*64,"fulfilment_order_id":ORDER,
            "request_id":REQUEST,"issued_at":NOW,
            "expires_at":NOW+timedelta(minutes=20),
        })


def test_writer_commit_failure_never_acknowledges_issuance():
    writer=PrivateBuyerIssuerPostgresWriter(
        "postgres://issuer",
        connect_factory=lambda s:Conn(
            Cursor(({"decision":"created",
                    "token_fingerprint":"a"*64},)),
            fail_commit=True,
        ))
    with pytest.raises(BuyerAccessDenied):
        writer({
            "token_fingerprint":"a"*64,"fulfilment_order_id":ORDER,
            "request_id":REQUEST,"issued_at":NOW,
            "expires_at":NOW+timedelta(minutes=20),
        })
