from pathlib import Path
import hashlib
import json

from empire_os.aeo_release import build_release_manifest, load_release, released_file, released_paths


def fixture(tmp_path: Path):
    aeo = tmp_path / "aeo"
    recovery = tmp_path / "recovery.json"
    release = tmp_path / "release.json"
    rows = []
    for niche, metro in (("roofing","DFW"),("hvac","DFW"),("general_contractor","NYC")):
        page = aeo / niche / metro / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(f"<html><title>{niche}</title><h1>{metro}</h1></html>")
        rows.append({
            "niche": niche, "metro": metro,
            "path": f"{niche}/{metro}/index.html",
            "content_hash": hashlib.sha256(page.read_bytes()).hexdigest(),
            "status": "structure_ready_for_evidence_review",
            "risk_flags": [],
            "title_present": True, "h1_present": True,
            "canonical_present": True, "json_ld_present": True,
            "meta_description_present": True,
        })
    recovery.write_text(json.dumps({"assets": rows}))
    return aeo, recovery, release


def test_bounded_release_is_exact_and_zero_paid(tmp_path: Path):
    aeo,recovery,release=fixture(tmp_path)
    manifest=build_release_manifest(
        [("roofing","DFW"),("hvac","DFW")],
        aeo_root=aeo,recovery_path=recovery,evidence_refs=["founder:approved"]
    )
    assert manifest["zero_paid_media"] is True
    assert len(manifest["pages"]) == 2
    release.write_text(json.dumps(manifest))
    loaded=load_release(aeo_root=aeo,recovery_path=recovery,release_path=release)
    assert loaded is not None
    assert released_paths(aeo_root=aeo,recovery_path=recovery,release_path=release) == [
        "/aeo/roofing/DFW/","/aeo/hvac/DFW/"
    ]
    assert released_file("general_contractor","NYC",aeo_root=aeo,recovery_path=recovery,release_path=release) is None


def test_release_fails_closed_on_hash_or_risk_change(tmp_path: Path):
    aeo,recovery,release=fixture(tmp_path)
    manifest=build_release_manifest(
        [("roofing","DFW")],
        aeo_root=aeo,recovery_path=recovery,evidence_refs=["live:test"]
    )
    release.write_text(json.dumps(manifest))
    (aeo/"roofing/DFW/index.html").write_text("changed")
    assert load_release(aeo_root=aeo,recovery_path=recovery,release_path=release) is None
