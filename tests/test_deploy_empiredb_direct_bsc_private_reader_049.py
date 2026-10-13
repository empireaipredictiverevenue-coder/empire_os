"""049 v2 protected deployment operator cannot run without separate consent."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
WRAPPER=ROOT/"scripts/deploy_empiredb_direct_bsc_private_reader_049.sh"
POST=ROOT/"scripts/inspect_direct_bsc_private_reader_049_postcommit.sql"
SQL=ROOT/"migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql"


def test_rejects_malformed_or_earlier_approvals_pre_side_effects():
    code=WRAPPER.read_text()
    assert code.count("--approved-049-v2-isolated-private-reader-only")==1
    assert code.index("--approved-049-v2-isolated-private-reader-only") < code.index("exec 9>")
    for flags in (
      [],["--preflight"],["--apply"],
      ["--apply","--approved-049-v1"],
      ["--apply","--approved-048-one-table-acl-seal-only"],
      ["--apply","--approved-049-v2-isolated-private-reader-only","extra"],
    ):
        p=subprocess.run(["bash",str(WRAPPER),*flags],
             capture_output=True,text=True,timeout=4)
        assert p.returncode==3
        assert "SEPARATE_EXACT_049_FOUNDER_APPROVAL_REQUIRED" in p.stderr


def test_backups_and_exact_committed_blob_guards_before_transaction():
    s=WRAPPER.read_text()
    for required in (
       "git hash-object", "HEAD:$file",
       "READONLY_049_V2_PREFLIGHT_HELD",
       "CANONICAL_APP_DB_MISMATCH",
       "DIRECT049_V2_CANONICAL_PREFLIGHT=PASS",
       "DIRECT049_BACKUP=VERIFIED",
       "pg_dump -w -Fc -d empiredb",
       "pg_dumpall -w --globals-only",
       "sha256sum -c SHA256SUMS",
       "pg_restore --list", "flock -n -x 9",
       "DIRECT049_FULL_RESTORE_REHEARSAL=NOT_PERFORMED",
       "DIRECT049_SQL_TRANSACTION=COMMITTED",
       "DIRECT049_TWELVE_POSTCOMMIT_SECURITY_CHECKS=PASS",
       "DIRECT049_CHECKOUT_FLAGS=STILL_OFF_VERIFIED",
       "DIRECT049_STATUS=ISOLATED_PRIVATE_READER_INSTALLED_NO_LOGIN_NO_ENDPOINT",
    ):
        assert required in s
    assert s.index("DIRECT049_BACKUP=VERIFIED") < s.index('if ! runuser -u postgres -- psql')
    for forbidden in (
       "systemctl restart", "systemctl daemon-reload",
       "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=ON",
       "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=ON",
       "ALTER ROLE empiredb_migrator_login", "GRANT CONNECT TO",
    ):
        assert forbidden not in s


def test_postcommit_twelve_checks_and_no_customer_rows():
    s=POST.read_text()
    assert "BEGIN READ ONLY;" in s
    assert "ROLLBACK;" in s
    for index in range(1,13):
        assert "'"+f"{index:02d}_" in s
    for mandatory in (
       "pg_catalog.pg_auth_members", "pg_catalog.pg_policy",
       "pg_catalog.pg_proc", "pg_catalog.aclexplode",
       "proowner=(SELECT oid FROM owner)",
       "empiredb_migrator_login", "relforcerowsecurity",
    ):
        assert mandatory in s
    for forbidden in (
       "ALTER ROLE", "CREATE ROLE", "CREATE POLICY",
       "GRANT SELECT ON", "COMMIT;", "FROM public.fulfilment_orders",
       "FROM public.bsc_payment_requests", "FROM public.buyers",
    ):
        assert forbidden not in s


def test_shell_syntax():
    for p in (WRAPPER,ROOT/"scripts/test_direct_bsc_private_reader_049_ephemeral.sh"):
        ret=subprocess.run(["bash","-n",str(p)],
                capture_output=True,text=True,timeout=3)
        assert ret.returncode==0,ret.stderr
