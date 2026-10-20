from pathlib import Path

import pytest

from scripts.review_native_buyer_proposal_build_20261020 import review


def fixture(tmp_path):
    root = tmp_path / "source"
    live = tmp_path / "live"
    for name in (
        "src/app/buy/page.tsx",
        "src/app/commercial/page.tsx",
        "src/lib/buyer-proposal-handoff.ts",
    ):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("export const verified = true;")
    js = root / "out/_next/static/chunks/page.js"
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(
        "REQUEST A PROPOSAL INSTEAD;"
        "commercial?product=;"
        "The requested product is not available for a proposal;"
        "/v1/checkout/commercial/offers;"
    )
    for name in ("buy.html", "commercial.html"):
        html = '<html><head><script src="/_next/static/chunks/page.js"></script></head><body>Buyer</body></html>'
        (root / "out" / name).write_text(html)
        live.mkdir(exist_ok=True)
        (live / name).write_text(html)
    return root, live


def test_source_backed_static_candidate_passes_but_never_authorizes_public_release(tmp_path):
    root, live = fixture(tmp_path)
    r = review(project=root, live=live)
    assert r["status"] == "STAGED_SOURCE_BUILD_VERIFIED_OWNER_RELEASE_REVIEW_REQUIRED"
    assert all(r["checks"].values())
    assert all(r["current_live_matches_staged_pages"].values())
    assert r["new_public_release_authorized"] is False
    assert r["existing_13_october_release_manifest_reapproved"] is False
    assert r["payment_execution"] is False
    assert r["form_or_order_submitted"] is False
    assert r["outbound_sent"] is False
    assert len(r["source_sha256"]) == 3


def test_old_live_export_does_not_change_staged_receipt_truth(tmp_path):
    root, live = fixture(tmp_path)
    (live / "buy.html").write_text("<html>unrelated live build</html>")
    result = review(project=root, live=live)
    assert result["status"] == "STAGED_SOURCE_BUILD_VERIFIED_OWNER_RELEASE_REVIEW_REQUIRED"
    assert result["current_live_matches_staged_pages"]["buy.html"] is False
    assert result["new_public_release_authorized"] is False


@pytest.mark.parametrize("tamper", [
    "missing_source", "missing_page", "script_outside_project",
    "script_missing", "external_script", "compiled_handoff_missing",
    "legacy_injected_overlay",
])
def test_untrusted_or_incomplete_build_fails_closed(tmp_path, tamper):
    root, live = fixture(tmp_path)
    source = root / "src/lib/buyer-proposal-handoff.ts"
    page = root / "out/buy.html"
    js = root / "out/_next/static/chunks/page.js"
    if tamper == "missing_source":
        source.unlink()
    if tamper == "missing_page":
        page.unlink()
    if tamper == "script_outside_project":
        js.unlink()
        js.symlink_to(source)
    if tamper == "script_missing":
        js.unlink()
    if tamper == "external_script":
        page.write_text(
            '<script src="https://untrusted.example/checkout.js"></script>'
        )
    if tamper == "compiled_handoff_missing":
        js.write_text("unrelated code")
    if tamper == "legacy_injected_overlay":
        page.write_text(
            '<script src="/_next/static/agency/selected-product-bridge-20261020.js"></script>'
        )
    result = review(project=root, live=live)
    assert result["status"] == "STAGED_BUILD_INTEGRITY_HOLD"
    assert result["new_public_release_authorized"] is False
    assert result["payment_execution"] is False
    assert result["database_writes"] is False
