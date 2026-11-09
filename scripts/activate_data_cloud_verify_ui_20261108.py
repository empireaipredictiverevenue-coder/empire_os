"""Founder-authorised additive one-button Data Cloud exchange check in existing CRM.

No base CRM changes. No new service. No database, key, provider, payment or
customer-operation change. Restarts only existing protected CRM issuer once
under the already approved founder-only guarded service-release scope.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import pwd
import re
import secrets
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path

from fastapi import FastAPI

ROOT=Path("/home/ubuntu/empire_worktrees/predictive_cloud_usage_review_20261107")
SRC=ROOT/"scripts"
RELEASE=Path("/opt/empire-ai/data-cloud-founder-verify-ui-20261108")
OVERLAY=Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/zzzzzzzzzzz-data-cloud-founder-verify-ui-20261108.conf")
RECEIPT=Path("/var/lib/empire-data-cloud-founder-pilot/VERIFY_UI_ACTIVATION_RECEIPT.json")
PATCH_BACKUP=Path("/etc/empire-data-cloud-founder-20261107/verify-ui-patch-before-lazy-router-fix.py")
OLD_PATCH_SHA="fdb6fb78b41079df8fa9e7eaee2fef03ba0c4ef6436575787f50e7eb8a5f1721"
ORIGINAL_ENTRYPOINT_SHA="52f0cee04a7236426053eb38273e920a398bd87257cb4f0bb0ac1b0156f19624"
SERVICE="empire-revenue-crm-pilot.service"
EXISTING_ENTRYPOINT="data_cloud_private_entrypoint_20261107:app"
NEW_ENTRYPOINT="data_cloud_verify_ui_entrypoint_20261108:app"
EXISTING_PRIVATE=Path("/opt/empire-ai/data-cloud-founder-pilot-20261107/data_cloud_private_entrypoint_20261107.py")
EXISTING_PRIVATE_SHA="853a54db3e3141ce735424cc89a4053c83d6aebd447c7527e33658807ae369d5"
EXCHANGE="/v1/data/auth/exchange"
LOGIN="/v1/revenue-crm/auth/login"
PAGE="/v1/revenue-crm/journeys/entry"
JS="/v1/revenue-crm/journeys/entry.js"
SOURCES=("data_cloud_verify_ui_entrypoint_20261108.py","data_cloud_verify_ui_patch_20261108.py")
UBUNTU=pwd.getpwnam("ubuntu")
LOCK=Path("/var/lock/empire-data-cloud-founder-verify-ui-20261108.lock")


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def run(cmd:list[str])->str:
    cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
    if cp.returncode:
        raise RuntimeError("owner_command_failure:"+cmd[0]+":"+str(cp.returncode))
    return cp.stdout.decode("utf8","strict").strip()


def fetch(path:str,*,method:str="GET") -> tuple[int,str]:
    import httpx
    try:
        with httpx.Client(trust_env=False,timeout=3,follow_redirects=False) as client:
            r=client.request(method,"http://127.0.0.1:8783"+path)
            return r.status_code,r.text
    except httpx.HTTPError:
        return 0,""


def systemd_preimage()->tuple[str,str]:
    if run(["systemctl","is-active",SERVICE])!="active":
        raise RuntimeError("protected_private_issuer_not_active")
    service=run(["systemctl","show",SERVICE,"-p","ExecStart","--value"])
    if EXISTING_ENTRYPOINT not in service or NEW_ENTRYPOINT in service:
        raise RuntimeError("original_owner_entrypoint_changed")
    environ=run(["systemctl","show",SERVICE,"-p","Environment","--value"])
    values=dict(part.split("=",1) for part in shlex.split(environ) if "=" in part)
    pythonpath=values.get("PYTHONPATH","")
    if ("/opt/empire-ai/data-cloud-founder-pilot-20261107" not in pythonpath
        or str(RELEASE) in pythonpath):
        raise RuntimeError("existing_private_crm_pythonpath_changed")
    return sha(run(["systemctl","cat",SERVICE]).encode()),pythonpath


def preflight(*, resuming:bool=False)->tuple[str,str]:
    if os.geteuid()!=0:
        raise RuntimeError("authorised_root_operator_required")
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("current_review_branch_missing")
    if run(["git","-C",str(ROOT),"branch","--show-current"])!="feature/predictive-cloud-usage-review-20261107":
        raise RuntimeError("review_branch_not_current")
    if run(["git","-C",str(ROOT),"status","--porcelain"]):
        raise RuntimeError("review_branch_dirty")
    if resuming:
        # Only the precise first failed founder UI attempt is eligible.
        if (RELEASE.is_symlink() or not RELEASE.is_dir()
                or RELEASE.stat().st_uid!=0
                or stat.S_IMODE(RELEASE.stat().st_mode)!=0o755
                or OVERLAY.exists() or OVERLAY.is_symlink()
                or RECEIPT.exists() or RECEIPT.is_symlink()):
            raise RuntimeError("exact_original_failed_ui_release_not_restored")
        if {x.name for x in RELEASE.iterdir()}!=set(SOURCES):
            raise RuntimeError("staged_release_file_inventory_changed")
        for name in SOURCES:
            frozen=RELEASE/name
            if (frozen.is_symlink() or not frozen.is_file()
                    or frozen.stat().st_uid!=0
                    or stat.S_IMODE(frozen.stat().st_mode)!=0o444):
                raise RuntimeError("staged_original_owner_file_permissions_changed")
        if sha((RELEASE/SOURCES[0]).read_bytes())!=ORIGINAL_ENTRYPOINT_SHA:
            raise RuntimeError("original_staged_ui_entrypoint_changed")
        frozen_sha=sha((RELEASE/SOURCES[1]).read_bytes())
        approved_sha=sha((SRC/SOURCES[1]).read_bytes())
        if frozen_sha not in (OLD_PATCH_SHA, approved_sha):
            raise RuntimeError("unrecognised_staged_ui_patch_preimage")
        if PATCH_BACKUP.is_symlink():
            raise RuntimeError("staged_ui_backup_symlink_not_permitted")
        if PATCH_BACKUP.exists():
            if (not PATCH_BACKUP.is_file() or PATCH_BACKUP.stat().st_uid!=0
                    or stat.S_IMODE(PATCH_BACKUP.stat().st_mode)!=0o400
                    or sha(PATCH_BACKUP.read_bytes())!=OLD_PATCH_SHA):
                raise RuntimeError("original_staged_ui_backup_changed")
        elif frozen_sha==approved_sha:
            raise RuntimeError("updated_ui_patch_without_protected_original_backup")
    elif (RELEASE.exists() or RELEASE.is_symlink() or OVERLAY.exists()
          or OVERLAY.is_symlink() or RECEIPT.exists() or RECEIPT.is_symlink()):
        raise RuntimeError("prior_or_partial_verify_ui_release_present")
    if (EXISTING_PRIVATE.is_symlink() or not EXISTING_PRIVATE.is_file()
        or sha(EXISTING_PRIVATE.read_bytes())!=EXISTING_PRIVATE_SHA):
        raise RuntimeError("previous_approved_private_issuer_changed")
    from importlib.util import spec_from_file_location,module_from_spec
    p=SRC/SOURCES[1]
    spec=spec_from_file_location("verify_ui_pure_release_check",p)
    mod=module_from_spec(spec);spec.loader.exec_module(mod)
    mod._pinned(mod.CRM_ASSETS/mod.HTML_NAME,mod.PINNED_HTML_SHA)
    mod._pinned(mod.CRM_ASSETS/mod.JS_NAME,mod.PINNED_JS_SHA)
    mod.patch_html((mod.CRM_ASSETS/mod.HTML_NAME).read_text())
    mod.patch_js((mod.CRM_ASSETS/mod.JS_NAME).read_text())
    for name in SOURCES:
        x=SRC/name
        if x.is_symlink() or not x.is_file() or x.stat().st_size>15000:
            raise RuntimeError("exact_verify_ui_source_missing_or_unreviewed")
    previous,pythonpath=systemd_preimage()
    if (fetch("/health")[0]!=200 or fetch(PAGE)[0]!=200
        or fetch(JS)[0]!=200 or fetch(EXCHANGE)[0]!=405
        or fetch(LOGIN)[0]!=405):
        raise RuntimeError("baseline_private_crm_login_or_issuer_unhealthy")
    if 'id="verify-data-cloud"' in fetch(PAGE)[1]:
        raise RuntimeError("verify_ui_already_active")
    return previous,pythonpath


def atomic_install(path:Path,data:bytes,mode:int):
    if path.is_symlink() or path.exists():
        raise RuntimeError("refusing_other_owner_release_path:"+path.name)
    temp=path.with_name("."+path.name+"."+secrets.token_hex(6))
    fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chown(temp,0,0)
        os.chmod(temp,mode)
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()


def repair_exact_original_staged_patch():
    """Replace only the frozen patch with the code verified on the REAL CRM app.

    Preserve the actual previously deployed bytes in the existing root-only
    credential directory, without touching the original CRM HTML/JS assets.
    """
    frozen=RELEASE/SOURCES[1]
    approved=(SRC/SOURCES[1]).read_bytes()
    current=frozen.read_bytes()
    if sha(current)==sha(approved):
        if (not PATCH_BACKUP.is_file() or PATCH_BACKUP.is_symlink()
                or sha(PATCH_BACKUP.read_bytes())!=OLD_PATCH_SHA):
            raise RuntimeError("patched_ui_image_has_no_verified_rollback_backup")
        return
    if sha(current)!=OLD_PATCH_SHA:
        raise RuntimeError("original_ui_patch_preimage_not_recognised")
    if not PATCH_BACKUP.exists():
        if (PATCH_BACKUP.parent.is_symlink() or
                PATCH_BACKUP.parent.stat().st_uid!=0 or
                stat.S_IMODE(PATCH_BACKUP.parent.stat().st_mode)!=0o700):
            raise RuntimeError("protected_root_only_backup_directory_invalid")
        atomic_install(PATCH_BACKUP,current,0o400)
    elif (PATCH_BACKUP.is_symlink() or sha(PATCH_BACKUP.read_bytes())!=OLD_PATCH_SHA):
        raise RuntimeError("frozen_original_ui_patch_backup_modified")
    tmp=frozen.with_name("."+frozen.name+"."+secrets.token_hex(6))
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(approved)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(tmp,0,0)
        os.chmod(tmp,0o444)
        os.replace(tmp,frozen)
    finally:
        if tmp.exists():tmp.unlink()
    if sha(frozen.read_bytes())!=sha(approved):
        raise RuntimeError("approved_ui_patch_frozen_readback_failed")


def rollback_only_additive_overlay(overlay_hash:str|None=None):
    removed=False
    if OVERLAY.is_symlink():
        raise RuntimeError("rollback_blocked_overlay_symlink")
    if OVERLAY.is_file():
        if overlay_hash is not None and sha(OVERLAY.read_bytes())!=overlay_hash:
            raise RuntimeError("rollback_blocked_other_owner_changed_overlay")
        OVERLAY.unlink()
        removed=True
    if not removed:
        if fetch("/health")[0]!=200:
            raise RuntimeError("original_crm_health_not_restored")
        return False
    run(["systemctl","daemon-reload"])
    run(["systemctl","restart",SERVICE])
    # systemd restart is asynchronous. A transient non-200 while Uvicorn
    # reloads must not be misreported as failed rollback.
    for _ in range(20):
        if (fetch("/health")[0]==200 and
                EXISTING_ENTRYPOINT in run([
                    "systemctl","show",SERVICE,"-p","ExecStart","--value"
                ])):
            return removed
        time.sleep(1)
    raise RuntimeError("original_crm_health_not_restored")


def verify_live(after_restart:bool)->None:
    for _ in range(12):
        if fetch("/health")[0]==200:break
        time.sleep(1)
    if fetch("/health")[0]!=200:
        raise RuntimeError("private_original_crm_health_regressed")
    code,page=fetch(PAGE)
    js_code,script=fetch(JS)
    if (code!=200 or js_code!=200
        or page.count('id="verify-data-cloud"')!=1
        or page.count('id="data-cloud-verify-status"')!=1
        or "verifyDataCloudExchange" not in script
        or '"/v1/data/auth/exchange"' not in script):
        raise RuntimeError("original_private_crm_verify_button_not_served")
    if fetch(EXCHANGE)[0]!=405 or fetch(EXCHANGE,method="POST")[0]!=401:
        raise RuntimeError("original_private_issuer_exchange_auth_regressed")
    if fetch(LOGIN)[0]!=405:
        raise RuntimeError("original_private_crm_login_route_regressed")
    if fetch("/v1/revenue-crm/journeys/blueprint")[0]!=401:
        raise RuntimeError("original_protected_crm_read_not_protected")
    import httpx
    with httpx.Client(trust_env=False,timeout=3) as client:
        data=client.get("http://127.0.0.1:80/v1/data/usage")
        if data.status_code!=401:
            raise RuntimeError("existing_public_data_cloud_usage_gateway_regressed")


def apply(*,resuming:bool=False):
    before,pythonpath=preflight(resuming=resuming)
    print("EXISTING_PRIVATE_CRM_AND_DATA_CLOUD_BASELINE=PASS")
    created=False
    overlay_data=b""
    try:
        if RELEASE.parent.is_symlink() or not RELEASE.parent.is_dir():
            raise RuntimeError("protected_release_parent_invalid")
        if resuming:
            repair_exact_original_staged_patch()
        else:
            RELEASE.mkdir(mode=0o755)
            os.chown(RELEASE,0,0)
            for name in SOURCES:
                atomic_install(RELEASE/name,(SRC/name).read_bytes(),0o444)
        # No modifications to original frozen CRM or Data Cloud release.
        if sha(run(["systemctl","cat",SERVICE]).encode())!=before:
            raise RuntimeError("other_owner_service_changed_during_preflight")
        overlay_data=(
            "[Service]\n"
            "# Founder-only read-only browser exchange button; previous layers preserved.\n"
            "Environment=PYTHONPATH="+pythonpath+":"+str(RELEASE)+"\n"
            "ExecStart=\n"
            "ExecStart=/srv/empire_os/.venv/bin/uvicorn "
            "data_cloud_verify_ui_entrypoint_20261108:app "
            "--host 127.0.0.1 --port 8783 --no-proxy-headers\n"
        ).encode()
        atomic_install(OVERLAY,overlay_data,0o644)
        created=True
        run(["systemctl","daemon-reload"])
        run(["systemctl","restart",SERVICE])
        verify_live(after_restart=True)
        receipt={
            "result":"FOUNDER_CRM_VERIFY_DATA_CLOUD_BUTTON_LIVE",
            "founder_real_login_already_observed":True,
            "founder_real_login_to_data_exchange_verified":False,
            "button_available_for_real_founder_click":True,
            "existing_private_crm_health":True,
            "existing_data_cloud_gateway_unauthenticated_401":True,
            "no_base_crm_asset_mutation":True,
            "no_database_changes":True,
            "no_provider_calls_or_billing":True,
            "overlaid_only_service":SERVICE,
            "frozen_original_private_entrypoint_sha256":EXISTING_PRIVATE_SHA,
            "original_unit_preimage_sha256":before,
            "overlay_sha256":sha(overlay_data),
            "source_sha256":{n:sha((SRC/n).read_bytes()) for n in SOURCES},
        }
        atomic_install(RECEIPT,(json.dumps(receipt,indent=2,sort_keys=True)+"\n").encode(),0o600)
        os.chown(RECEIPT,UBUNTU.pw_uid,UBUNTU.pw_gid)
        print("VERIFY_DATA_CLOUD_BUTTON_LIVE=true")
        print("REAL_CRM_TO_DATA_CLOUD_EXCHANGE=WAIT_FOR_FOUNDER_CLICK")
        print("ORIGINAL_CRM_HEALTH=true; DB_WRITES=0; BILLING=false")
    except Exception as exc:
        print("VERIFY_UI_ACTIVATION_FAILED="+str(exc),file=sys.stderr)
        try:
            rollback_only_additive_overlay(sha(overlay_data) if created else None)
            print("ORIGINAL_CRM_SERVICE_ROLLBACK=VERIFIED",file=sys.stderr)
        except Exception:
            print("ORIGINAL_CRM_SERVICE_ROLLBACK=REQUIRES_OPERATOR_REVIEW",file=sys.stderr)
        raise


def inspect():
    print("PRIVATE_CRM_HEALTH_HTTP="+str(fetch("/health")[0]))
    print("CRM_LOGIN_PAGE_HTTP="+str(fetch(PAGE)[0]))
    print("DATA_EXCHANGE_METHOD_HTTP="+str(fetch(EXCHANGE)[0]))
    print("VERIFY_UI_BUTTON_PRESENT="+str('id="verify-data-cloud"' in fetch(PAGE)[1]).lower())
    print("VERIFY_UI_RECEIPT_PRESENT="+str(RECEIPT.is_file()).lower())
    print("VERIFY_UI_OVERLAY_PRESENT="+str(OVERLAY.is_file()).lower())
    if RECEIPT.is_file() and not RECEIPT.is_symlink():
        print("VERIFY_UI_REDACTED_RECEIPT="+RECEIPT.read_text())


def main():
    parser=argparse.ArgumentParser()
    flags=parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--preflight-read-only",action="store_true")
    flags.add_argument("--resume-preflight-read-only",action="store_true")
    flags.add_argument("--resume-founder-approved",action="store_true")
    flags.add_argument("--apply-founder-approved",action="store_true")
    flags.add_argument("--inspect-read-only",action="store_true")
    flags.add_argument("--rollback-founder-approved",action="store_true")
    args=parser.parse_args()
    if args.inspect_read_only:
        inspect()
        return
    if args.preflight_read_only or args.resume_preflight_read_only:
        before,path=preflight(resuming=args.resume_preflight_read_only)
        print("VERIFY_UI_PREFLIGHT=PASS; CHANGES=0; ROOT_CRMS=UNTOUCHED")
        if args.resume_preflight_read_only:
            print("EXACT_PREVIOUS_FAILED_UI_RELEASE_VERIFIED=true")
        return
    if os.geteuid()!=0:
        raise RuntimeError("founder_authorised_root_required")
    fd=os.open(LOCK,os.O_RDWR|os.O_CREAT,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.apply_founder_approved or args.resume_founder_approved:
            apply(resuming=args.resume_founder_approved)
        else:
            if RECEIPT.is_file():
                receipt=json.loads(RECEIPT.read_text())
                rollback_only_additive_overlay(receipt["overlay_sha256"])
            else:
                rollback_only_additive_overlay()
            print("VERIFY_UI_SCOPED_ROLLBACK=PASS")
    finally:
        os.close(fd)


if __name__=="__main__":
    main()
