"""Regression for the October 14 protected systemd credential mode hold."""
import json
import pytest
from empire_os import direct_bsc_buyer_checkout_release as release
from empire_os.bsc_usdt_verifier import BscUsdtConfig
from scripts.provision_direct_bsc_buyer_status_logins import (
    READ_KEY, ISSUE_KEY, READ_LOGIN, ISSUE_LOGIN, dsn_for
)

TREASURY="0x1339b487046b0ad924a10c20b1791608ea8595a8"


def dsn_entries():
    return {
       READ_KEY: dsn_for("dbname=empiredb host=127.0.0.1 port=5432",
                         READ_LOGIN,"reader_dummy_secret_A"),
       ISSUE_KEY: dsn_for("dbname=empiredb host=127.0.0.1 port=5432",
                         ISSUE_LOGIN,"issuer_dummy_secret_B"),
    }


def credentials(tmp_path,monkeypatch):
    key=tmp_path/release.CREDENTIAL_KEY
    dsns=tmp_path/release.CREDENTIAL_DSN
    key.write_bytes(bytes(range(32)))
    dsns.write_text("".join(k+"="+json.dumps(v)+"\n" for k,v in dsn_entries().items()))
    key.chmod(0o600)
    dsns.chmod(0o600)
    monkeypatch.setattr(release,"_credential_dir",lambda:tmp_path)
    monkeypatch.setattr(BscUsdtConfig,"from_env",classmethod(
       lambda cls: cls(rpc_url="http://127.0.0.1:8080",
            treasury_address=TREASURY,
            token_contract="0x55d398326f99059ff775485246999027b3197955",
            min_confirmations=12)))



def test_systemd_delivered_0444_credentials_in_private_checkout_unit_are_accepted(
    tmp_path, monkeypatch
):
    # Systemd's delivered copies are intentionally read-only 0444. Their
    # directory is private (0550), unlike root-owned 0600 source files.
    directory=tmp_path/"empire-self-serve-checkout.service"
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(release,"CHECKOUT_CREDENTIAL_DIR",directory)
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(directory))
    key=directory/release.CREDENTIAL_KEY
    dsns=directory/release.CREDENTIAL_DSN
    key.write_bytes(bytes(range(32)))
    dsns.write_text("".join(k+"="+json.dumps(v)+"\n" for k,v in dsn_entries().items()))
    key.chmod(0o444)
    dsns.chmod(0o444)
    directory.chmod(0o550)
    monkeypatch.setattr(BscUsdtConfig,"from_env",classmethod(
       lambda cls: cls(rpc_url="http://127.0.0.1:8080",
            treasury_address=TREASURY,
            token_contract="0x55d398326f99059ff775485246999027b3197955",
            min_confirmations=12)))
    reader,issuer,secret,treasury=release._config()
    assert READ_LOGIN in reader
    assert ISSUE_LOGIN in issuer
    assert len(secret)==32
    assert treasury==TREASURY


def test_checkout_credential_directory_must_be_exact_and_private(tmp_path,monkeypatch):
    directory=tmp_path/"empire-self-serve-checkout.service"
    directory.mkdir(mode=0o550)
    directory.chmod(0o550)
    monkeypatch.setattr(release,"CHECKOUT_CREDENTIAL_DIR",directory)
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(tmp_path))
    with pytest.raises(ValueError,match="exact checkout"):
        release._credential_dir()
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(directory))
    assert release._credential_dir()==directory
    directory.chmod(0o755)
    with pytest.raises(ValueError,match="traversal"):
        release._credential_dir()
    directory.chmod(0o550)
    alias=tmp_path/"alias"
    alias.symlink_to(directory,target_is_directory=True)
    monkeypatch.setattr(release,"CHECKOUT_CREDENTIAL_DIR",alias)
    monkeypatch.setenv("CREDENTIALS_DIRECTORY",str(alias))
    with pytest.raises(ValueError,match="untrusted"):
        release._credential_dir()


def test_systemd_credential_copy_must_have_no_write_bits(tmp_path,monkeypatch):
    credentials(tmp_path,monkeypatch)
    dsns=tmp_path/release.CREDENTIAL_DSN
    dsns.chmod(0o444)
    (tmp_path/release.CREDENTIAL_KEY).chmod(0o444)
    assert release._config()[2]==bytes(range(32))
    dsns.chmod(0o644)
    with pytest.raises(release.PrivateStatusConfigurationHeld) as held:
        release._config()
    assert held.value.stage=="credential_files"
    dsns.chmod(0o444)
    key=tmp_path/release.CREDENTIAL_KEY
    key.unlink()
    key.symlink_to(tmp_path/"missing")
    with pytest.raises(release.PrivateStatusConfigurationHeld) as held:
        release._config()
    assert held.value.stage=="credential_files"
