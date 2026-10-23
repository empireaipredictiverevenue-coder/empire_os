"""Optimised licensed vehicle delivery with actual WordPress and fail-closed GPU tests."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json

from scripts.premium_wp_v1.check_client_glb_admission_v9 import check_model_bytes, MAX_MODEL_BYTES

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOCS=ROOT/"docs/commercial"
ACCEPTANCE=DOCS/"EMPIRE_CAR_YARD_MESHOPT_V9_BROWSER_ACCEPTANCE_20261023.json"
ADMISSION=DOCS/"EMPIRE_CAR_YARD_MESHOPT_V9_TECHNICAL_ADMISSION_20261023.json"
MODEL=THEME/"assets/models/car-concept-studio-meshopt.glb"
PROVENANCE=THEME/"assets/models/MODEL_PROVENANCE_MESHOPT_V9.json"

def test_actual_glb_reduced_at_least_sixty_percent_with_original_materials():
    meta=json.loads(PROVENANCE.read_text())
    raw=MODEL.read_bytes()
    assert raw[:4]==b"glTF"
    assert len(raw)==meta["derivative_bytes"]==2_825_112
    assert sha256(raw).hexdigest()==meta["derivative_sha256"]
    assert len(raw)<meta["v8_source_bytes"]*.4
    assert meta["upstream_license"].startswith("Creative Commons Attribution")
    assert meta["production_release"].startswith("HOLD")
    assert meta["compression_type"]=="EXT_meshopt_compression"
    assert meta["upstream_model_author"]
    assert meta["v8_source_sha256"]==sha256(
        (THEME/"assets/models/car-concept-editorial-webp.glb").read_bytes()).hexdigest()

def test_v9_offline_model_admission_not_client_trademark_approval():
    data=json.loads(ADMISSION.read_text())
    provenance=json.loads(PROVENANCE.read_text())
    assert data==check_model_bytes(MODEL.read_bytes(),provenance)
    assert data["technical_check_passed"] is True
    assert data["triangles"]==213195
    assert data["input_bytes"]<=MAX_MODEL_BYTES
    assert set(("EXT_meshopt_compression","EXT_texture_webp","KHR_mesh_quantization")).issubset(
        data["required_extensions"])
    for key in ("commercial_release_eligible","rights_owner_verified",
                "site_grant_verified","model_brand_trademarks_cleared",
                "device_gpu_test_verified","production_changes"):
        assert data[key] is False,key
    assert data["release_status"].startswith("HOLD_")

def test_preflight_rejects_full_size_model_and_external_sources():
    original=(THEME/"assets/models/car-concept-editorial-webp.glb").read_bytes()
    meta=json.loads(PROVENANCE.read_text())
    rejected=check_model_bytes(original,meta)
    assert rejected["technical_check_passed"] is False
    assert "MODEL_EXCEEDS_5MB_OPTIMIZED_DELIVERY_BUDGET" in rejected["issues"]
    bad=check_model_bytes(b"javascript:fetch('https://bad.invalid/')",{})
    assert not bad["technical_check_passed"]
    assert bad["on_rejection"]=="retain_existing_wordpress_procedural_vehicle"

def test_real_wordpress_98_browser_checks_opt_in_and_booking_restore():
    receipt=json.loads(ACCEPTANCE.read_text())
    assert receipt["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert receipt["browser_check_count"]==len(receipt["browser_checks"])==98
    assert all(receipt["browser_checks"].values())
    for check in (
        "v9_meshopt_optimized_glb_only_loads_after_explicit_opt_in",
        "v9_data_saver_shows_compressed_size",
        "v7_high_detail_glb_not_downloaded_before_opt_in",
        "v7_studio_pbr_model_loaded_from_local_wordpress_glb",
        "v7_studio_pbr_camera_view_switch",
        "v7_studio_pbr_material_finish_switch",
        "v7_studio_can_return_to_lightweight_concept",
        "v5_mobile_opt_in_avoids_automatic_3d_download",
        "v8_data_saver_requires_second_confirmation",
        "v5_reduced_motion_no_webgl_canvas",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt",
    ):
        assert receipt["browser_checks"][check] is True,check
    assert receipt["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert receipt["restore_verified"]["booking_audit_events"]==3
    assert receipt["production_changes"] is False
    assert receipt["synthetic_data_only"] is True
    assert receipt["customer_bookings_enabled"] is False

def test_98_check_receipt_source_sha_screenshots_and_honest_device_status():
    r=json.loads(ACCEPTANCE.read_text())
    assert len(r["source_manifest_sha256"])>=26
    for path,digest in r["source_manifest_sha256"].items():
        assert sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    assert len(r["screenshots"])==6
    for name,meta in r["screenshots"].items():
        p=DOCS/"car_yard_react_browser_evidence_v9"/name
        assert p.is_file() and p.stat().st_size==meta["bytes"]
        assert sha256(p.read_bytes()).hexdigest()==meta["sha256"]
    frame=r["model_frame_lab"]
    assert frame["backend_class"]=="software_swiftshader"
    assert frame["physical_device_measurement"] is False
    assert frame["method"]=="requestAnimationFrame_interval_lab_not_gpu_frame_query"
    assert frame["glb_encoded_bytes"]==2_825_112
    assert r["mobile_emulation"]["not_field_core_web_vitals"] is True
    assert not r["mobile_lab_measurement"]["scene_requested_before_opt_in"]

def test_showroom_uses_meshopt_with_bundled_decoder_no_external_draco():
    scene=(THEME/"src/StudioPBRVehicle.jsx").read_text()
    php=(THEME/"functions.php").read_text()
    main=(THEME/"src/main.jsx").read_text()
    assert "useGLTF(modelUrl, false, true)" in scene
    assert "car-concept-studio-meshopt.glb" in php
    assert "car-concept-studio-meshopt.glb" in main
    assert "2.8 MB" in main
    assert "Load Studio PBR" in main
    assert "9 MB" not in main
    assert "https://www.gstatic.com/draco" not in scene
    assert "React.lazy(() => import('./StudioPBRVehicle.jsx'))" in (THEME/"src/ShowroomScene.jsx").read_text()

def test_installable_v9_theme_only_contains_compressed_glb():
    zip_path=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-meshopt-v9-preview.zip"
    assert zip_path.is_file()
    with ZipFile(zip_path) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert all(name.startswith("empire-yard-atelier/") for name in names)
        assert "empire-yard-atelier/assets/models/car-concept-studio-meshopt.glb" in names
        assert "empire-yard-atelier/assets/models/car-concept-editorial-webp.glb" not in names
        assert "empire-yard-atelier/assets/models/MODEL_PROVENANCE_MESHOPT_V9.json" in names
        assert "empire-yard-atelier/assets/models/UPSTREAM_LICENSE.md" in names
        assert len([name for name in names if "yard-StudioPBRVehicle-" in name])==1
        assert not any("node_modules" in name or ".env" in name for name in names)
        assert len(z.read("empire-yard-atelier/assets/models/car-concept-studio-meshopt.glb"))==2_825_112
