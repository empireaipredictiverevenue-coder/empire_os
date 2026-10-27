"""No fabricated approvals: original site owner V11 only reads V10 evidence."""
import json
from hashlib import sha256
from pathlib import Path

import pytest

from empire_os.microsite_owner_handoff_v11 import (
    CANDIDATE_ID, PREVIEW_NAME, EXPECTED_BRAND_CONTRACT,
    EXPECTED_OWNER_LOGO, check_original_owner_handoff
)


@pytest.fixture
def private_packet(tmp_path):
    path = tmp_path / "private"
    qa = path / "browser_qa"
    qa.mkdir(parents=True)
    html = ('<html><meta name="robots" content="noindex,nofollow,noarchive">'
            '<style>.research-signal-strip{} .research-visual-grid{}</style>'
            '<img src="data:image/png;base64,AAAA"/>'
            '<div class="research-visual-grid">Original sourced evidence</div></html>')
    (path / PREVIEW_NAME).write_text(html)
    digest = sha256(html.encode()).hexdigest()
    packet = {
        "schema_version": "empire.microsite_factory_draft_batch.v2",
        "published": False, "stage_only": True, "publishable_candidates": 0,
        "held": 1, "candidates_reviewed": 1, "previews": [PREVIEW_NAME],
        "packets": [{
            "id": CANDIDATE_ID, "html_sha256": digest,
            "status": "HOLD_EVIDENCE", "publishing_enabled": False,
            "indexation_enabled": False, "payments_enabled": False,
            "outbound_enabled": False, "linked_official_source_count": 5,
            "locally_useful_research_steps": 5, "copy_audit": {"score": 5},
            "visual_qa": {
                "canonical_brand_reference_used": True,
                "canonical_brand_contract_sha256": EXPECTED_BRAND_CONTRACT,
                "original_brand_logo_sha256": EXPECTED_OWNER_LOGO,
                "brand_public_distribution_approved_by_owner": False,
            }
        }]
    }
    (path / "manifest.json").write_text(json.dumps(packet))
    checks=[]
    for label, width, height in (("desktop",1440,900),("mobile",390,844)):
        shot = qa / (label+".png")
        shot.write_bytes((label + "_screenshot").encode())
        checks.append({
            "viewport": label, "width": width, "height": height, "passed": True,
            "metrics": {"h1":1,"main":1,"forms":0,"logo_loaded":True,
                        "horizontal_overflow": False,
                        "robots":"noindex,nofollow,noarchive"},
            "screenshot": str(shot),
            "screenshot_sha256": sha256(shot.read_bytes()).hexdigest()
        })
    receipt={
        "schema_version": "empire.microsite.browser_review.puppeteer_v1",
        "status":"BROWSER_QA_PASS","input_sha256":digest,
        "private":True,"published":False,"changed_production":False,
        "browser_visual_review_complete":True,"blocked_external_requests":0,
        "script_errors":[],"checks":checks
    }
    (qa/"puppeteer_browser_review.json").write_text(json.dumps(receipt))
    return path


def five_release():
    return {"campaigns": [{"campaign_id":f"campaign_{i:016x}"} for i in range(5)]}


def five_routes():
    return [f"/research/campaign_{i:016x}" for i in range(5)]


def review(path, *, released=five_release, paths=five_routes):
    return check_original_owner_handoff(
        path, original_release_reader=released, original_paths_reader=paths)


def test_v11_succeeds_but_does_not_grant_owner_signoff(private_packet):
    result = review(private_packet)
    assert result["original_browser_qa"] == "PASS"
    assert result["original_five_released_routes_preserved"] is True
    assert result["status"] == "OWNER_SIGNOFF_AND_RELEASE_PENDING"
    assert result["chicago_public_url"] is None
    assert result["brand_public_artwork_distribution_approved"] is False
    assert result["original_website_release_readback"] is False
    assert result["new_site_routes"] == result["production_writes"] == 0


@pytest.mark.parametrize("field,value", [
    ("published", True),("stage_only",False),("held",0),
    ("publishable_candidates",1)
])
def test_v11_rejects_pretended_release(private_packet, field, value):
    m=private_packet/"manifest.json"
    data=json.loads(m.read_text())
    data[field]=value
    m.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="misrepresented"):
        review(private_packet)


def test_v11_rejects_modified_html(private_packet):
    with (private_packet/PREVIEW_NAME).open("a") as f:
        f.write("<p>tampered</p>")
    with pytest.raises(ValueError,match="SHA"):
        review(private_packet)


def test_v11_rejects_browser_digest_forgery(private_packet):
    p=private_packet/"browser_qa/puppeteer_browser_review.json"
    r=json.loads(p.read_text())
    r["input_sha256"]="f"*64
    p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match="Chromium"):
        review(private_packet)


def test_v11_rejects_overwritten_screenshot(private_packet):
    shot=private_packet/"browser_qa/desktop.png"
    shot.write_bytes(b"changed image")
    with pytest.raises(ValueError,match="altered"):
        review(private_packet)


def test_v11_requires_original_five_site_routes(private_packet):
    with pytest.raises(ValueError,match="five"):
        review(private_packet,paths=lambda:five_routes()[:4])


def test_v11_does_not_take_founder_design_approval_for_brand_rights(private_packet):
    p=private_packet/"manifest.json"
    data=json.loads(p.read_text())
    data["packets"][0]["visual_qa"]["brand_public_distribution_approved_by_owner"]=True
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="brand"):
        review(private_packet)


def test_v11_refuses_junction_or_symlinked_draft(private_packet):
    p=private_packet/PREVIEW_NAME
    content=p.read_bytes()
    p.unlink()
    original=private_packet/"source.html"
    original.write_bytes(content)
    p.symlink_to(original)
    with pytest.raises(ValueError,match="symlink"):
        review(private_packet)
