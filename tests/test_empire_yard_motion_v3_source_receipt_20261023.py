"""Native WordPress v3 interactive showroom / lazy Three.js acceptance receipt."""
from pathlib import Path
from hashlib import sha256
import gzip
import json
import re
import subprocess
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOCS=ROOT/"docs/commercial"
RECEIPT=DOCS/"EMPIRE_CAR_YARD_REACT_MOTION_V3_BROWSER_ACCEPTANCE_20261023.json"

def source():
    return json.loads(RECEIPT.read_text())

def test_genuine_wordpress_mariadb_chromium_interactions_and_restore():
    r=source()
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==40
    assert all(r["browser_checks"].values())
    for name in (
        "native_wordpress_es_module_loaded",
        "3d_chunk_requested_separately",
        "real_three_js_webgl_canvas_rendered",
        "real_view_and_paint_controls_rendered",
        "side_view_interaction_state",
        "paint_palette_interaction_state",
        "all_vehicle_controls_are_real_buttons",
        "webgl_is_active_in_visible_hero",
        "offscreen_scene_unmounted_to_save_gpu",
        "returning_to_hero_restores_scene",
        "desktop_no_horizontal_overflow",
        "mobile_no_horizontal_overflow",
        "staff_hold_receipt",
        "staff_confirmation_receipt",
        "staff_cancel_receipt",
    ):
        assert r["browser_checks"][name] is True,name
    assert r["wordPress_mysql_same_runtime"] is True
    assert r["loopback_only_http"] is True
    assert r["mariadb_unix_socket_only"] is True
    assert r["production_changes"] is False
    assert r["synthetic_data_only"] is True
    assert r["customer_bookings_enabled"] is False
    assert r["outbound_or_payments_enabled"] is False
    assert r["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["restore_verified"]["booking_audit_events"]==3
    assert len(r["screenshots"])==4
    for name,meta in r["screenshots"].items():
        file=DOCS/"car_yard_react_browser_evidence_v3"/name
        assert file.is_file(),name
        assert file.stat().st_size==meta["bytes"]
        assert sha256(file.read_bytes()).hexdigest()==meta["sha256"]

def test_source_manifest_and_real_async_es_module_bundle():
    r=source()
    for rel,digest in r["source_manifest_sha256"].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel
    main=(THEME/"src/main.jsx").read_text()
    scene=(THEME/"src/ShowroomScene.jsx").read_text()
    config=(THEME/"vite.config.mjs").read_text()
    functions=(THEME/"functions.php").read_text()
    assert "React.lazy(() => import('./ShowroomScene.jsx'))" in main
    assert "IntersectionObserver" in main
    assert "visibilitychange" in main
    assert "data-camera-view=" in main
    assert "data-paint-finish=" in main
    assert "aria-pressed" in main
    assert "role=\"status\"" in main
    assert "Suspense" in main
    assert "const angle = view === 'front'" in scene
    assert "color={paint.body}" in scene and "color={paint.roof}" in scene
    assert "formats: ['es']" in config
    assert "chunkFileNames:" in config
    assert "wp_enqueue_script_module" in functions
    assert "wp_mail(" not in functions and "register_rest_route" not in functions
    assert "fetch(" not in main and "fetch(" not in scene
    assert "https://" not in main and "http://" not in main
    chunks=list((THEME/"dist").glob("yard-ShowroomScene-*.js"))
    entry=list((THEME/"dist").glob("yard-main-*.js"))
    assert len(chunks)==len(entry)==1
    assert (THEME/"dist/yard.js").read_text().strip().startswith('import "./yard-main-')
    assert b"data-react-showroom" in entry[0].read_bytes()
    assert b"showroom-webgl" in chunks[0].read_bytes()
    assert len(gzip.compress(entry[0].read_bytes(),mtime=0)) < 200000

def test_no_handwritten_css_and_no_new_runtime_dependencies():
    css=(THEME/"style.css").read_text()
    assert re.sub(r"/\\*.*?\\*/", "", css, flags=re.DOTALL).strip()==""
    assert (THEME/"src/tailwind.css").read_text().splitlines()==[
        '@import "tailwindcss";', '@source "../templates";', '@source "../parts";'
    ]
    deps=json.loads((THEME/"package.json").read_text())["dependencies"]
    assert "motion" in deps and "@react-three/fiber" in deps and "@react-three/drei" in deps
    assert "gsap" not in deps and "lenis" not in deps

def test_historical_v2_proof_still_pinned_to_original_commit():
    receipt=json.loads((DOCS/"EMPIRE_CAR_YARD_REACT_THREE_DESIGN_V2_ACCEPTANCE_20261022.json").read_text())
    commit="9135648ca0a924bc32aa3722e6177164a9c7bfc2"
    for rel,expected in receipt["source_manifest_sha256"].items():
        original=subprocess.run(["git","show",commit+":"+rel],cwd=ROOT,
                                check=True,capture_output=True).stdout
        assert sha256(original).hexdigest()==expected,rel

def test_wordpress_installable_motion_v3_preview_has_all_chunks():
    archive=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-motion-v3-preview.zip"
    assert archive.is_file()
    assert sha256(archive.read_bytes()).hexdigest()=="6efc0d008f1743c13752d8abb91e6c1470105f8264afa0e101ef41ebc6299bbf"
    with ZipFile(archive) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert all(x.startswith("empire-yard-atelier/") for x in names)
        assert "empire-yard-atelier/functions.php" in names
        assert "empire-yard-atelier/dist/yard.js" in names
        assert "empire-yard-atelier/dist/yard.css" in names
        assert len([x for x in names if "yard-main-" in x])==1
        assert len([x for x in names if "yard-ShowroomScene-" in x])==1
        assert not any("node_modules" in x or "test" in x for x in names)
