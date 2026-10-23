"""Motion research must describe real code, avoid redundant installs, and preserve build gates."""
from pathlib import Path
from hashlib import sha256
import gzip
import subprocess

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier'
NOTE=ROOT/'docs/commercial/EMPIRE_CAR_YARD_DEEP_MOTION_ARCHITECTURE_20261022.md'

# Original 2026-10-22 code-review facts describe the pinned historical state,
# before the new on-demand showroom implementation.
def historical(path):
    result = subprocess.run(
        ['git','show','9135648ca0a924bc32aa3722e6177164a9c7bfc2:'+path],
        cwd=ROOT,check=True,capture_output=True)
    return result.stdout
def test_motion_report_matches_historical_eager_threejs_architecture():
    main=historical('prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/src/main.jsx').decode()
    three=historical('prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/src/ShowroomScene.jsx').decode()
    report=NOTE.read_text()
    assert "import ShowroomScene from './ShowroomScene.jsx'" in main
    assert "import { motion, useReducedMotion } from 'motion/react'" in main
    assert "useFrame" in three and 'dpr={[1, 1.6]}' in three
    assert 'ContactShadows' in three and '<Canvas' in three
    assert "IntersectionObserver" not in main
    assert "frameloop=\"demand\"" not in three
    assert "1,275,464 bytes raw" in report
    data=historical('prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/dist/yard.js')
    assert len(data)==1275464
    assert len(gzip.compress(data,mtime=0))>350000
    assert "364,276 bytes gzip" in report

def test_research_selects_existing_motion_first_and_preserves_production():
    report=NOTE.read_text()
    for value in ['motiondivision/motion', 'ibelick/motion-primitives',
        'darkroomengineering/lenis','greensock/GSAP', '14islands/r3f-scroll-rig',
        'pmndrs/react-spring', 'theatre-js/theatre']:
        assert 'github.com/'+value in report, value
    assert 'MIT' in report
    assert 'ISC' in report
    assert 'AGPL-3.0' in report
    assert 'standard no-charge licence' in report
    assert 'no handwritten CSS' in report
    assert 'no public booking' in report.lower()
    assert 'No new animation packages' in report
    assert "code-split real 3d" in report.lower()

def test_existing_demo_plugin_and_theme_not_modified_by_research():
    plugin=(ROOT/'prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/empire-car-yard.php').read_text()
    assert 'Version: 0.3.0' in plugin
    assert "Booking persistence is dormant" in plugin
    assert "register_rest_route" not in plugin
    css=(THEME/'style.css').read_text()
    assert 'Template: empire-local-services' in css
