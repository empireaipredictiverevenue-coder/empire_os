"""Build a reproducible OFFLINE WordPress child-theme ZIP; no deployment."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "prototypes/agency_wordpress_service_handoff_20261022"
THEME = BASE / "empire-yard-atelier"
OUTPUT = BASE / "dist/empire-yard-atelier-concept-0.2.0.zip"
INCLUDE = (
    "style.css",
    "functions.php",
    "templates/front-page.html",
    "templates/page.html",
    "parts/header.html",
    "parts/footer.html",
    "dist/yard.js",
    "dist/yard.css",
    "src/inventory-enhance.js",
)

def run() -> dict:
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise FileExistsError("Refuse to replace existing theme release")
    if "Template: empire-local-services" not in (THEME / "style.css").read_text():
        raise ValueError("Not the approved child theme")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, mode="x", compression=ZIP_DEFLATED, compresslevel=9) as zipped:
        for rel in INCLUDE:
            file = THEME / rel
            if not file.is_file() or file.is_symlink():
                raise ValueError("Invalid compiled theme file: " + rel)
            if file.stat().st_size > 3_000_000:
                raise ValueError("Unexpected theme file size")
            info = ZipInfo("empire-yard-atelier/" + rel, date_time=(2026, 10, 22, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = ZIP_DEFLATED
            zipped.writestr(info, file.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    return {
        "status": "OFFLINE_CONCEPT_CHILD_THEME_PACKAGED_NOT_INSTALLED",
        "path": str(OUTPUT.relative_to(ROOT)),
        "bytes": OUTPUT.stat().st_size,
        "sha256": sha256(OUTPUT.read_bytes()).hexdigest(),
        "includes": len(INCLUDE),
        "parent_theme_required": "empire-local-services",
        "public_booking_enabled": False,
    }

if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
