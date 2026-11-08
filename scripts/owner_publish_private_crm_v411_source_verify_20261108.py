"""One founder-approved guarded CRM restart to expose original V4.11 HELD verify.

Owner-only release; preserving original private CRM issuer, original 066
read-only source rights, original Data Cloud exchange, all previous systemd
drop-ins, permissions, production rollback and credential custody.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path("/home/ubuntu/empire_worktrees/predictive_cloud_usage_review_20261107")
COMMIT="b9570b2f0c0a2e1776ccbc3824bc8cbb74b60a33"
UNIT="empire-revenue-crm-pilot.service"
DROPIN=Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/"
            "zzzzzzzzzzzz-predictive-source-review-20261108.conf")
RELEASE=Path("/opt/empire-ai/data-cloud-predictive-source-review-20261108")
BACKUP=Path("/var/backups/empire-founder/predictive-source-crm-review-20261108")
CREDS=Path("/var/backups/empiredb/predictive-source-tenant-held-20261108/rights_reader_dsn")
CRED_NAME="empire-predictive-source-rights-dsn"
FILES={
 "private_crm_original_v411_source_review_candidate_20261108.py":
 "7961715002fa2513362b173c0890e393118e0e9649611ecbb50135dce84d780a",
 "private_crm_original_v411_source_entrypoint_20261108.py":
 "c42c40dbc0a735f6e9c7bddc8a32326a47134413f87750febf67a6a2a87e3740",
}
OLD_MAIN="data_cloud_verify_ui_entrypoint_20261108:app"
NEW_MAIN="private_crm_original_v411_source_entrypoint_20261108:app"
ORIGINAL_PATHS=(
 "/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1",
 "/opt/empire-ai/data-cloud-founder-pilot-20261107",
 "/opt/empire-ai/data-cloud-founder-verify-ui-20261108",
)
HTML="/v1/revenue-crm/journeys/entry"
JS=HTML+".js"
REV="/v1/predictive-cloud/source-rights/verify"
HTML_SHA="1d86ce33e8f7b4edb63a52a14ccf76f0f7dfc617a2763173eceaa845ab849282"
JS_SHA="7f50fa36289a7539a33e7b058038c4373b9d64e556f2f5c751fb3932c707be6f"


def cmd(args,*,timeout=15,input=None):
    proc=subprocess.run(args,input=input,text=True,capture_output=True,timeout=timeout)
    if proc.returncode!=0:
        raise RuntimeError("owner_operator_failed:"+args[0])
    return proc.stdout.strip()

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def http(path,*,method="GET",expected=None):
    req=Request("http://127.0.0.1:8783"+path,method=method)
    try:
        with urlopen(req,timeout=4) as r:
            status=r.status
            body=r.read(180000)
            headers=dict(r.headers.items())
    except HTTPError as e:
        status=e.code
        body=e.read(2048)
        headers=dict(e.headers.items())
    if expected is not None and status!=expected:
        raise RuntimeError("CRM_"+path.replace("/","_")+"_unexpected_http_status")
    return status,body,headers

def preflight():
    if os.geteuid()!=0:
        raise RuntimeError("root_guard_required")
    head=cmd(["git","-C",str(ROOT),"rev-parse","HEAD"])
    cmd(["git","-C",str(ROOT),"merge-base","--is-ancestor",COMMIT,head])
    allowed={"scripts/owner_publish_private_crm_v411_source_verify_20261108.py",
             "tests/test_owner_publish_private_crm_v411_source_verify_20261108.py"}
    additions=set(cmd(["git","-C",str(ROOT),"diff","--name-only",COMMIT,head]).splitlines())
    if not additions.issubset(allowed):
        raise RuntimeError("release_branch_changed_outside_scoped_operator")
    if cmd(["git","-C",str(ROOT),"status","--porcelain"]):
        raise RuntimeError("release_worktree_dirty")
    if DROPIN.exists() or DROPIN.is_symlink() or RELEASE.exists() or BACKUP.exists():
        raise RuntimeError("release_or_backup_already_exists_fail_closed")
    for name,expected in FILES.items():
        p=ROOT/"scripts"/name
        if p.is_symlink() or not p.is_file() or digest(p)!=expected:
            raise RuntimeError("source_module_sha_mismatch")
    if CREDS.is_symlink() or not CREDS.is_file() or CREDS.stat().st_uid!=0 or stat.S_IMODE(CREDS.stat().st_mode)!=0o600:
        raise RuntimeError("original_root_only_restricted_credential_missing")
    if not 70 < CREDS.stat().st_size < 1024:
        raise RuntimeError("original_source_reader_credential_size_invalid")
    for parent in (DROPIN.parent, RELEASE.parent,BACKUP.parent):
        if parent.is_symlink() or not parent.is_dir() or parent.stat().st_uid!=0:
            raise RuntimeError("original_root_release_parent_untrusted")
    if cmd(["systemctl","is-active",UNIT])!="active":
        raise RuntimeError("original_private_crm_not_active")
    old_exec=cmd(["systemctl","show",UNIT,"--value","-p","ExecStart"])
    if OLD_MAIN not in old_exec or NEW_MAIN in old_exec:
        raise RuntimeError("other_owner_changed_private_crm_execstart")
    raw_env=cmd(["systemctl","show",UNIT,"--value","-p","Environment"])
    python=[x.split("=",1)[1] for x in shlex.split(raw_env) if x.startswith("PYTHONPATH=")]
    if len(python)!=1 or any(v not in python[0].split(":") for v in ORIGINAL_PATHS):
        raise RuntimeError("original_crm_pythonpath_owner_drift")
    if str(RELEASE) in python[0].split(":") or any(c in python[0] for c in ('"',"\n","\r","%")):
        raise RuntimeError("untrusted_pythonpath_for_systemd")
    status,h,_=http("/health",expected=200)
    for path,sha in ((HTML,HTML_SHA),(JS,JS_SHA)):
        status,data,headers=http(path,expected=200)
        if (hashlib.sha256(data).hexdigest()!=sha
            or headers.get("Cache-Control")!="no-store"):
            raise RuntimeError("original_protected_crm_ui_changed")
    if http(REV,method="POST")[0]!=404:
        raise RuntimeError("original_new_route_collision")
    if http("/v1/data/auth/exchange",method="POST")[0]!=401:
        raise RuntimeError("original_data_cloud_exchange_modified")
    return {"ready":True,"release_operator_commit":head,"original_pythonpath":python[0],
            "original_execstart":old_exec,
            "source_files":FILES,
            "old_service_pid":cmd(["systemctl","show",UNIT,"--value","-p","MainPID"]),
            "production_changes":False}

def private_file(path,data,mode):
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,mode)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(path,mode)
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise

def add_release(pre):
    BACKUP.mkdir(mode=0o700)
    os.chmod(BACKUP,0o700)
    unit=cmd(["systemctl","cat",UNIT])
    private_file(BACKUP/"original_effective_systemd_unit.txt",
                 (unit+"\n").encode(),0o600)
    before={
        "previous_execstart_contains_original":OLD_MAIN in pre["original_execstart"],
        "previous_service_pid":pre["old_service_pid"],
        "previous_pythonpath_sha256":hashlib.sha256(pre["original_pythonpath"].encode()).hexdigest(),
        "original_live_html_sha256":HTML_SHA,"original_live_js_sha256":JS_SHA,
        "release_candidate_commit":COMMIT,
        "release_operator_commit":pre["release_operator_commit"],
        "source_files":FILES,
        "original_dropin_did_not_exist":True,
    }
    private_file(BACKUP/"preflight.json",json.dumps(before,sort_keys=True,indent=2).encode()+b"\n",0o600)
    RELEASE.mkdir(mode=0o755)
    os.chmod(RELEASE,0o755)
    for filename,sha in FILES.items():
        original=ROOT/"scripts"/filename
        data=original.read_bytes()
        if hashlib.sha256(data).hexdigest()!=sha:
            raise RuntimeError("source_sha_changed_during_install")
        private_file(RELEASE/filename,data,0o444)
    newpath=str(RELEASE)+":"+pre["original_pythonpath"]
    text=(
        "[Service]\n"
        "# Founder approved one protected source-rights READ-only CRM overlay.\n"
        '# Original CRM login, Data Cloud issuer and membership stay authoritative.\n'
        'Environment="PYTHONPATH='+newpath+'"\n'
        'LoadCredential='+CRED_NAME+':'+str(CREDS)+'\n'
        'ExecStart=\n'
        'ExecStart=/srv/empire_os/.venv/bin/uvicorn '+NEW_MAIN+
        ' --host 127.0.0.1 --port 8783 --no-proxy-headers\n'
    )
    private_file(DROPIN,text.encode(),0o644)
    return hashlib.sha256(text.encode()).hexdigest()

def rollback(*,restart_needed:bool):
    # Removing ONLY this new drop-in preserves all other owner releases.
    DROPIN.unlink(missing_ok=True)
    cmd(["systemctl","daemon-reload"],timeout=12)
    if restart_needed:
        cmd(["systemctl","restart",UNIT],timeout=25)
    for _ in range(20):
        try:
            status,_,_=http("/health")
            if status==200 and http(REV,method="POST")[0]==404:
                return "ORIGINAL_CRM_EXECSTART_RESTORED_AND_HEALTHY"
        except (URLError,TimeoutError,RuntimeError):
            pass
        time.sleep(.5)
    return "ORIGINAL_UNIT_RESTORED_BUT_HEALTH_NOT_PROVED"

def apply():
    pre=preflight()
    new_sha=add_release(pre)
    started=False
    try:
        cmd(["systemctl","daemon-reload"],timeout=12)
        cmd(["systemd-analyze","verify",UNIT],timeout=20)
        current=cmd(["systemctl","show",UNIT,"--value","-p","ExecStart"])
        if NEW_MAIN not in current:
            raise RuntimeError("new_private_crm_entrypoint_not_effective")
        py_env=cmd(["systemctl","show",UNIT,"--value","-p","Environment"])
        paths=[e.split("=",1)[1] for e in shlex.split(py_env) if e.startswith("PYTHONPATH=")]
        if len(paths)!=1 or paths[0] != str(RELEASE)+":"+pre["original_pythonpath"]:
            raise RuntimeError("original_python_import_paths_not_preserved")
        started=True
        cmd(["systemctl","restart",UNIT],timeout=25)
        checks={}
        for _ in range(20):
            try:
                checks["crm_health"]=http("/health")[0]
                if checks["crm_health"]==200:
                    break
            except (URLError,TimeoutError):
                pass
            time.sleep(.5)
        if checks.get("crm_health")!=200:
            raise RuntimeError("CRM_health_failed_after_restart")
        checks["anonymous_new_source_route"]=http(REV,method="POST")[0]
        checks["read_only_source_get"]=http(REV,method="GET")[0]
        checks["anonymous_data_exchange"]=http("/v1/data/auth/exchange",method="POST")[0]
        checks["crm_html"],html,headers=http(HTML)
        checks["crm_js"],js,jsheaders=http(JS)
        if (checks["anonymous_new_source_route"]!=401
            or checks["read_only_source_get"]!=405
            or checks["anonymous_data_exchange"]!=401
            or checks["crm_html"]!=200 or checks["crm_js"]!=200
            or b'id="verify-predictive-source"' not in html
            or b'id="verify-data-cloud"' not in html
            or b'verifyPredictiveSource' not in js
            or b'verifyDataCloudExchange' not in js
            or headers.get("Cache-Control")!="no-store"
            or jsheaders.get("Cache-Control")!="no-store"
            or cmd(["systemctl","is-active",UNIT])!="active"):
            raise RuntimeError("original_crm_or_source_route_postrelease_failed")
        if cmd(["systemctl","show",UNIT,"--value","-p","MainPID"])==pre["old_service_pid"]:
            raise RuntimeError("private_CRM_new_entrypoint_not_started")
        receipt={
            "result":"FOUNDER_PRIVATE_CRM_V411_HELD_SOURCE_VERIFY_ROUTE_LIVE",
            "installed_at":datetime.now(timezone.utc).isoformat(),
            "founder_restart_authorized":True,
            "release_candidate_commit":COMMIT,
            "release_operator_commit":pre["release_operator_commit"],
            "release_dropin_sha256":new_sha,
            "original_service_pid_changed":True,
            "checks":checks,
            "source_rights_state":"PENDING_HELD",
            "signed_browser_http200_verified":False,
            "source_rights_independently_approved":False,
            "customer_predictions_enabled":False,
            "public_search_enabled":False,
            "public_data_delivery_enabled":False,
            "paid_providers_enabled":False,
            "rollback_remove_only":str(DROPIN),
            "preflight_backup":str(BACKUP/"preflight.json"),
        }
        private_file(BACKUP/"activation_receipt.json",
                     json.dumps(receipt,sort_keys=True,indent=2).encode()+b"\n",0o600)
        return receipt
    except BaseException:
        try:
            outcome=rollback(restart_needed=started)
            private_file(BACKUP/"rollback_receipt.json",
              json.dumps({"result":"CRM_SOURCE_RELEASE_NOT_VERIFIED",
                          "rollback":outcome,
                          "original_restart_required":started,
                          "original_data_source_held":True},sort_keys=True).encode()+b"\n",0o600)
        except BaseException:
            raise RuntimeError("CRM_SOURCE_RELEASE_FAILED_AND_ROLLBACK_UNVERIFIED") from None
        raise RuntimeError("CRM_SOURCE_RELEASE_FAILED_ROLLED_BACK_ORIGINAL") from None


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight",action="store_true")
    mode.add_argument("--apply-founder-approved",action="store_true")
    args=parser.parse_args()
    result=preflight() if args.preflight else apply()
    # Never echo original PYTHONPATH, credentials, bearer or private unit data.
    if args.preflight:
        result={"ready":result["ready"],"release_commit":COMMIT,
                "source_file_hashes_verified":True,
                "original_issuer_healthy":True,"changes":False}
    print(json.dumps(result,sort_keys=True))
