"""Founder-approved V2 site cannot accidentally lift buyer call safeguards."""
from pathlib import Path
import json

from empire_os import lead_smart_v2_landing_compatibility as v2
from scripts import materialize_lead_smart_launch_readiness as ready


ROOT = Path("/srv/empire_os")


def test_v2_reviewer_reports_exact_semantic_proof_under_root_receipt():
    # The root publication receipt is 0600, so only a root operator has
    # authority to run the complete original evidence review. Unit tests
    # examine the DOM and published pins independently.
    old = v2.ConsumerDOM.of(v2.REVIEWED_ROOFING.read_bytes())
    new = v2.ConsumerDOM.of((v2.SITE / "roofing.html").read_bytes())
    assert v2.sha(v2.REVIEWED_ROOFING) == v2.REVIEWED_HTML_SHA
    assert v2.sha(v2.SITE / "roofing.html") == v2.V2_HTML_SHA
    assert old.equivalent(new)
    assert not any(str(x[0]).startswith("tel:") for x in new.anchors)


def test_editing_buyer_text_is_never_equivalent():
    raw = v2.REVIEWED_ROOFING.read_bytes()
    altered = raw.replace(b"Planning a roof replacement or installation?",
                          b"Guaranteed instant roofing leads")
    assert altered != raw
    old, modified = v2.ConsumerDOM.of(raw), v2.ConsumerDOM.of(altered)
    assert not old.equivalent(modified)


def test_raw_live_layout_change_without_attestation_is_held(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    site = tmp_path / "site"
    original_source = ROOT / "templates/lead_smart/roofing/page.tsx"
    active_source = ROOT / "apps/empire-public-site/src/app/roofing/page.tsx"
    for rel, src in (
        ("templates/lead_smart/roofing/page.tsx", original_source),
        ("apps/empire-public-site/src/app/roofing/page.tsx", active_source),
    ):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    site.mkdir()
    (site / "roofing.html").write_bytes((v2.SITE / "roofing.html").read_bytes())
    report = {"approved": True,
              "source_ref": "gmail:1a12bc009d04fcc9",
              "reviewed_source_sha256": v2.FROZEN_APPROVED_SOURCE_SHA}
    monkeypatch.setattr(v2, "accept_installed_attestation", lambda: False)
    assert ready.approved_candidate_matches(report, root=root)
    assert not ready.approved_live_publication(report, repo_root=root, site_root=site)
    monkeypatch.setattr(v2, "accept_installed_attestation", lambda: True)
    assert ready.approved_live_publication(report, repo_root=root, site_root=site)
    (site / "roofing.html").write_bytes(b"changed-unreviewed-html")
    assert not ready.approved_live_publication(report, repo_root=root, site_root=site)


def test_malformed_local_marker_not_trusted(tmp_path):
    p = tmp_path / "spoof.json"
    p.write_text(json.dumps({"status":"EXACT_FOUNDER_V2_WITH_REVIEWED_CONSUMER_CONTENT"}))
    assert not v2.accept_installed_attestation(p)


def test_current_review_without_root_receipt_is_not_falsely_approved():
    result = v2.review(receipt=Path("/path/absent/buyer-receipt.json"))
    assert result["all_compatibility_checks_passed"] is False
    assert result["call_activation_authorized"] is False
    assert result["legal_compliance_certified"] is False
    assert result["revenue_verified"] is False
