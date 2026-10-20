"""Cinematic source release guard refuses unreviewed page substitutions."""
import hashlib
from pathlib import Path
from scripts.review_flagship_cinematic_source_release_20261020 import (
    APPROVED_HOME_SHA, HOMEPAGE_TOKENS, PROTECTED, SOURCE_IMPORT, review,
)

def write_bytes(root, relative, data):
    dest = root / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def fixtures(tmp_path):
    live, candidate, source = (tmp_path / n for n in ("live","candidate","source"))
    source.mkdir()
    (source/"src/app").mkdir(parents=True)
    (source/"src/app/page.tsx").write_text(SOURCE_IMPORT)
    homepage=b" ".join(HOMEPAGE_TOKENS)
    for path in PROTECTED:
        data=homepage if path=="index.html" else b"independent-approval"
        write_bytes(live,"out/"+path,data)
        write_bytes(candidate,"out/"+path,data)
    return live,candidate,source


def test_candidate_separate_page_difference_holds(tmp_path):
    live,candidate,source=fixtures(tmp_path)
    write_bytes(candidate,"out/roofing.html",b"OVERRIDDEN_CONSENT")
    result=review(candidate,live,source)
    assert "roofing.html" in result["protected_page_differences"]
    assert result["full_site_release_authorized"] is False
    assert result["production_files_modified"] is False


def test_old_source_theme_holds_even_if_build_artwork_good(tmp_path):
    live,candidate,source=fixtures(tmp_path)
    (source/"src/app/page.tsx").write_text("import EmpireWorld from './EmpireWorld';")
    result=review(candidate,live,source)
    assert result["source_imports_cinematic"] is False
    assert result["full_site_release_authorized"] is False


def test_live_homepage_unapproved_hash_stops_promotion(tmp_path):
    live,candidate,source=fixtures(tmp_path)
    assert review(candidate,live,source)["live_approved_cinematic_homepage_verified"] is False
    assert review(candidate,live,source)["full_site_release_authorized"] is False


def test_exact_approved_sha_constant():
    assert len(APPROVED_HOME_SHA)==64
    assert APPROVED_HOME_SHA=="0e63856577b9894ebc62d3715f95cb96e788c4caf9c0e45c382e14bb5cbecf1c"


def test_missing_protected_page_is_not_a_pass(tmp_path):
    live,candidate,source=fixtures(tmp_path)
    (candidate/"out/trust.html").unlink()
    result=review(candidate,live,source)
    assert "trust.html" in result["protected_page_differences"]
    assert result["full_site_release_authorized"] is False
