"""Static guard + denial tests for one-shot, privileged DBA operator release."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/activate_crm_founder_owner_membership.sh"
SQL = ROOT / "scripts/activate_crm_founder_owner_membership.sql"
DNS = ROOT / "scripts/crm_founder_domain_challenge.py"


def test_pinned_sources_and_exact_approval():
    body=SCRIPT.read_text()
    assert f"sql_sha={hashlib.sha256(SQL.read_bytes()).hexdigest()}" in body
    assert f"dns_sha={hashlib.sha256(DNS.read_bytes()).hexdigest()}" in body
    assert "--approved-single-active-owner" in body
    assert "RELEASE_SOURCE_NOT_COMMITTED" in body
    assert "ROOT_OPERATOR_REQUIRED" in body
    assert "EXPLICIT_FOUNDER_APPROVAL_REQUIRED" in body
    assert "APP_AND_OPERATOR_DATABASE_DIFFER" in body
    assert "EXISTING_MEMBERSHIP_OR_AUTHORITY_DRIFT_RECONCILE_FIRST" in body
    assert "'1|1|1|0|2|1|1|0|1|1'" in body


def test_dns_verification_strict_both_nameservers_and_precommit_recheck():
    body=SCRIPT.read_text()
    assert "runuser -u ubuntu -- env -i" in body
    assert "PATH=/usr/bin:/bin HOME=/home/ubuntu USER=ubuntu" in body
    assert "crm_founder_domain_challenge.py --verify" in body
    assert "gracie.ns.cloudflare.com" in body
    assert "nash.ns.cloudflare.com" in body
    assert '"dns_control_challenge_verified") is True' in body
    assert "AUTHORITATIVE_DNS_CHALLENGE_MISSING_OR_EXPIRED" in body
    assert body.count("verify_dns\n") == 2


def test_backup_and_postcommit_safety():
    body=SCRIPT.read_text()
    for phrase in (
        "set -euo pipefail", "umask 077", "postgresql@18-main.service",
        "/var/lib/postgresql/18/main", "pg_dump -w -Fc -d empiredb",
        "pg_dumpall -w --globals-only", "pg_restore --list",
        "sha256sum -c SHA256SUMS",
        "CRM_FOUNDER_ACTIVE_TRANSACTION=COMMITTED",
        "CRM_FOUNDER_ACTIVE_POST_DEPLOYMENT=CATALOG_VERIFIED",
        "CRM_FOUNDER_ACTIVE_CREDENTIAL_ROWS=0",
        "CRM_FOUNDER_ACTIVE_LOGIN_ROLES=NOLOGIN_UNCHANGED",
        "CRM_FOUNDER_ACTIVE_EMAIL_OR_INVITE_SENT=NO",
        "CRM_FOUNDER_ACTIVE_HTTP_CONFIG_CHANGED=NO",
        "CRM_FOUNDER_ACTIVE_RESULT=ONE_ACTIVE_MEMBERSHIP_ONLY_LOGIN_AND_API_HELD",
    ):
        assert phrase in body, phrase
    assert body.count('  -f "$sql" >') == 1
    for forbidden in (
        "ALTER ROLE", "GRANT ", "CREATE ROLE", "systemctl restart",
        "systemctl enable", "INSERT INTO public.empire_crm_login_credentials",
    ):
        assert forbidden not in body


def test_missing_approval_always_blocked():
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
    for flags in ([], ["--apply"], ["--approved-single-active-owner"]):
        result=subprocess.run(["bash", str(SCRIPT), *flags],
                              text=True, capture_output=True, timeout=4)
        assert result.returncode != 0
        assert "EXPLICIT_FOUNDER_APPROVAL_REQUIRED" in result.stderr


def test_unprivileged_execution_fails_closed():
    if os.geteuid()==0:
        return
    result=subprocess.run(["bash", str(SCRIPT), "--apply", "--approved-single-active-owner"],
                          text=True, capture_output=True, timeout=4)
    assert result.returncode != 0
    assert "ROOT_OPERATOR_REQUIRED" in result.stderr
