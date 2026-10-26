"""No network or writes: original AEO gate and exact three-page stage."""
import json
from pathlib import Path

from empire_os.aeo_release import load_release
from empire_os.aeo_recovery import build_aeo_recovery_census
from scripts.aeo_metro_gen import generate_page

STAGE=Path("/home/ubuntu/empire_releases/seo_aeo_entry_claim_v2_20261026_stage")
PAIRS={("general_contractor","NYC"),("hvac","DFW"),("roofing","DFW")}

def test_original_publisher_prepared_exact_three_and_preserves_207():
    before=json.loads((STAGE/"old_recovery.json").read_text())
    after=json.loads((STAGE/"new_recovery.json").read_text())
    assert before["asset_count"]==after["asset_count"]==210
    assert before["risk_counts"]==after["risk_counts"]
    old={(v["niche"],v["metro"]):v["content_hash"] for v in before["assets"]}
    new={(v["niche"],v["metro"]):v["content_hash"] for v in after["assets"]}
    assert {p for p in old if old[p]!=new[p]}==PAIRS
    approved=json.loads((STAGE/"new_release.json").read_text())
    assert approved["release_verified"] is True
    assert approved["zero_paid_media"] is True
    assert approved["execution_authority"]=="none"
    assert {(x["niche"],x["metro"]) for x in approved["pages"]}==PAIRS
    assert load_release(
      aeo_root=STAGE/"pages_runtime",
      recovery_path=STAGE/"new_recovery.json",
      release_path=STAGE/"new_release.json")==approved

def test_canonical_generator_same_exact_three_candidate_html():
    for n,m in PAIRS:
        expected=generate_page(n,m).encode()
        old=(STAGE/"old_recovery.json").read_bytes()
        for side in ("pages_source","pages_runtime"):
            assert (STAGE/side/n/m/"index.html").read_bytes()==expected
        assert expected.count(b'href="/commercial?entry=')==1
        assert expected.count(b'#commercial-enquiry')==1

def test_live_or_prepared_release_has_original_validation():
    from scripts.activate_aeo_entry_claim_v2_20261026 import RESULT
    if RESULT.exists():
        receipt=json.loads(RESULT.read_text())
        assert receipt["status"] in {
            "ORIGINAL_THREE_AEO_SOURCE_HINT_RELEASE_LIVE_VERIFIED",
            "ORIGINAL_AEO_ROLLBACK_RESTORED",
        }
    else:
        assert load_release() is not None
