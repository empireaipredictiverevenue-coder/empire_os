"""050 source safety contract: prepared only, owner/caller isolated."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"migrations/empiredb/050_direct_bsc_buyer_status_private_issuer.sql"
SH=ROOT/"scripts/test_direct_bsc_private_issuer_050_ephemeral.sh"


def test_iso_roles_and_exact_bound_sql():
    s=SQL.read_text()
    assert s.startswith("-- EmpireDB 050 v1: ISOLATED")
    assert "STAGED ONLY" in s.splitlines()[0]
    assert s.startswith("--") and s.rstrip().endswith("COMMIT;")
    for role in (
        "empire_direct_checkout_status_issuer_owner",
        "empire_direct_checkout_status_issuer",
    ):
        assert "CREATE ROLE "+role in s
    assert s.count("NOLOGIN NOINHERIT NOSUPERUSER")==2
    assert s.count("GRANT SELECT (")==1
    assert s.count("GRANT INSERT (")==1
    assert "WITH CHECK (revoked_at IS NULL" in s
    assert "FOR SELECT TO empire_direct_checkout_status_issuer_owner" in s
    assert "FOR INSERT TO empire_direct_checkout_status_issuer_owner" in s
    assert "OWNER TO empire_direct_checkout_status_issuer_owner" in s
    assert "SECURITY DEFINER" in s
    assert "SET search_path=''" in s
    assert "DIRECT050_PENDING_BOUND_REQUEST_REQUIRED" in s
    assert "r.status IS DISTINCT FROM 'pending'" in s
    assert "p_issued_at < r.created_at" in s
    assert "p_expires_at > r.expires_at" in s
    assert "DIRECT050_047_GUARD_TRIGGER_DRIFT" in s
    assert "DIRECT050_049_ISOLATED_READER_CONTRACT_DRIFT" in s
    assert "empire_direct_checkout_status_reader" in s


def test_deployment_not_embedded_in_source_or_live_api():
    s=SQL.read_text()
    for bad in (
        "GRANT empiredb_migrator TO","GRANT empire_direct_checkout_status_issuer TO",
        "ALTER DEFAULT PRIVILEGES","GRANT CONNECT ON DATABASE",
        "SET ROLE empiredb_migrator","ALTER TABLE public.direct_bsc_buyer_capabilities OWNER TO",
        "INSERT INTO public.fulfilment_orders",
        "UPDATE public.bsc_payment_requests",
    ):
        assert bad not in s
    gateway=(ROOT/"empire_os/public_gateway.py").read_text()
    checkout=(ROOT/"empire_os/self_serve_checkout_api.py").read_text()
    assert "create_private_buyer_status_router" not in gateway
    assert "create_private_buyer_status_router" not in checkout
    assert "mint_private_buyer_access" not in gateway
    assert "mint_private_buyer_access" not in checkout


def test_disposable_harness_only_and_valid_bash():
    script=SH.read_text()
    for x in (
        "pg_virtualenv -v 18",
        "PGPORT",
        "scripts/test_direct_bsc_private_reader_049_ephemeral.sh",
        "migrations/empiredb/050_direct_bsc_buyer_status_private_issuer.sql",
        "EPHEMERAL_ISSUER_TO_READER_END_TO_END=PASS",
        "EPHEMERAL_DUPLICATE_ISSUANCE_DENIED=PASS",
        "EPHEMERAL_APPROVED_REQUEST_NEW_TOKEN_DENIED=PASS",
        "PRODUCTION_POSTGRES_PORT_ACCESSED=NO",
    ):
        assert x in script
    assert "5432" in script
    result=subprocess.run(["bash","-n",str(SH)],
                          capture_output=True,text=True,timeout=4)
    assert result.returncode==0,result.stderr
