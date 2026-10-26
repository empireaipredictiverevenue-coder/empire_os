from pathlib import Path
from json import loads
from empire_os.aeo_release import load_release

STAGE=Path("/home/ubuntu/empire_releases/seo_aeo_governed_three_cta_20261026_v2")
SCOPE={("general_contractor","NYC"),("hvac","DFW"),("roofing","DFW")}

def test_original_release_builder_validates_three_only_no_new_risks():
    old=loads((STAGE/"old_recovery.json").read_text())
    new=loads((STAGE/"new_recovery.json").read_text())
    assert old["asset_count"]==new["asset_count"]==210
    assert old["risk_counts"]==new["risk_counts"]=={}
    a={(r["niche"],r["metro"]):r["content_hash"] for r in old["assets"]}
    b={(r["niche"],r["metro"]):r["content_hash"] for r in new["assets"]}
    assert {key for key in a if a[key]!=b[key]}==SCOPE
    release=loads((STAGE/"new_release.json").read_text())
    assert len(release["pages"])==3 and release["zero_paid_media"] is True
    assert release["execution_authority"]=="none"
    assert load_release(aeo_root=STAGE/"pages_runtime",
                        recovery_path=STAGE/"new_recovery.json",
                        release_path=STAGE/"new_release.json")==release

def test_privileged_activation_preflight_or_verified_release_is_valid():
    from scripts.activate_original_three_aeo_b2b_links_20261026 import preflight, RESULT
    if RESULT.exists():
        result=loads(RESULT.read_text())
        assert result["status"] in {
            "ORIGINAL_THREE_AEO_B2B_LINKS_GATED_RELEASE_LIVE_VERIFIED",
            "ORIGINAL_AEO_ROLLBACK_RESTORED",
        }
        from empire_os.aeo_release import load_release
        assert load_release() is not None
    else:
        p=preflight()
        assert p["publish_authorized_pages"]==3
        assert p["other_207_content_hashes_unchanged"] is True
        assert p["original_publisher_load_release_verified"] is True

def test_three_candidate_roots_equal_original_generator():
    from scripts.aeo_metro_gen import generate_page
    for niche,metro in SCOPE:
        html=generate_page(niche,metro).encode()
        for folder in ("pages_runtime","pages_source"):
            assert (STAGE/folder/niche/metro/"index.html").read_bytes()==html
        assert html.count(b'href="/commercial"')==1
