"""V11: actual WebGL context-loss recovery, keyboard controls and 320px reflow."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOC=ROOT/"docs/commercial"
RECEIPT=DOC/"EMPIRE_CAR_YARD_CONTEXT_KEYBOARD_V11_BROWSER_ACCEPTANCE_20261024.json"

V11_COMMIT="91a59012dcaa3b7571ad5e82d7541327aa7ea204"
def original_v11(relative):
    return subprocess.run(["git","show",V11_COMMIT+":"+relative],
        cwd=ROOT,check=True,capture_output=True).stdout


def receipt():
    return json.loads(RECEIPT.read_text())

def test_real_wordpress_browser_context_loss_keyboard_and_reflow():
    r=receipt()
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==115
    assert all(r["browser_checks"].values())
    for key in (
        "v11_keyboard_space_changes_camera_and_aria_pressed",
        "v11_keyboard_enter_changes_paint_and_aria_pressed",
        "v11_real_browser_webgl_loss_extension_invoked",
        "v11_webgl_context_loss_switches_to_static_preview",
        "v11_context_loss_accessible_notice_and_no_retry",
        "v11_context_loss_browser_outbound_blocked",
        "v11_320px_mobile_reflow_no_horizontal_scroll",
        "v11_keyboard_skip_link_visible_and_main_targeted",
        "v11_320px_reduced_motion_avoids_model_request",
        "v11_320px_browser_outside_requests_blocked",
        "v10_real_glb_failure_recovers_original_concept",
        "v10_bad_glb_retries_disabled_after_failure",
        "v10_bad_glb_only_requested_once",
        "v10_axe_wcag_no_automated_violations",
        "v9_meshopt_optimized_glb_only_loads_after_explicit_opt_in",
        "v9_data_saver_shows_compressed_size",
        "v5_mobile_opt_in_avoids_automatic_3d_download",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt",
    ):
        assert r["browser_checks"][key] is True,key
    assert r["context_loss_diagnostic"]=={"supported":True,"lost":True}
    reflow=r["small_screen_reflow"]
    assert reflow["width"]==320
    assert reflow["page_scroll_width"]==320
    assert reflow["no_horizontal_overflow"] is True
    assert reflow["skip_link_visible_on_focus"] is True
    assert reflow["model_not_auto_loaded"] is True
    assert reflow["h1_count"]==1
    assert r["model_failure_injection"]["requests"]==1
    assert r["restore_verified"]["booking_audit_events"]==3
    assert r["production_changes"] is False
    assert r["synthetic_data_only"] is True
    assert r["customer_bookings_enabled"] is False
    assert r["outbound_or_payments_enabled"] is False

def test_accessibility_results_are_accurately_scoped_not_wide_certification():
    axe=receipt()["axe_wcag_audit"]
    assert axe["engine"]=="axe-core 4.10.3"
    assert axe["automated_only"] is True
    assert axe["violations"]==[]
    assert axe["incomplete"] != []  # manual inspection still necessary
    assert any(v["id"]=="color-contrast" and v["affected_nodes"]>=1
               for v in axe["incomplete"])
    assert axe["browser_external_request_attempts"]==axe["browser_external_requests_blocked"]

def test_v11_source_sha_receipts_and_screenshots():
    r=receipt()
    assert len(r["source_manifest_sha256"])>=26
    for rel,digest in r["source_manifest_sha256"].items():
        assert sha256(original_v11(rel)).hexdigest()==digest,rel
    assert len(r["screenshots"])==6
    for name,details in r["screenshots"].items():
        img=DOC/"car_yard_react_browser_evidence_v11"/name
        assert img.is_file() and img.stat().st_size==details["bytes"]
        assert sha256(img.read_bytes()).hexdigest()==details["sha256"],name

def test_canvas_listener_and_hardened_default_survive_without_parallel_system():
    scene=original_v11("prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/src/ShowroomScene.jsx").decode()
    app=original_v11("prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/src/main.jsx").decode()
    assert "function RenderContextMonitor" in scene
    assert "webglcontextlost" in scene
    assert "event.preventDefault()" in scene
    assert "canvas.removeEventListener('webglcontextlost'" in scene
    assert "onRendererLost={handleRendererLost}" in app
    assert "data-renderer-lost" in app
    assert "data-renderer-recovered" in app
    assert "setContextLost(true)" in app
    assert "setModelMode('concept')" in app
    assert "&& !contextLost" in app
    assert "break-words" in app
    assert "min-w-0" in app
    assert "wp_remote_post(" not in (THEME/"functions.php").read_text()
    assert "register_rest_route(" not in (THEME/"functions.php").read_text()

def test_installable_v11_theme_does_not_include_qa_or_old_large_glb():
    zip_path=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-context-qa-v11-preview.zip"
    assert zip_path.exists()
    with ZipFile(zip_path) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert all(x.startswith("empire-yard-atelier/") for x in names)
        assert "empire-yard-atelier/assets/models/car-concept-studio-meshopt.glb" in names
        assert "empire-yard-atelier/assets/models/car-concept-editorial-webp.glb" not in names
        assert len([x for x in names if "yard-StudioPBRVehicle-" in x])==1
        assert not any("axe-core" in x or "node_modules" in x or ".env" in x
                       for x in names)
