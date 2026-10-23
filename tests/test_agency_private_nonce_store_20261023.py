"""Exclusive-create, owner-owned replay store; no distributed or production claims."""
from pathlib import Path
import json
import os
import secrets
import concurrent.futures
import pytest
from empire_os.agency_private_nonce_store import PrivateAgencyNonceStore

def store(tmp_path):
    directory=tmp_path/"nonce-receipts"
    directory.mkdir(mode=0o700)
    return PrivateAgencyNonceStore(directory,os.getuid())

def test_nonce_survives_adapter_restart_and_fails_replay(tmp_path):
    first=store(tmp_path)
    token=secrets.token_urlsafe(30)
    assert first(token) is True
    second=PrivateAgencyNonceStore(first.directory,os.getuid())
    assert second(token) is False
    files=list(first.directory.iterdir())
    assert len(files)==1
    assert token not in files[0].name
    assert files[0].stat().st_mode & 0o777==0o600

def test_concurrent_same_nonce_only_one_winner(tmp_path):
    instance=store(tmp_path)
    token=secrets.token_urlsafe(30)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(instance,[token]*24))
    assert results.count(True)==1
    assert results.count(False)==23

def test_bad_nonce_permissions_symlink_and_missing_store_deny(tmp_path):
    instance=store(tmp_path)
    for candidate in ("", "../evil", "bad/path", "short", "?"*32):
        assert instance(candidate) is False
    instance.directory.chmod(0o755)
    assert instance(secrets.token_urlsafe(25)) is False
    instance.directory.chmod(0o700)
    assert PrivateAgencyNonceStore(instance.directory,os.getuid()+1)(
        secrets.token_urlsafe(25)) is False
    original=instance.directory
    relocated=tmp_path/"relocated"
    original.rename(relocated)
    original.symlink_to(relocated)
    assert instance(secrets.token_urlsafe(25)) is False

def test_fail_closed_missing_directory(tmp_path):
    instance=PrivateAgencyNonceStore(tmp_path/"not-provisioned",os.getuid())
    assert instance(secrets.token_urlsafe(30)) is False
