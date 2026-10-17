"""Existing buyer Gmail read-only OAuth recovery cannot silently send or rotate."""
from pathlib import Path
import hashlib
import subprocess
import pytest


ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/renew_buyer_gmail_readonly_20261017.sh'
TOKEN=ROOT/'runtime/secrets/buyer-gmail-readonly-token.json'
CLIENT=ROOT/'runtime/secrets/buyer-gmail-readonly-client.json'
AUTHORISER=ROOT/'scripts/authorize_buyer_gmail_readonly.py'


def test_wrapper_has_valid_shell_syntax_and_explicit_apply():
    assert subprocess.run(['bash','-n',str(SCRIPT)],capture_output=True).returncode==0
    script=SCRIPT.read_text()
    assert 'getProfile(userId=' in script
    assert "flavag83@gmail.com" in script
    assert 'GOOGLE_ACCOUNT_MISMATCH_OLD_TOKEN_RESTORED' in script
    assert 'mv -- "$TOKEN" "$BACKUP"' in script
    assert 'mv -- "$BACKUP" "$TOKEN"' in script
    assert "trap restore_on_exit EXIT" in script
    assert 'flock -n 8' in script
    assert 'CREDS' not in script
    assert 'gmail.send' not in script and 'gmail.modify' not in script
    assert 'sender' not in script
    assert "BUYR_GMAIL" not in script


def test_no_implicit_activation_or_credential_rotation_from_wrong_cli():
    args=[['bash',str(SCRIPT)], ['bash',str(SCRIPT),'--try'],
          ['bash',str(SCRIPT),'--apply','--preflight']]
    for cmd in args:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=8)
        assert p.returncode==2
        assert 'Usage:' in p.stderr


def test_readonly_preflight_does_not_modify_existing_credentials_or_start_auth():
    if not TOKEN.is_file() or not CLIENT.is_file() or not AUTHORISER.is_file():
        pytest.skip("production private read-only Gmail OAuth files not mounted")
    before={p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (TOKEN,CLIENT)}
    p=subprocess.run(['bash',str(SCRIPT),'--preflight'],capture_output=True,text=True,timeout=18)
    assert p.returncode==0, p.stderr[:180]
    assert 'READY_REQUIRES_FOUNDERS_GOOGLE_BROWSER_CONSENT' in p.stdout
    assert 'NO_TOKEN_CHANGED' in p.stdout
    assert 'NO_EMAIL_SENT' in p.stdout
    after={p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (TOKEN,CLIENT)}
    assert before==after


def test_existing_authoriser_only_requests_readonly_permission():
    source=AUTHORISER.read_text()
    assert 'https://www.googleapis.com/auth/gmail.readonly' in source
    assert 'gmail.send' not in source
    assert 'gmail.modify' not in source
    assert "open_browser=False" in source
    assert 'refusing overwrite' in source
