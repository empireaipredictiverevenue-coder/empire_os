#!/usr/bin/env python3
"""Scoped rollback-ready deployment of SEO Operations into EXISTING Founder Console.

Prebuilt candidate was compiled from the ACTUAL running Founder release source,
plus exactly two route files. --preflight makes no modifications. --activate
requires the authorized server operator/root because the EXISTING service
must restart. The service unit, other routes, PostgreSQL, outbound, payments
and unrelated owner files are never modified by this script.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import fcntl

STAGE=Path("/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3/web")
CANDIDATE=Path("/home/ubuntu/empire_releases/seo_founder_operations_candidate_20261026/web")
RELEASE=CANDIDATE.parent
BACKUP=RELEASE/"activation_backups"
ORIGINAL_BUILD="wdN7DxxQUqWJQKtpIH4nN"
NEW_BUILD="S1a8PikANQu_TGMcw75JP"
ORIGINAL_RESULTS_SHA="6217fddf95403387066216f37eb5e836167277f6dfafb53466144886d334a14b"
CANDIDATE_RESULTS_SHA="0e8d344014932715dc6acd9a602c5c50958949e56a1091651bdb929bacaa3e2d"
ORIGINAL_FOUNDER_SHA="81ef9399ea3d16d66b8f3033464fb1d76c90a88d1532034f416c950eff550bed"
ORIGINAL_FOUNDER_API_SHA="716ef70c7c5e05b8add49455f6b1c0e557d24a1cc565173c3fe36c4f5f8b32c6"
CANDIDATE_SEO_SHA="56059ee003bb21843a60de4adf59b647b94b3ea32887b747ab6b26c1a53567e4"
SEO_PAGE=Path("src/app/founder/seo-operations/page.tsx")
RESULTS_PAGE=Path("src/app/founder/results/page.tsx")
OWNER_PAGES=(Path("src/app/founder/page.tsx"),Path("src/lib/founder-api.ts"))
HEALTH_ROUTES=(
    "/founder", "/founder/results", "/founder/seo-operations",
    "/founder/agency", "/founder/commercial-pipeline",
    "/founder/research", "/founder/intent-review",
    "/founder/youtube", "/department", "/technical",
)


class ReleaseHeld(RuntimeError):
    pass


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReleaseHeld(code)


def call(*cmd: str) -> str:
    return subprocess.check_output(cmd, text=True, timeout=24).strip()


def status(url: str, seconds: float=7.0) -> tuple[int, bytes]:
    try:
        with urlopen(url,timeout=seconds) as response:
            return response.status,response.read(250000)
    except HTTPError as err:
        return err.code,b""
    except (OSError,TimeoutError,URLError):
        return 0,b""


def preflight() -> dict:
    require(STAGE.is_dir() and CANDIDATE.is_dir(), "EXISTING_FOUNDER_STAGE_REQUIRED")
    require(not STAGE.is_symlink() and not CANDIDATE.is_symlink(), "STAGE_SYMLINK_REJECTED")
    require(STAGE.stat().st_mode & 0o077 == 0, "ORIGINAL_FOUNDER_STAGE_NOT_PRIVATE")
    require((STAGE/".next/BUILD_ID").read_text().strip()==ORIGINAL_BUILD,
            "ORIGINAL_BUILD_CHANGED_ABORT_WITHOUT_WRITES")
    require((CANDIDATE/".next/BUILD_ID").read_text().strip()==NEW_BUILD,
            "REVIEWED_CANDIDATE_BUILD_CHANGED")
    require(digest(STAGE/RESULTS_PAGE)==ORIGINAL_RESULTS_SHA,
            "EXISTING_RESULTS_OWNER_SOURCE_CHANGED")
    require(digest(CANDIDATE/RESULTS_PAGE)==CANDIDATE_RESULTS_SHA,
            "CANDIDATE_NAVIGATION_CHANGED")
    require(digest(CANDIDATE/SEO_PAGE)==CANDIDATE_SEO_SHA,
            "CANDIDATE_SEO_SOURCE_CHANGED")
    require(not (STAGE/SEO_PAGE).exists() and not (STAGE/SEO_PAGE).is_symlink(),
            "NEW_ROUTE_ALREADY_PRESENT")
    for original,expect in zip(OWNER_PAGES,(ORIGINAL_FOUNDER_SHA,ORIGINAL_FOUNDER_API_SHA)):
        require(digest(STAGE/original)==expect
                and digest(CANDIDATE/original)==expect,
                "UNRELATED_FOUNDER_OWNER_CHANGED")
    require(call("systemctl","show","empire-founder-console.service","-p","WorkingDirectory","--value")==str(STAGE),
            "NOT_EXISTING_FOUNDER_SERVICE_WORKDIR")
    require(call("systemctl","is-active","empire-founder-console.service")=="active",
            "ORIGINAL_FOUNDER_SERVICE_NOT_ACTIVE")
    require(status("http://127.0.0.1:3001/founder/results")[0]==200,
            "ORIGINAL_FOUNDER_RESULTS_UNHEALTHY")
    require(status("http://127.0.0.1:3001/founder/agency")[0]==200,
            "ORIGINAL_PRIVATE_AGENCY_NOT_READY")
    return {
        "status":"SCOPED_ORIGINAL_FOUNDER_SEO_RELEASE_PREFLIGHT_PASS",
        "original_build":ORIGINAL_BUILD,
        "candidate_build":NEW_BUILD,
        "changed_routes":["/founder/seo-operations","/founder/results"],
        "other_owner_sources_identical":True,
        "service_running":True,
        "writes":False,
        "database_writes":False,"outbound_sent":False,
    }


def write_atomic(src: Path,dest: Path) -> None:
    temporary=dest.with_name(dest.name+".seo-publish-tmp")
    require(not temporary.exists() and not temporary.is_symlink(),"STALE_SOURCE_TMP")
    shutil.copy2(src,temporary)
    os.replace(temporary,dest)


def verify_live() -> dict:
    states={}
    for route in HEALTH_ROUTES:
        result=0
        body=b""
        for _ in range(16):
            result,body=status("http://127.0.0.1:3001"+route,seconds=3)
            if result==200:
                break
            time.sleep(0.75)
        states[route]=result
        require(result==200,"FOUNDER_ROUTE_NOT_200:"+route)
        if route=="/founder/seo-operations":
            for marker in (b"SEO Operations",b"Original actions",b"Live tests",
                           b"Verified / resolved",b"Measured revenue",b"Not verified"):
                require(marker in body,"SEO_BOARD_PRIVATE_EVIDENCE_NOT_RENDERED")
    require(call("systemctl","is-active","empire-founder-console.service")=="active",
            "FOUNDER_SERVICE_POST_RELEASE_NOT_ACTIVE")
    return states


def activate() -> dict:
    require(os.geteuid()==0,"ACTIVATION_REQUIRES_AUTHORIZED_SUDO")
    RELEASE.mkdir(exist_ok=True)
    lockfd=os.open(RELEASE/".founder-seo-activation.lock",
                   os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lockfd,"rb") as fd:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        check=preflight()
        require(not BACKUP.exists() and not BACKUP.is_symlink(),
                "ORIGINAL_FOUNDER_BACKUP_ALREADY_EXISTS")
        BACKUP.mkdir(mode=0o700)
        old_next=BACKUP/".next.original"
        old_results=BACKUP/"results.page.original.tsx"
        failed_next=BACKUP/".next.failed_candidate"
        incoming_next=STAGE/".next.seo-operations-candidate"
        require(not incoming_next.exists() and not incoming_next.is_symlink(),
                "PREVIOUS_CANDIDATE_STAGE_EXISTS")
        shutil.copy2(STAGE/RESULTS_PAGE,old_results)
        try:
            # Build copy while original service is still running.
            shutil.copytree(CANDIDATE/".next",incoming_next,symlinks=True)
            require((incoming_next/"BUILD_ID").read_text().strip()==NEW_BUILD,
                    "COPIED_BUILD_NOT_MATCHING_REVIEW")
            # Only two source changes; no modification of other owners' files.
            (STAGE/SEO_PAGE).parent.mkdir(parents=True,exist_ok=True)
            write_atomic(CANDIDATE/SEO_PAGE,STAGE/SEO_PAGE)
            write_atomic(CANDIDATE/RESULTS_PAGE,STAGE/RESULTS_PAGE)
            # Both directories are on the same filesystem; renames atomic.
            os.replace(STAGE/".next",old_next)
            os.replace(incoming_next,STAGE/".next")
            call("systemctl","restart","empire-founder-console.service")
            routes=verify_live()
        except BaseException:
            # Preserve failed build for debugging and restore the exact old one.
            if old_next.is_dir():
                if (STAGE/".next").exists():
                    os.replace(STAGE/".next",failed_next)
                os.replace(old_next,STAGE/".next")
            if old_results.is_file():
                write_atomic(old_results,STAGE/RESULTS_PAGE)
            (STAGE/SEO_PAGE).unlink(missing_ok=True)
            if incoming_next.is_dir():
                shutil.rmtree(incoming_next)
            try:
                call("systemctl","restart","empire-founder-console.service")
            except Exception:
                pass
            raise
        output={
            "status":"ORIGINAL_FOUNDER_SEO_OPERATIONS_LIVE_VERIFIED",
            "old_build_backup":str(old_next),
            "previous_results_source":str(old_results),
            "new_build":NEW_BUILD,
            "route_http_statuses":routes,
            "source_files_changed":2,
            "other_founder_owner_sources_changed":False,
            "new_timer":False,"database_writes":False,
            "outbound_sent":False,"payment_activated":False,
        }
        receipt=RELEASE/"activation_result.json"
        f=os.open(receipt,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(f,"w") as out:
            json.dump(output,out,sort_keys=True,indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        return output


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--activate",action="store_true")
    a=p.parse_args()
    try:
        print(json.dumps(activate() if a.activate else preflight(),sort_keys=True))
        return 0
    except Exception as err:
        print(json.dumps({"status":"ORIGINAL_FOUNDER_SEO_RELEASE_HELD_OR_ROLLED_BACK",
                          "error_code":type(err).__name__,
                          "reason":str(err)[:180],
                          "live_verified":False,
                          "database_writes":False},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
