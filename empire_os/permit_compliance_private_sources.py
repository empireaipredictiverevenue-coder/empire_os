"""Lightweight custody-only reader for original Permit Compliance review inputs.

Reuses existing original workbench and Gmail draft observation validators.
This module contains NO acquisition research, original sender, DB gateway or
permit scraper dependencies; safe to import from the existing Gmail timer.
"""
from __future__ import annotations

from datetime import datetime,timedelta
from hashlib import sha256
import json,stat
from pathlib import Path

from empire_os.permit_national_buyer_pilot_readiness import (
    validate_observation,_aware,
)
from empire_os.permit_national_outreach_value_first_workbench import validate_workbench

PRIVATE=Path("runtime/permit_intelligence/founder_growth_previews")
WORKBENCH_FOLDER=PRIVATE/"private_national_value_first"
PINNED_FOLDER=PRIVATE/"private_national_workspace_draft_observations"


def _read_private(root:Path,path:Path,folder:Path,low:int,high:int)->tuple[dict,bytes]:
    root=root.resolve()
    parent=root/folder
    path=path.absolute()
    if (parent.is_symlink() or path.is_symlink()
        or path.parent!=parent or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode)!=0o600
        or not low<=path.stat().st_size<=high):
        raise ValueError("ORIGINAL_COMPLIANCE_CUSTODIED_INPUT_MISSING")
    raw=path.read_bytes()
    try:value=json.loads(raw)
    except ValueError:raise ValueError("ORIGINAL_COMPLIANCE_INPUT_JSON_INVALID") from None
    if not isinstance(value,dict):
        raise ValueError("ORIGINAL_COMPLIANCE_INPUT_JSON_INVALID")
    return value,raw


def read_workbench(*,root:Path,path:Path)->dict:
    workbench,raw=_read_private(root,path,WORKBENCH_FOLDER,1000,130000)
    validate_workbench(workbench)
    proof,_=_read_private(
        root,path.with_name(path.stem+".receipt.json"),
        WORKBENCH_FOLDER,100,4000,
    )
    if (proof.get("schema_version")!="empire.permit_data.original_value_first_owner_review_receipt.v1"
        or proof.get("workbench_sha256")!=workbench["value_first_workbench_sha256"]
        or proof.get("report_sha256")!=sha256(raw).hexdigest()
        or proof.get("approved_recipients")!=0
        or proof.get("real_sends")!=0):
        raise ValueError("ORIGINAL_COMPLIANCE_WORKBENCH_RECEIPT_NOT_VERIFIED")
    return workbench


def read_connector_observation(*,root:Path,path:Path,
                               now:datetime,pin_only:bool=False)->dict:
    observation,raw=_read_private(root,path,PINNED_FOLDER,3000,30000)
    if pin_only:
        anchor=_aware(observation.get("observed_at_utc"))
        validate_observation(observation,anchor)
        if now.utcoffset() is None or now<anchor or now-anchor>timedelta(days=30):
            raise ValueError("ORIGINAL_COMPLIANCE_PINNED_DRAFT_COHORT_EXPIRED")
    else:
        validate_observation(observation,now)
    proof,_=_read_private(
        root,path.with_name(path.stem+".receipt.json"),
        PINNED_FOLDER,100,4000,
    )
    if (proof.get("schema_version")!="empire.permit_data.workspace_drafts_local_sha_receipt.v1"
        or proof.get("observed_data_sha256")!=sha256(raw).hexdigest()
        or proof.get("source_observation_sha256")!=observation["observation_sha256"]
        or proof.get("read_only") is not True
        or proof.get("new_messages_sent") is not False):
        raise ValueError("ORIGINAL_COMPLIANCE_PINNED_DRAFT_RECEIPT_NOT_VERIFIED")
    return observation
