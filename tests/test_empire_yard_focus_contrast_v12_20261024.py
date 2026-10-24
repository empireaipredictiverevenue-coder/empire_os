"""V12: native mobile keyboard nav, responsive layouts, manual axe contrast evidence."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOC=ROOT/"docs/commercial"
RECEIPT=DOC/"EMPIRE_CAR_YARD_FOCUS_CONTRAST_V12_BROWSER_ACCEPTANCE_20261024.json"

def load():
    return json.loads(RECEIPT.read_text())

def test_real_wordpress_navigation_and_responsive_acceptance():
    r=load()
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==125
    assert all(r["browser_checks"].values())
    for check in (
        "v12_incomplete_contrast_nodes_are_not_auto_approved",
        "v12_keyboard_mobile_menu_open_by_space",
        "v12_mobile_menu_first_link_reachable_by_tab",
        "v12_escape_collapses_mobile_menu_and_restores_focus",
        "v12_keyboard_nav_activates_collection_and_closes_menu",
        "v12_mobile_keyboard_nav_no_outbound",
        "v12_real_chromium_responsive_viewport_sweep",
        "v12_enlarged_root_text_reflow_no_horizontal_scroll",
        "v12_enlarged_text_editorial_photographs_loaded",
        "v12_responsive_sweep_external_requests_blocked",
        "v11_real_browser_webgl_loss_extension_invoked",
        "v11_webgl_context_loss_switches_to_static_preview",
        "v10_real_glb_failure_recovers_original_concept",
        "v10_axe_wcag_no_automated_violations",
        "v9_meshopt_optimized_glb_only_loads_after_explicit_opt_in",
        "v8_data_saver_requires_second_confirmation",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt",
    ):
        assert r["browser_checks"][check] is True,check
    assert r["mobile_nav_external_blocked"] is True
    assert r["restore_verified"]["booking_audit_events"]==3
    assert r["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["production_changes"] is False
    assert r["synthetic_data_only"] is True
    assert r["customer_bookings_enabled"] is False
    assert r["outbound_or_payments_enabled"] is False

def test_responsive_real_css_viewports_and_separate_root_text_scaling():
    r=load()
    widths=[item["viewport_css_px"] for item in r["responsive_viewport_sweep"]]
    assert widths==[320,360,390,640,768,1024]
    for item in r["responsive_viewport_sweep"]:
        assert item["no_horizontal_scroll"]
        assert item["has_main"]
        assert item["auto_glb_fetched"] is False
    increased=r["enlarged_root_text"]
    assert increased["root_font_size"]=="32px"
    assert increased["requested_size_px"]==32
    assert increased["viewport_css_px"]==390
    assert increased["no_horizontal_scroll"] is True
    assert increased["skip_focus_visible"] is True
    assert increased["no_auto_glb_fetched"] is True
    assert "not browser zoom" in increased["method"]

def test_manual_axe_contrast_details_remain_explicitly_unapproved():
    axe=load()["axe_wcag_audit"]
    assert axe["engine"]=="axe-core 4.10.3"
    assert axe["automated_only"] is True
    assert axe["violations"]==[]
    assert axe["incomplete"] != []
    records=axe["manual_contrast_review"]
    assert len(records)>=20
    assert any(x["id"]=="color-contrast" for x in axe["incomplete"])
    assert all(item["clearance"]=="MANUAL_REVIEW_NOT_GRANTED" for item in records)
    assert all(item["target"] and item["ancestor_layers"] and item["box"] for item in records)
    assert all(len(item["ancestor_layers"])<=5 for item in records)

def test_source_sha_screenshots_zip_provenance_immutable():
    r=load()
    assert len(r["source_manifest_sha256"])>=26
    for relative, digest in r["source_manifest_sha256"].items():
        assert sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
    assert len(r["screenshots"])==8
    for name,details in r["screenshots"].items():
        p=DOC/"car_yard_react_browser_evidence_v12"/name
        assert p.is_file() and p.stat().st_size==details["bytes"]
        assert sha256(p.read_bytes()).hexdigest()==details["sha256"],name
    p=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-focus-v12-preview.zip"
    assert p.exists()
    with ZipFile(p) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert all(name.startswith("empire-yard-atelier/") for name in names)
        assert "empire-yard-atelier/assets/models/car-concept-studio-meshopt.glb" in names
        assert not any("axe-core" in name or "node_modules" in name or ".env" in name for name in names)

def test_accessible_native_menu_without_duplicate_platform_or_css():
    main=(THEME/"src/main.jsx").read_text()
    assert 'aria-controls="agency-navigation-links"' in main
    assert 'id="agency-navigation-links"' in main
    assert "mobileMenuTrigger.current?.focus()" in main
    assert "event.key === 'Escape'" in main
    assert "onClick={closeMobileMenu}" in main
    assert 'aria-expanded={menu}' in main
    assert "focus-visible:outline-" in main
    assert "min-h-11" in main
    assert "useRef(null)" in main
    assert "register_rest_route(" not in (THEME/"functions.php").read_text()
    assert "wp_remote_post(" not in (THEME/"functions.php").read_text()
