#!/usr/bin/env python3
"""Root-owned original AEO content-hash release, exact three preapproved pages.

Uses original AEO census and original release manifest. No hash bypass, no
mass rebuild, no extra provider, no new service. Rollback all eight objects
on failed release readback; backing up is prerequisite before any write.
"""
from __future__ import annotations
import argparse,fcntl,hashlib,json,os,shutil,stat,time
from pathlib import Path
from subprocess import check_output
import requests

from empire_os.aeo_release import load_release,release_status,build_release_manifest
from empire_os.aeo_recovery import build_aeo_recovery_census

ROOT=Path("/srv/empire_os")
STAGE=Path("/home/ubuntu/empire_releases/seo_aeo_entry_claim_v2_20261026_stage")
PUBLIC="https://empire-ai.co.uk"
SOURCE=ROOT/"scripts/_aeo_pages"
RUNTIME=ROOT/"runtime/aeo"
RECOVERY=ROOT/"runtime/search_intelligence/aeo_recovery/latest.json"
RELEASE=ROOT/"runtime/search_intelligence/aeo_release.json"
PAIRS=(("general_contractor","NYC"),("hvac","DFW"),("roofing","DFW"))
RESULT=STAGE/"activation_result.json"
PREPARED=STAGE/"candidate_manifest.json"

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def jread(path:Path):return json.loads(path.read_text())

def document_set():
    """Order three published files, three generation files, then two manifests."""
    items=[]
    for root,folder in [(RUNTIME,"pages_runtime"),(SOURCE,"pages_source")]:
        for niche,metro in PAIRS:
            rel=f"{niche}/{metro}/index.html"
            items.append((root/rel,STAGE/folder/rel))
    items += [(RECOVERY,STAGE/"new_recovery.json"),
              (RELEASE,STAGE/"new_release.json")]
    return items

