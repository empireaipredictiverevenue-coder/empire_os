"""050 guarded deployment operator must refuse any unapproved call."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SH=ROOT/"scripts/deploy_empiredb_direct_bsc_private_issuer_050.sh"
POST=ROOT/"scripts/inspect_direct_bsc_private_issuer_050_postcommit.sql"


def test_missing_or_old_approval_no_side_effects():
    for args in (
        [],["--apply"],
        ["--apply","--approved-049-v2-isolated-private-reader-only"],
        ["--apply","--approved-050-v1"],
        ["--preflight"],
        ["--apply","--approved-050-private-token-issuer-only","extra"],
    ):
        result=subprocess.run(["bash",str(SH),*args],
                              capture_output=True,text=True,timeout=3)
        assert result.returncode==3
        assert "SEPARATE_EXACT_050_FOUNDER_APPROVAL_REQUIRED" in result.stderr


def test_fails_closed_on_backup_and_checks_role_source_hashes_before_sql():
    text=SH.read_text()
    assert text.count("--approved-050-private-token-issuer-only")==1
    assert text.index("--approved-050-private-token-issuer-only") < text.index("exec 9>")
    for term in (
        "git hash-object",
        "scripts.inspect_direct_bsc_private_issuer_050 --preflight",
        "scripts/inspect_direct_bsc_private_issuer_050_postcommit.sql",
        "scripts/inspect_direct_bsc_private_issuer_050.py",
        "050_direct_bsc_buyer_status_private_issuer.sql",
        "READY_FOR_SEPARATELY_APPROVED_PRIVATE_ISSUER_050",
        "DIRECT050_CANONICAL_PREFLIGHT=PASS",
        "049_BACKUP_HASH_FAILED",
        "20261013T191124Z",
        "CANONICAL_APP_DB_MISMATCH",
        "pg_dump -w -Fc -d empiredb",
        "pg_dumpall -w --globals-only",
        "sha256sum -c SHA256SUMS",
        "pg_restore --list",
        "flock -n -x 9",
        "DIRECT050_BACKUP=VERIFIED",
        "DIRECT050_SQL_TRANSACTION=COMMITTED",
        "DIRECT050_TEN_POSTCOMMIT_SECURITY_CHECKS=PASS",
        "DIRECT050_CHECKOUT_FLAGS=STILL_OFF_VERIFIED",
        "DIRECT050_STATUS=PRIVATE_TOKEN_ISSUER_INSTALLED_NO_LOGIN_NO_ENDPOINT",
    ):
        assert term in text
    assert text.index("DIRECT050_BACKUP=VERIFIED") < text.index(
        'if ! runuser -u postgres -- psql')
    assert '[[ "$count" == 10 ]]' in text
    for forbidden in (
        "systemctl restart","systemctl daemon-reload",
        "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=ON",
        "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=ON",
        "GRANT empire_direct_checkout_status_issuer TO",
    ):
        assert forbidden not in text


def test_postcommit_checks_catalog_only():
    s=POST.read_text()
    for n in range(1,11):
        assert "'"+f"{n:02d}_" in s
    assert "BEGIN READ ONLY;" in s
    assert "ROLLBACK;" in s
    assert "pg_catalog.pg_policy" in s
    assert "pg_catalog.pg_auth_members" in s
    assert "pg_catalog.pg_proc" in s
    for forbidden in (
        "FROM public.bsc_payment_requests",
        "FROM public.direct_bsc_buyer_capabilities",
        "SELECT * FROM public.","CREATE ROLE ","CREATE POLICY ",
        "UPDATE public.","INSERT INTO public.","COMMIT;",
    ):
        assert forbidden not in s


def test_bash_parse_is_valid():
    r=subprocess.run(["bash","-n",str(SH)],
                     capture_output=True,text=True,timeout=3)
    assert r.returncode==0,r.stderr
