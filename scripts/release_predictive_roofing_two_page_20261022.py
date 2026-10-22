"""GUARDED two-page public SEO release (operator explicitly approves exact bytes).

Read-only by default. Never alters unrelated pages, the 30 legacy AEO routes,
DNS, mail, checkout, payment, Ringba, CRM or Jev model configuration.
Publishes only FOUR existing page payload files and EIGHT collision-free
content-hashed assets. Rolls back these files if any operation fails.
"""
from __future__ import annotations

import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Callable, Mapping

from scripts.prepare_predictive_roofing_mobile_overlay_20261022 import (
    LIVE, OUT, REPLACE, LIVE_SHA, NEW_SHA, ScopedOverlayHeld, inventory,
    review_private, plan,
)

BACKUP=Path("/var/backups/empire-website/seo-two-page-prepublish-20261022T121506Z.tar")
BACKUP_RECEIPT=BACKUP.with_suffix(".receipt.json")
BACKUP_SHA="ce96f4736d24d4d3ce5158b8cde745d5c144b677f25a20abf9956dc39594fa50"
BACKUP_RECEIPT_SHA="812a26346fc63186da8b0fcf7b967fac8499beaffc91717a401a71ffff7775e8"
OVERLAY_RECEIPT_SHA="2f33238d06878150d908663b1ec3415a415db62ad7266254f2438a0899edc62a"
BROWSER_SHA="8565d384217bfa4674195e4990db9a0b4f75e8f0b1589b449513f49bbeba919f"
APPROVAL="--apply-founder-approved-predictive-roofing-two-pages"
RELEASE_RECEIPT=OUT/"ACTIVATED_TWO_PAGE_RELEASE_20261022.json"


class TwoPageReleaseHeld(ValueError):
    pass


def sha(path:Path)->str:
    return sha256(path.read_bytes()).hexdigest()


def require_restore_custody() -> dict[str,Any]:
    if os.geteuid()!=0:
        raise TwoPageReleaseHeld("ROOT_PROTECTED_ROLLBACK_READ_REQUIRED")
    if (BACKUP.is_symlink() or BACKUP_RECEIPT.is_symlink()
            or not BACKUP.is_file() or not BACKUP_RECEIPT.is_file()
            or stat.S_IMODE(BACKUP.stat().st_mode)!=0o600
            or BACKUP.stat().st_uid!=0):
        raise TwoPageReleaseHeld("ROOT_PROTECTED_BACKUP_MISSING_OR_UNSAFE")
    if sha(BACKUP)!=BACKUP_SHA or sha(BACKUP_RECEIPT)!=BACKUP_RECEIPT_SHA:
        raise TwoPageReleaseHeld("BACKUP_SHA256_DRIFT")
    d=json.loads(BACKUP_RECEIPT.read_text(encoding="utf-8"))
    if (d.get("complete_live_file_count")!=645
            or d.get("archive_sha256")!=BACKUP_SHA
            or d.get("all_645_live_file_contents_readback_verified") is not True
            or d.get("new_content_published") is not False
            or d.get("new_publishing_authority") is not False):
        raise TwoPageReleaseHeld("BACKUP_CUSTODY_RECEIPT_HOLD")
    return {"root_private_verified_backup":str(BACKUP),
            "root_private_archive_sha256":BACKUP_SHA,
            "files":645}


def _pinned_candidate()->dict[str,Any]:
    original=OUT/"RELEASE_CANDIDATE_RECEIPT.json"
    browser=OUT/"BROWSER_CANDIDATE_QA.json"
    if any(p.is_symlink() or not p.is_file() for p in (original,browser)):
        raise TwoPageReleaseHeld("PINNED_CANDIDATE_RECEIPT_MISSING")
    if sha(original)!=OVERLAY_RECEIPT_SHA or sha(browser)!=BROWSER_SHA:
        raise TwoPageReleaseHeld("PINNED_QA_OR_OVERLAY_MANIFEST_DRIFT")
    private=review_private()
    if private.get("site_publication_authorized") is not False:
        raise TwoPageReleaseHeld("UNEXPECTED_AUTHORITY_IN_PRIVATE_MANIFEST")
    d=json.loads(browser.read_text(encoding="utf-8"))
    if (d.get("status")!="PRIVATE_DESKTOP_MOBILE_BROWSER_SMOKE_PASS_NOT_PUBLISHED"
            or len(d.get("route_checks",[]))!=8
            or len(d.get("navigation_checks",[]))!=2
            or d.get("page_errors")!=[]
            or d.get("missing_local_assets")!=[]
            or d.get("form_submissions")!=0
            or d.get("blocked_external")!=0
            or d.get("blocked_non_get")!=0
            or any(row.get("overflow") or row.get("http_status")!=200 or not row.get("hasText")
                   for row in d["route_checks"])
            or any(n.get("passed") is not True for n in d["navigation_checks"])):
        raise TwoPageReleaseHeld("PRIVATE_BROWSER_QA_NOT_PASSED")
    return private


