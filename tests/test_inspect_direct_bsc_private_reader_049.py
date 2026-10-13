"""049 v2 preflight: exact production catalog after 047/048; zero writes."""
import inspect
import pytest
from scripts import inspect_direct_bsc_private_reader_049 as gate


def safe():
    return {
        "identity": ("empiredb","postgres",False),
        "capability": (True,True,"empiredb_migrator",0,0),
        "owner_role_absent": True,
        "reader_role_absent": True,
        "reader_function_absent": True,
        "migrator_incoming_member_details": [gate.EXPECTED_INCOMING.copy()],
        "parents": gate.EXPECTED_PARENTS.copy(),
        "parent_select_policy_counts": [5,6,11],
        "source_selects": (True,True,True),
    }


def test_exact_existing_live_role_membership_is_expected_not_removed():
    result=gate.classify(safe())
    assert result["status"]=="READY_FOR_SEPARATELY_APPROVED_PRIVATE_READER_049"
    assert result["expected_existing_migrator_login_preserved"] is True
    assert result["parent_rls_matches_audited_baseline"] is True
    assert result["parent_select_policy_present"] is True
    assert result["schema_version"].endswith(".v2")
    assert result["mode"]=="READ_ONLY"
    assert result["migration_049_applied"] is False
    assert result["reader_login_assigned"] is False
    assert result["buyer_status_endpoint_activated"] is False
    assert result["payment_execution"] is False
    assert result["release_gate"]=="FOUNDER_APPROVAL_049_REQUIRED"


@pytest.mark.parametrize("field,value",[
    ("identity",("foreign","postgres",False)),
    ("identity",("empiredb","empiredb_migrator",False)),
    ("identity",("empiredb","postgres",True)),
    ("capability",(True,False,"empiredb_migrator",0,0)),
    ("capability",(True,True,"postgres",0,0)),
    ("capability",(True,True,"empiredb_migrator",1,0)),
    ("capability",(True,True,"empiredb_migrator",0,1)),
    ("capability",None),
    ("owner_role_absent",False),
    ("reader_role_absent",False),
    ("reader_function_absent",False),
    ("migrator_incoming_member_details",[]),
    ("migrator_incoming_member_details",[
       {"role":"empiredb_migrator_login","can_login":False}
    ]),
    ("migrator_incoming_member_details",[
       {**gate.EXPECTED_INCOMING,"set_option":False}
    ]),
    ("migrator_incoming_member_details",[
       gate.EXPECTED_INCOMING,gate.EXPECTED_INCOMING
    ]),
    ("parents",gate.EXPECTED_PARENTS[:2]),
    ("parents",[("bsc_payment_evidence","postgres",True,False,9,0),
                  *gate.EXPECTED_PARENTS[1:]]),
    ("parents",[("bsc_payment_evidence","empiredb_migrator",True,True,9,0),
                  *gate.EXPECTED_PARENTS[1:]]),
    ("parents",[("bsc_payment_evidence","empiredb_migrator",True,False,9,1),
                  *gate.EXPECTED_PARENTS[1:]]),
    ("parents",[("bsc_payment_evidence","empiredb_migrator",True,False,8,0),
                  *gate.EXPECTED_PARENTS[1:]]),
    ("parent_select_policy_counts",[5,6,12]),
    ("parent_select_policy_counts",[0,6,11]),
    ("source_selects",(True,False,True)),
])
def test_each_privilege_or_catalog_drift_fails_closed(field,value):
    data=safe()
    data[field]=value
    assert gate.classify(data)["status"]=="HELD_PRIVATE_READER_049_GATES"


def test_rejects_nonreadonly_invocation_and_prevents_mutation(capsys):
    assert gate.main([])==3
    assert gate.main(["--apply"])==3
    assert gate.main(["--preflight","--apply"])==3
    assert "HELD_EXACT_READONLY_PREFLIGHT_FLAG_REQUIRED" in capsys.readouterr().out
    src=inspect.getsource(gate)
    assert "SET TRANSACTION READ ONLY" in src
    assert "pg_catalog.pg_auth_members" in src
    assert "pg_catalog.pg_policy" in src
    assert "pg_catalog.pg_roles" in src
    assert "pg_catalog.aclexplode" in src
    assert "pg_catalog.to_regprocedure" in src
    for invalid in (
       "ALTER ROLE ","CREATE ROLE ","CREATE POLICY ",
       "COMMIT;","GRANT SELECT ","REVOKE ","UPDATE public.",
       "DELETE FROM public.","INSERT INTO public.","FROM public.buyers",
       "FROM public.bsc_payment_requests","FROM public.fulfilment_orders",
       "FROM public.direct_bsc_buyer_capabilities",
    ):
        assert invalid not in src
