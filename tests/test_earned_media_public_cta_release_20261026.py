"""Public release is exactly two source-only files, no private or backend path."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import subprocess

import pytest

from empire_os.earned_media_public_cta_release import (
    BASE_HASHES, BACKEND, ENTRY, GUIDE, SCHEMA,
    review_public_cta_candidate,
)
from scripts.review_earned_media_public_cta_release_20261026 import main


ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    base = tmp_path / "live"
    staging = tmp_path / "staged"
    for folder in (base, staging):
        folder.mkdir()
    for file in (GUIDE, ENTRY, BACKEND):
        old = subprocess.check_output([
            "git", "-C", str(ROOT), "show", f"362288a6e^:{file}",
        ])
        assert sha256(old).hexdigest() == BASE_HASHES[file]
        node = base / file
        node.parent.mkdir(parents=True, exist_ok=True)
        node.write_bytes(old)
        candidate = staging / file
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes((ROOT / file).read_bytes())
    return staging, base


def test_two_file_patch_exact_and_does_not_touch_backend(tmp_path):
    staging, base = fixture(tmp_path)
    out = review_public_cta_candidate(staging, live_root=base, include_patch=True)
    assert out["schema_version"] == SCHEMA
    assert out["changed_file_count"] == 2
    assert set(x["path"] for x in out["files_proposed"]) == {ENTRY, GUIDE}
    assert out["backend_unchanged_sha256"] == BASE_HASHES[BACKEND]
    assert out["exact_original_baseline_verified"] is True
    assert out["status"] == "EXACT_TWO_FILE_PUBLIC_CTA_CANDIDATE_OWNER_REVIEW_REQUIRED"
    assert out["site_owner_release_authorized"] is False
    assert out["deployment_authorized"] is False
    assert out["gateway_restart_in_scope"] is False
    assert out["new_private_founder_route_in_scope"] is False
    assert out["real_buyer_enquiry_verified"] is False
    assert out["verified_revenue"] is False
    patch = out["source_patch"]
    assert patch.count("--- a/") == patch.count("+++ b/") == 2
    assert "first_party_sales_interest" not in patch
    assert "founder" not in patch.casefold()
    assert "/commercial?entry=" in patch
    assert "ownedRevenueGuideProposalHref" in patch
    assert "return \"/commercial?entry=\"" in patch
    assert not any(line.startswith(("+", "-")) and
                   not line.startswith(("+++", "---")) and
                   "\"/insights/revenue-opportunity-assessment\"" in line
                   for line in patch.splitlines())


def test_generated_patch_applies_to_unmodified_baseline(tmp_path):
    staging, base = fixture(tmp_path)
    patch = review_public_cta_candidate(
        staging, live_root=base, include_patch=True,
    )["source_patch"]
    result = subprocess.run(["git", "apply", "--check", "-"],
                            cwd=base, input=patch, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_baseline_drift_holds_instead_of_overwriting_owner(tmp_path):
    staging, base = fixture(tmp_path)
    node = base / GUIDE
    node.write_bytes(node.read_bytes() + b"// newer owner work\n")
    out = review_public_cta_candidate(staging, live_root=base)
    assert out["status"] == "HELD_PUBLIC_OWNER_BASELINE_OR_PATCH_DRIFT"
    assert "PRODUCTION_SOURCE_DRIFT" in out["reason_code"]
    assert out["files_proposed"] == []


def test_backend_owner_drift_holds_even_though_backend_is_not_in_patch(tmp_path):
    staging, base = fixture(tmp_path)
    node = base / BACKEND
    node.write_bytes(node.read_bytes() + b"# concurrent owner change\n")
    out = review_public_cta_candidate(staging, live_root=base)
    assert "PRODUCTION_SOURCE_DRIFT" in out["reason_code"]
    assert out["web_deployment_executed"] is False


@pytest.mark.parametrize("path", (GUIDE, ENTRY))
def test_staged_file_tamper_fails_closed(tmp_path, path):
    staging, base = fixture(tmp_path)
    node = staging / path
    node.write_bytes(node.read_bytes() + b"\n// unexpected code\n")
    out = review_public_cta_candidate(staging, live_root=base)
    assert out["status"] == "HELD_PUBLIC_OWNER_BASELINE_OR_PATCH_DRIFT"
    assert out["files_proposed"] == []


def test_symlinked_staged_file_holds(tmp_path):
    staging, base = fixture(tmp_path)
    original = staging / GUIDE
    original.unlink()
    original.symlink_to(base / GUIDE)
    out = review_public_cta_candidate(staging, live_root=base)
    assert out["status"] == "HELD_PUBLIC_OWNER_BASELINE_OR_PATCH_DRIFT"


def test_review_cli_only_emits_json_and_patch_no_writes(tmp_path, capsys):
    staging, base = fixture(tmp_path)
    args = ["--read-only", "--repo-root", str(staging),
            "--production-root", str(base)]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["source_patch"] is None
    assert report["changed_file_count"] == 2
    assert main([*args, "--emit-patch"]) == 0
    patch = capsys.readouterr().out
    assert patch.count("--- a/") == 2
    assert report["web_deployment_executed"] is False


def test_owner_release_patch_and_manifest_match_exact_current_review():
    patch_path = ROOT / 'docs/commercial/EMPIRE_PUBLIC_OWNED_GUIDE_CTA_TWO_FILE_20261026.patch'
    manifest_path = ROOT / 'docs/commercial/EMPIRE_PUBLIC_OWNED_GUIDE_CTA_TWO_FILE_20261026.json'
    # This is an exact local release preflight, not a signed permission slip.
    actual = review_public_cta_candidate(ROOT, live_root=Path('/srv/empire_os'), include_patch=True)
    assert actual['status'] == 'EXACT_TWO_FILE_PUBLIC_CTA_CANDIDATE_OWNER_REVIEW_REQUIRED'
    assert patch_path.read_text() == actual['source_patch']
    expected = dict(actual)
    expected['source_patch'] = None
    assert json.loads(manifest_path.read_text()) == expected
