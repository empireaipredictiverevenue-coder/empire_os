"""V10: actual synthetic WordPress model-failure recovery + local axe WCAG audit."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOC=ROOT/"docs/commercial"
PROOF=DOC/"EMPIRE_CAR_YARD_FAILURE_A11Y_V10_BROWSER_ACCEPTANCE_20261024.json"

def data():
    return json.loads(PROOF.read_text())

def test_real_wordpress_recovers_from_forced_glb_failure_without_retry_loop():
    r=data()
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==105
    assert all(r["browser_checks"].values())
    for check in (
        "v10_real_glb_failure_recovers_original_concept",
        "v10_bad_glb_retries_disabled_after_failure",
        "v10_bad_glb_only_requested_once",
        "v10_external_requests_blocked_during_failure",
        "v7_studio_pbr_model_loaded_from_local_wordpress_glb",
        "v9_meshopt_optimized_glb_only_loads_after_explicit_opt_in",
        "v9_data_saver_shows_compressed_size",
        "v8_data_saver_requires_second_confirmation",
        "v5_mobile_opt_in_avoids_automatic_3d_download",
        "v5_reduced_motion_no_webgl_canvas",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt",
         "v10_real_axe_core_wcag_rules_executed","v10_axe_external_requests_blocked",
        "v10_axe_wcag_no_automated_violations"
    ):
        assert r["browser_checks"][check] is True,check
    failure=r["model_failure_injection"]
    assert failure["requests"]==1
    assert failure["outside"]==failure["outsideBlocked"]
    assert r["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["restore_verified"]["booking_audit_events"]==3
    assert r["production_changes"] is False
    assert r["synthetic_data_only"] is True
    assert r["customer_bookings_enabled"] is False
    assert r["outbound_or_payments_enabled"] is False

def test_axe_runs_real_wcag_audit_but_does_not_claim_full_certification():
    r=data()
    axe=r["axe_wcag_audit"]
    assert axe["engine"]=="axe-core 4.10.3"
    assert "mobile" in axe["scope"]
    assert axe["automated_only"] is True
    assert axe["assessed_rules"]>25
    assert axe["passes"]>15
    assert axe["violations"]==[]
    assert isinstance(axe["incomplete"],list)
    assert all("id" in v and "impact" in v and "affected_nodes" in v
               for v in axe["violations"])

def test_original_source_hashes_and_real_browser_screenshots():
    r=data()
    assert len(r["source_manifest_sha256"])>=25
    for rel,digest in r["source_manifest_sha256"].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel
    assert len(r["screenshots"])==6
    for name,props in r["screenshots"].items():
        screen=DOC/"car_yard_react_browser_evidence_v10"/name
        assert screen.is_file() and screen.stat().st_size==props["bytes"]
        assert sha256(screen.read_bytes()).hexdigest()==props["sha256"]

def test_react_failure_recovery_and_test_only_axe_injection():
    main=(THEME/"src/main.jsx").read_text()
    assert "componentDidCatch()" in main
    assert "this.props.onFailure?.()" in main
    assert "data-studio-recovered" in main
    assert "if (!interactive || reduce || !modelUrl || modelError) return" in main
    assert "disabled={!modelUrl || reduce || !interactive || modelError}" in main
    assert "Studio unavailable — reload to retry" in main
    browser=(ROOT/"scripts/premium_wp_v1/browser_acceptance_v10.cjs").read_text()
    assert "STAGING_EXPECTED_SYNTHETIC_MODEL_UNAVAILABLE" in browser
    assert "status:503" in browser
    assert "axe.run(document" in browser
    assert "v10_real_glb_failure_recovers_original_concept" in browser
    assert "requestfailed" in browser
    assert "v10_real_axe_core_wcag_rules_executed" in browser
    core=ROOT/"scripts/premium_wp_v1/vendor/axe-core-4.10.3.min.js"
    assert core.is_file() and core.stat().st_size>500_000
    assert (ROOT/"scripts/premium_wp_v1/vendor/AXE_CORE_LICENSE.txt").is_file()
    assert not (THEME/"dist/axe-core-4.10.3.min.js").exists()

def test_zip_remains_original_wordpress_child_theme_without_test_dependencies():
    archive=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-resilience-v10-preview.zip"
    assert archive.is_file()
    with ZipFile(archive) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert all(n.startswith("empire-yard-atelier/") for n in names)
        assert "empire-yard-atelier/assets/models/car-concept-studio-meshopt.glb" in names
        assert "empire-yard-atelier/assets/models/car-concept-editorial-webp.glb" not in names
        assert not any("axe-core" in n or "node_modules" in n or ".env" in n for n in names)
