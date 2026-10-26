#!/usr/bin/env python3
"""Guarded original Founder Console SEO tool-suite V2 release (with rollback).

Build is composed from exactly the running Next.js release plus:
  src/app/founder/seo-operations/page.tsx
  src/app/founder/seo-operations/seo-workbench.tsx
No other source owner or public website files may change.
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
from urllib.error import HTTPError, URLError

LIVE=Path("/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3/web")
PROPOSAL=Path("/home/ubuntu/empire_releases/seo_unified_tool_suite_candidate_20261026/web")
OWNER=PROPOSAL.parent
BACKUP=OWNER/"activation_backups"
OLD_BUILD="S1a8PikANQu_TGMcw75JP"
NEW_BUILD="y_0Wp6TsIUjnSaJ_2thQ4"
OLD_SEO_SHA="56059ee003bb21843a60de4adf59b647b94b3ea32887b747ab6b26c1a53567e4"
NEW_SEO_SHA="428166ec4cdc47afa5e624b8f068bcd6fc2fd23d81a8ae40dc8e77ea956d3d43"
NEW_WORKBENCH_SHA="0fc221d3945a370e160eb921680dc7c32573ec7d063fd888db2daa5260ce0063"
OWNER_HASHES={
    "src/app/founder/page.tsx":"81ef9399ea3d16d66b8f3033464fb1d76c90a88d1532034f416c950eff550bed",
    "src/app/founder/results/page.tsx":"0e8d344014932715dc6acd9a602c5c50958949e56a1091651bdb929bacaa3e2d",
    "src/lib/founder-api.ts":"716ef70c7c5e05b8add49455f6b1c0e557d24a1cc565173c3fe36c4f5f8b32c6",
}
SEO=Path("src/app/founder/seo-operations/page.tsx")
WORKBENCH=Path("src/app/founder/seo-operations/seo-workbench.tsx")
ROUTES=("/founder","/founder/results","/founder/seo-operations",
        "/founder/agency","/founder/commercial-pipeline",
        "/founder/intent-review","/founder/research","/founder/youtube",
        "/department","/technical")


class SEOReleaseHeld(RuntimeError):
    pass


def ensure(ok:bool, reason:str)->None:
    if not ok:
        raise SEOReleaseHeld(reason)


def digest(path:Path)->str:
    return sha256(path.read_bytes()).hexdigest()


def cmd(*parts:str)->str:
    return subprocess.check_output(parts,text=True,timeout=25).strip()


def http(url:str)->tuple[int,bytes]:
    try:
        with urlopen(url,timeout=5) as response:
            return response.status,response.read(400000)
    except HTTPError as error:
        return error.code,b""
    except (URLError,TimeoutError,OSError):
        return 0,b""


def check()->dict:
    ensure(LIVE.is_dir() and PROPOSAL.is_dir()
           and not LIVE.is_symlink() and not PROPOSAL.is_symlink(),
           "EXACT_ORIGINAL_FOUNDER_RELEASE_REQUIRED")
    ensure(LIVE.stat().st_mode & 0o077==0,"ORIGINAL_FOUNDER_RELEASE_NOT_PRIVATE")
    ensure((LIVE/".next/BUILD_ID").read_text().strip()==OLD_BUILD,
           "ORIGINAL_FOUNDER_BUILD_CHANGED")
    ensure((PROPOSAL/".next/BUILD_ID").read_text().strip()==NEW_BUILD,
           "EXACT_TESTED_TOOL_SUITE_BUILD_REQUIRED")
    ensure(digest(LIVE/SEO)==OLD_SEO_SHA,"ORIGINAL_SEO_OWNER_PAGE_CHANGED")
    ensure(digest(PROPOSAL/SEO)==NEW_SEO_SHA,"SEO_SUITE_PAGE_CHANGED")
    ensure(digest(PROPOSAL/WORKBENCH)==NEW_WORKBENCH_SHA,
           "SEO_TOOL_SUITE_SOURCE_CHANGED")
    ensure(not (LIVE/WORKBENCH).exists() and not (LIVE/WORKBENCH).is_symlink(),
           "SEO_WORKBENCH_ALREADY_EXISTS")
    for rel,expected in OWNER_HASHES.items():
        ensure(digest(LIVE/rel)==expected and digest(PROPOSAL/rel)==expected,
               "UNRELATED_FOUNDER_OWNER_SOURCE_MISMATCH")
    ensure(cmd("systemctl","show","empire-founder-console.service",
               "-p","WorkingDirectory","--value")==str(LIVE),
           "NOT_EXISTING_FOUNDER_OWNER_SERVICE")
    ensure(cmd("systemctl","is-active","empire-founder-console.service")=="active",
           "ORIGINAL_FOUNDER_SERVICE_NOT_ACTIVE")
    for route in ("/founder","/founder/agency","/founder/seo-operations"):
        ensure(http("http://127.0.0.1:3001"+route)[0]==200,
               "EXISTING_FOUNDER_ROUTE_NOT_READY:"+route)
    return {
        "status":"SEO_UNIFIED_TOOL_SUITE_V2_PREFLIGHT_PASSED",
        "previous_build":OLD_BUILD,"new_build":NEW_BUILD,
        "exact_source_changes":[str(SEO),str(WORKBENCH)],
        "unchanged_original_owner_sources":list(OWNER_HASHES),
        "live_modified":False,"database_writes":False,"new_timer":False,
        "outbound":False,"payments":False,
    }


def atomic_copy(src:Path,dest:Path)->None:
    temp=dest.with_name(dest.name+".seo-suite-v2-tmp")
    ensure(not temp.exists() and not temp.is_symlink(),"STALE_SEO_TEMP")
    shutil.copy2(src,temp)
    os.replace(temp,dest)


def verify()->dict:
    results={}
    for route in ROUTES:
        state,body=0,b""
        for _ in range(16):
            state,body=http("http://127.0.0.1:3001"+route)
            if state==200:
                break
            time.sleep(0.75)
        results[route]=state
        ensure(state==200,"FOUNDER_SUITE_ROUTE_FAILURE:"+route)
        if route=="/founder/seo-operations":
            for marker in (b"Organic Growth Command Centre",b"Keyword intelligence",
                           b"Execution queue",b"All SEO tools",b"Observed keywords",
                           b"Commercial queries",b"Not verified"):
                ensure(marker in body,"SEO_TOOL_SUITE_MISSING_EVIDENCE")
    ensure(cmd("systemctl","is-active","empire-founder-console.service")=="active",
           "FOUNDER_OWNER_NOT_RUNNING_AFTER_RELEASE")
    return results


def activate()->dict:
    ensure(os.geteuid()==0,"ACTIVATION_REQUIRES_AUTHORIZED_SUDO")
    lockfd=os.open(OWNER/".seo-suite-v2-activation.lock",
                   os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lockfd,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        check()
        ensure(not BACKUP.exists() and not BACKUP.is_symlink(),
               "SEPARATE_RELEASE_ALREADY_ATTEMPTED")
        BACKUP.mkdir(mode=0o700)
        oldnext=BACKUP/".next.original"
        oldpage=BACKUP/"seo.page.original.tsx"
        failednext=BACKUP/".next.failed"
        incoming=LIVE/".next.seo-suite-v2-incoming"
        ensure(not incoming.exists() and not incoming.is_symlink(),
               "UNRELATED_INCOMING_BUILD_PRESENT")
        shutil.copy2(LIVE/SEO,oldpage)
        try:
            shutil.copytree(PROPOSAL/".next",incoming,symlinks=True)
            ensure((incoming/"BUILD_ID").read_text().strip()==NEW_BUILD,
                   "COPIED_NEW_BUILD_ID_MISMATCH")
            atomic_copy(PROPOSAL/SEO,LIVE/SEO)
            atomic_copy(PROPOSAL/WORKBENCH,LIVE/WORKBENCH)
            os.replace(LIVE/".next",oldnext)
            os.replace(incoming,LIVE/".next")
            cmd("systemctl","restart","empire-founder-console.service")
            routes=verify()
        except BaseException:
            # Restore the exact original runtime, preserving the failed build.
            if oldnext.exists():
                if (LIVE/".next").exists():
                    os.replace(LIVE/".next",failednext)
                os.replace(oldnext,LIVE/".next")
            if oldpage.is_file():
                atomic_copy(oldpage,LIVE/SEO)
            (LIVE/WORKBENCH).unlink(missing_ok=True)
            if incoming.is_dir():
                shutil.rmtree(incoming)
            try:
                cmd("systemctl","restart","empire-founder-console.service")
            except Exception:
                pass
            raise
        report={
            "status":"ORIGINAL_FOUNDER_SEO_TOOL_SUITE_V2_LIVE_VERIFIED",
            "new_build":NEW_BUILD,
            "old_build_backup":str(oldnext),
            "old_page_backup":str(oldpage),
            "route_http_statuses":routes,
            "source_files_changed":2,
            "original_founder_owner_files_changed":False,
            "no_new_database":True,"no_new_scheduler":True,
            "outbound_sent":False,"payment_activated":False,
            "public_website_modified":False,
        }
        receipt=OWNER/"activation_result.json"
        fd=os.open(receipt,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w") as out:
            json.dump(report,out,indent=2,sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        return report


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--activate",action="store_true")
    args=parser.parse_args()
    try:
        print(json.dumps(activate() if args.activate else check(),sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({
            "status":"SEO_UNIFIED_TOOL_SUITE_V2_RELEASE_HELD_OR_ROLLED_BACK",
            "reason_code":type(error).__name__,"reason":str(error)[:160],
            "live_verified":False,"database_writes":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
