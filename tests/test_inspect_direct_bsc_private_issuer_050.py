"""050 preflight classify failures without production database writes."""
import inspect
import pytest
from scripts import inspect_direct_bsc_private_issuer_050 as gate


def snapshot():
    return {
        "identity":("empiredb","postgres",False),
        "capability":(True,True,"empiredb_migrator",1),
        "reader_roles":[(gate.OWNER,False,False,False),
                        (gate.READER,False,False,False)],
        "reader_role_member_count":0,
        "status_function":(gate.OWNER,True,True,False),
        "payment_request_rls":(True,False,11),
        "guard_trigger":True,
        "issuer_roles_absent":(True,True),
        "issuer_function_absent":True,
        "migrator_login":(True,True,True,True),
    }


def test_full_049_catalog_before_050_ready_but_no_installation():
    result=gate.classify(snapshot())
    assert result["status"]=="READY_FOR_SEPARATELY_APPROVED_PRIVATE_ISSUER_050"
    assert all(
        result[name] for name in (
            "canonical_empiredb","capability_force_rls_one_policy",
            "reader_and_owner_isolated","reader_role_memberships_zero",
            "private_status_function_sealed","request_rls_policy_count",
            "047_guard_trigger_present","issuer_roles_absent",
            "issuer_function_absent","existing_migrator_login_preserved",
        )
    )
    assert result["migration_050_applied"] is False
    assert result["buyer_status_endpoint_activated"] is False
    assert result["payment_execution"] is False
    assert result["release_gate"]=="FOUNDER_APPROVAL_050_REQUIRED"


@pytest.mark.parametrize("name,value",[
    ("identity",("wrong","postgres",False)),
    ("capability",(True,False,"empiredb_migrator",1)),
    ("capability",(True,True,"empiredb_migrator",0)),
    ("reader_roles",[]),
    ("reader_role_member_count",1),
    ("status_function",(gate.OWNER,False,True,False)),
    ("status_function",(gate.OWNER,True,True,True)),
    ("payment_request_rls",(True,False,12)),
    ("payment_request_rls",(True,True,11)),
    ("guard_trigger",False),
    ("issuer_roles_absent",(False,True)),
    ("issuer_function_absent",False),
    ("migrator_login",(False,True,True,True)),
])
def test_any_catalog_drift_blocks(name,value):
    data=snapshot();data[name]=value
    assert gate.classify(data)["status"]=="HELD_PRIVATE_ISSUER_050_GATES"


def test_exact_readonly_invocation(capsys):
    assert gate.main([])==3
    assert gate.main(["--apply"])==3
    assert "HELD_READONLY_PREFLIGHT_FLAG_REQUIRED" in capsys.readouterr().out
    src=inspect.getsource(gate)
    assert "SET TRANSACTION READ ONLY" in src
    for forbidden in (
        "INSERT INTO public.","UPDATE public.","DELETE FROM public.",
        "CREATE ROLE ","ALTER ROLE ","CREATE POLICY ",
        "COMMIT;","GRANT SELECT ON",
        "FROM public.bsc_payment_requests",
        "FROM public.direct_bsc_buyer_capabilities",
        "FROM public.fulfilment_orders",
    ):
        assert forbidden not in src