def preflight(*,live:Path=LIVE, backup_required:bool=True) ->dict[str,Any]:
    if (OUT/"ACTIVATED_TWO_PAGE_RELEASE_20261022.json").exists():
        raise TwoPageReleaseHeld("RELEASE_ALREADY_RECORDED_NO_REPEAT")
    _pinned_candidate()
    if backup_required:
        require_restore_custody()
    candidate=plan(live=live)
    actual=inventory(live)
    if len(actual)!=645 or len(candidate["added_static_sha256"])!=8:
        raise TwoPageReleaseHeld("TARGET_SCOPE_OR_LIVE_GENERATION_DRIFT")
    if any(actual.get(k,(None,))[0]!=LIVE_SHA[k] for k in REPLACE):
        raise TwoPageReleaseHeld("ORIGINAL_FOUR_PAGE_PAYLOADS_CHANGED")
    return {
        "schema_version":"empire.website.two_page_public_seo_release_preflight.v1",
        "status":"READY_FOR_SPECIFIC_FOUNDER_PUBLICATION_APPROVAL",
        "existing_public_files":len(actual),
        "files_to_replace":list(REPLACE),
        "new_only_assets":list(candidate["added_static_sha256"]),
        "new_only_asset_count":8,
        "candidate_receipt_sha256":OVERLAY_RECEIPT_SHA,
        "browser_qa_receipt_sha256":BROWSER_SHA,
        "backed_up_current_live_files":645 if backup_required else None,
        "candidate_source_commit":"79dd421bb",
        "founder_visual_approval_recorded":False,
        "publication_not_yet_authorised":True,
        "writes_performed":False,
        "execution_authority":"NONE",
    }


