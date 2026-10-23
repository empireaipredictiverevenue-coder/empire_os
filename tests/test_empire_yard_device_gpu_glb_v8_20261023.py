"""V8: safe client-asset technical admission and measured SwiftShader QA."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import struct

from scripts.premium_wp_v1.check_client_glb_admission_v8 import check_model_bytes, MAX_MODEL_BYTES

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOC = ROOT/"docs/commercial"
RECEIPT = DOC/"EMPIRE_CAR_YARD_DEVICE_GATE_V8_BROWSER_ACCEPTANCE_20261023.json"
ADMISSION = DOC/"EMPIRE_CAR_YARD_GLTF_V8_TECHNICAL_ADMISSION_20261023.json"

def mini_glb(gltf: dict) -> bytes:
    encoded = json.dumps(gltf, separators=(",",":")).encode()
    padded = encoded + b" " * ((-len(encoded)) % 4)
    total = 12+8+len(padded)+8
    return struct.pack("<4sII",b"glTF",2,total)+struct.pack("<I4s",len(padded),b"JSON")+padded+struct.pack("<I4s",0,b"BIN\x00")

def legal_fictional_minimum() -> dict:
    return {
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":0}],
        "meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}],
        "accessors":[{"count":6}],
        "nodes":[{"mesh":0}],
        "scenes":[{"nodes":[0]}],
        "scene":0
    }

def proof(data:bytes) -> dict:
    return {
        "upstream_model_author":"Fictional synthetic unit-test artist",
        "upstream_model":"https://example.invalid/original",
        "derivative_sha256":sha256(data).hexdigest(),
        "license_url":"https://example.invalid/licence",
    }

def test_valid_small_embedded_model_still_has_release_hold():
    raw=mini_glb(legal_fictional_minimum())
    result=check_model_bytes(raw,proof(raw))
    assert result["technical_check_passed"]
    assert result["triangles"]==2
    assert result["commercial_release_eligible"] is False
    assert not result["rights_owner_verified"]
    assert not result["device_gpu_test_verified"]
    assert result["release_status"].startswith("HOLD_")
    assert result["status"]=="TECHNICAL_PREVIEW_REVIEW_ONLY"

def test_glb_external_uri_is_rejected_without_network_access():
    model=legal_fictional_minimum()
    model["images"]=[{"uri":"https://untrusted.invalid/tracker.png"}]
    raw=mini_glb(model)
    result=check_model_bytes(raw,proof(raw))
    assert result["status"]=="TECHNICAL_PREVIEW_REJECTED"
    assert "EXTERNAL_OR_DATA_URI_ASSET_DISALLOWED" in result["issues"]
    assert not result["technical_check_passed"]
    assert result["on_rejection"]=="retain_existing_wordpress_procedural_vehicle"

def test_bad_format_unknown_extension_and_wrong_digest_all_rejected():
    bad=check_model_bytes(b"not glb",{})
    assert bad["status"]=="TECHNICAL_PREVIEW_REJECTED"
    model=legal_fictional_minimum()
    model["extensionsRequired"]=["VENDOR_unknown_mesh_loader"]
    raw=mini_glb(model)
    result=check_model_bytes(raw,proof(raw))
    assert "UNREVIEWED_REQUIRED_GLTF_EXTENSION" in result["issues"]
    mismatch=proof(raw)
    mismatch["derivative_sha256"]="0"*64
    mismatch_result=check_model_bytes(raw,mismatch)
    assert "MODEL_SOURCE_DIGEST_MISMATCH" in mismatch_result["issues"]
    large=check_model_bytes(b"x"*(MAX_MODEL_BYTES+1),{})
    assert "MODEL_EXCEEDS_12MB_PRIVATE_PREVIEW_BUDGET" in large["issues"]

def test_actual_sample_model_passes_technical_checks_without_licence_clearance():
    model=THEME/"assets/models/car-concept-editorial-webp.glb"
    actual=json.loads(ADMISSION.read_text())
    meta=json.loads((THEME/"assets/models/MODEL_PROVENANCE.json").read_text())
    assert actual==check_model_bytes(model.read_bytes(),meta)
    assert actual["technical_check_passed"] is True
    assert actual["commercial_release_eligible"] is False
    assert actual["rights_owner_verified"] is False
    assert actual["site_grant_verified"] is False
    assert actual["triangles"]==213195
    assert actual["input_sha256"]==meta["derivative_sha256"]
    assert actual["structure_counts"]["meshes"]==95
    assert actual["structure_counts"]["images"]==14

def test_real_wordpress_data_saver_and_mobile_controls():
    r=json.loads(RECEIPT.read_text())
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==96
    assert all(r["browser_checks"].values())
    for name in (
        "v8_data_saver_requires_second_confirmation",
        "v8_mobile_model_control_is_disabled_before_webgl_opt_in",
        "v8_real_stage_frame_intervals_measured",
        "v7_studio_pbr_model_loaded_from_local_wordpress_glb",
        "v7_high_detail_glb_not_downloaded_before_opt_in",
        "v5_mobile_opt_in_avoids_automatic_3d_download",
        "v5_reduced_motion_no_webgl_canvas",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt",
    ):
        assert r["browser_checks"][name],name
    assert r["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["restore_verified"]["booking_audit_events"]==3
    assert r["synthetic_data_only"] is True
    assert r["production_changes"] is False
    assert r["customer_bookings_enabled"] is False
    assert r["outbound_or_payments_enabled"] is False

def test_performance_receipt_cannot_claim_physical_gpu_frame_rate():
    lab=json.loads(RECEIPT.read_text())["model_frame_lab"]
    assert lab["backend_class"]=="software_swiftshader"
    assert lab["physical_device_measurement"] is False
    assert lab["field_core_web_vitals"] is False
    assert lab["method"]=="requestAnimationFrame_interval_lab_not_gpu_frame_query"
    assert 8 <= lab["sampled_frame_intervals"] <=45
    assert 0<lab["p50_interval_ms"]<=lab["p95_interval_ms"]
    assert lab["glb_encoded_bytes"]==9338828
    assert lab["glb_transfer_ms"]>0
    assert lab["webgl_limits"]["max_texture_size"]>=2048
    assert lab["inferred_fps"]>0  # Browser callback frequency, not rendered GPU FPS.
    r=json.loads(RECEIPT.read_text())
    assert r["mobile_emulation"]["not_field_core_web_vitals"]
    assert not r["mobile_lab_measurement"]["scene_requested_before_opt_in"]

def test_versioned_original_evidence_and_installable_theme_package():
    r=json.loads(RECEIPT.read_text())
    assert len(r["source_manifest_sha256"])>=24
    for rel,digest in r["source_manifest_sha256"].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel
    assert len(r["screenshots"])==6
    for name,meta in r["screenshots"].items():
        p=DOC/"car_yard_react_browser_evidence_v8"/name
        assert p.is_file() and p.stat().st_size==meta["bytes"]
        assert sha256(p.read_bytes()).hexdigest()==meta["sha256"]
    z=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-device-gate-v8-preview.zip"
    assert z.is_file()
    with ZipFile(z) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert "empire-yard-atelier/assets/models/car-concept-editorial-webp.glb" in names
        assert len([x for x in names if "yard-StudioPBRVehicle-" in x])==1
        assert not any("node_modules/" in x or ".env" in x for x in names)

def test_original_viewer_safe_recovery_and_datacap_in_real_source():
    src=(THEME/"src/main.jsx").read_text()
    assert "navigator.connection?.saveData" in src
    assert "navigator.deviceMemory" in src
    assert "Number(window.navigator.deviceMemory) <= 2" in src
    assert "largeModelConfirmed" in src
    assert "data-device-caution" in src
    assert "Confirm Studio PBR" in src
    assert "componentDidCatch()" in src
    assert "data-studio-recovered" in src
    assert "setModelMode('concept')" in src
    assert "data-model-mode=\"studio\"" in src
