"""Offline approval and security contract for protected EmpireDB 047 deployer."""
from pathlib import Path
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deploy_empiredb_direct_bsc_buyer_capability_047.sh"


def source():
    return SCRIPT.read_text()


def test_exact_approval_gate_precedes_all_side_effects():
    s = source()
    exact = '--approved-047-sealed-buyer-capability-only'
    assert s.count(exact) == 1
    assert s.index(exact) < s.index('exec 9>')
    assert s.index(exact) < s.index('pg_dump')
    assert s.index(exact) < s.index('psql -X')
    assert 'ROOT_OPERATOR_REQUIRED' in s
    assert 'EXACT_FOUNDER_MIGRATION_APPROVAL_REQUIRED' in s


def test_refuses_no_wrong_or_partial_approvals_without_sudo_or_db():
    for argv in ([], ["--preflight"], ["--apply"],
                 ["--apply", "--approved-direct-bsc-readonly-config-and-checkout-restart"],
                 ["--apply", "--approved-046-suppression-only"],
                 ["--approved-047-sealed-buyer-capability-only"]):
        proc = subprocess.run(["bash", str(SCRIPT), *argv],
                              capture_output=True, text=True, timeout=3)
        assert proc.returncode == 3
        assert "EXACT_FOUNDER_MIGRATION_APPROVAL_REQUIRED" in proc.stderr


def test_lock_backup_hash_and_single_sql_transaction_required():
    s = source()
    assert 'flock -n -x 9' in s
    assert 'git hash-object "$SQL"' in s
    assert "HEAD:$SQL" in s
    assert '--globals-only' in s
    assert 'pg_dump -w -Fc -d empiredb' in s
    assert 'pg_restore --list' in s
    assert 'sha256sum -c SHA256SUMS' in s
    assert 'BACKUP_INSUFFICIENT_SPACE' in s
    assert 'ON_ERROR_STOP=1' in s
    assert 'SQL_ABORTED_INSPECT_PRIVATE_LOG_DO_NOT_RETRY' in s
    assert 'POSTCOMMIT_PRIVILEGE_DRIFT_DO_NOT_RETRY' in s


def test_rechecks_true_security_conditions_and_never_grants_payment():
    s = source()
    assert "empire.direct-bsc-buyer-capability-migration-preflight.v2" in s
    assert 'exact_existing_tenant_reader_membership' in s
    assert 'no_transitive_reader_memberships' in s
    assert 'tenant_reader_role_restricted' in s
    assert 'CANONICAL_POSTGRESQL_SERVICE_INACTIVE' in s
    assert 'APPLICATION_DATABASE_MISMATCH' in s
    assert 'DIRECT047_RLS_AND_FINANCIAL_ROLE_DENIAL=VERIFIED' in s
    assert 'has_table_privilege' in s
    assert 'guard_direct_bsc_buyer_capability()' in s
    assert 'DIRECT047_RUNTIME_FINANCIAL_GATES=STILL_OFF_VERIFIED' in s
    for not_permitted in (
        "ALTER ROLE empiredb_", "CREATE ROLE empire_", "GRANT SELECT ON public.",
        "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=ON",
        "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=ON",
        "systemctl restart", "systemctl daemon-reload",
        "wallet.send", "eth_sendRawTransaction",
    ):
        assert not_permitted not in s


def test_shell_syntax():
    p = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=3)
    assert p.returncode == 0, p.stderr
