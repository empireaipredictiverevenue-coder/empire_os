"""Actual V5 WordPress/MariaDB + mobile opt-in and measured accessibility receipt."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import gzip
import json

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOCS=ROOT/"docs/commercial"
RECEIPT=DOCS/"EMPIRE_CAR_YARD_SHOWROOM_V5_MOBILE_A11Y_ACCEPTANCE_20261023.json"
BASELINE=DOCS/"EMPIRE_CAR_YARD_SHOWROOM_V5_MOBILE_EAGER_BASELINE_20261023.json"

def result():
    return json.loads(RECEIPT.read_text())

def test_isolated_real_wordpress_browser_with_optional_3d_and_booking_restore():
    r=result()
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==71
    assert all(r["browser_checks"].values())
    for check in (
        "real_three_js_webgl_canvas_rendered","real_view_and_paint_controls_rendered",
        "side_view_interaction_state","paint_palette_interaction_state",
        "offscreen_scene_unmounted_to_save_gpu","returning_to_hero_restores_scene",
        "v5_mobile_hero_text_not_hidden_by_entrance_animation",
        "v5_mobile_preview_and_opt_in_visible_before_screenshot",
        "v5_mobile_opt_in_avoids_automatic_3d_download",
        "v5_mobile_3d_chunk_load_recorded_after_opt_in",
        "v5_mobile_emulation_fcp_recorded",
        "v5_accessibility_one_h1_and_main","v5_accessibility_buttons_have_names",
        "v5_accessibility_links_have_names",
        "v5_accessibility_ax_tree_no_unnamed_links_buttons",
        "v5_accessibility_hero_contrast_aa",
        "v5_accessibility_controls_pressed_states",
        "v5_reduced_motion_no_webgl_canvas","admin_login_success",
        "wordpress_admin_branding_saved","configured_stock_page_200",
        "configured_stock_header_uses_saved_brand","configured_stock_footer_uses_saved_brand",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt",
        "all_external_browser_requests_blocked",
    ):
        assert r["browser_checks"][check] is True,check
    assert r["restore_verified"]["booking_audit_events"]==3
    assert r["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["synthetic_data_only"] is True
    assert r["production_changes"] is False
    assert r["outbound_or_payments_enabled"] is False
    assert r["customer_bookings_enabled"] is False

def test_mobile_lab_metrics_are_real_but_not_field_core_web_vitals():
    r=result()
    lab=r["mobile_lab_measurement"]
    emu=r["mobile_emulation"]
    assert emu["runs"]==1 and emu["not_field_core_web_vitals"] is True
    assert emu["viewport_width_px"]==390 and emu["device_scale_factor"]==2
    assert emu["network_throughput_mbps"]==1.6
    assert emu["cpu_throttle_factor"]==4
    assert 0<lab["fcp_ms"]<45000
    assert 0<lab["ttfb_ms"]<15000
    assert lab["dom_nodes"]>100
    assert lab["opt_in_button_visible"] is True
    assert lab["canvas_visible"] is False
    assert lab["scene_requested_before_opt_in"] is False
    assert lab["horizontal_overflow"] is False
    assert len(lab["js_resources"])>=1
    assert all("ShowroomScene" not in item["name"] for item in lab["js_resources"])
    after=r["mobile_opt_in_3d"]
    assert after["canvas_visible"] is True
    assert len(after["scene_chunks"])==1
    assert after["scene_chunks"][0]["encoded_bytes"]>100_000
    assert after["scene_chunks"][0]["duration_ms"]>0
    baseline=json.loads(BASELINE.read_text())
    assert baseline["not_field_core_web_vitals"] is True
    assert baseline["mobile_lab_measurement"]["canvas_visible"] is True
    assert baseline["mobile_lab_measurement"]["fcp_ms"]>0
    assert baseline["mobile_emulation"]==emu
    assert any("ShowroomScene" in item["name"] for item in
               baseline["mobile_lab_measurement"]["js_resources"])
    # One-run laboratory samples only: do not assert LCP improvement without field evidence.

def test_targeted_accessibility_audit_and_reduced_motion():
    r=result()
    a=r["targeted_accessibility"]
    assert a["h1_count"]==1
    assert a["main_landmarks"]==1
    assert a["named_buttons"] and a["named_links"]
    assert a["unnamed_ax_interactive_nodes"]==0
    assert a["skip_link"] is True and a["live_region_count"]>=1
    assert a["paint_button_pressed_states"] is True
    assert a["hero_text_contrast"]>=4.5
    assert a["hero_highlight_contrast"]>=4.5
    assert r["reduced_motion_measurement"]=={
        "fallback":True,"live_canvas":False,"scene_chunk_requests":0
    }

def test_exact_v5_source_hashes_and_browser_screenshots():
    r=result()
    assert len(r["source_manifest_sha256"])>=16
    for path,digest in r["source_manifest_sha256"].items():
        assert sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    assert len(r["screenshots"])==4
    for name,metadata in r["screenshots"].items():
        screen=DOCS/"car_yard_react_browser_evidence_v5"/name
        assert screen.is_file() and screen.stat().st_size==metadata["bytes"]
        assert sha256(screen.read_bytes()).hexdigest()==metadata["sha256"]

def test_original_procedural_gt_details_and_opt_in_source():
    src=(THEME/"src/ShowroomScene.jsx").read_text()
    main=(THEME/"src/main.jsx").read_text()
    for value in ("function Tire(", "function SideGlass(", "shapeGeometry",
                  "torusGeometry","windshield","Grille","clearcoat","meshPhysicalMaterial",
                  "shadow-mapSize", "paint.body","paint.roof"):
        assert value.lower() in src.lower(),value
    for value in ("mobileTouch","mobile3DRequested","data-launch-3d",
                  "prefers-reduced-motion", "React.lazy("):
        # Reduced motion is checked via Motion hook (not a hard-coded media string).
        if value=="prefers-reduced-motion":
            assert "useReducedMotion" in main
        else:
            assert value in main
    assert "fetch(" not in main and "fetch(" not in src
    assert "http://" not in main and "https://" not in main
    manifest=json.loads((THEME/"package.json").read_text())
    assert "gsap" not in manifest["dependencies"] and "lenis" not in manifest["dependencies"]
    entry=next(iter((THEME/"dist").glob("yard-main-*.js")))
    scene=next(iter((THEME/"dist").glob("yard-ShowroomScene-*.js")))
    assert len(gzip.compress(entry.read_bytes(),mtime=0))<200_000
    assert len(gzip.compress(scene.read_bytes(),mtime=0))<410_000

def test_wordpress_installable_preview_contains_both_chunks_and_native_branding():
    archive=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-showroom-v5-preview.zip"
    assert archive.is_file()
    with ZipFile(archive) as zip:
        assert zip.testzip() is None
        names=zip.namelist()
        assert all(n.startswith("empire-yard-atelier/") for n in names)
        assert "empire-yard-atelier/functions.php" in names
        assert "empire-yard-atelier/parts/header.html" in names
        assert "empire-yard-atelier/dist/yard.js" in names
        assert len([x for x in names if "yard-main-" in x])==1
        assert len([x for x in names if "yard-ShowroomScene-" in x])==1
        assert not any("node_modules" in x or "private" in x for x in names)
