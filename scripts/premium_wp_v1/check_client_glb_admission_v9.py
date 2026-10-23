"""Fail-closed *technical* preflight for agency showroom glTF binary assets.

Not a rights/tenant approval authority, antivirus engine, or client deployment.
Inspects the actual GLB offline, without executing its content or making network calls.
The owner must independently approve site grant, identity, imagery and trademarks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

MAX_MODEL_BYTES = 5_000_000
MAX_TRIANGLES = 280_000
MAX_NODES = 160
MAX_MESHES = 120
MAX_TEXTURES = 20
MAX_IMAGES = 20
MAX_MATERIALS = 45
MAX_ACCESSORS = 850
ALLOWED_REQUIRED_EXTENSIONS = {"EXT_texture_webp", "KHR_texture_basisu", "EXT_meshopt_compression", "KHR_mesh_quantization"}
FALLBACK = "retain_existing_wordpress_procedural_vehicle"

def check_model_bytes(raw: bytes, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    """Produce complete read-only evidence, never an owner approval."""
    issues: list[str] = []
    def deny(reason: str):
        if reason not in issues:
            issues.append(reason)
    report: dict[str, Any] = {
        "schema": "empire.agency.meshopt_glb_admission_review.v9",
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "input_bytes": len(raw),
        "technical_check_passed": False,
        "status": "TECHNICAL_PREVIEW_REJECTED",
        "release_status": "HOLD_CANONICAL_SITE_GRANT_IP_RIGHTS_AND_PHYSICAL_DEVICE_TEST",
        "commercial_release_eligible": False,
        "site_grant_verified": False,
        "rights_owner_verified": False,
        "model_brand_trademarks_cleared": False,
        "device_gpu_test_verified": False,
        "production_changes": False,
        "source": "local_read_only_model_bytes",
        "on_rejection": FALLBACK,
    }
    if len(raw) > MAX_MODEL_BYTES:
        deny("MODEL_EXCEEDS_5MB_OPTIMIZED_DELIVERY_BUDGET")
    if len(raw) < 24:
        deny("INCOMPLETE_GLB")
    if issues:
        report["issues"] = issues
        return report
    magic, version, file_length = struct.unpack_from("<4sII", raw)
    if magic != b"glTF" or version != 2 or file_length != len(raw):
        deny("INVALID_GLB_MAGIC_VERSION_OR_LENGTH")
        report["issues"] = issues
        return report
    json_length, json_type = struct.unpack_from("<I4s", raw, 12)
    if json_type != b"JSON" or json_length > len(raw) - 20:
        deny("INVALID_GLB_JSON_CHUNK")
        report["issues"] = issues
        return report
    try:
        gltf = json.loads(raw[20:20+json_length].decode("utf-8").rstrip("\x00 "))
    except (UnicodeDecodeError, ValueError):
        deny("INVALID_GLB_JSON_PAYLOAD")
        report["issues"] = issues
        return report
    if not isinstance(gltf, dict):
        deny("INVALID_GLB_STRUCTURE")
        report["issues"] = issues
        return report
    categories = ("nodes","meshes","materials","accessors","textures","images","buffers")
    if any(not isinstance(gltf.get(name, []), list) for name in categories):
        deny("INVALID_GLB_ARRAY_STRUCTURE")
        report["issues"] = issues
        return report
    counts = {name: len(gltf.get(name, [])) for name in categories}
    report["structure_counts"] = counts
    limits = {"nodes":MAX_NODES,"meshes":MAX_MESHES,"textures":MAX_TEXTURES,
              "images":MAX_IMAGES,"materials":MAX_MATERIALS,"accessors":MAX_ACCESSORS}
    for name, limit in limits.items():
        if counts[name] > limit:
            deny("GLB_"+name.upper()+"_BUDGET_EXCEEDED")
    required = gltf.get("extensionsRequired", [])
    if not isinstance(required,list) or any(not isinstance(x,str) for x in required):
        deny("INVALID_GLB_REQUIRED_EXTENSION_LIST")
        required = []
    report["required_extensions"] = required
    if set(required) - ALLOWED_REQUIRED_EXTENSIONS:
        deny("UNREVIEWED_REQUIRED_GLTF_EXTENSION")
    if "EXT_meshopt_compression" not in required:
        deny("MESHOPT_DELIVERY_EXTENSION_REQUIRED")
    if "KHR_mesh_quantization" not in required:
        deny("MESHOPT_POSITION_QUANTIZATION_REQUIRED")
    if gltf.get("asset", {}).get("version") != "2.0":
        deny("UNSUPPORTED_GLTF_ASSET_VERSION")
    # Embedded asset requirement. External URLs and data URIs introduce fetching
    # and provenance risks; we require a self-contained GLB for this preview path.
    for typ in ("buffers","images"):
        for record in gltf.get(typ, []):
            if not isinstance(record, dict):
                deny("INVALID_"+typ.upper()+"_RECORD")
            elif "uri" in record:
                deny("EXTERNAL_OR_DATA_URI_ASSET_DISALLOWED")
    for node in gltf.get("nodes", []):
        if not isinstance(node, dict):
            deny("INVALID_GLTF_NODE")
            break
    tris = 0
    try:
        accessors = gltf.get("accessors", [])
        for mesh in gltf.get("meshes", []):
            for primitive in mesh["primitives"]:
                if primitive.get("mode", 4) != 4:
                    deny("NON_TRIANGLE_GEOMETRY_REQUIRES_MANUAL_REVIEW")
                    continue
                idx = primitive.get("indices")
                if idx is None:
                    idx = primitive["attributes"]["POSITION"]
                tris += int(accessors[idx]["count"]) // 3
    except (IndexError,KeyError,ValueError,TypeError):
        deny("MALFORMED_GEOMETRY_ACCESSORS")
    report["triangles"] = tris
    if tris <= 0:
        deny("NO_TRIANGULAR_GEOMETRY")
    if tris > MAX_TRIANGLES:
        deny("MODEL_EXCEEDS_280K_TRIANGLE_PREVIEW_BUDGET")
    author = (provenance or {}).get("upstream_model_author")
    if not author or not isinstance(author,str) or not author.strip():
        deny("PROVENANCE_AUTHOR_MISSING")
    source = (provenance or {}).get("upstream_model")
    if not isinstance(source,str) or not source.startswith("https://"):
        deny("PROVENANCE_ORIGINAL_URL_MISSING")
    expected_digest = (provenance or {}).get("derivative_sha256")
    if expected_digest != report["input_sha256"]:
        deny("MODEL_SOURCE_DIGEST_MISMATCH")
    license_url = (provenance or {}).get("license_url")
    if not isinstance(license_url,str) or not license_url.startswith("https://"):
        deny("LICENSE_URL_UNVERIFIED")
    report["author_claim"] = author if isinstance(author,str) else None
    report["license_claim"] = license_url if isinstance(license_url,str) else None
    report["technical_check_passed"] = not issues
    report["issues"] = issues
    # A valid technical preflight is not permission to publish a model.
    report["status"] = "TECHNICAL_PREVIEW_REVIEW_ONLY" if not issues else "TECHNICAL_PREVIEW_REJECTED"
    report["release_status"] = "HOLD_CANONICAL_SITE_GRANT_IP_RIGHTS_AND_PHYSICAL_DEVICE_TEST"
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--receipt", type=Path,
                        help="Create-only report path. Never updates WordPress or EmpireDB.")
    args = parser.parse_args()
    if args.model.stat().st_size > MAX_MODEL_BYTES:
        h = hashlib.sha256()
        with args.model.open("rb") as source:
            while chunk := source.read(1_048_576):
                h.update(chunk)
        result = {
            "schema": "empire.agency.meshopt_glb_admission_review.v9",
            "status": "TECHNICAL_PREVIEW_REJECTED",
            "release_status": "HOLD_CANONICAL_SITE_GRANT_IP_RIGHTS_AND_PHYSICAL_DEVICE_TEST",
            "input_sha256": h.hexdigest(),
            "input_bytes": args.model.stat().st_size,
            "technical_check_passed": False,
            "commercial_release_eligible": False,
            "site_grant_verified": False,
            "rights_owner_verified": False,
            "model_brand_trademarks_cleared": False,
            "device_gpu_test_verified": False,
            "production_changes": False,
            "issues": ["MODEL_EXCEEDS_5MB_OPTIMIZED_DELIVERY_BUDGET"],
            "on_rejection": FALLBACK,
        }
    else:
        raw = args.model.read_bytes()
        result = check_model_bytes(raw,json.loads(args.provenance.read_text()))
    out=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        with args.receipt.open("x") as handle:
            handle.write(out)
    print(out,end="")
    return 0 if result["technical_check_passed"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
