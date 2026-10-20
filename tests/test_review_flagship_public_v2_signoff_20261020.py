"""Static website V2 release review cannot self-authorize a publication."""
import json
from pathlib import Path
import pytest
from scripts import review_flagship_public_v2_signoff_20261020 as v2
from scripts.review_flagship_full_export_union_20261020 import ReleaseHold


def sample():
    names = ["cinematic-home", "new-buyer-checkout", "new-commercial-enquiry",
             "preserved-about", "preserved-insight", "new-roofing-guide"]
    routes = [
        {"route": n, "width": width, "passed": True}
        for width in (390,1440) for n in names
    ]
    nav = [
        {"from": src, "to": dst, "width": width, "passed": True}
        for width in (390,1440)
        for src, dst in (("/buy", "/commercial"), ("/about", "/buy"))
    ]
    return {
        "schema_version": "empire.website.flagship_checkout_union_browser.v1",
        "status": "PRIVATE_UNION_BROWSER_TECHNICAL_PASS",
        "routes": routes, "navigation": nav,
        "read_only_existing_public_api_gets": [
            {"route": "/v1/checkout/catalog", "valid": True}
            for _ in range(6)],
        "missing_local_assets": [], "browser_page_errors": [],
        "external_requests_blocked": 0, "non_get_requests_blocked": 0,
        "checkout_posts_submitted": 0,
        "release_approved": False, "public_site_modified": False,
        "payment_execution": False,
    }


def test_independently_verified_browser_contract_is_still_not_release_approval(tmp_path):
    p = tmp_path / "private.json"
    p.write_text(json.dumps(sample()))
    result = v2._browser_evidence(p)
    assert len(result["routes"]) == 12
    assert result["release_approved"] is False


@pytest.mark.parametrize("key,violation", [
    ("status", "PUBLIC_RELEASED"),
    ("release_approved", True),
    ("payment_execution", True),
    ("checkout_posts_submitted", 1),
    ("missing_local_assets", ["/critical.js"]),
    ("browser_page_errors", [{"message":"crash"}]),
    ("non_get_requests_blocked", 1),
    ("external_requests_blocked", 2),
    ("routes", []),
    ("navigation", []),
    ("read_only_existing_public_api_gets", []),
])
def test_browser_forged_release_or_missing_proof_stays_held(tmp_path, key, violation):
    p = tmp_path / "private.json"
    original = sample()
    original[key] = violation
    p.write_text(json.dumps(original))
    with pytest.raises(ReleaseHold, match="BROWSER_PROOF_UNVERIFIED"):
        v2._browser_evidence(p)


def test_public_review_packet_cannot_be_used_as_website_signoff(tmp_path):
    x = sample()
    assert x["release_approved"] is False
    from scripts.review_flagship_public_v2_signoff_20261020 import SCHEMA
    assert SCHEMA.endswith(".v2")
    assert "founder" in v2.review.__doc__ if v2.review.__doc__ else True


def test_malformed_or_symlinked_input_refused(tmp_path):
    a=tmp_path/"too_large.json"
    a.write_bytes(b"x"*200_001)
    with pytest.raises(ReleaseHold):
        v2._load_bounded_json(a)
    b=tmp_path/"link.json"
    b.symlink_to(a)
    with pytest.raises(ReleaseHold):
        v2._load_bounded_json(b)
