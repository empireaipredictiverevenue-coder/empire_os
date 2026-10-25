"""Owner-only publication of one paired SaaS route and ten new hashed assets.

Default invocation is read-only. Deployment is never authorised by the founder
chat approval alone. The already designated ASTRA owner must separately create
a protected root-only approval receipt and complete a matching *root-owned*
all-file rollback archive before an exact-scope publish is allowed.

No checkouts, CRM records, email, payment rails, DNS or services are touched.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile
from typing import Callable

from scripts import review_saas_evidence_release_candidate_20261025 as qa

FOUNDER = Path(
    "/srv/empire_os/docs/website/release_candidates/"
    "SAAS_EVIDENCE_FOUNDER_APPROVAL_20261025.json"
)
OWNER_AUTHORITY = Path(
    "/var/backups/empire-website/"
    "saas-evidence-20261025-website-owner-approval.json"
)
ROOT_BACKUP = Path(
    "/var/backups/empire-website/"
    "saas-evidence-20261025-root-backup.tar.gz"
)
ROOT_RECEIPT = Path(
    "/var/backups/empire-website/"
    "saas-evidence-20261025-published.json"
)
LOCK = Path("/var/lock/empire-saas-evidence-paired-route-release-20261025.lock")
APPLY_FLAG = "--apply-owner-approved-saas-evidence-paired-route"


class SiteReleaseHeld(ValueError):
    pass


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
        raise SiteReleaseHeld("APPROVAL_DOCUMENT_UNTRUSTED")
    obj = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(obj, dict):
        raise SiteReleaseHeld("APPROVAL_DOCUMENT_NOT_OBJECT")
    return obj


def verify_founder() -> dict:
    obj = _read_json(FOUNDER)
    if (
        obj.get("schema_version") != "empire.website.saas_evidence_founder_approval.v1"
        or obj.get("decision") !=
        "FOUNDER_APPROVES_EXACT_SCOPE_SUBJECT_TO_WEBSITE_OWNER_AND_PROTECTED_ROLLBACK"
        or obj.get("founder_approval_for_exact_candidate") is not True
        or obj.get("website_owner_independent_signoff_verified") is not False
        or obj.get("root_protected_rollback_verified") is not False
        or obj.get("publication_authorized_now") is not False
        or obj.get("site_published") is not False
        or obj.get("replaced_files") != sorted(qa.REPLACE)
        or obj.get("manifest_sha256") != digest(qa.MANIFEST)
    ):
        raise SiteReleaseHeld("FOUNDER_APPROVAL_SCOPE_OR_SOURCE_MISMATCH")
    manifest = _read_json(qa.MANIFEST)
    if (
        obj.get("expected_candidate_full_inventory_sha256") !=
        manifest.get("candidate_inventory_sha256")
        or obj.get("expected_live_file_count") != qa.EXPECTED_LIVE_COUNT
        or obj.get("expected_candidate_file_count") != qa.EXPECTED_UNION_COUNT
    ):
        raise SiteReleaseHeld("FOUNDER_APPROVAL_PIN_MISMATCH")
    return obj


def _root_file(path: Path) -> None:
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_uid != 0
            or stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise SiteReleaseHeld("ROOT_OWNED_MODE_0600_FILE_REQUIRED")


def verify_owner_and_backup(owner_path: Path = OWNER_AUTHORITY,
                            backup_path: Path = ROOT_BACKUP,
                            *, founder_sha: str | None = None,
                            expected: dict[str, str] | None = None) -> dict:
    """Only invoke from an explicitly privileged original release session."""
    if os.geteuid() != 0:
        raise SiteReleaseHeld("EXISTING_ROOT_WEBSITE_RELEASE_OPERATOR_REQUIRED")
    if not (owner_path.parent.is_dir()
            and owner_path.parent.stat().st_uid == 0
            and stat.S_IMODE(owner_path.parent.stat().st_mode) == 0o700):
        raise SiteReleaseHeld("ROOT_PROTECTED_WEBSITE_ROLLBACK_DIRECTORY_REQUIRED")
    _root_file(owner_path)
    _root_file(backup_path)
    source = _read_json(owner_path)
    required = {
        "schema_version": "empire.website.saas_evidence_owner_release_authority.v1",
        "original_owner": "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER",
        "independent_website_owner_review_complete": True,
        "approval_for_exact_paired_route_release": True,
        "founder_approval_sha256": founder_sha,
        "candidate_inventory_sha256": _read_json(qa.MANIFEST).get(
            "candidate_inventory_sha256"),
        "root_backup_archive_sha256": digest(backup_path),
        "publication_performed": False,
    }
    for name,value in required.items():
        if source.get(name) != value or type(source.get(name)) is not type(value):
            raise SiteReleaseHeld("OWNER_AUTHORITY_NOT_ATTESTED_" + name)
    if not re.fullmatch(r"[0-9a-f]{64}",source["root_backup_archive_sha256"]):
        raise SiteReleaseHeld("BACKUP_DIGEST_NOT_SHA256")
    if expected is None:
        raise SiteReleaseHeld("NO_APPROVED_SOURCE_INVENTORY")
    with tarfile.open(backup_path, "r:gz") as tar:
        members = tar.getmembers()
        if len(members) != len(expected) or len(members) != qa.EXPECTED_LIVE_COUNT:
            raise SiteReleaseHeld("PROTECTED_BACKUP_FILE_COUNT_MISMATCH")
        seen=set()
        total=0
        for member in members:
            name=member.name
            if (not member.isfile() or name not in expected
                    or name in seen or member.size > 20_000_000):
                raise SiteReleaseHeld("BACKUP_MEMBER_UNSAFE_OR_UNAPPROVED")
            seen.add(name)
            total += member.size
            if total > 120_000_000:
                raise SiteReleaseHeld("BACKUP_UNBOUNDED")
            fd=tar.extractfile(member)
            if fd is None or sha256(fd.read()).hexdigest()!=expected[name]:
                raise SiteReleaseHeld("ROOT_BACKUP_SOURCE_HASH_MISMATCH")
        if seen != set(expected):
            raise SiteReleaseHeld("PROTECTED_BACKUP_INCOMPLETE")
    return {
        "verified_owner_root_receipt": True,
        "verified_root_owned_rollback_file_count": len(expected),
        "verified_root_backup_archive_sha256": digest(backup_path),
    }


def atomic_replace(path: Path, content: bytes, mode: int, uid: int, gid: int) -> None:
    fd,temp = tempfile.mkstemp(prefix=".saas-page-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
            os.fchmod(file.fileno(),mode)
            if os.geteuid() == 0:
                os.fchown(file.fileno(),uid,gid)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def transaction(live: Path, stage: Path, baseline: dict[str,str],
                final: dict[str,str], *, on_applied: Callable[[],None]
                ) -> dict:
    """Fault-injectable exact-scoped transaction; rollback on failure."""
    names=sorted(qa.REPLACE)
    additions=sorted(set(final)-set(baseline))
    if len(additions)!=10 or set(baseline)-set(final):
        raise SiteReleaseHeld("RELEASE_DELTA_NOT_PINNED")
    if ({k for k in baseline if baseline[k]!=final[k]} != qa.REPLACE
            or any(not k.startswith("_next/static/") for k in additions)):
        raise SiteReleaseHeld("RELEASE_OLD_FILE_SCOPE_CHANGED")
    old = {}
    for name in names:
        file=live/name
        if file.is_symlink() or not file.is_file() or digest(file)!=baseline[name]:
            raise SiteReleaseHeld("LIVE_ROUTE_NOT_ON_APPROVED_VERSION")
        info=file.stat()
        old[name]=(file.read_bytes(),stat.S_IMODE(info.st_mode),
                   info.st_uid,info.st_gid)
    for name in additions:
        src=stage/name
        if ((live/name).exists() or (live/name).is_symlink()
                or src.is_symlink() or not src.is_file()
                or digest(src)!=final[name]):
            raise SiteReleaseHeld("NEW_STATIC_ASSET_SCOPE_OR_BYTES_UNTRUSTED")
    swapped=[]
    installed=[]
    try:
        for name in additions:
            target=live/name
            target.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            installed.append(name)
            with os.fdopen(fd,"wb") as out:
                out.write((stage/name).read_bytes())
                owner=target.parent.stat()
                if os.geteuid() == 0:
                    os.fchown(out.fileno(),owner.st_uid,owner.st_gid)
                out.flush()
                os.fsync(out.fileno())
            if digest(target)!=final[name]:
                raise SiteReleaseHeld("ADDED_ASSET_HASH_MISMATCH")
        for name in names:
            target=live/name
            if digest(target)!=baseline[name]:
                raise SiteReleaseHeld("LIVE_ROUTE_CHANGED_DURING_PUBLISH")
            content=(stage/name).read_bytes()
            if sha256(content).hexdigest()!=final[name]:
                raise SiteReleaseHeld("STAGED_ROUTE_CHANGED_DURING_PUBLISH")
            blob,mode,uid,gid=old[name]
            atomic_replace(target,content,mode,uid,gid)
            swapped.append(name)
            if digest(target)!=final[name]:
                raise SiteReleaseHeld("PUBLISHED_ROUTE_HASH_MISMATCH")
        on_applied()
        return {
            "files_replaced":len(swapped),
            "new_hashed_static_assets":len(installed),
            "other_existing_files_changed":0,
        }
    except Exception:
        conflicts=[]
        for name in reversed(swapped):
            target=live/name
            if target.is_symlink() or not target.is_file() or digest(target)!=final[name]:
                conflicts.append(name)
                continue
            blob,mode,uid,gid=old[name]
            atomic_replace(target,blob,mode,uid,gid)
        for name in reversed(installed):
            target=live/name
            if target.is_symlink() or not target.is_file() or digest(target)!=final[name]:
                conflicts.append(name)
                continue
            target.unlink()
        if conflicts:
            raise SiteReleaseHeld(
                "CONCURRENT_MODIFICATION_ROLLBACK_REQUIRES_ORIGINAL_OWNER")
        raise


def read_only_preflight() -> dict:
    founder=verify_founder()
    report=qa.review()
    return {
        "schema_version":"empire.website.saas_evidence_owner_release_preflight.v1",
        "status":"FOUNDER_APPROVED_AWAITING_ORIGINAL_WEBSITE_OWNER_ROOT_CUSTODY",
        "original_qa_status":report["status"],
        "founder_exact_scope_approved":True,
        "replaced_files":report["replacement_files"],
        "new_only_assets":len(report["added_assets"]),
        "protected_root_backup_verified":False,
        "independent_website_owner_approval_verified":False,
        "publication_authorized":False,
        "publication_performed":False,
    }


def apply() -> dict:
    if os.geteuid()!=0:
        raise SiteReleaseHeld("ROOT_OPERATOR_ONLY_NOT_EMPIREOS_BUILDER")
    if ROOT_RECEIPT.exists() or ROOT_RECEIPT.is_symlink():
        raise SiteReleaseHeld("ALREADY_PUBLISHED_OR_RECEIPT_CONFLICT_NO_REPEAT")
    verify_founder()
    if qa.review().get("status") != "PRIVATE_REVIEW_PASS_PUBLICATION_HELD":
        raise SiteReleaseHeld("LIVE_CANDIDATE_PREFLIGHT_NOT_PASSED")
    baseline=qa.read_index(qa.LIVE)
    final=qa.read_index(qa.CANDIDATE)
    owner=verify_owner_and_backup(
        founder_sha=digest(FOUNDER), expected=baseline)
    manifest=_read_json(qa.MANIFEST)
    if final != qa.read_index(qa.CANDIDATE):
        raise SiteReleaseHeld("CANDIDATE_CHANGED_DURING_AUTHORIZATION")
    def postcommit():
        actual=qa.read_index(qa.LIVE)
        if actual!=final:
            raise SiteReleaseHeld("LIVE_FINAL_FULL_INVENTORY_NOT_EXACT")
        receipt={
            "schema_version":"empire.website.saas_evidence_root_publication.v1",
            "status":"EXACT_TWO_PAYLOAD_TEN_ASSET_RELEASE_PUBLISHED",
            "candidate_inventory_sha256":qa.index_digest(final),
            "source_founder_approval_sha256":digest(FOUNDER),
            "root_rollback_sha256":owner["verified_root_backup_archive_sha256"],
            "root_owner_receipt_sha256":digest(OWNER_AUTHORITY),
            "exact_new_file_count":len(final),
            "new_messages_sent":0,
            "money_moved":False,
        }
        fd=os.open(ROOT_RECEIPT,
                   os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w",encoding="utf8") as out:
            json.dump(receipt,out,indent=2,sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
    return transaction(qa.LIVE,qa.CANDIDATE,baseline,final,on_applied=postcommit)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight",action="store_true")
    g.add_argument(APPLY_FLAG,action="store_true")
    args=parser.parse_args()
    try:
        if args.preflight:
            print(json.dumps(read_only_preflight(),sort_keys=True))
        else:
            if os.geteuid()!=0:
                raise SiteReleaseHeld("ROOT_OPERATOR_ONLY_NOT_EMPIREOS_BUILDER")
            fd=os.open(LOCK,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"rb") as lock:
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                print(json.dumps(apply(),sort_keys=True))
        return 0
    except (SiteReleaseHeld,qa.SitePreflightHold,OSError,ValueError,
            TypeError,tarfile.TarError) as exc:
        print(json.dumps({
            "status":"SITE_RELEASE_HELD_NO_PUBLICATION",
            "reason":str(exc) if isinstance(exc,ValueError) else type(exc).__name__,
            "publication_authorized":False,
            "publication_performed":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
