"""First-party buyer status key custody and one-time checkout receipt tests."""
import os
from pathlib import Path
import stat
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import pytest

from empire_os import direct_bsc_status_key_custody as keys
from empire_os.direct_bsc_buyer_receipt_bridge import with_new_buyer_status_receipt
from empire_os.direct_bsc_buyer_status import fingerprint

NOW=datetime.now(timezone.utc)
KEY=bytes(range(32))
OID=str(uuid4());RID=str(uuid4())
RESPONSE={
    "decision":"order_created","order_id":OID,"settlement_mode":"direct",
    "payment_request_created":True,"payment_request_status":"pending",
    "payment_request_id":RID,"payment_instructions_ready":False,
    "actual_revenue":False,
}
ROW={
    "id":RID,"fulfilment_order_id":OID,"settlement_mode":"direct",
    "status":"pending","created_at":NOW-timedelta(minutes=3),
    "expires_at":NOW+timedelta(minutes=37),
}


def call(overrides=None,row=None,persist=None,enabled=True):
    saved=[]
    def store(p):
        saved.append(p)
        return {"decision":"created","token_fingerprint":p["token_fingerprint"]}
    result=with_new_buyer_status_receipt(
        RESPONSE if overrides is None else {**RESPONSE,**overrides},
        enabled=enabled,hmac_key=KEY,
        request_lookup=lambda rid:ROW if row is None else row,
        persist_fingerprint=persist or store,now=NOW,
    )
    return result,saved


def test_key_path_never_generates_implicitly(tmp_path):
    empty=tmp_path/"missing.key"
    with pytest.raises(ValueError):
        keys.read_key(empty,expected_owner=os.geteuid())
    assert not empty.exists()
    assert keys.main([])==0


def test_explicit_installer_only_and_no_secret_printed(tmp_path,monkeypatch):
    f=tmp_path/"key"
    monkeypatch.setattr(keys,"KEY_FILE",f)
    monkeypatch.setattr(keys.os,"geteuid",lambda:0)
    # Patch uid only for the test; current process creates this disposable
    # file as its real user, not production root.
    monkeypatch.setattr(keys,"read_key",lambda p: p.read_bytes())
    keys.install_key(f)
    assert len(f.read_bytes())==32
    assert stat.S_IMODE(f.stat().st_mode)==0o600
    with pytest.raises(ValueError,match="existing"):
        keys.install_key(f)
    assert len(f.read_bytes())==32


def test_read_key_rejects_corrupt_untrusted_and_symlink(tmp_path):
    target=tmp_path/"key";target.write_bytes(b"x"*31)
    target.chmod(0o600)
    with pytest.raises(ValueError):
        keys.read_key(target,expected_owner=os.geteuid())
    target.write_bytes(b"x"*32)
    target.chmod(0o644)
    with pytest.raises(ValueError):
        keys.read_key(target,expected_owner=os.geteuid())
    target.chmod(0o600)
    assert keys.read_key(target,expected_owner=os.geteuid())==b"x"*32
    alias=tmp_path/"alias";alias.symlink_to(target)
    with pytest.raises(ValueError):
        keys.read_key(alias,expected_owner=os.geteuid())


def test_initially_disabled_bridge_never_reads_or_issues():
    calls=[]
    res=with_new_buyer_status_receipt(
        RESPONSE,enabled=False,hmac_key=KEY,
        request_lookup=lambda rid:calls.append("read"),
        persist_fingerprint=lambda p:calls.append("write"),
        now=NOW,
    )
    assert res["buyer_status_token_delivered"] is False
    assert res["buyer_status_release_active"] is False
    assert calls==[]


def test_new_pending_request_delivers_one_time_token_after_commit():
    res,saved=call()
    assert res["buyer_status_token_delivered"] is True
    assert res["buyer_status_delivery_method"]=="first_party_checkout_response_once"
    assert len(saved)==1
    assert saved[0]["token_fingerprint"]==fingerprint(
        res["buyer_status_token"],KEY)
    assert res["buyer_status_token"] not in str(saved)
    assert res["payment_instructions_ready"] is False


@pytest.mark.parametrize("overrides",[
    {"decision":"existing_order"},
    {"decision":"some_other_result"},
    {"payment_request_created":False},
    {"payment_request_status":"approved"},
    {"payment_request_status":"rejected"},
    {"settlement_mode":"escrow"},
    {"payment_instructions_ready":True},
    {"actual_revenue":True},
])
def test_replays_approved_requests_escrow_and_payment_claims_never_issue(overrides):
    reads=[]
    res=with_new_buyer_status_receipt(
        {**RESPONSE,**overrides},enabled=True,hmac_key=KEY,
        request_lookup=lambda rid:reads.append("read"),
        persist_fingerprint=lambda p:reads.append("write"),now=NOW)
    assert res["buyer_status_token_delivered"] is False
    assert "buyer_status_token" not in res
    assert reads==[]


@pytest.mark.parametrize("bad",[
    {"id":str(uuid4())},
    {"fulfilment_order_id":str(uuid4())},
    {"status":"approved"},
    {"settlement_mode":"escrow"},
    {"expires_at":NOW-timedelta(seconds=1)},
    {"created_at":NOW+timedelta(seconds=1)},
])
def test_wrong_request_identity_or_expiry_denied_without_bearer(bad):
    res,saved=call(row={**ROW,**bad})
    assert "buyer_status_token" not in res
    assert res["buyer_status_unavailable"] is True
    assert not saved


def test_failed_database_commit_discards_token():
    def fail(p):
        raise RuntimeError("PRIVATE_PASSWORD_NEVER_EXPOSE")
    res,_=call(persist=fail)
    assert res["buyer_status_token_delivered"] is False
    assert res["buyer_status_unavailable"] is True
    assert "PRIVATE_PASSWORD" not in str(res)


def test_bridge_returns_only_from_new_response_not_from_lookup_ids():
    wrong={**RESPONSE,"order_id":str(uuid4())}
    response,_=call(overrides=wrong)
    assert response["buyer_status_token_delivered"] is False


def test_error_never_overwrites_original_pending_payment_data():
    before=dict(RESPONSE)
    result,_=call(persist=lambda p:{"decision":"existing"})
    for k,v in before.items():
        assert result[k]==v
    assert "buyer_status_token" not in result


def test_custody_module_has_no_automatic_key_or_payment_side_effect():
    source=Path(keys.__file__).read_text()
    assert 'secrets.token_bytes(32)' in source
    assert 'O_EXCL' in source
    assert 'os.fsync' in source
    assert 'key_bytes_printed":False' in source
    assert 'buyer_token_issued":False' in source
    assert "os.environ[" not in source
