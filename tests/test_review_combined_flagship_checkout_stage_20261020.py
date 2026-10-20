"""Offline stage receipt checks; never publish, submit checkout, or repin."""
from pathlib import Path
import json

import pytest

from scripts.review_combined_flagship_checkout_stage_20261020 import (
    MANIFEST, PAGES, SOURCES, manifest_for_stage, verify,
)


def create_fixture(tmp_path):
    root = tmp_path / "apps/empire-public-site"
    for rel in SOURCES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("reviewed_source_bytes")
    out = root / "out"
    chunk = out / "_next/static/chunks/entry.js"
    chunk.parent.mkdir(parents=True)
    chunk.write_text(
        "REQUEST A PROPOSAL INSTEAD /commercial?product= "
        "The requested product is not available for a proposal "
        "/v1/checkout/commercial/offers"
    )
    for number in range(5):
        (chunk.parent / f"other{number}.js").write_text(f"reviewed static {number}")
    refs = "".join(
        f'<script src="/_next/static/chunks/{file.name}"></script>'
        for file in chunk.parent.glob("*.js")
    )
    for name in PAGES:
        (out / name).write_text(
            "<!DOCTYPE html><html><head>" + refs +
            "</head><body><main>EmpireOS Intelligence Infrastructure"
            "</main></body></html>"
        )
    manifest = manifest_for_stage(project=root)
    pin = tmp_path / "manifest.json"
    pin.write_text(json.dumps(manifest))
    return root, pin


def test_exact_build_hash_verified_no_rebaseline(tmp_path):
    project, pin = create_fixture(tmp_path)
    report = verify(project=project, pinned=pin)
    assert report["status"] == "COMBINED_STAGED_BUILD_HASH_VERIFIED"
    assert report["source_and_build_match_original_pins"] is True
    assert report["new_public_release_authorized"] is False
    assert report["buyer_order_or_email_submitted"] is False
    assert report["payment_execution"] is False


@pytest.mark.parametrize("change", ["source", "html", "asset", "manifest"])
def test_stage_tampering_denied(tmp_path, change):
    project, pin = create_fixture(tmp_path)
    if change == "source":
        (project / SOURCES[0]).write_text("later_modified_source")
    elif change == "html":
        (project / "out/index.html").write_text("<html>unreviewed homepage</html>")
    elif change == "asset":
        (project / "out/_next/static/chunks/entry.js").write_text("unreviewed script")
    elif change == "manifest":
        pin.write_text('{"schema_version":"tampered"}')
    report = verify(project=project, pinned=pin)
    assert report["status"] == "COMBINED_STAGED_BUILD_INTEGRITY_HOLD"
    assert report["source_and_build_match_original_pins"] is False
    assert report["new_public_release_authorized"] is False


def test_unknown_external_script_blocked(tmp_path):
    project, pin = create_fixture(tmp_path)
    path = project / "out/buy.html"
    path.write_text(path.read_text().replace(
        "</head>", '<script src="https://unknown.example/script.js"></script></head>'
    ))
    assert verify(project=project, pinned=pin)["source_and_build_match_original_pins"] is False


def test_symlinked_asset_and_path_escape_denied(tmp_path):
    project, pin = create_fixture(tmp_path)
    path = project / "out/_next/static/chunks/entry.js"
    path.unlink()
    path.symlink_to(tmp_path / "outside.js")
    assert verify(project=project, pinned=pin)["status"] == "COMBINED_STAGED_BUILD_INTEGRITY_HOLD"


def test_original_owner_manifest_is_separate_from_new_candidate():
    assert "FLAGSHIP_CHECKOUT_COMBINED_STAGE_20261020.json" in str(MANIFEST)
    assert "DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST" not in str(MANIFEST)