def preflight():
    import subprocess
    from datetime import datetime, timezone
    from bs4 import BeautifulSoup
    import requests
    site=requests.get("https://empire-ai.co.uk/commercial",timeout=14)
    if site.status_code!=200:
        raise RuntimeError("ORIGINAL_COMMERCIAL_PAGE_NOT_LIVE")
    bs=BeautifulSoup(site.content,"html.parser")
    approved=False
    for tag in bs.select("script[src]"):
        uri=tag.get("src") or ""
        if not uri.startswith("/_next/static/chunks/app/commercial/page-"):
            continue
        script=requests.get("https://empire-ai.co.uk"+uri,timeout=14)
        if script.status_code==200 and all(
            v in script.text for v in (
                "/aeo/general_contractor/NYC/",
                "/aeo/hvac/DFW/",
                "/aeo/roofing/DFW/",
            )
        ):
            approved=True
    if not approved:raise RuntimeError("ORIGINAL_COMMERCIAL_CLIENT_AEO_ALLOWLIST_NOT_LIVE")
    active=subprocess.check_output(
       ["systemctl","show","empire-self-serve-checkout.service",
        "-p","ActiveState","--value"],text=True).strip()
    if active!="active":raise RuntimeError("EXISTING_CHECKOUT_NOT_ACTIVE")
    stamp=subprocess.check_output(
       ["systemctl","show","empire-self-serve-checkout.service",
        "-p","ExecMainStartTimestamp","--value"],text=True).strip()
    try:
        started=datetime.strptime(stamp,"%a %Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        updated=datetime.fromtimestamp(int(subprocess.check_output(
          ["git","-C",str(ROOT),"show","-s","--format=%ct",
           "36bed2353"],text=True).strip()),timezone.utc)
    except Exception as exc:
        raise RuntimeError("CHECKOUT_CODE_ACTIVATION_TIMESTAMP_UNAVAILABLE") from exc
    if started <= updated:
        raise RuntimeError("CHECKOUT_RUNNING_OLD_ENTRY_ALLOWLIST_RESTART_REQUIRED")
    health=requests.get("http://127.0.0.1:8098/v1/commercial/offers",timeout=10)
    if health.status_code!=200 or health.json().get("status")!="FOUNDER_LED_ENQUIRY_AVAILABLE":
        raise RuntimeError("EXISTING_COMMERCIAL_OFFERS_UNHEALTHY")
    if RESULT.exists() or RESULT.is_symlink():
        raise RuntimeError("RELEASE_ALREADY_ATTEMPTED_OR_OTHER_OPERATOR_OWNS")
    if not STAGE.is_dir() or STAGE.is_symlink():
        raise RuntimeError("ORIGINAL_REVIEWED_STAGE_MISSING")
    m=jread(PREPARED)
    if (m.get("schema_version")!="empire.seo.exact_three_aeo_governed_release_candidate.v1"
        or m.get("status")!="ORIGINAL_AEO_RELEASE_BUILDER_EXACT_CANDIDATE_VALID"
        or m.get("publish_authorized_pages")!=3
        or m.get("other_207_content_hashes_unchanged") is not True
        or m.get("original_publisher_load_release_verified") is not True):
        raise RuntimeError("REVIEWED_THREE_ONLY_PUBLISHER_CANDIDATE_MISSING")
    if sha(RECOVERY.read_bytes())!=m["original_live_recovery_sha256"]:
        raise RuntimeError("ORIGINAL_RECOVERY_REFRESHED_SINCE_STAGE_REBUILD_REQUIRED")
    if sha(RELEASE.read_bytes())!=m["original_live_release_sha256"]:
        raise RuntimeError("ROOT_OWNED_ORIGINAL_RELEASE_CHANGED")
    if sha((ROOT/"scripts/aeo_metro_gen.py").read_bytes())!=m["source_generator_sha256"]:
        raise RuntimeError("GENERATING_SOURCE_WAS_CHANGED")
    if sha((STAGE/"new_recovery.json").read_bytes())!=m["candidate_recovery_sha256"]:
        raise RuntimeError("CANDIDATE_RECOVERY_SOURCE_CHANGED")
    if sha((STAGE/"new_release.json").read_bytes())!=m["candidate_release_sha256"]:
        raise RuntimeError("CANDIDATE_RELEASE_SOURCE_CHANGED")
    if load_release() is None:
        raise RuntimeError("CURRENT_AEO_RELEASE_INVALID_BEFORE_ACTIVATION")
    new=jread(STAGE/"new_release.json")
    if (new.get("release_verified") is not True or new.get("zero_paid_media") is not True
        or new.get("execution_authority")!="none"
        or {(x["niche"],x["metro"]) for x in new.get("pages",[])}!=set(PAIRS)):
        raise RuntimeError("NEW_RELEASE_HAS_UNAPPROVED_SCOPE")
    if load_release(
        aeo_root=STAGE/"pages_runtime",
        recovery_path=STAGE/"new_recovery.json",
        release_path=STAGE/"new_release.json")!=new:
        raise RuntimeError("ORIGINAL_AEO_RELEASE_VALIDATOR_REJECTS_NEW_CANDIDATE")

    assets=jread(RECOVERY)["assets"]
    oldassets={(r["niche"],r["metro"]):r["content_hash"] for r in assets}
    newassets={(r["niche"],r["metro"]):r["content_hash"]
               for r in jread(STAGE/"new_recovery.json")["assets"]}
    if len(oldassets)!=210 or len(newassets)!=210:
        raise RuntimeError("UNEXPECTED_ORIGINAL_210_AEO_SOURCE_SCOPE")
    changed={x for x in oldassets if oldassets[x]!=newassets[x]}
    if changed!=set(PAIRS):
        raise RuntimeError("UNAPPROVED_PUBLISHABLE_PAGE_CHANGED")
    for root,stage_dir in ((RUNTIME,STAGE/"pages_runtime"),
                           (SOURCE,STAGE/"pages_source")):
        for key in oldassets:
            path=root/key[0]/key[1]/"index.html"
            cand=stage_dir/key[0]/key[1]/"index.html"
            if not path.is_file() or path.is_symlink() or not cand.is_file():
                raise RuntimeError("UNTRUSTED_AEO_ASSET_PATH:"+str(key))
            import re
            normalized=sha(re.sub(r"\s+"," ",path.read_text()).strip().encode())
            if normalized!=oldassets[key]:
                raise RuntimeError("LIVE_AEO_SOURCE_DRIFT:"+str(key))
            candidate_normalized=sha(re.sub(r"\s+"," ",cand.read_text()).strip().encode())
            if candidate_normalized!=newassets[key]:
                raise RuntimeError("CANDIDATE_AEO_SOURCE_DRIFT:"+str(key))
    if {(r["niche"],r["metro"]) for r in m["exact_changed_pairs"]}!=set(PAIRS):
        raise RuntimeError("EXACT_3_REVIEWED_PAIR_MANIFEST_INVALID")
    return m

