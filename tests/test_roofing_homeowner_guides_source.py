"""Source-only SEO release checks: these guides are not approved for live indexation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "apps" / "empire-public-site" / "src"
SHARED = SITE / "components" / "RoofingHomeownerGuide.tsx"
SLUGS = ("replacement-vs-repair", "installation-checklist")


def test_both_homeowner_guides_exist_and_have_distinct_metadata():
    titles = set()
    for slug in SLUGS:
        source = (SITE / "app" / "roofing" / slug / "page.tsx").read_text()
        assert f'/roofing/{slug}' in source
        assert "robots: { index: false, follow: false }" in source
        assert '<RoofingHomeownerGuide' in source
        assert "tel:" not in source and "TRACKING_NUMBER" not in source
        title_line = next(line.strip() for line in source.splitlines() if line.strip().startswith("title: "))
        assert title_line not in titles
        titles.add(title_line)


def test_homeowner_guides_offer_real_information_not_unverified_routing():
    shared = SHARED.read_text()
    assert 'href="/roofing"' in shared
    assert 'href="/privacy"' in shared
    assert 'href="/terms"' in shared
    assert "No live call service" in shared
    assert "tel:" not in shared and "TRACKING_NUMBER" not in shared
    assert "contractor availability" in shared.lower()

    repair = (SITE / "app" / "roofing" / SLUGS[0] / "page.tsx").read_text()
    install = (SITE / "app" / "roofing" / SLUGS[1] / "page.tsx").read_text()
    assert "Do not climb onto a damaged or wet roof" in repair
    assert "itemised" in repair.lower()
    assert "licence or registration" in install
    assert "change order" in install.lower()
    assert '/roofing/installation-checklist' in repair
    assert '/roofing/replacement-vs-repair' in install
