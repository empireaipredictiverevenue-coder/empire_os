from pathlib import Path
import shutil
from empire_os.website_designos_roofing_guard import (
    FROZEN_ROOFING_RELEASE_DIGESTS, FROZEN_ROOFING_DESIGN_STATE,
    current_roofing_export_frozen, frozen_roofing_page_body,
)

SOURCE = Path("/srv/empire_os/apps/empire-public-site/out")

def copied(root):
    for name in FROZEN_ROOFING_RELEASE_DIGESTS:
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, dest)

def test_legacy_frozen_does_not_mean_design_approved(tmp_path):
    assert FROZEN_ROOFING_DESIGN_STATE == "LEGACY_LIVE_VISUALLY_REJECTED"
    copied(tmp_path)
    assert current_roofing_export_frozen(tmp_path)
    assert frozen_roofing_page_body(tmp_path) == (SOURCE / "roofing.html").read_bytes()

def test_modified_html_refused(tmp_path):
    copied(tmp_path)
    page = tmp_path / "roofing.html"
    page.write_bytes(page.read_bytes() + b" ")
    assert not current_roofing_export_frozen(tmp_path)

def test_modified_rsc_refused(tmp_path):
    copied(tmp_path)
    p = tmp_path / "roofing.txt"
    p.write_bytes(p.read_bytes() + b" ")
    assert not current_roofing_export_frozen(tmp_path)

def test_modified_browser_js_refused(tmp_path):
    copied(tmp_path)
    name = next(n for n in FROZEN_ROOFING_RELEASE_DIGESTS
                if n.startswith("_next/static/chunks/app/roofing/"))
    p = tmp_path / name
    p.write_bytes(p.read_bytes() + b" ")
    assert not current_roofing_export_frozen(tmp_path)

def test_missing_and_symlink_refused(tmp_path):
    copied(tmp_path)
    p = tmp_path / "roofing.txt"
    p.unlink()
    assert not current_roofing_export_frozen(tmp_path)
    p.symlink_to(SOURCE / "roofing.txt")
    assert not current_roofing_export_frozen(tmp_path)

def test_fake_founder_approval_json_does_not_override(tmp_path):
    copied(tmp_path)
    (tmp_path / "founder_approved.json").write_text('{"approved":true}')
    (tmp_path / "roofing.html").write_text("<html>fake replacement</html>")
    assert not current_roofing_export_frozen(tmp_path)
