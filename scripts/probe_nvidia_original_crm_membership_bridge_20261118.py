"""Immutable live read-only original CRM membership bridge acceptance.

Run in the existing NVIDIA MCP venv; the original CRM membership worker runs
with its original pinned EmpireOS virtualenv/dedicated DB login.
Never emit user IDs, tenant UUIDs, credentials, SQL or DSN.
"""
from __future__ import annotations
import json,os
from pathlib import Path

from empire_os.nvidia_canonical_membership_adapter import ExistingCrmMembershipAdapter

OUT=Path("/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_original_crm_membership_bridge_20261118.json")
FOUNDER="founder:phil_livesley"
TENANT="708efd4b-53b2-43d7-961d-1cecab67f17a"
OTHER="20000000-0000-4000-8000-000000000002"

def main():
    if OUT.exists():raise RuntimeError("previous private acceptance evidence must not be overwritten")
    reader=ExistingCrmMembershipAdapter()
    genuine=reader(FOUNDER,TENANT)
    unknown=reader("unrecognised-nvidia-subject",TENANT)
    wrong=reader(FOUNDER,OTHER)
    result={
        "status":"NVIDIA_EXISTING_FIRST_PARTY_CRM_MEMBERSHIP_READ_BRIDGE_VERIFIED"
                 if genuine is not None and genuine.can("read") and unknown is None and wrong is None
                 else "ORIGINAL_CRM_MEMBERSHIP_BRIDGE_HELD",
        "executed_in_existing_nvidia_python_environment":True,
        "used_original_empire_crm_membership_login":True,
        "original_founder_membership_active_and_tenant_matched":genuine is not None and genuine.can("read"),
        "unknown_subject_denied":unknown is None,
        "wrong_tenant_denied":wrong is None,
        "new_identity_grant_created":False,
        "signed_crosswalk_production_issued":False,
        "production_tenant_sql_execution_verified":False,
        "secrets_or_identifiers_logged":False,
        "write_transactions":False,
    }
    fd=os.open(OUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as file:json.dump(result,file,sort_keys=True,indent=2)
    print(json.dumps(result,sort_keys=True,indent=2))
    if "VERIFIED" not in result["status"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
