"""Review of live private identity without exposing/creating production keys."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat

import pytest

P=Path(__file__).resolve().parents[1]/"scripts/review_consumer_private_identity_session_20261021.py"
spec=importlib.util.spec_from_file_location("private_identity_check",P)
mod=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

PASSWORD="a"*64
KEYS={
    "email_hmac":"b"*64,
    "token_hmac":"c"*64,
    "email_encryption":"d"*64,
    "key_reference":"consumer-key-v1",
}
PGPASS=f"127.0.0.1:5432:empiredb:empire_consumer_optin_login:{PASSWORD}\n".encode()


def _mock_files(monkeypatch, pass_content=PGPASS, key_content=None):
    if key_content is None:
        key_content=json.dumps(KEYS).encode()
    def read(path,*,parent):
        return pass_content if path.name=="subscriber.pgpass" else key_content
    monkeypatch.setattr(mod,"_root_only_file",read)


def test_keys_custody_accepts_only_original_scope(monkeypatch):
    _mock_files(monkeypatch)
    password,keys=mod.read_custody(vault=Path("/synthetic-read-only"))
    assert password==PASSWORD
    assert keys==KEYS
    assert PASSWORD not in str(keys)


@pytest.mark.parametrize("badfile",[
    b"localhost:5432:empiredb:empire_consumer_optin_login:"+PASSWORD.encode(),
    b"127.0.0.1:5432:empiredb:empiredb_app:"+PASSWORD.encode(),
    b"127.0.0.1:5432:postgres:empire_consumer_optin_login:"+PASSWORD.encode(),
    b"127.0.0.1:5432:empiredb:empire_consumer_optin_login:weak",
])
def test_broken_identity_or_password_fails(monkeypatch,badfile):
    _mock_files(monkeypatch,pass_content=badfile)
    with pytest.raises(RuntimeError,match="PRIVATE_CREDENTIAL_FORMAT_HOLD"):
        mod.read_custody(vault=Path("/synthetic-read-only"))


@pytest.mark.parametrize("badkeys",[
    {"email_hmac":"b"*64,"token_hmac":"b"*64,"email_encryption":"d"*64,
     "key_reference":"consumer-key-v1"},
    {"email_hmac":"b"*64,"token_hmac":"c"*64,"email_encryption":"not-a-key",
     "key_reference":"consumer-key-v1"},
    {"email_hmac":"b"*64,"token_hmac":"c"*64,"email_encryption":"d"*64,
     "key_reference":"consumer-key-v2"},
    {"email_hmac":"b"*64,"token_hmac":"c"*64,"email_encryption":"d"*64,
     "key_reference":"consumer-key-v1","another_role":"empiredb_app"},
])
def test_weak_reused_wrong_version_or_extra_secret_fails(monkeypatch,badkeys):
    _mock_files(monkeypatch,key_content=json.dumps(badkeys).encode())
    with pytest.raises(RuntimeError,match="PRIVATE_CREDENTIAL_FORMAT_HOLD"):
        mod.read_custody(vault=Path("/synthetic-read-only"))


def test_secret_files_root_owner_mode_symlink_guard(tmp_path,monkeypatch):
    vault=tmp_path/"private"
    vault.mkdir(mode=0o700)
    f=vault/"subscriber.pgpass"
    f.write_bytes(PGPASS)
    f.chmod(0o600)
    # Under unprivileged fixture UID, a root-owned original is required.
    if os.geteuid()!=0:
        with pytest.raises(RuntimeError,match="VAULT_OWNERSHIP_OR_MODE_HOLD"):
            mod._root_only_file(f,parent=vault)
    vault.chmod(0o755)
    with pytest.raises(RuntimeError,match="VAULT_OWNERSHIP_OR_MODE_HOLD"):
        mod._root_only_file(f,parent=vault)
    vault.chmod(0o700)
    link=vault/"link"
    link.symlink_to(f)
    expected = ("SECRET_FILE_MISSING_OR_SYMLINK" if os.geteuid()==0
                else "VAULT_OWNERSHIP_OR_MODE_HOLD")
    with pytest.raises(RuntimeError,match=expected):
        mod._root_only_file(link,parent=vault)


def test_root_required_and_user_cannot_trigger_probe(monkeypatch):
    monkeypatch.setattr(mod.os,"geteuid",lambda:1000)
    monkeypatch.setattr(mod,"read_custody",
                        lambda **kwargs:pytest.fail("vault opened"))
    with pytest.raises(RuntimeError,match="ROOT_LOCAL_REVIEW_REQUIRED"):
        mod.diagnostic()


def test_public_output_never_contains_password_or_keys(monkeypatch):
    _mock_files(monkeypatch)
    monkeypatch.setattr(mod.os,"geteuid",lambda:0)
    monkeypatch.setattr(mod,"original_readonly_session",
                        lambda **kwargs:{
                            "scram_authenticated_tcp_loopback":True,
                            "no_subscriber_rows_fetched":True,
                        })
    output=mod.diagnostic(vault=Path("/synthetic-read-only"))
    encoded=json.dumps(output)
    assert output["status"]=="CONSUMER_PRIVATE_IDENTITY_LIVE_READONLY_VALIDATED"
    assert output["production_database_modified"] is False
    assert output["email_sent"] is False
    for value in (PASSWORD,"b"*64,"c"*64,"d"*64):
        assert value not in encoded


def test_no_apply_flag_in_readonly_tool():
    src=P.read_text()
    assert "--apply" not in src
    assert "SET TRANSACTION READ ONLY" in src
    assert "LIMIT 0" in src
    assert "GRANT "+mod.WRITER+" TO" not in src
    assert "INSERT INTO" not in src
