"""Read-only ASTRA owner intake for EXACT 662-to-670 public SaaS candidate.

Owner receipts are independently authored, never synthesized here.
No website promotion, backend restart, CRM, user identity or payment actions.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import stat
import tarfile

from empire_os.earned_media_saas_release_scope import check_scope
from empire_os.earned_media_saas_rebased_release import (
    read_index, index_digest, ReleaseHeld,
)

SCHEMA = "empire.website.earned_media_saas670_owner_preflight.v1"
PINNED_SOURCE_INDEX_SHA = "e894e2a9134ad13c6612f886c59b54da72b9c4791947dd0429e912723f0cdaa9"
PINNED_CANDIDATE_INDEX_SHA = "2d37c7537329914fcecf531b34ff6fbeec42413da7dd42f5d5e4174f1411742b"
PINNED_BROWSER_QA_SHA = "99bf63c7f7a592cecfb003da07e39503ea457126ff72243c6aa60583f154e9c5"
FOUNDER_SCHEMA = "empire.website.saas670_founder_exact_approval.v1"
OWNER_SCHEMA = "empire.website.saas670_astra_owner_authority.v1"
LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
ROOT = Path("/home/ubuntu/empire_releases/earned_media_saas_union_20261026")
CANDIDATE = ROOT / "rebased_candidate"
PRIVATE_RECEIPT = ROOT / "private_candidate_receipt.json"
FOUNDER = Path("/srv/empire_os/docs/website/release_candidates/SAAS670_FOUNDER_EXACT_APPROVAL_20261026.json")
PROTECTED = Path("/var/backups/empire-website")
ROOT_BACKUP = PROTECTED / "saas670-pre-release-20261026.tar.gz"
ASTRA_AUTHORITY = PROTECTED / "saas670-original-astra-owner-authority.json"
BROWSER_RECEIPT = Path(__file__).resolve().parents[1] / (
    "docs/website/release_candidates/EARNED_MEDIA_SAAS_REBASED_BROWSER_QA_20261026.json"
)


def _read_json(path: Path, *, protected: bool = False) -> dict | None:
    try:
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_size > 100000):
            return None
        if protected and (path.stat().st_uid != 0 or
                stat.S_IMODE(path.stat().st_mode) != 0o600):
            return None
        content = json.loads(path.read_text("utf-8"))
        return content if isinstance(content, dict) else None
    except (OSError, UnicodeError, ValueError):
        return None


def _verify_root_backup(source: dict[str, str]) -> tuple[bool, str | None]:
    """Read protected archive only; root directory itself must remain private."""
    try:
        if (PROTECTED.is_symlink() or not PROTECTED.is_dir()
                or PROTECTED.stat().st_uid != 0
                or stat.S_IMODE(PROTECTED.stat().st_mode) != 0o700
                or ROOT_BACKUP.is_symlink() or not ROOT_BACKUP.is_file()
                or ROOT_BACKUP.stat().st_uid != 0
                or stat.S_IMODE(ROOT_BACKUP.stat().st_mode) != 0o600):
            return False, None
        actual: dict[str, str] = {}
        size = 0
        with tarfile.open(ROOT_BACKUP, "r:gz") as tar:
            for member in tar:
                rel = PurePosixPath(member.name)
                name = member.name.removeprefix("./")
                if (not member.isfile() or name not in source
                        or name in actual or rel.is_absolute()
                        or ".." in rel.parts or member.size > 20000000):
                    return False, None
                size += member.size
                if size > 120000000:
                    return False, None
                reader = tar.extractfile(member)
                if reader is None:
                    return False, None
                with reader:
                    digest = sha256(reader.read()).hexdigest()
                if digest != source[name]:
                    return False, None
                actual[name] = digest
        if actual != source:
            return False, None
        return True, sha256(ROOT_BACKUP.read_bytes()).hexdigest()
    except (OSError, PermissionError, tarfile.TarError, EOFError, ValueError):
        return False, None


def review(
    *,
    live: Path = LIVE,
    candidate: Path = CANDIDATE,
    receipt_path: Path = PRIVATE_RECEIPT,
    founder_path: Path = FOUNDER,
    owner_path: Path = ASTRA_AUTHORITY,
    browser_path: Path = BROWSER_RECEIPT,
    verify_root_backup: bool = True,
) -> dict:
    try:
        scope = check_scope(live, candidate)
        source = read_index(live)
        proposed = read_index(candidate)
    except (OSError, ReleaseHeld, ValueError) as exc:
        return {
            "schema_version": SCHEMA,
            "status": "RELEASE_HELD_CURRENT_SOURCE_OR_CANDIDATE_DRIFT",
            "reason": str(exc) if isinstance(exc, ReleaseHeld) else type(exc).__name__,
            "publication_authorized": False,
            "website_modified": False,
        }
    receipt = _read_json(receipt_path)
    candidate_valid = bool(
        receipt and receipt.get("schema_version") ==
            "empire.website.earned_media_saas_rebased_static_candidate.v1"
        and index_digest(source) == PINNED_SOURCE_INDEX_SHA
        and index_digest(proposed) == PINNED_CANDIDATE_INDEX_SHA
        and receipt.get("source_live_inventory_sha256") == PINNED_SOURCE_INDEX_SHA
        and receipt.get("rebased_candidate_inventory_sha256") == PINNED_CANDIDATE_INDEX_SHA
        and receipt.get("rebased_candidate_file_count") == 670
        and receipt.get("production_publication_authorized") is False
        and receipt.get("production_mutated") is False
    )
    browser = _read_json(browser_path)
    browser_valid = bool(
        browser and browser_path.is_file() and not browser_path.is_symlink()
        and sha256(browser_path.read_bytes()).hexdigest() == PINNED_BROWSER_QA_SHA
        and browser.get("status") ==
            "PRIVATE_REBASED_BROWSER_CTA_AND_CONSENT_PASS"
        and browser.get("form_posts") == 0
        and browser.get("requests_4xx_5xx") == 0
        and browser.get("runtime_exceptions") == 0
        and browser.get("external_requests") == 0
        and browser.get("publication_executed") is False
    )
    founder = _read_json(founder_path)
    founder_valid = bool(
        founder and founder.get("schema_version") == FOUNDER_SCHEMA
        and founder.get("decision") ==
            "FOUNDER_APPROVES_EXACT_REVISED_662_TO_670_PAYLOAD_FOR_ASTRA_REVIEW"
        and founder.get("candidate_file_count") == 670
        and founder.get("source_live_inventory_sha256") == index_digest(source)
        and founder.get("candidate_inventory_sha256") == index_digest(proposed)
        and founder.get("original_website_release_owner") ==
            "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER"
        and founder.get("publication_performed") is False
    )
    root_ok, backup_digest = (
        _verify_root_backup(source) if verify_root_backup
        else (False, None)
    )
    owner = _read_json(owner_path, protected=True)
    owner_valid = bool(
        owner and founder_valid and root_ok
        and owner.get("schema_version") == OWNER_SCHEMA
        and owner.get("original_release_owner") ==
            "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER"
        and owner.get("independent_visual_consent_and_source_review") is True
        and owner.get("scope_approved") == "TWO_ROUTES_EIGHT_STATIC_ASSETS"
        and owner.get("candidate_inventory_sha256") == index_digest(proposed)
        and owner.get("source_live_inventory_sha256") == index_digest(source)
        and owner.get("protected_rollback_sha256") == backup_digest
        and owner.get("exact_founder_approval_sha256") ==
            sha256(founder_path.read_bytes()).hexdigest()
        and owner.get("publication_performed") is False
    )
    gates = {
        "exact_source_and_670_candidate_pinned": candidate_valid,
        "isolated_browser_hydration_and_consent_passed": browser_valid,
        "revised_exact_payload_founder_approval_verified": founder_valid,
        "root_owned_662_member_backup_verified": root_ok,
        "original_astra_owner_exact_receipt_verified": owner_valid,
        "current_scope_exact_two_route_eight_assets": bool(
            len(scope["two_paired_route_files"]) == 2
            and len(scope["eight_immutable_assets"]) == 8
        ),
    }
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY",
        "status": (
            "OWNER_EVIDENCE_COMPLETE_REQUIRES_SEPARATE_PRIVILEGED_PUBLISHER"
            if all(gates.values()) else "RELEASE_HELD_MISSING_INDEPENDENT_AUTHORITY"
        ),
        "gates": gates,
        "missing_evidence": [name for name, good in gates.items() if not good],
        "site_baseline_files": 662,
        "rebased_candidate_files": 670,
        "production_owner_receipt_created": False,
        "protected_backup_created_by_this_tool": False,
        "publication_authorized_by_this_tool": False,
        "publication_performed": False,
        "root_publisher_invoked": False,
        "database_writes": False,
        "outbound_or_payments": False,
        "original_root_publisher_incompatible_with_new_candidate": True,
        "old_672_candidate_approval_not_reused": True,
    }
