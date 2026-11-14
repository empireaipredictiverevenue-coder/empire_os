"""Durable supervised migration candidate for the 57 existing department hooks.

No production service changes. Ordered jobs by default until dependencies are
independently proved. Fail closed on interrupted jobs, drift and missing gate.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any, Callable, Mapping

INVENTORY_SCHEMA="empire.orchestration.existing_service_hook_inventory.v1"
STATE_SCHEMA="empire.department_hook_supervisor.v1"

class HookSupervisorError(ValueError):
    pass

def _read(path: Path) -> dict[str,Any] | None:
    try:
        d=json.loads(path.read_text())
    except (OSError,ValueError):
        return None
    return d if isinstance(d,dict) else None

def _write(path: Path, data: Mapping[str,Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    tmp.replace(path)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def validate_inventory(data: Mapping[str,Any]) -> list[dict[str,Any]]:
    rows=data.get("hooks")
    if data.get("schema_version")!=INVENTORY_SCHEMA or not isinstance(rows,list) or not 1<=len(rows)<=64:
        raise HookSupervisorError("invalid_inventory")
    result=[]
    for index,row in enumerate(rows,1):
        if not isinstance(row,dict) or row.get("order")!=index:
            raise HookSupervisorError("invalid_order")
        command=row.get("command")
        optional=row.get("failure_ignored_by_systemd")
        if not isinstance(command,str) or type(optional) is not bool or command.startswith("-")!=optional:
            raise HookSupervisorError("invalid_command_or_semantics")
        argv=shlex.split(command[1:] if optional else command)
        if not argv or argv[0] not in ("/srv/empire_os/.venv/bin/python","/bin/bash"):
            raise HookSupervisorError("executable_not_allowlisted")
        if argv[0]=="/bin/bash" and (len(argv)!=3 or argv[1]!="-c"):
            raise HookSupervisorError("bash_contract_unknown")
        result.append({"position":index,"command":command,"argv":argv,
                       "optional":optional,"drop_in":row.get("drop_in")})
    return result

def inventory_digest(jobs: list[dict[str,Any]]) -> str:
    return sha256(json.dumps(
        [(j["position"],j["command"],j["optional"],j["drop_in"]) for j in jobs],
        sort_keys=True,separators=(",",":")
    ).encode()).hexdigest()

def matches_current_service(jobs: list[dict[str,Any]],service_cat: str) -> bool:
    current=[line.split("=",1)[1] for line in service_cat.splitlines() if line.startswith("ExecStartPost=")]
    return len(jobs)==len(current) and all(x["command"]==y for x,y in zip(jobs,current))

def _initial(jobs: list[dict[str,Any]],cycle: str) -> dict[str,Any]:
    return {
        "schema_version":STATE_SCHEMA,"cycle_id":cycle,
        "inventory_digest":inventory_digest(jobs),
        "status":"PENDING","created_at":_now(),"updated_at":_now(),
        "next_position":1,"service_modified":False,
        "jobs":[{
            "position":j["position"],"optional":j["optional"],
            "command_sha256":sha256(j["command"].encode()).hexdigest(),
            "depends_on_previous":j["position"]>1,
            "state":"PENDING"} for j in jobs],
    }

def supervise(
    jobs: list[dict[str,Any]],*,cycle_id: str,checkpoint: Path,
    execute: bool=False,max_items: int=4,
    governance_check: Callable[[],bool] | None=None,
    runner: Callable[...,Any]=subprocess.run,
) -> dict[str,Any]:
    if not jobs or type(max_items) is not int or not 1<=max_items<=12:
        raise HookSupervisorError("invalid_batch")
    if not cycle_id or len(cycle_id)>120 or "/" in cycle_id or ".." in cycle_id:
        raise HookSupervisorError("invalid_cycle")
    if not execute:
        return {
            "status":"DRY_RUN","job_count":len(jobs),
            "inventory_digest":inventory_digest(jobs),
            "checkpoint_created":False,"commands_executed":0,
            "sequential_dependencies_preserved":True,
        }
    if governance_check is None or governance_check() is not True:
        raise HookSupervisorError("governed_activation_required")
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    with checkpoint.with_suffix(".lock").open("a+") as lease:
        try:
            fcntl.flock(lease.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise HookSupervisorError("concurrent_supervisor_denied") from exc
        state=_read(checkpoint)
        if state is None:
            if checkpoint.exists():
                raise HookSupervisorError("checkpoint_unreadable_fail_closed")
            state=_initial(jobs,cycle_id)
        if (state.get("schema_version")!=STATE_SCHEMA or
            state.get("inventory_digest")!=inventory_digest(jobs) or
            state.get("cycle_id")!=cycle_id):
            raise HookSupervisorError("unrecognised_or_changed_cycle")
        rows=state.get("jobs")
        if not isinstance(rows,list) or len(rows)!=len(jobs):
            raise HookSupervisorError("checkpoint_incomplete")
        for i,(task,job) in enumerate(zip(rows,jobs),1):
            if (task.get("position")!=i or task.get("command_sha256")!=sha256(job["command"].encode()).hexdigest()):
                raise HookSupervisorError("job_identity_changed")
        if any(x["state"]=="RUNNING" for x in rows):
            state["status"]="INTERRUPTED_REQUIRES_REVIEW"
            state["updated_at"]=_now()
            _write(checkpoint,state)
            return state
        if state["status"] in ("COMPLETE","HELD_REQUIRED_FAILURE","INTERRUPTED_REQUIRES_REVIEW"):
            return state
        count=0
        for item,job in zip(rows,jobs):
            if item["state"] in ("DONE","OPTIONAL_FAILED"):
                continue
            if item["state"]!="PENDING":
                raise HookSupervisorError("unexpected_job_state")
            if count>=max_items:
                break
            item["state"]="RUNNING"; item["started_at"]=_now()
            state["status"]="IN_PROGRESS";state["next_position"]=job["position"]
            _write(checkpoint,state)
            try:
                response=runner(
                    job["argv"],cwd="/srv/empire_os",
                    capture_output=True,text=True,timeout=75,check=False,
                )
                code=response.returncode
                failure=None if code==0 else "NONZERO_EXIT"
            except subprocess.TimeoutExpired:
                code=None;failure="TIMEOUT"
            except OSError:
                code=None;failure="OS_EXECUTION_ERROR"
            item["completed_at"]=_now();item["exit_code"]=code
            item["failure_class"]=failure
            item["state"]=("DONE" if failure is None else
                           "OPTIONAL_FAILED" if job["optional"] else "FAILED")
            state["next_position"]=job["position"]+1
            count+=1
            if failure and not job["optional"]:
                state["status"]="HELD_REQUIRED_FAILURE"
                break
            _write(checkpoint,state)
        if all(x["state"] in ("DONE","OPTIONAL_FAILED") for x in rows):
            state["status"]="COMPLETE"
        state["updated_at"]=_now()
        _write(checkpoint,state)
        return state
