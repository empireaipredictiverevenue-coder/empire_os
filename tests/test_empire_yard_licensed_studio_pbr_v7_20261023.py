"""Stage-only native WordPress/R3F PBR vehicle evidence and original asset rights."""
import hashlib
import json
import re
import struct
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
ASSET=THEME/"assets/models/car-concept-editorial-webp.glb"
META=THEME/"assets/models/MODEL_PROVENANCE.json"
RECEIPT=ROOT/"docs/commercial/EMPIRE_CAR_YARD_STUDIO_PBR_V7_BROWSER_ACCEPTANCE_20261023.json"

def test_cc_by_asset_license_and_derivative_mark_exclusions():
    meta=json.loads(META.read_text())
    raw=ASSET.read_bytes()
    assert len(raw)<10_000_000
    assert hashlib.sha256(raw).hexdigest()==meta["derivative_sha256"]
    assert len(raw)==meta["derivative_bytes"]
    assert meta["upstream_sha256"]=="c272098089d78c5cd9fd9f24ff50ee8acf8d932c55f2d55fc10adb6c8998966b"
    assert meta["modified_derivative"] is True
    assert "Creative Commons Attribution 4.0" in meta["upstream_license"]
    assert "HOLD" in meta["production_release"]
    assert raw[:4]==b"glTF"
    _,version,total=struct.unpack_from("<4sII",raw)
    assert version==2 and total==len(raw)
    json_size,chunk_type=struct.unpack_from("<I4s",raw,12)
    assert chunk_type==b"JSON"
    gltf=json.loads(raw[20:20+json_size])
    assert "EXT_texture_webp" in gltf["extensionsRequired"]
    assert "KHR_materials_clearcoat" in gltf["extensionsUsed"]
    assert "KHR_materials_variants" in gltf["extensionsUsed"]
    assert len(gltf["nodes"])>=90 and len(gltf["meshes"])>=80
    assert not any(node.get("name") in ("InteriorSteeringEmblem","License Plate")
                   for node in gltf["nodes"])
    assert "Creative Commons Attribution 4.0" in (THEME/"assets/models/UPSTREAM_LICENSE.md").read_text()

def test_existing_app_loads_optional_local_asset_not_a_remote_model():
    scene=(THEME/"src/ShowroomScene.jsx").read_text()
    viewer=(THEME/"src/StudioPBRVehicle.jsx").read_text()
    main=(THEME/"src/main.jsx").read_text()
    php=(THEME/"functions.php").read_text()
    assert "React.lazy(() => import('./StudioPBRVehicle.jsx'))" in scene
    assert "frameloop={modelMode === 'studio' ? 'demand' : 'always'}" in scene
    assert "modelMode !== 'studio' && <ContactShadows" in scene
    assert "useGLTF(modelUrl)" in viewer
    assert "model.clone" not in viewer or "scene.clone(true)" in viewer
    assert "OrbitControls" in viewer
    assert "onReady?.()" in viewer
    assert "data-model-mode=\"studio\"" in main
    assert "data-model-mode=\"concept\"" in main
    assert "data-studio-model-ready" in main
    assert "Load Studio PBR" in main
    assert "Khronos glTF Sample Assets" in main
    assert "creativecommons.org/licenses/by/4.0" in main
    assert "showroom_model_url" in main and "showroom_model_url" in php
    assert "get_stylesheet_directory_uri()" in php
    assert "register_rest_route(" not in php and "wp_remote_post(" not in php
    assert "fetch(" not in scene and "fetch(" not in viewer
    assert "http://" not in viewer
    assert re.sub(r"/\\*.*?\\*/","",(THEME/"style.css").read_text(),flags=re.DOTALL).strip()==""

def test_actual_wordpress_studio_model_switch_and_recovery():
    receipt=json.loads(RECEIPT.read_text())
    assert receipt["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert receipt["browser_check_count"]==len(receipt["browser_checks"])==93
    assert all(receipt["browser_checks"].values())
    for key in (
        "v7_studio_pbr_controls_registered",
        "v7_high_detail_glb_not_downloaded_before_opt_in",
        "v7_studio_pbr_model_loaded_from_local_wordpress_glb",
        "v7_studio_pbr_status_and_attribution",
        "v7_studio_pbr_canvas_visible",
        "v7_studio_pbr_camera_view_switch",
        "v7_studio_pbr_material_finish_switch",
        "v7_studio_can_return_to_lightweight_concept",
        "v7_mobile_pbr_model_not_requested_initially",
        "v5_mobile_opt_in_avoids_automatic_3d_download",
        "v5_reduced_motion_no_webgl_canvas",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt"
    ):
        assert receipt["browser_checks"][key] is True,key
    assert receipt["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert receipt["restore_verified"]["booking_audit_events"]==3
    assert receipt["production_changes"] is False
    assert receipt["customer_bookings_enabled"] is False
    assert receipt["outbound_or_payments_enabled"] is False
    assert receipt["synthetic_data_only"] is True

def test_v7_source_manifest_and_evidence_screenshots_exact():
    r=json.loads(RECEIPT.read_text())
    assert len(r["source_manifest_sha256"])>=20
    for rel,digest in r["source_manifest_sha256"].items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel
    assert len(r["screenshots"])==6
    for name,props in r["screenshots"].items():
        img=ROOT/"docs/commercial/car_yard_react_browser_evidence_v7"/name
        assert img.is_file() and img.stat().st_size==props["bytes"]
        assert hashlib.sha256(img.read_bytes()).hexdigest()==props["sha256"]

def test_installable_v7_package_exact_assets_and_no_external_credentials():
    p=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-studio-pbr-v7-preview.zip"
    assert p.is_file()
    with ZipFile(p) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert all(name.startswith("empire-yard-atelier/") for name in names)
        for rel in (
            "functions.php","assets/models/car-concept-editorial-webp.glb",
            "assets/models/MODEL_PROVENANCE.json","assets/models/UPSTREAM_LICENSE.md",
            "dist/yard.js","dist/yard.css","src/brand-media-picker.js",
        ):
            assert "empire-yard-atelier/"+rel in names
        assert len([n for n in names if "yard-StudioPBRVehicle-" in n])==1
        assert not any("node_modules/" in n or ".env" in n or "secret" in n for n in names)
