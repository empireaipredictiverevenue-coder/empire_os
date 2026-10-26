"""Read-only evidence intake for the original ASTRA website release owner.

Checks the exact 700 -> 708 source/payload, explicit founder consent, isolated
Chrome results and independently produced root archive/owner receipt.
No privilege escalation, no backups created, no publisher, no outbound.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import stat
import tarfile

from empire_os.earned_media_saas700_reconciliation import (
    LIVE, DESTINATION, RECEIPT, verify,
)
from empire_os.earned_media_saas_rebased_release import (
    read_index, index_digest, ReleaseHeld,
)

SCHEMA = "empire.website.saas708_original_astra_owner_preflight.v1"
SOURCE_SHA = "f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df"
CANDIDATE_SHA = "62b62b184d5597ffc806a825723c4638f2953702c823561233d30058e398dab2"
FOUNDER_SHA = "9c50507dc469678b2e4f69c57bba035c6ea45c07832acab1d0dd89e7b9c67ee6"
BROWSER_SHA = "16e15e8ed3b888976045cda37312389a43d1415560044d8ab8bc0856cc6470fc"
FOUNDER_PATH = Path(
    "/srv/empire_os/docs/website/release_candidates/"
    "SAAS708_FOUNDER_EXACT_APPROVAL_20261026.json"
)
BROWSER_PATH = Path(__file__).resolve().parents[1] / (
    "docs/website/release_candidates/"
    "EARNED_MEDIA_SAAS708_CURRENT_SITE_BROWSER_QA_20261026.json"
)
ROOT_DIR = Path("/var/backups/empire-website")
ROOT_ARCHIVE = ROOT_DIR / "saas708-original-site-700-20261026.tar.gz"
OWNER_RECEIPT = ROOT_DIR / "saas708-original-astra-owner-release-authority.json"
OWNER_SCHEMA = "empire.website.saas708_astra_owner_authority.v1"


def read_json(path: Path, *, protected: bool = False) -> dict | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000:
            return None
        if protected and (path.stat().st_uid != 0 or
                          stat.S_IMODE(path.stat().st_mode) != 0o600):
            return None
        result = json.loads(path.read_text("utf8"))
        return result if type(result) is dict else None
    except (ValueError, OSError, UnicodeError):
        return None


def verify_protected_site_backup(
    original: dict[str, str], *,
    root: Path = ROOT_DIR, archive: Path = ROOT_ARCHIVE,
) -> tuple[bool, str | None]:
    """Inspect a separate root-owned, original-owner archive, never create it."""
    try:
        if (root.is_symlink() or not root.is_dir() or root.stat().st_uid != 0
            or stat.S_IMODE(root.stat().st_mode) != 0o700
            or archive.is_symlink() or not archive.is_file()
            or archive.stat().st_uid != 0 or
            stat.S_IMODE(archive.stat().st_mode) != 0o600):
            return False, None
        observed = {}
        total = 0
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar:
                rel = PurePosixPath(member.name)
                name = member.name.removeprefix("./")
                if member.isdir():
                    if rel.is_absolute() or ".." in rel.parts:
                        return False, None
                    continue
                if (not member.isfile() or rel.is_absolute()
                    or ".." in rel.parts or name not in original
                    or name in observed or member.size > 20_000_000):
                    return False, None
                total += member.size
                if total > 120_000_000:
                    return False, None
                stream = tar.extractfile(member)
                if stream is None:
                    return False, None
                with stream:
                    digest = sha256(stream.read()).hexdigest()
                if digest != original[name]:
                    return False, None
                observed[name] = digest
        if len(observed) != 700 or observed != original:
            return False, None
        return True, sha256(archive.read_bytes()).hexdigest()
    except (OSError, tarfile.TarError, ValueError, EOFError):
        return False, None


def review(*,
           founder_path: Path = FOUNDER_PATH,
           browser_path: Path = BROWSER_PATH,
           owner_path: Path = OWNER_RECEIPT,
           root_dir: Path = ROOT_DIR,
           root_archive: Path = ROOT_ARCHIVE) -> dict:
    try:
        source = read_index(LIVE)
        candidate = read_index(DESTINATION)
        stage = verify()
    except (OSError, ValueError, ReleaseHeld) as exc:
        return {
            "schema_version": SCHEMA,
            "status": "RELEASE_HELD_SOURCE_OR_CANDIDATE_CHANGED",
            "reason": str(exc), "publication_performed": False,
        }
    inventory_ok = (
        len(source) == 700 and len(candidate) == 708
        and index_digest(source) == SOURCE_SHA
        and index_digest(candidate) == CANDIDATE_SHA
        and stage["replaced_existing_files"] ==
            ["predictive-revenue.html", "predictive-revenue.txt"]
        and stage["new_static_assets_count"] == 8
        and stage["other_original_files_preserved_exactly"] == 698
        and stage["site_publication_authorized"] is False
        and stage["site_publication_performed"] is False
    )
    receipt = read_json(RECEIPT)
    manifest_ok = bool(
        receipt and receipt.get("schema_version") ==
            "empire.website.earned_media_saas700_source_reconciliation.v1"
        and receipt.get("source_live_inventory_sha256") == SOURCE_SHA
        and receipt.get("candidate_inventory_sha256") == CANDIDATE_SHA
        and receipt.get("new_founder_approval_verified") is False
        and receipt.get("site_publication_authorized") is False
    )
    founder = read_json(founder_path)
    founder_ok = bool(
        founder and founder_path.is_file() and not founder_path.is_symlink()
        and sha256(founder_path.read_bytes()).hexdigest() == FOUNDER_SHA
        and founder.get("schema_version") ==
            "empire.website.saas708_founder_exact_approval.v1"
        and founder.get("decision") ==
            "FOUNDER_APPROVES_EXACT_REVISED_700_TO_708_PAYLOAD_FOR_ASTRA_REVIEW"
        and founder.get("scope") ==
            "EXACT_708_FILE_CANDIDATE_FOR_ASTRA_FINAL_REVIEW_ONLY"
        and founder.get("source_live_inventory_sha256") == SOURCE_SHA
        and founder.get("candidate_inventory_sha256") == CANDIDATE_SHA
        and founder.get("immediate_publication_authorized") is False
        and founder.get("publication_performed") is False
    )
    browser = read_json(browser_path)
    browser_ok = bool(
        browser and browser_path.is_file() and not browser_path.is_symlink()
        and sha256(browser_path.read_bytes()).hexdigest() == BROWSER_SHA
        and browser.get("status") ==
            "PRIVATE_708_CURRENT_SITE_BROWSER_CTA_AND_CONSENT_PASS"
        and browser.get("actual_consent_form_checkbox_rendered") is True
        and browser.get("exact_new_cta") ==
            "/commercial?entry=%2Fpredictive-revenue#commercial-enquiry"
        and all(browser.get(k) == 0 for k in
            ("runtime_exceptions","requests_4xx_5xx","external_requests","form_posts"))
        and browser.get("publication_executed") is False
    )
    backup_ok, backup_sha = verify_protected_site_backup(
        source, root=root_dir, archive=root_archive
    )
    owner = read_json(owner_path, protected=True)
    owner_ok = bool(
        owner and founder_ok and backup_ok and inventory_ok and browser_ok
        and owner_path.parent == root_dir
        and owner.get("schema_version") == OWNER_SCHEMA
        and owner.get("original_release_owner") ==
            "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER"
        and owner.get("exact_release_scope") ==
            "REPLACE_TWO_SAAS_ROUTES_ADD_EIGHT_IMMUTABLE_ASSETS"
        and owner.get("independent_visual_mobile_consent_review_complete") is True
        and owner.get("concurrent_seo_commercial_release_reconciled") is True
        and owner.get("commercial_html_rsc_metadata_review_complete") is True
        and owner.get("source_live_inventory_sha256") == SOURCE_SHA
        and owner.get("candidate_inventory_sha256") == CANDIDATE_SHA
        and owner.get("founder_approval_sha256") == FOUNDER_SHA
        and owner.get("root_backup_sha256") == backup_sha
        and owner.get("independent_exact_scope_release_authorized") is True
        and owner.get("publication_performed") is False
    )
    gates = {
        "live_700_and_candidate_708_exact_sha256": inventory_ok,
        "private_candidate_scope_preserved": manifest_ok,
        "explicit_708_founder_review_approval": founder_ok,
        "isolated_real_browser_cta_consent": browser_ok,
        "original_owner_root_700_member_backup": backup_ok,
        "independent_original_astra_owner_release_approval": owner_ok,
    }
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY",
        "status": ("OWNER_EVIDENCE_COMPLETE_SEPARATE_PUBLISHER_REQUIRED"
                   if all(gates.values()) else
                   "RELEASE_HELD_MISSING_INDEPENDENT_OWNER_EVIDENCE"),
        "gates": gates,
        "missing_evidence": [k for k, passed in gates.items() if not passed],
        "source_inventory_sha256": SOURCE_SHA,
        "candidate_inventory_sha256": CANDIDATE_SHA,
        "founder_receipt_sha256": FOUNDER_SHA,
        "protected_root_backup_sha256": backup_sha if backup_ok else None,
        "original_old_publisher_672_not_applicable": True,
        "production_publication_authorized_by_preflight": False,
        "root_backup_created_by_preflight": False,
        "independent_owner_receipt_created_by_preflight": False,
        "website_modified": False,
        "publisher_invoked": False,
        "crm_or_database_writes": False,
        "outbound_or_payments": False,
    }
