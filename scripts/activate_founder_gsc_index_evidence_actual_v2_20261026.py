#!/usr/bin/env python3
"""Guarded v2 activation against REAL systemd WorkingDirectory.

The earlier v1 script used /srv/empire_os/apps/search-command-centre/.next,
but the effective Founder Console WorkingDirectory is an existing private
release under /home/ubuntu/empire_releases/property_birmingham_.../web.
This v2 preserves all pre-existing private founder routes. One service only.
"""
from __future__ import annotations

import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import urlopen

APP = Path("/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3/web")
RELEASE = Path("/home/ubuntu/empire_releases/seo_founder_indexed_evidence_20261026_v2")
SNAPSHOT = RELEASE / "actual_current_web_snapshot"
CANDIDATE = APP / ".next_gsc_indexed_actual_release_candidate_20261026"
LIVE = APP / ".next"
PREVIOUS = APP / ".next_before_gsc_indexed_actual_v2_20261026"
FAILED = APP / ".next_failed_gsc_indexed_actual_v2_20261026"
RESULT = RELEASE / "activation_result.json"
SELECTION = (
    "src/lib/search-api.ts",
    "src/app/department/evidence/page.tsx",
)
UNIT = "empire-founder-console.service"

def sha(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()

def unit_property(name: str) -> str:
    return subprocess.check_output(
        ["systemctl", "show", UNIT, "--value", "-p", name],
        text=True, timeout=12,
    ).strip()

def unit_restart(action: str) -> None:
    subprocess.run(["systemctl", action, UNIT], check=True, timeout=35,
                   stdout=subprocess.DEVNULL)

def original_files(base: Path) -> dict[str, str]:
    rows = {}
    for path in base.rglob("*"):
        rel = path.relative_to(base)
        if any(seg in {"node_modules", ".next"} or
               seg.startswith(".next-") or seg.startswith(".next.") or
               seg.startswith(".next_") for seg in rel.parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        if (rel.parts[0] == "src" or
            str(rel) in {
                "package.json", "package-lock.json", "next.config.ts",
                "next-env.d.ts", "tsconfig.json", "postcss.config.mjs",
                "eslint.config.mjs",
            }):
            rows[str(rel)] = sha(path)
    return rows

def check_preflight() -> dict:
    if unit_property("WorkingDirectory") != str(APP):
        raise RuntimeError("RUNTIME_WORKDIR_CHANGED_REFUSE_UNSAFE_RELEASE")
    if unit_property("ActiveState") != "active":
        raise RuntimeError("ORIGINAL_FOUNDER_CONSOLE_NOT_ACTIVE")
    start = unit_property("ExecStart")
    if "/srv/empire_os/apps/search-command-centre/node_modules/next/dist/bin/next" not in start:
        raise RuntimeError("ORIGINAL_NEXTJS_EXECUTION_OWNER_CHANGED")
    record = json.loads((RELEASE / "preflight.json").read_text())
    if (record.get("status") !=
          "CURRENT_ACTUAL_RELEASE_BUILD_STAGED_AND_READY_FOR_GUARDED_ACTIVATION"
        or record.get("effective_working_directory") != str(APP)):
        raise RuntimeError("ACTUAL_RUNTIME_SOURCE_REVIEW_MISSING")
    if RESULT.exists() or PREVIOUS.exists() or FAILED.exists():
        raise RuntimeError("ACTIVATION_ALREADY_ATTEMPTED_REVIEW_RECEIPTS")
    if (not CANDIDATE.is_dir() or CANDIDATE.is_symlink()
        or not LIVE.is_dir() or LIVE.is_symlink()):
        raise RuntimeError("COMPILED_BUILD_NOT_NORMAL_DIR")
    if ((LIVE / "BUILD_ID").read_text().strip() != record["old_build_id"]
        or (CANDIDATE / "BUILD_ID").read_text().strip() != record["candidate_build_id"]):
        raise RuntimeError("LIVE_OR_CANDIDATE_BUILD_ID_CHANGED")
    before = original_files(APP)
    if before != record["actual_runtime_source_sha256_before"]:
        raise RuntimeError("ACTIVE_FOUNDER_RELEASE_CHANGED_BY_OTHER_OWNER")
    if original_files(SNAPSHOT) != record["candidate_snapshot_source_sha256"]:
        raise RuntimeError("REVIEWED_FOUNDER_CANDIDATE_SOURCE_CHANGED")
    if set(record["source_diff_exactly_two_SEO_files"]) != set(SELECTION):
        raise RuntimeError("REVIEWED_FILE_SCOPE_IS_NOT_TWO_ORIGINAL_SEO_FILES")
    for rel in SELECTION:
        diff = record["source_diff_exactly_two_SEO_files"][rel]
        if sha(APP / rel) != diff["old_sha256"] or sha(SNAPSHOT / rel) != diff["new_sha256"]:
            raise RuntimeError("EXACT_SOURCE_PREIMAGE_MISSING:" + rel)
    return record

def live_page_ok() -> bool:
    expected = {
        "/department/evidence": ("Indexed versions", "five owned pages"),
        "/founder": (),
        "/founder/agency": ("Agency acquisition readiness",),
        "/founder/commercial-pipeline": (),
        "/founder/research": (),
        "/founder/youtube": (),
        "/founder/intent-review": (),
    }
    for _ in range(14):
        try:
            values = []
            for route, snippets in expected.items():
                with urlopen("http://127.0.0.1:3001" + route, timeout=10) as res:
                    body = res.read(300_000).decode("utf-8", "replace")
                    values.append(res.status == 200 and
                                  all(s in body for s in snippets))
            if all(values):
                return True
        except (OSError, TimeoutError):
            pass
        time.sleep(1)
    return False

def write_receipt(state: str, **fields: object) -> None:
    doc = {
        "schema_version": "empire.search.founder_actual_runtime_activation.v2",
        "status": state,
        "effective_original_working_directory": str(APP),
        "unit": UNIT,
        "google_indexing_submission": False,
        "database_writes": False,
        "no_new_service": True,
        "other_founder_features_preserved": True,
        **fields,
    }
    temp = RESULT.with_name("activation_result.json.tmp")
    temp.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    os.replace(temp, RESULT)

def activate() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("EXISTING_SYSTEMD_SERVICE_RESTART_REQUIRES_SUDO")
    lockfd = os.open("/run/lock/empire-founder-actual-gsc-v2.lock",
                     os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(lockfd, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=check_preflight()
        source_backups=[]
        new_build=False
        old_build=False
        stopped=False
        try:
            # The service and source stay untouched until every preimage passes.
            unit_restart("stop")
            stopped=True
            # Preserve original inode metadata so a rollback returns exact state.
            for rel in SELECTION:
                old=APP/rel
                bak=old.with_name(old.name+".before_gsc_indexed_actual_v2")
                if bak.exists():raise RuntimeError("SOURCE_BACKUP_COLLISION:"+rel)
                os.rename(old,bak)
                source_backups.append((old,bak))
                copy=old.with_name(old.name+".new_seo_indexed_actual_v2")
                if copy.exists():raise RuntimeError("TEMP_NEW_SOURCE_COLLISION:"+rel)
                shutil.copy2(SNAPSHOT/rel,copy)
                st=os.stat(bak)
                os.chown(copy, st.st_uid, st.st_gid)
                os.replace(copy,old)
                if sha(old)!=state["source_diff_exactly_two_SEO_files"][rel]["new_sha256"]:
                    raise RuntimeError("NEW_SEO_SOURCE_MISMATCH:"+rel)
            os.rename(LIVE,PREVIOUS)
            old_build=True
            os.rename(CANDIDATE,LIVE)
            new_build=True
            unit_restart("start")
            if not live_page_ok() or unit_property("ActiveState") != "active":
                raise RuntimeError("NEW_TRUE_RUNTIME_SEO_OR_FOUNDER_ROUTES_FAILED")
            write_receipt(
                "FOUNDER_GSC_INDEX_EVIDENCE_LIVE_VERIFIED",
                old_build_id=state["old_build_id"],
                new_build_id=state["candidate_build_id"],
                original_build_backup=str(PREVIOUS),
                source_backups_kept=[str(b) for _,b in source_backups],
                checked_private_routes=7,
                seo_indexed_view_http=200,
            )
            print(json.dumps({"status":"FOUNDER_GSC_INDEX_EVIDENCE_LIVE_VERIFIED",
              "service":UNIT,"route":"/department/evidence",
              "checked_private_routes":7,
              "backup":str(PREVIOUS)},sort_keys=True))
        except Exception as reason:
            # Restore BOTH the running build and the original source files.
            if stopped:
                try:
                    unit_restart("stop")
                    if new_build and LIVE.exists() and not FAILED.exists():
                        os.rename(LIVE,FAILED)
                    if old_build and PREVIOUS.exists() and not LIVE.exists():
                        os.rename(PREVIOUS,LIVE)
                    for old,bak in reversed(source_backups):
                        if old.exists():old.unlink()
                        if bak.exists():os.rename(bak,old)
                    unit_restart("start")
                    write_receipt("ROLLED_BACK_OLD_ACTUAL_RELEASE_RESTORED",
                                  failure_code=type(reason).__name__,
                                  current_service_active=unit_property("ActiveState"))
                except Exception as recovery_error:
                    write_receipt("OPERATOR_RECOVERY_REQUIRED",
                                  failure_code=type(reason).__name__,
                                  rollback_error=type(recovery_error).__name__)
                    raise
            raise

def main() -> None:
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight",action="store_true")
    g.add_argument("--activate",action="store_true")
    args=p.parse_args()
    if args.preflight:
        r=check_preflight()
        print(json.dumps({"status":"ACTUAL_FOUNDER_RELEASE_READY",
          "effective_working_directory":str(APP),
          "old_build_id":r["old_build_id"],
          "candidate_build_id":r["candidate_build_id"],
          "unchanged_running_source_files":len(r["actual_runtime_source_sha256_before"]),
          "reviewed_seo_source_files":len(SELECTION),"restart_performed":False},
          sort_keys=True))
    else:
        activate()

if __name__=="__main__":
    main()
