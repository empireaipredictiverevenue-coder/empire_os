"""Restricted Scaleway IAM token delivery without repo or env secrets."""
import pytest

from empire_os.inbound_calendar_scaleway_iam import (
    read_calendar_secret_manager_iam_token, CREDENTIAL_NAME,
)
from empire_os.inbound_google_calendar_adapter import CalendarVerificationError


def test_not_provisioned_does_not_discover_ambient_api_keys(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    monkeypatch.setenv("SCW_SECRET_KEY", "ambient-credential-never-accepted")
    with pytest.raises(CalendarVerificationError, match="not_provisioned"):
        read_calendar_secret_manager_iam_token()


def test_only_private_explicit_credential_directory_is_accepted(tmp_path):
    private = tmp_path / "calendar-secrets"
    private.mkdir(mode=0o700)
    secret = private / CREDENTIAL_NAME
    secret.write_text("local-fixture-scw-private-token-" + "a" * 25)
    secret.chmod(0o400)
    assert read_calendar_secret_manager_iam_token(
        credential_directory=private,
    ).startswith("local-fixture-scw")
    secret.chmod(0o444)
    with pytest.raises(CalendarVerificationError, match="permissions"):
        read_calendar_secret_manager_iam_token(
            credential_directory=private,
        )
    secret.chmod(0o400)
    private.chmod(0o755)
    with pytest.raises(CalendarVerificationError, match="permissions"):
        read_calendar_secret_manager_iam_token(
            credential_directory=private,
        )


def test_symlink_secret_never_accepted(tmp_path):
    private = tmp_path / "secrets"
    private.mkdir(mode=0o700)
    target = tmp_path / "target"
    target.write_text("fixture-some-token-credential-" + "t" * 35)
    target.chmod(0o400)
    (private / CREDENTIAL_NAME).symlink_to(target)
    with pytest.raises(CalendarVerificationError, match="not_found"):
        read_calendar_secret_manager_iam_token(
            credential_directory=private,
        )


def test_bad_token_characters_and_length_denied(tmp_path):
    private = tmp_path / "secrets"
    private.mkdir(mode=0o700)
    credential = private / CREDENTIAL_NAME
    for content in ("too-short", "fixture-iam-secret-token embedded-space"):
        if credential.exists():
            credential.chmod(0o600)
        credential.write_text(content)
        credential.chmod(0o400)
        with pytest.raises(CalendarVerificationError, match="permissions|invalid"):
            read_calendar_secret_manager_iam_token(
                credential_directory=private,
            )
