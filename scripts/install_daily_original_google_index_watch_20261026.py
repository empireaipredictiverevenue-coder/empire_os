#!/usr/bin/env python3
"""Attach five-URL Google index review to EXISTING organic-search daily timer.

Only a systemd drop-in for original empire-organic-search-recovery.service.
Never restarts the service/timer. No new service, outbound or DB authority.
Preflight works without privilege; activation requires founder sudo.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

SRC=Path("/srv/empire_os/deploy/systemd/empire-organic-search-recovery.daily-google-index-20261026.conf")
DROPIN_DIR=Path("/etc/systemd/system/empire-organic-search-recovery.service.d")
DROPIN=DROPIN_DIR/"70-seo-google-index-evidence-20261026.conf"
SCRIPT=Path("/srv/empire_os/scripts/review_daily_original_google_index_20261026.py")
EVIDENCE=Path("/home/ubuntu/empire_releases/seo_daily_index_status_20261026")
RECEIPT=EVIDENCE/"activation_receipt.json"
SERVICE="empire-organic-search-recovery.service"
TIMER="empire-organic-search-recovery.timer"

def output(*args:str)->str:
    return subprocess.check_output(args,text=True,timeout=15).strip()

def preflight():
    if not SRC.is_file() or SRC.is_symlink() or not SCRIPT.is_file() or SCRIPT.is_symlink():
        raise RuntimeError("REVIEWED_ORIGINAL_SOURCE_FILES_MISSING")
    content=SRC.read_text()
    if content.count("ExecStartPost=")!=1 or content.count("ReadWritePaths=")!=1:
        raise RuntimeError("ONE_APPEND_ONLY_POST_REVIEW_REQUIRED")
    if "ExecStartPost=-/srv/empire_os/.venv/bin/python -B " not in content or "--write-daily" not in content:
        raise RuntimeError("ORIGINAL_REVIEW_ONLY_COMMAND_NOT_RECOGNIZED")
    if DROPIN.exists() or DROPIN.is_symlink() or RECEIPT.exists():
        raise RuntimeError("ORIGINAL_UNIT_ALREADY_ACTIVATED_OR_OTHER_OWNER_CONFLICT")
    if not EVIDENCE.is_dir() or EVIDENCE.is_symlink() or EVIDENCE.stat().st_mode & 0o077:
        raise RuntimeError("PRIVATE_EVIDENCE_FOLDER_MISSING")
    if not (EVIDENCE/"google-index-2026-10-26.json").is_file():
        raise RuntimeError("VERIFIED_DAY_ONE_BASELINE_REQUIRED")
    if output("systemctl","is-active",TIMER)!="active":
        raise RuntimeError("ORIGINAL_DAILY_TIMER_MUST_REMAIN_ACTIVE")
    if output("systemctl","show",SERVICE,"--value","-p","User")!="ubuntu":
        raise RuntimeError("ORIGINAL_SERVICE_USER_CHANGED")
    start=output("systemctl","show",SERVICE,"--value","-p","ExecStart")
    if "/srv/empire_os/scripts/preflight_organic_search_legacy_recovery.py" not in start:
        raise RuntimeError("ORIGINAL_ORGANIC_OBSERVER_OWNER_CHANGED")
    if output("systemctl","show",SERVICE,"--value","-p","ExecStartPost"):
        raise RuntimeError("OTHER_AGENT_ALREADY_ATTACHED_ORIGINAL_SERVICE_POST_REVIEW")
    if output("systemctl","show",SERVICE,"--value","-p","ActiveState")=="activating":
        raise RuntimeError("ORIGINAL_ONESHOT_SERVICE_ALREADY_RUNNING")
    return {"status":"EXISTING_ORGANIC_DAILY_OWNER_ADDENDUM_READY",
            "original_unit":SERVICE,"original_timer":TIMER,
            "next_elapse":output("systemctl","show",TIMER,"--value","-p","NextElapseUSecRealtime"),
            "source_sha256":sha256(SRC.read_bytes()).hexdigest(),
            "new_services":0,"new_timers":0,
            "current_daily_receipt_exists":True,
            "systemd_modified":False}

def activate():
    if os.geteuid()!=0:
        raise RuntimeError("FOUNDERS_SYSTEMD_OPERATOR_APPROVAL_REQUIRED_SUDO")
    manifest=preflight()
    DROPIN_DIR.mkdir(parents=True,exist_ok=True)
    # Never overwrite a file created by another worker.
    fd=os.open(DROPIN,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
    installed=False
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(SRC.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        installed=True
        subprocess.run(["systemctl","daemon-reload"],check=True,timeout=25)
        hooked=output("systemctl","show",SERVICE,"--value","-p","ExecStartPost")
        if "review_daily_original_google_index_20261026.py" not in hooked:
            raise RuntimeError("SYSTEMD_POST_REVIEW_NOT_INSTALLED")
        if output("systemctl","is-active",TIMER)!="active":
            raise RuntimeError("ORIGINAL_TIMER_NO_LONGER_ACTIVE")
        result={**manifest,"status":"EXISTING_ORGANIC_DAILY_GOOGLE_INDEX_WATCH_INSTALLED",
                "systemd_dropin":str(DROPIN),"systemd_modified":True,
                "original_timer_restarted":False,
                "original_service_restarted":False,"new_services":0,
                "new_timers":0,"database_writes":False,
                "new_google_indexing_submissions":False,
                "next_review_on_original_timer":True}
        tmp=RECEIPT.with_name(RECEIPT.name+".tmp")
        tmp.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        os.chmod(tmp,0o600)
        os.replace(tmp,RECEIPT)
        print(json.dumps({"status":result["status"],
            "dropin":str(DROPIN),"next_review":result["next_elapse"],
            "same_existing_timer":True,"baseline":"2026-10-26",
            "new_service":False},sort_keys=True))
    except Exception:
        if installed and DROPIN.is_file():
            DROPIN.unlink()
            subprocess.run(["systemctl","daemon-reload"],check=False,timeout=25)
        raise

def main():
    p=argparse.ArgumentParser()
    choices=p.add_mutually_exclusive_group(required=True)
    choices.add_argument("--preflight",action="store_true")
    choices.add_argument("--activate",action="store_true")
    args=p.parse_args()
    if args.preflight:
        print(json.dumps(preflight(),sort_keys=True))
    else:
        activate()

if __name__=="__main__":
    main()
