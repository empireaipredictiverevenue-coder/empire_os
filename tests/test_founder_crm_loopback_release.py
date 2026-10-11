"""Pilot activation and founder SSH redemption safety contracts."""
from pathlib import Path
import importlib.util
import pytest
ROOT=Path(__file__).resolve().parents[1]
DEPLOY=ROOT/"scripts/deploy_founder_crm_loopback_service.sh"
REDEEM=ROOT/"scripts/redeem_founder_crm_invitation_local.py"
spec=importlib.util.spec_from_file_location("crm_redeem_local",REDEEM)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_pilot_deploy_exact_scope_no_public_ingress():
    s=DEPLOY.read_text()
    assert "set -euo pipefail" in s
    assert '"$EUID" -ne 0' in s
    assert "--approved-founder-loopback-only" in s
    assert "systemctl start" in s
    assert "systemctl daemon-reload" in s
    assert "127.0.0.1 --port 8783 --no-proxy-headers" in s
    assert "CRM_LOOPBACK_UNAUTHENTICATED_CRM=401" in s
    assert "CRM_LOOPBACK_API_DOCUMENTATION=404" in s
    assert "ss -H -lnt" in s
    assert "systemctl stop" in s
    assert "systemctl enable" not in s
    assert "pg_hba" not in s
    assert "CREATE ROLE" not in s and "ALTER ROLE" not in s
    assert "CREATE TABLE" not in s and "INSERT INTO" not in s
    assert "cloudflared" not in s
    assert "mail" not in s.lower() or "OUTBOUND_SENT" in s


def test_founder_ssh_redemption_never_emits_secrets():
    s=REDEEM.read_text()
    assert "getpass.getpass" in s
    assert "sys.stdin.isatty()" in s
    assert "os.geteuid()" in s
    assert 'HTTPConnection("127.0.0.1",8783,timeout=8)' in s
    assert "flavag83@gmail.com" in s
    assert "127.0.0.1" in s
    assert "print(record[" not in s
    assert "print(reply[" not in s
    assert "send_email" not in s
    assert "subprocess" not in s
    assert "os.environ" not in s
    assert "authorization" not in s.lower() or "bearer" in s.lower()
    assert "ALTER ROLE" not in s


def test_redemption_whitelists_endpoints():
    with pytest.raises(ValueError):
        m.post("/admin",{})
    with pytest.raises(ValueError):
        m.get_authenticated("/untrusted","not-a-real-token")
