"""Evidence-only upstream design research, without runtime or production changes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
REVIEW = ROOT / "docs/commercial/EMPIRE_CAR_YARD_OPEN_SOURCE_DESIGN_REVIEW_20261022.md"

def test_claude_design_brand_and_plan_in_repo():
    design = (THEME / "DESIGN_SYSTEM.md").read_text()
    plan = (THEME / "DESIGN_PLAN.md").read_text()
    assert "Claude Design-inspired Step 0" in design
    assert "not customer-approved" in design
    assert "no invented social proof" in design
    assert "Tailwind" in design and "prefers-reduced-motion" in design
    assert "31/31" in plan and "Lighthouse" in plan
    assert "no-handwritten-CSS" in plan
    assert "not a client acceptance" in plan.lower()

def test_source_licences_and_no_unreviewed_installer():
    doc = REVIEW.read_text()
    for repo in ("chinazane/claude-design", "pbakaus/impeccable",
                 "magicuidesign/magicui", "ibelick/motion-primitives",
                 "shadcn-ui/ui", "dequelabs/axe-core",
                 "GoogleChrome/lighthouse", "DavidHDev/react-bits",
                 "theatre-js/theatre"):
        assert "https://github.com/" + repo in doc, repo
    assert "MIT + Commons Clause" in doc
    assert "Studio AGPL-3.0" in doc
    assert "MPL-2.0" in doc
    assert "not an installed skill" in doc
    assert "no handwritten css" in doc.lower()
    assert "No customer identity/brand/claims" in doc
    assert "no production write" in doc.lower()

def test_existing_wordpress_runtime_protected():
    import json
    import re
    plugin = ROOT / "prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/empire-car-yard.php"
    assert "Version: 0.3.0" in plugin.read_text()
    css = (THEME / "style.css").read_text()
    assert re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL).strip() == ""
    manifest = json.loads((ROOT / "docs/commercial/EMPIRE_CAR_YARD_REACT_THREE_DESIGN_V2_ACCEPTANCE_20261022.json").read_text())
    assert manifest["browser_check_count"] == 31
    assert manifest["production_changes"] is False
