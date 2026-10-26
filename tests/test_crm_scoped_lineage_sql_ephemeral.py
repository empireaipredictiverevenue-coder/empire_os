"""EXACT held RPC SQL on throwaway local PostgreSQL; never production.

No EmpireDB DB credentials. One temporary PG18 Unix-socket instance is
created under /tmp and stopped at fixture teardown. Tests prove SQL behavior
and cross-tenant denial, not authorization to install the held function.
"""
from __future__ import annotations

from pathlib import Path
import socket
import subprocess
import tempfile

import pytest

BIN = Path("/usr/lib/postgresql/18/bin")
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/crm_scoped_lineage_isolated_fixture.sql"
HELD = ROOT / "docs/architecture/CRM_SCOPED_LINEAGE_RPC_HELD_20261026.sql"
P = "00000000-0000-0000-0000-000000000001"
O = "00000000-0000-0000-0000-000000000003"
EA = "00000000-0000-0000-0000-0000000000a3"
EB = "00000000-0000-0000-0000-0000000000b3"
ENULL = "00000000-0000-0000-0000-0000000000c3"
OA = "00000000-0000-0000-0000-0000000000a4"
OB = "00000000-0000-0000-0000-0000000000b4"
ONULL = "00000000-0000-0000-0000-0000000000c4"
TA = "00000000-0000-0000-0000-0000000000a1"
TB = "00000000-0000-0000-0000-0000000000b1"

@pytest.fixture(scope="module")
def pg():
    if not (BIN/"initdb").exists() or not (BIN/"pg_ctl").exists():
        pytest.skip("PostgreSQL 18 test-only server binaries unavailable")
    with tempfile.TemporaryDirectory(prefix="empire-lineage-fixture-",dir="/tmp") as name:
        root=Path(name)
        (root/"socket").mkdir(mode=0o700)
        data=root/"db"
        def proc(*args,timeout=30):
            return subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        init=proc(str(BIN/"initdb"),"-D",str(data),"-A","trust",
                  "--no-locale","-E","UTF8")
        assert init.returncode==0,init.stderr
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            port=sock.getsockname()[1]
        address=str(root/"socket")
        start=proc(str(BIN/"pg_ctl"),"-D",str(data),"-l",str(root/"pg.log"),
                   "-o",f"-c listen_addresses='' -k {address} -p {port}",
                   "-w","start")
        assert start.returncode==0,start.stderr
        def run(sql=None,*,username="ubuntu",file=None,expect_error=False):
            args=[str(BIN/"psql"),"-X","-At","-v","ON_ERROR_STOP=1",
                  "-h",address,"-p",str(port),"-U",username,
                  "-d","crm_exact_lineage_fixture"]
            if file:
                args.extend(["-f",str(file)])
            else:
                args.extend(["-c",sql])
            result=proc(*args)
            if expect_error:
                assert result.returncode!=0, (result.stdout,result.stderr)
            else:
                assert result.returncode==0,(result.stdout,result.stderr)
            return result.stdout.strip(),result.stderr
        try:
            created=proc(str(BIN/"createdb"),"-h",address,"-p",str(port),
                         "-U","ubuntu","crm_exact_lineage_fixture")
            assert created.returncode==0,created.stderr
            run(file=FIXTURE)
            run(file=HELD)
            yield run
        finally:
            proc(str(BIN/"pg_ctl"),"-D",str(data),"-m","immediate","-w","stop")


def query(login,receipt,kind="event",prospect=P,opportunity=O):
    return f"""BEGIN READ ONLY;
SET LOCAL ROLE empire_revenue_crm_reader;
SELECT prospect_id, entity_id, tenant_id, opportunity_id, evidence_id, evidence_kind
FROM public.empire_crm_exact_lineage(
  '{prospect}'::uuid,'{opportunity}'::uuid,'{receipt}'::uuid,'{kind}'
);
ROLLBACK;"""


def test_original_tenant_a_only_gets_buyer_a_event_and_order(pg):
    run=pg
    for receipt,kind in ((EA,"event"),(OA,"order")):
        result,_=run(query("crm_fixture_a",receipt,kind),
                     username="crm_fixture_a")
        assert receipt in result and TA in result
    for receipt,kind in ((EB,"event"),(OB,"order"),(ENULL,"event"),(ONULL,"order")):
        result,_=run(query("crm_fixture_a",receipt,kind),
                     username="crm_fixture_a")
        assert "00000000-0000-0000-0000-000000000002" not in result


