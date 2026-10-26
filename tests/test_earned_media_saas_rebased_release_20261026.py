"""ASTRA SaaS CTA: offline full-site union, isolated hydration and owner scope."""
from __future__ import annotations

import copy
from pathlib import Path
import json

import pytest

from empire_os.earned_media_saas_rebased_release import (
    CURRENT_LIVE_COUNT, LIVE_DRIFT, REPLACE, LINK, OLD_LINK, ReleaseHeld,
    read_index, index_digest, route_static_references, plan_rebased_delta,
    validate_inputs, prepare_private_candidate,
)
from scripts.prepare_earned_media_saas_rebased_union_20261026 import (
    LIVE, PIN, ORIGINAL_PREVIEW, REBUILD, OUTPUT, RECEIPT, audit,
)

ROOT = Path(__file__).resolve().parents[1]


def _built():
    live = read_index(LIVE)
    built = read_index(REBUILD)
    html = (REBUILD / "predictive-revenue.html").read_text()
    rsc = (REBUILD / "predictive-revenue.txt").read_text()
    refs = route_static_references(html, rsc)
    js = {p:(REBUILD / p).read_bytes()
          for p in refs if "/app/predictive-revenue/page-" in p}
    return live, built, html, rsc, js


def test_rebased_candidate_preserves_the_newer_live_pages():
    live = read_index(LIVE)
    stage = read_index(OUTPUT)
    assert len(live) == 662
    assert len(stage) == 670
    assert {k for k in live if live[k] != stage[k]} == REPLACE
    assert set(stage) - set(live) == set(
        json.loads(RECEIPT.read_text())["build"]["new_asset_paths"])
    assert len(set(stage) - set(live)) == 8
    assert all(k.startswith("_next/static/") for k in set(stage) - set(live))
    assert all(stage[k] == live[k] for k in LIVE_DRIFT)
    assert stage["commercial.html"] == live["commercial.html"]
    assert stage["commercial.txt"] == live["commercial.txt"]


def test_staged_client_js_and_html_agree_after_hydration():
    live, built, html, rsc, js = _built()
    plan, additions = plan_rebased_delta(live, built, html, rsc, js)
    assert len(additions) == 8
    assert plan["html_new_cta_count"] == 1
    assert plan["client_hydration_new_cta_count"] == 1
    assert html.count(LINK) == 1
    assert OLD_LINK not in html
    assert (OUTPUT / "predictive-revenue.html").read_text() == html
    assert (OUTPUT / "predictive-revenue.txt").read_text() == rsc
    page = OUTPUT / plan["original_build_chunk"]
    assert b'"/commercial?entry="+encodeURIComponent("/predictive-revenue")' in page.read_bytes()
    assert b"/commercial#commercial-enquiry" not in page.read_bytes()


def test_tampered_html_or_broken_hydration_holds():
    live, built, html, rsc, js = _built()
    with pytest.raises(ReleaseHeld, match="BUILT_SAAS_HTML"):
        plan_rebased_delta(live, built, html.replace(LINK, OLD_LINK), rsc, js)
    altered = dict(js)
    k = next(iter(altered))
    altered[k] = altered[k].replace(
        b'"/commercial?entry="+encodeURIComponent("/predictive-revenue")',
        b'"/commercial#commercial-enquiry"+encodeURIComponent("/predictive-revenue")')
    with pytest.raises(ReleaseHeld, match="CLIENT_HYDRATION"):
        plan_rebased_delta(live, built, html, rsc, altered)


def test_missing_or_colliding_static_asset_holds():
    live, built, html, rsc, js = _built()
    refs = route_static_references(html, rsc)
    new_asset = next(x for x in refs if x not in live)
    missing = dict(built)
    del missing[new_asset]
    with pytest.raises(ReleaseHeld, match="REFERENCED_STATIC_ASSET_MISSING"):
        plan_rebased_delta(live, missing, html, rsc, js)
    collide = dict(live)
    collide[new_asset] = "f"*64
    with pytest.raises(ReleaseHeld, match="COLLIDES"):
        plan_rebased_delta(collide, built, html, rsc, js)


def test_unexpected_new_live_page_drift_holds():
    live = read_index(LIVE)
    pinned = json.loads(PIN.read_text())["private_candidate_sha256"]
    built = read_index(REBUILD)
    preview = read_index(ORIGINAL_PREVIEW)
    ok = validate_inputs(live, pinned, built, preview)
    assert len(ok["historical_pin_mismatched_owner_pages"]) == 5
    assert set(ok["historical_pin_mismatched_owner_pages"]) == LIVE_DRIFT
    changed = dict(live)
    changed["index.html"] = "0"*64
    with pytest.raises(ReleaseHeld, match="CONCURRENT_OWNER_PAGE_DRIFT"):
        validate_inputs(changed, pinned, built, preview)


def test_unreviewed_rebase_never_pretends_to_be_published():
    result = audit()
    assert result["status"] == (
        "OFFLINE_ASTRA_REBASED_CANDIDATE_INTEGRITY_PASS_RELEASE_HELD")
    assert result["source_live_file_count"] == 662
    assert result["rebased_candidate_file_count"] == 670
    assert result["public_release_authorized"] is False
    assert result["published_html_changed"] is False
    assert result["browser_qa_independently_verified"] is False
    assert result["real_buyer_enquiry_verified"] is False
    assert result["revenue_verified"] is False
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["production_publication_authorized"] is False
    assert receipt["new_founder_approval_verified"] is False
    assert receipt["independent_astra_website_owner_approval_verified"] is False
    assert receipt["production_mutated"] is False
    assert receipt["outbound_sent"] is False
    assert receipt["money_moved"] is False


def test_existing_output_cannot_be_silently_overwritten():
    with pytest.raises(ReleaseHeld, match="DESTINATION_ALREADY_EXISTS"):
        prepare_private_candidate(
            live_root=LIVE, prior_pin=PIN, prior_preview=ORIGINAL_PREVIEW,
            rebuilt_root=REBUILD, output_root=OUTPUT)


def test_path_traversal_or_untrusted_asset_references_hold():
    with pytest.raises(ReleaseHeld, match="ASSET_REFERENCE_UNSAFE"):
        route_static_references(
            '<script src="/_next/static/../../evil.js"></script>',
            "static/chunks/app/predictive-revenue/page-abc123.js",
        )


def test_generated_candidate_inventory_checksum_is_stable():
    receipt = json.loads(RECEIPT.read_text())
    assert index_digest(read_index(LIVE)) == receipt["source_live_inventory_sha256"]
    assert index_digest(read_index(OUTPUT)) == receipt["rebased_candidate_inventory_sha256"]
    assert len(set(read_index(OUTPUT))) == receipt["rebased_candidate_file_count"]