def public_check(new:bool):
    expected=STAGE/"pages_runtime" if new else RUNTIME
    for niche,metro in PAIRS:
        route=f"/aeo/{niche}/{metro}/"
        res=requests.get(PUBLIC+route,timeout=14,headers={"Cache-Control":"no-cache"})
        if res.status_code!=200 or res.url.rstrip("/")!=(PUBLIC+route).rstrip("/"):
            raise RuntimeError("PUBLIC_AEO_GATEWAY_NOT_VALID:"+route+":"+str(res.status_code))
        if res.content!=(expected/niche/metro/"index.html").read_bytes():
            raise RuntimeError("PUBLIC_AEO_HTML_BYTE_HASH_NOT_EXPECTED:"+route)

def write_result(status:str,**details):
    doc={"schema_version":"empire.seo.original_gated_aeo_source_hint_release.v2",
        "status":status,"exact_approved_pages":3,"other_aeo_pages_untouched":207,
        "no_indexing_submissions":True,"no_new_services":True,
        "no_database_writes":True,"no_paid_placements":True,**details}
    tmp=RESULT.with_name(RESULT.name+".pending")
    tmp.write_text(json.dumps(doc,sort_keys=True,indent=2)+"\n")
    os.replace(tmp,RESULT)

def activate():
    if os.geteuid()!=0:
        raise RuntimeError("ORIGINAL_ROOT_OWNED_AEO_MANIFEST_REQUIRES_SUDO")
    fd=os.open("/run/lock/empire_aeo_entry_claim_v2_20261026.lock",
               os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        preflight()
        public_check(new=False)
        # Build all future file replacements next to current paths BEFORE
        # the first swap. Preserve original uid/gid/mode, even for root manifest.
        originals=document_set()
        prepared=[]
        rollback=[]
        original_stats={}
        backup=STAGE/"activation_backups"
        backup.mkdir(mode=0o700)
        for i,(dest,source) in enumerate(originals):
            if not dest.is_file() or dest.is_symlink():raise RuntimeError("NOT_NORMAL_OWNED_FILE")
            old=backup/f"{i:02d}.bak"
            original_stats[dest]=dest.stat()
            shutil.copy2(dest,old)
            rollback.append((dest,old))
            temp=dest.with_name(dest.name+".aeo20261026_new")
            if temp.exists():raise RuntimeError("OTHER_RELEASE_IN_PROGRESS_TEMP_EXISTS")
            shutil.copy2(source,temp)
            st=dest.stat()
            os.chown(temp,st.st_uid,st.st_gid)
            os.chmod(temp,stat.S_IMODE(st.st_mode))
            prepared.append((dest,temp))
        applied=[]
        try:
            for dest,temp in prepared:
                os.replace(temp,dest)
                applied.append(dest)
            if load_release() is None:
                raise RuntimeError("POST_INSTALL_ORIGINAL_RELEASE_VALIDATOR_FAILED")
            public_check(new=True)
            write_result("ORIGINAL_THREE_AEO_SOURCE_HINT_RELEASE_LIVE_VERIFIED",
                         live_http_200_pages=3,original_release_valid=True,
                         recovery_sha256=sha(RECOVERY.read_bytes()),
                         release_sha256=sha(RELEASE.read_bytes()),
                         backup_folder=str(backup))
            print(json.dumps({"status":"ORIGINAL_THREE_AEO_SOURCE_HINT_RELEASE_LIVE_VERIFIED",
                "pages":3,"rest_of_aeo_unchanged":207,
                "backup":str(backup),"receipt":str(RESULT)},sort_keys=True))
        except Exception as error:
            for dest,old in reversed(rollback):
                if dest not in applied:continue
                restore=dest.with_name(dest.name+".aeo20261026_rollback")
                shutil.copy2(old,restore)
                st=original_stats[dest]
                os.chown(restore,st.st_uid,st.st_gid)
                os.chmod(restore,stat.S_IMODE(st.st_mode))
                os.replace(restore,dest)
            try: public_check(new=False)
            except Exception:
                write_result("ORIGINAL_AEO_ROLLBACK_PUBLIC_REVIEW_REQUIRED",
                             cause=type(error).__name__)
                raise
            write_result("ORIGINAL_AEO_ROLLBACK_RESTORED",
                         cause=type(error).__name__)
            raise

def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight",action="store_true")
    group.add_argument("--activate",action="store_true")
    args=parser.parse_args()
    if args.preflight:
        data=preflight()
        print(json.dumps({"status":"ORIGINAL_GATED_THREE_AEO_RELEASE_READY",
            "approved_exact_pages":3,"unmodified_pages":207,
            "release_manifest_currently_valid":True,
            "recovery_candidate_valid":True,
            "original_release_sha256":data["original_live_release_sha256"],
            "site_mutated":False},sort_keys=True))
    else:
        activate()

if __name__=="__main__":
    main()
