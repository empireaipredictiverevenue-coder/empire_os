"""Review reported protected backup without inventing root or ASTRA authority."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from empire_os.earned_media_saas700_reconciliation import LIVE, verify
from empire_os.earned_media_saas_private_backup_audit import inspect_private_backup
from empire_os.earned_media_saas708_owner_preflight import review

ROOT = Path(__file__).resolve().parents[1]
REPORTED = ROOT / (
    "docs/website/release_candidates/"
    "EARNED_MEDIA_SAAS708_ROOT_ARCHIVE_OPERATOR_EVIDENCE_20261026.json"
)
PRIVATE = Path(
    "/home/ubuntu/empire_releases/earned_media_saas_union_20261026/"
    "private_700_baseline_backup/live_700_pre_708.tar.gz"
)


def test_reported_operator_archive_sha_is_byte_identical_to_audited_private():
    report = json.loads(REPORTED.read_text("utf-8"))
    assert report["root_create_command_returned_checksum"] == sha256(PRIVATE.read_bytes()).hexdigest()
    assert report["root_create_command_returned_checksum"] == (
        "65f7d9ab99a3808ea4e18922ef662c94365a1511d4e62c0019f03f92bbf220c7"
    )
    result = inspect_private_backup(PRIVATE, LIVE, expected_count=700)
    assert result["status"] == "PRIVATE_700_ARCHIVE_MEMBER_HASHES_EXACT"
    assert result["verified_regular_files"] == 700
    assert result["live_site_inventory_sha256"] == report["source_inventory_sha256"]


def test_user_reported_root_backup_does_not_fabricate_independent_owner_approval():
    report = json.loads(REPORTED.read_text("utf-8"))
    stage = verify()
    assert stage["candidate_index_sha256"] == report["staged_candidate_inventory_sha256"]
    assert report["original_astra_owner_root_direct_archive_member_audit_completed"] is False
    assert report["root_archive_content_directly_read_by_unprivileged_agent"] is False
    assert report["original_astra_owner_signoff_verified"] is False
    assert report["production_publication_authorized_by_this_report"] is False
    assert review()["gates"]["independent_original_astra_owner_release_approval"] is False


def test_direct_root_operator_audit_instruction_has_no_extraction_or_publish():
    p = ROOT / "docs/website/EARNED_MEDIA_SAAS708_ROOT_ARCHIVE_DIRECT_AUDIT_20261026.md"
    doc = p.read_text("utf-8")
    assert "sudo /usr/bin/python3 - <<'PY'" in doc
    assert 'with tarfile.open(archive, "r:gz") as tar:' in doc
    assert "extractfile(entry)" in doc
    assert "extractall(" not in doc
    assert "publication_performed" in doc
    assert "root-owned" in doc.lower()