def _atomic(path:Path,data:bytes, mode:int=0o644,
            uid:int|None=None,gid:int|None=None)->None:
    fd,temp=tempfile.mkstemp(prefix=".seo-two-page-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp,mode)
        if uid is not None and gid is not None and os.geteuid()==0:
            os.chown(temp,uid,gid)
        os.replace(temp,path)
    finally:
        Path(temp).unlink(missing_ok=True)


def apply_four_pages_and_eight_assets(
    *,
    live:Path, stage:Path,
    baseline:Mapping[str,str], replacements:Mapping[str,str],
    additions:Mapping[str,str],
    final_probe:Callable[[],None]|None=None,
)->dict[str,Any]:
    """Isolated transaction core, suitable for temp-tree fault-injection tests."""
    old={}
    for name, digest in replacements.items():
        p=live/name
        if p.is_symlink() or not p.is_file() or sha(p)!=baseline[name]:
            raise TwoPageReleaseHeld("CHANGED_PRIOR_PUBLIC_PAGE_"+name)
        src=stage/name
        if src.is_symlink() or not src.is_file() or sha(src)!=digest:
            raise TwoPageReleaseHeld("CANDIDATE_CONTENT_DRIFT_"+name)
        old[name]=(p.read_bytes(),p.stat().st_mode & 0o777,p.stat().st_uid,p.stat().st_gid)
    for name,digest in additions.items():
        p=live/name
        src=stage/name
        if p.exists() or p.is_symlink() or src.is_symlink() or not src.is_file() or sha(src)!=digest:
            raise TwoPageReleaseHeld("STAGED_BUNDLE_PATH_COLLISION_"+name)
    swapped=[]
    installed=[]
    try:
        for name,digest in additions.items():
            target=live/name
            target.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
            installed.append(name)
            with os.fdopen(fd,"wb") as f:
                f.write((stage/name).read_bytes())
                if os.geteuid()==0:
                    parent=target.parent.stat()
                    os.fchown(f.fileno(),parent.st_uid,parent.st_gid)
                f.flush()
                os.fsync(f.fileno())
            if sha(target)!=digest:
                raise TwoPageReleaseHeld("STATIC_COPY_MISMATCH")
        for name,digest in replacements.items():
            target=live/name
            if sha(target)!=baseline[name]:
                raise TwoPageReleaseHeld("PAGE_CHANGED_MID_RELEASE")
            data=(stage/name).read_bytes()
            blob,mode,uid,gid=old[name]
            _atomic(target,data,mode,uid,gid)
            swapped.append(name)
            if sha(target)!=digest:
                raise TwoPageReleaseHeld("POST_SWAP_CONTENT_MISMATCH")
        if final_probe:
            final_probe()
        return {
            "status":"EXACT_TWO_PAGE_STATIC_RELEASE_APPLIED",
            "page_navigation_files_replaced":len(swapped),
            "new_hashed_assets_installed":len(installed),
            "unrelated_routes_replaced":0,
        }
    except Exception:
        conflicts=[]
        for name in reversed(swapped):
            target=live/name
            if target.is_symlink() or not target.is_file() or sha(target)!=replacements[name]:
                conflicts.append(name)
                continue
            blob,mode,uid,gid=old[name]
            _atomic(target,blob,mode,uid,gid)
        for name in reversed(installed):
            target=live/name
            if target.is_symlink() or not target.is_file() or sha(target)!=additions[name]:
                conflicts.append(name)
                continue
            target.unlink()
        if conflicts:
            raise TwoPageReleaseHeld("ROLLBACK_CONCURRENT_CHANGE_REQUIRES_MANUAL_CUSTODY") from None
        raise


def publish()->dict[str,Any]:
    if os.geteuid()!=0:
        raise TwoPageReleaseHeld("ROOT_CONTROLLED_TWO_PAGE_RELEASE_REQUIRED")
    summary=preflight()
    receipt=json.loads((OUT/"RELEASE_CANDIDATE_RECEIPT.json").read_text(encoding="utf-8"))
    if RECEIPT_HOLDER()!=False:
        raise TwoPageReleaseHeld("PUBLIC_RELEASE_RECEIPT_ALREADY_EXISTS")
    live_before=inventory(LIVE)
    expected_old=receipt["public_live_baseline_sha256"]
    if {k:v[0] for k,v in live_before.items()}!=expected_old:
        raise TwoPageReleaseHeld("PUBLIC_STATIC_TREE_CHANGED_BEFORE_RELEASE")
    stage=OUT/"out"
    final=receipt["private_candidate_sha256"]
    additions=receipt["added_static_sha256"]
    def check_local():
        current=inventory(LIVE)
        if {k:v[0] for k,v in current.items()}!=final:
            raise TwoPageReleaseHeld("POST_PUBLICATION_TREE_CONTENT_NOT_PINNED_653")
    outcome=apply_four_pages_and_eight_assets(
        live=LIVE,stage=stage,baseline=LIVE_SHA,replacements=NEW_SHA,
        additions=additions,final_probe=check_local,
    )
    status={
        **outcome,
        "schema_version":"empire.website.seo_two_page_publication.v1",
        "source_commit":"79dd421bb",
        "private_receipt_sha256":OVERLAY_RECEIPT_SHA,
        "root_private_backup_sha256":BACKUP_SHA,
        "public_file_count_after":653,
        "manual_owner_approval_required_to_execute":True,
        "gsc_or_customer_result_not_yet_observed":True,
        "outbound_or_money_moved":False,
    }
    try:
        fd=os.open(RELEASE_RECEIPT,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(status,f,sort_keys=True,indent=2)
            f.write("\n");f.flush();os.fsync(f.fileno())
    except Exception:
        # This is a serious operational issue: content may be live while receipt
        # creation failed. Never claim a rollback that wasn't executed.
        raise TwoPageReleaseHeld("RELEASE_APPLIED_BUT_RECEIPT_WRITE_FAILED_OWNER_REVIEW_REQUIRED") from None
    return status


def RECEIPT_HOLDER()->bool:
    return RELEASE_RECEIPT.exists() or RELEASE_RECEIPT.is_symlink()


def locked_publish()->dict[str,Any]:
    """Exclude concurrent invocations of this exact release operator."""
    path="/var/lock/empire-seo-predictive-roofing-two-page-20261022.lock"
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"rb") as f:
        try:
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise TwoPageReleaseHeld("ANOTHER_TWO_PAGE_RELEASE_IN_PROGRESS") from exc
        return publish()


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight",action="store_true")
    g.add_argument(APPROVAL,action="store_true")
    args=p.parse_args()
    try:
        out=preflight() if args.preflight else locked_publish()
        print(json.dumps(out,sort_keys=True))
    except (OSError,ValueError,ScopedOverlayHeld,TwoPageReleaseHeld) as exc:
        print(json.dumps({
            "status":"EXACT_TWO_PAGE_PUBLIC_RELEASE_HELD",
            "reason":str(exc) if isinstance(exc,ValueError) else "BACKUP_OR_SITE_IO_FAILURE",
            "automated_publication_authority":False,
            "new_payments_or_outbound":False,
        },sort_keys=True))
        raise SystemExit(2) from None


if __name__=="__main__":
    main()