def test_original_tenant_b_only_gets_buyer_b_event_and_order(pg):
    run=pg
    for receipt,kind in ((EB,"event"),(OB,"order")):
        result,_=run(query("crm_fixture_b",receipt,kind),
                     username="crm_fixture_b")
        assert receipt in result and TB in result
    for receipt,kind in ((EA,"event"),(OA,"order"),(ENULL,"event"),(ONULL,"order")):
        result,_=run(query("crm_fixture_b",receipt,kind),
                     username="crm_fixture_b")
        assert "00000000-0000-0000-0000-000000000002" not in result


def test_no_raw_table_read_for_restricted_login(pg):
    run=pg
    for table in ("prospect_entity_links",
                  "tenant_business_entity_bindings",
                  "commercial_events","fulfilment_orders"):
        _,error=run(f"BEGIN READ ONLY;SET LOCAL ROLE empire_revenue_crm_reader;"
                    f"SELECT count(*) FROM public.{table};ROLLBACK;",
                    username="crm_fixture_a",expect_error=True)
        assert "permission denied" in error


def test_wrong_prospect_opportunity_or_unsupported_kind_yields_no_row(pg):
    run=pg
    wrong="99999999-9999-4999-8999-999999999999"
    for stmt in (
        query("crm_fixture_a",EA,prospect=wrong),
        query("crm_fixture_a",EA,opportunity=wrong),
        query("crm_fixture_a",EA,kind="payment"),
    ):
        result,_=run(stmt,username="crm_fixture_a")
        assert "00000000-0000-0000-0000-000000000002" not in result


def test_revoked_tenant_binding_immediately_denies_previous_receipt(pg):
    run=pg
    before,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA in before
    run(f"""UPDATE public.tenant_business_entity_bindings
        SET active=false WHERE tenant_id='{TA}'::uuid;""")
    after,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA not in after
    other,_=run(query("crm_fixture_b",EB),username="crm_fixture_b")
    assert EB in other
    run(f"UPDATE public.tenant_business_entity_bindings SET active=true WHERE tenant_id='{TA}'::uuid;")


def test_unresolved_identity_conflict_blocks_exact_buyer_receipt(pg):
    run=pg
    before,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA in before
    conflict=f"""INSERT INTO public.business_entity_conflicts VALUES
        ('{P}'::uuid,'00000000-0000-0000-0000-000000000002'::uuid,'unresolved');"""
    try:
        run(conflict)
        after,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
        assert EA not in after
    finally:
        run(f"DELETE FROM public.business_entity_conflicts WHERE prospect_id='{P}'::uuid;")
    restored,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA in restored


def test_ambiguous_duplicate_same_tenant_binding_blocks_receipt(pg):
    run=pg
    before,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA in before
    try:
        run(f"""INSERT INTO public.tenant_business_entity_bindings
           (tenant_id,entity_id,binding_kind,evidence_ref,active,valid_from)
           VALUES ('{TA}'::uuid,
             '00000000-0000-0000-0000-000000000002'::uuid,
             'managed','fixture:duplicate',true,CURRENT_TIMESTAMP-INTERVAL '1 day');""")
        held,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
        assert EA not in held
    finally:
        run(f"""DELETE FROM public.tenant_business_entity_bindings
            WHERE tenant_id='{TA}'::uuid AND binding_kind='managed';""")
    after,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA in after


def test_source_provenance_method_invalid_cannot_qualify_even_with_exact_buyer(pg):
    run=pg
    before,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA in before
    try:
        run(f"""UPDATE public.prospect_entity_links
            SET match_method='score_only' WHERE prospect_id='{P}'::uuid;""")
        held,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
        assert EA not in held
    finally:
        run(f"""UPDATE public.prospect_entity_links
            SET match_method='verified_source_identity' WHERE prospect_id='{P}'::uuid;""")


def test_reader_role_without_trusted_session_tenant_receives_nothing(pg):
    run=pg
    for receipt in (EA,EB,ENULL):
        result,_=run(query("crm_fixture_unbound",receipt),
                     username="crm_fixture_unbound")
        assert "00000000-0000-0000-0000-000000000002" not in result


def test_event_order_link_must_match_same_buyer_and_source_identity(pg):
    run=pg
    before,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
    assert EA in before
    try:
        # A's event references B's order on the shared company. A must NOT
        # receive a purported continuous handoff from inconsistent receipts.
        run(f"""UPDATE public.commercial_events
          SET fulfilment_order_id='{OB}'::uuid WHERE id='{EA}'::uuid;""")
        invalid,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
        assert EA not in invalid
        run(f"""UPDATE public.commercial_events
          SET fulfilment_order_id='{OA}'::uuid WHERE id='{EA}'::uuid;""")
        valid,_=run(query("crm_fixture_a",EA),username="crm_fixture_a")
        assert EA in valid
    finally:
        run(f"""UPDATE public.commercial_events
            SET fulfilment_order_id=NULL WHERE id='{EA}'::uuid;""")
