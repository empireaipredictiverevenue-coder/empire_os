#!/usr/bin/env python3
"""One-page original Founder Console release, with exact preimages and rollback."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT=Path("/srv/empire_os")
ACTIVE=Path("/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3/web")
STAGE=Path("/home/ubuntu/empire_releases/seo_founder_revenue_focus_20261026_candidate")
CANDIDATE=STAGE/"web"
PAGE="src/app/founder/seo-operations/page.tsx"
HELPER="src/lib/seo-revenue-focus-review.ts"
UNIT="empire-founder-console.service"
RECEIPT=STAGE/"activation_result.json"
PREPARED=STAGE/"prepared_manifest.json"
BACKUP=STAGE/"activation_backups"
OLD=ACTIVE/".next_before_revenue_seo_focus_20261026"
INCOMING=ACTIVE/".next_incoming_revenue_seo_focus_20261026"
FAILED=ACTIVE/".next_failed_revenue_seo_focus_20261026"
ROUTES=(
 "/founder","/founder/agency","/founder/commercial-pipeline",
 "/founder/research","/department/evidence","/founder/seo-operations",
 "/founder/intent-review","/founder/youtube","/department","/technical",
)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prop(name):
    return subprocess.check_output(
        ["systemctl","show",UNIT,"--value","-p",name],text=True,timeout=12
    ).strip()
def inventory(base):
    files={}
    for p in (base/"src").rglob("*"):
        if not p.is_file() or p.is_symlink():continue
        rel=str(p.relative_to(base))
        if ".before_" in rel or ".new_" in rel:continue
        files[rel]=sha(p)
    for x in ("package.json","package-lock.json","next.config.ts",
              "tsconfig.json","postcss.config.mjs"):
        if (base/x).is_file(): files[x]=sha(base/x)
    return files
def check():
    if prop("WorkingDirectory")!=str(ACTIVE) or prop("ActiveState")!="active":
        raise RuntimeError("EXISTING_FOUNDER_SERVICE_CHANGED")
    if "node_modules/next/dist/bin/next" not in prop("ExecStart"):
        raise RuntimeError("EXISTING_NEXTJS_OWNER_CHANGED")
    if not ACTIVE.is_dir() or not CANDIDATE.is_dir():
        raise RuntimeError("EXISTING_PRIVATE_FOUNDER_SOURCE_MISSING")
    before=inventory(ACTIVE);after=inventory(CANDIDATE)
    removed=set(before)-set(after)
    added=set(after)-set(before)
    changed={p for p in before.keys()&after if before[p]!=after[p]}
    if removed or added!={HELPER} or changed!={PAGE}:
        raise RuntimeError("EXACT_TWO_REVIEWED_SEO_FILES_REQUIRED")
    for path in (PAGE,HELPER):
        if sha(CANDIDATE/path)!=sha(ROOT/"apps/search-command-centre"/path):
            raise RuntimeError("ORIGINAL_GIT_OWNER_CHANGED:"+path)
    if (ACTIVE/HELPER).exists() or (ACTIVE/HELPER).is_symlink():
        raise RuntimeError("ORIGINAL_FOUNDER_HELPER_COLLISION")
    if not (ACTIVE/".next/BUILD_ID").is_file() or not (CANDIDATE/".next/BUILD_ID").is_file():
        raise RuntimeError("COMPILED_ACTUAL_BUILD_ID_MISSING")
    old=(ACTIVE/".next/BUILD_ID").read_text().strip()
    new=(CANDIDATE/".next/BUILD_ID").read_text().strip()
    if old==new:raise RuntimeError("REBUILT_SEO_BUILD_NOT_NEW")
    for path in (RECEIPT,OLD,INCOMING,FAILED):
        if path.exists() or path.is_symlink():
            raise RuntimeError("ACTIVATION_OR_OTHER_OWNER_ALREADY_OWNS_PATH")
    return {
        "schema_version":"empire.seo.founder_revenue_focus_actual_release.v1",
        "status":"CURRENT_ORIGINAL_FOUNDER_SEO_REVENUE_FOCUS_READY",
        "working_directory":str(ACTIVE),
        "old_build_id":old,"candidate_build_id":new,
        "current_source_sha256":before,"candidate_source_sha256":after,
        "changed_files":[PAGE,HELPER],
        "other_source_files_identical":len(before)-1,
        "other_private_routes_to_preserve":list(ROUTES),
        "database_writes":False,"outbound_sent":False,
        "payments_activated":False,"new_services":0,
    }
def http(route):
    try:
        with urlopen("http://127.0.0.1:3001"+route,timeout=10) as r:
            return r.status,r.read(300000).decode("utf8","replace")
    except HTTPError as error:return error.code,""
    except OSError:return 0,""
def verify():
    result={}
    for route in ROUTES:
        for _ in range(12):
            code,body=http(route)
            if code==200:break
            time.sleep(0.75)
        result[route]=code
        if code!=200:raise RuntimeError("ORIGINAL_PRIVATE_ROUTE_REGRESSION:"+route)
        if route=="/founder/seo-operations":
            if not all(x in body for x in (
              "Revenue-first operating focus",
              "AEO → Commercial navigation health",
              "Original actions","Measured revenue"
            )):
                raise RuntimeError("NEW_SEO_EVIDENCE_PANEL_NOT_SERVED")
    return result
def restart():
    subprocess.run(["systemctl","restart",UNIT],check=True,
                   stdout=subprocess.DEVNULL,timeout=45)
def activation():
    if os.geteuid()!=0:
        raise RuntimeError("AUTHORISED_FOUNDER_SERVICE_SUDO_REQUIRED")
    lockfd=os.open("/run/lock/empire_founder_revenue_seo_focus_20261026.lock",
      os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lockfd,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not PREPARED.is_file() or PREPARED.is_symlink():
            raise RuntimeError("PRIVATE_REVIEWED_PREPARED_MANIFEST_MISSING")
        manifest=json.loads(PREPARED.read_text())
        if check()!=manifest:
            raise RuntimeError("FOUNDER_RUNTIME_CHANGED_SINCE_PREVIEW")
        if http("/founder/seo-operations")[0]!=200:
            raise RuntimeError("ORIGINAL_FOUNDER_SEO_NOT_HEALTHY")
        if BACKUP.exists():raise RuntimeError("BACKUP_ALREADY_PRESENT")
        BACKUP.mkdir(mode=0o700)
        original=BACKUP/"seo_operations_page.original.tsx"
        shutil.copy2(ACTIVE/PAGE,original)
        changed=[]
        swapped=False
        copied=False
        previous_mode=stat.S_IMODE((ACTIVE/PAGE).stat().st_mode)
        previous_uid=(ACTIVE/PAGE).stat().st_uid
        previous_gid=(ACTIVE/PAGE).stat().st_gid
        try:
            shutil.copytree(CANDIDATE/".next",INCOMING,symlinks=True)
            copied=True
            if (INCOMING/"BUILD_ID").read_text().strip()!=manifest["candidate_build_id"]:
                raise RuntimeError("CANDIDATE_BUILD_HASH_CHANGED")
            for rel in (PAGE,HELPER):
                dest=ACTIVE/rel
                if rel==PAGE and sha(dest)!=manifest["current_source_sha256"][PAGE]:
                    raise RuntimeError("ACTIVE_SEO_SOURCE_CHANGED")
                if rel==HELPER and (dest.exists() or dest.is_symlink()):
                    raise RuntimeError("HELPER_ADDED_BY_OTHER_OWNER")
                staged=dest.with_name(dest.name+".candidate_focus_20261026")
                if staged.exists():raise RuntimeError("STAGED_SOURCE_FILE_COLLISION")
                shutil.copy2(CANDIDATE/rel,staged)
                os.chown(staged,previous_uid,previous_gid)
                os.chmod(staged,previous_mode)
                os.replace(staged,dest)
                changed.append(rel)
                if sha(dest)!=sha(CANDIDATE/rel):
                    raise RuntimeError("COPIED_FOUNDER_FOCUS_SOURCE_CHANGED")
            os.replace(ACTIVE/".next",OLD)
            swapped=True
            os.replace(INCOMING,ACTIVE/".next")
            copied=False
            restart()
            healthy=verify()
            if prop("ActiveState")!="active":
                raise RuntimeError("FOUNDER_SERVICE_NOT_ACTIVE")
            result={
              "status":"ORIGINAL_FOUNDER_REVENUE_FOCUS_BOARD_LIVE_VERIFIED",
              "schema_version":manifest["schema_version"],
              "new_build_id":manifest["candidate_build_id"],
              "old_build_backup":str(OLD),
              "original_source_backup":str(original),
              "source_files_changed":list((PAGE,HELPER)),
              "existing_founder_routes_http":healthy,
              "other_founder_sources_unchanged":True,
              "original_daily_seo_receipts_unchanged":True,
              "new_services":0,"database_writes":False,
              "outbound_sent":False,"payments_activated":False,
            }
            fd=os.open(RECEIPT,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"w") as stream:
                json.dump(result,stream,indent=2,sort_keys=True);stream.write("\n")
            print(json.dumps({
             "status":result["status"],
             "route":"/founder/seo-operations",
             "private_routes_http_200":len(healthy),
             "rollback":str(OLD),
             "no_new_services":True},sort_keys=True))
        except BaseException:
            try:
                if swapped:
                    if (ACTIVE/".next").is_dir() and not FAILED.exists():
                        os.replace(ACTIVE/".next",FAILED)
                    if OLD.is_dir() and not (ACTIVE/".next").exists():
                        os.replace(OLD,ACTIVE/".next")
                if PAGE in changed:
                    restored=ACTIVE/PAGE
                    temporary=restored.with_name(restored.name+".restored_focus_20261026")
                    shutil.copy2(original,temporary)
                    os.chown(temporary,previous_uid,previous_gid)
                    os.chmod(temporary,previous_mode)
                    os.replace(temporary,restored)
                if HELPER in changed:(ACTIVE/HELPER).unlink(missing_ok=True)
                if copied and INCOMING.is_dir():shutil.rmtree(INCOMING)
                restart()
            except Exception as err:
                print("ROLLBACK_REVIEW_REQUIRED:"+type(err).__name__)
            raise

def main():
    p=argparse.ArgumentParser()
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight",action="store_true")
    group.add_argument("--activate",action="store_true")
    args=p.parse_args()
    if args.preflight:
        current=check()
        if PREPARED.exists():
            if json.loads(PREPARED.read_text())!=current:
                raise RuntimeError("EXISTING_REVIEWED_PREVIEW_CHANGED")
        else:
            fd=os.open(PREPARED,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"w") as out:
                json.dump(current,out,sort_keys=True,indent=2);out.write("\n")
        print(json.dumps({
         "status":current["status"],
         "original_build_id":current["old_build_id"],
         "candidate_build_id":current["candidate_build_id"],
         "source_files_changed":current["changed_files"],
         "unrelated_source_files_preserved":current["other_source_files_identical"],
         "service_not_restarted":True},sort_keys=True))
    else:activation()
if __name__=="__main__":main()
