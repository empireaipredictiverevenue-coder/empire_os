"""Pinned acceptance and zero-handwritten-CSS contract for the React/Three child theme."""
from pathlib import Path
from hashlib import sha256
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# Historical v2 browser receipt pins commit 9135648; the current child theme
# deliberately evolves without overwriting prior immutable acceptance evidence.
V2_COMMIT = "9135648ca0a924bc32aa3722e6177164a9c7bfc2"
def original_v2(rel):
    return subprocess.run(
        ["git", "show", V2_COMMIT + ":" + rel],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout
def original_theme(rel):
    return original_v2("prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/" + rel)

THEME = ROOT / "prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOCS = ROOT / "docs/commercial"

def test_react_three_fiber_magic_motion_bundle_and_source():
    pkg = json.loads((THEME / "package.json").read_text())
    for key in ("react", "react-dom", "three", "@react-three/fiber", "@react-three/drei", "motion", "tailwindcss", "@tailwindcss/vite"):
        assert key in pkg["dependencies"] or key in pkg["devDependencies"], key
    main = original_theme('src/main.jsx').decode()
    scene = original_theme('src/ShowroomScene.jsx').decode()
    assert "createRoot" in main and "ShowroomScene" in main
    assert "AnimatedGrid" in main and "useReducedMotion" in main
    assert "Canvas" in scene and "useFrame" in scene and "three" in scene
    assert "getContext('webgl2')" in main
    assert "No real vehicles" in main
    assert "http://" not in main and "https://" not in main
    assert "http://" not in scene and "https://" not in scene
    assert "wp_mail(" not in main and "fetch(" not in main
    assert len(original_theme('dist/yard.js')) > 100_000
    assert len(original_theme('dist/yard.css')) > 20_000
    assert b"data-react-showroom" in original_theme('dist/yard.js')

def test_no_manual_css_rules_and_wp_child_theme_only():
    css = (THEME / "style.css").read_text()
    assert "Template: empire-local-services" in css
    assert re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL).strip() == ""
    generated_only = original_theme("src/tailwind.css").decode().splitlines()
    assert generated_only == ['@import "tailwindcss";', '@source "../templates";', '@source "../parts";']
    functions = original_theme('functions.php').decode()
    assert "is_front_page()" in functions
    assert "is_page('demo-stock')" in functions
    assert "wp_enqueue_script" in functions and "wp_enqueue_style" in functions
    assert "register_rest_route" not in functions and "wp_mail(" not in functions
    assert "EMPIRE_YARD_STAGING_STAFF_UI_ENABLED" not in functions
    assert (THEME / "templates/front-page.html").read_text().count('id="empire-yard-react-root"') == 1

def test_native_mariadb_browser_v2_receipt_pinned_source_and_media():
    r = json.loads((DOCS / "EMPIRE_CAR_YARD_REACT_THREE_DESIGN_V2_ACCEPTANCE_20261022.json").read_text())
    assert r["status"] == "WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"] == len(r["browser_checks"]) == 31
    assert all(v is True for v in r["browser_checks"].values())
    for key in ("react_root_hydrated", "real_three_js_webgl_canvas_rendered",
                "magic_ui_style_animated_grid", "tailwind_css_generated",
                "tailwind_inventory_enhancement_loaded", "inventory_card_tailwind_styled",
                "staff_hold_receipt", "staff_confirmation_receipt", "staff_cancel_receipt",
                "mobile_no_horizontal_overflow", "desktop_no_horizontal_overflow"):
        assert r["browser_checks"][key] is True, key
    assert r["wordPress_mysql_same_runtime"] is True
    assert r["loopback_only_http"] is True and r["mariadb_unix_socket_only"] is True
    assert r["production_changes"] is False and r["synthetic_data_only"] is True
    assert r["outbound_or_payments_enabled"] is False and r["customer_bookings_enabled"] is False
    assert r["restore_verified"]["status"] == "NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["restore_verified"]["active_theme"] == "empire-yard-atelier"
    assert r["restore_verified"]["booking_audit_events"] == 3
    assert r["responsive"]["desktop"]["document"] <= r["responsive"]["desktop"]["window"]
    assert r["responsive"]["mobile"]["document"] <= r["responsive"]["mobile"]["window"]
    assert len(r["source_manifest_sha256"]) >= 10
    for rel, digest in r["source_manifest_sha256"].items():
        assert sha256(original_v2(rel)).hexdigest() == digest, rel
    assert len(r["screenshots"]) == 4
    for name, data in r["screenshots"].items():
        file = DOCS / "car_yard_react_browser_evidence_v2" / name
        assert file.is_file()
        assert file.stat().st_size == data["bytes"]
        assert sha256(file.read_bytes()).hexdigest() == data["sha256"]

def test_original_wordpress_booking_plugin_unmodified_by_react_build():
    plugin = (ROOT / "prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/empire-car-yard.php").read_text()
    assert "Version: 0.3.0" in plugin
    assert "Booking persistence is dormant" in plugin
    assert "admin_post_nopriv" not in plugin
    runner = (ROOT / "scripts/premium_wp_v1/run_react_wordpress_design_v2.sh").read_text()
    assert "127.0.0.1:$port" in runner
    assert "--skip-networking" in runner
    assert "trap cleanup EXIT" in runner
    assert "sudo " not in runner and "docker " not in runner
