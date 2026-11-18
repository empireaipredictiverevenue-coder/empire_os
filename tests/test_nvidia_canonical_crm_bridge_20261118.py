"""NVIDIA's actual original EmpireOS CRM membership bridge: fail-closed tests."""
from __future__ import annotations
import json
import subprocess
from dataclasses import dataclass
from types import SimpleNamespace
import pytest

from empire_os.nvidia_canonical_membership_adapter import ExistingCrmMembershipAdapter

TENANT="708efd4b-53b2-43d7-961d-1cecab67f17a"
OTHER="20000000-0000-4000-8000-000000000002"
USER="founder:phil_livesley"


def fake_runner(result,record=None):
    def run(argv,**kwargs):
        if record is not None:record.append((argv,kwargs))
        if isinstance(result,Exception):raise result
        return result
    return run


def completed(reply,exit_code=0):
    return SimpleNamespace(returncode=exit_code,stdout=reply,stderr="")


def test_original_membership_bridge_accepts_only_canonical_role():
    recorded=[]
    reader=ExistingCrmMembershipAdapter(runner=fake_runner(
        completed('{"verified":true,"role":"viewer"}\n'),recorded))
    member=reader(USER,TENANT)
    assert member is not None
    assert member.user_id==USER and member.tenant_id==TENANT
    assert member.can("read") is True
    assert len(recorded)==1
    argv,kw=recorded[0]
    assert argv[0].endswith("/srv/empire_os/.venv/bin/python")
    assert argv[-1]=="scripts.nvidia_existing_crm_membership_worker_20261118"
    assert "password" not in kw["input"].lower()
    assert json.loads(kw["input"])=={"subject":USER,"tenant_id":TENANT}
    assert "PGPASSFILE" not in kw["env"]
    assert kw["timeout"]==6
    assert kw["check"] is False


@pytest.mark.parametrize("response,exit_code",[
    ('{"verified":false}',2),
    ('{"verified":true,"role":"superuser"}',0),
    ('{"verified":true,"role":"viewer","admin":true}',0),
    ("",0),
    ("garbage",0),
    ('{"verified":true,"role":"viewer"}',3),
    ('{"verified":true,"role":"viewer"}'*100,0),
    ('{"verified":true,"role":null}',0),
])
def test_unexpected_original_worker_readback_denied(response,exit_code):
    reader=ExistingCrmMembershipAdapter(
        runner=fake_runner(completed(response,exit_code)))
    assert reader(USER,TENANT) is None


@pytest.mark.parametrize("bad_user,bad_tenant",[
    ("",TENANT),("candidate user",TENANT),("subject", "not-a-uuid"),
    ("subject",OTHER+" "),("../etc/passwd",TENANT),
    ("subject\nother",TENANT),
])
def test_untrusted_caller_input_cannot_reach_original_db(bad_user,bad_tenant):
    hits=[]
    reader=ExistingCrmMembershipAdapter(
        runner=fake_runner(completed('{"verified":true,"role":"owner"}'),hits))
    assert reader(bad_user,bad_tenant) is None
    assert hits==[]


def test_database_timeout_and_os_error_fail_closed():
    for err in (subprocess.TimeoutExpired("membership",6),
                OSError("cannot start dedicated CRM member reader")):
        assert ExistingCrmMembershipAdapter(
            runner=fake_runner(err))(USER,TENANT) is None


def test_no_business_data_or_identity_values_printed_by_original_worker(tmp_path):
    from pathlib import Path
    script=Path(__file__).resolve().parents[1]/"scripts/nvidia_existing_crm_membership_worker_20261118.py"
    code=script.read_text()
    assert "EmpireDbCrmMembershipReader" in code
    assert "empire_crm_membership_login" in code
    assert "psycopg.connect" not in code  # don't rebuild identity SQL
    assert "member.__dict__" not in code
    assert "print(member" not in code


def test_live_original_first_party_canonical_membership_readback():
    from pathlib import Path
    config=Path("/var/lib/empire-crm-first-party/pilot-runtime.json")
    if not config.is_file():
        pytest.skip("Live first-party founder CRM is not present")
    member=ExistingCrmMembershipAdapter()(USER,TENANT)
    assert member is not None
    assert member.can("read") is True
    assert ExistingCrmMembershipAdapter()(USER,OTHER) is None
    assert ExistingCrmMembershipAdapter()("unrecognised-subject",TENANT) is None
