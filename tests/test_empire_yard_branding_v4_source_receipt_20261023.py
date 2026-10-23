"""Native WordPress admin-saved agency branding, interior page and safe link receipt."""
from pathlib import Path
from hashlib import sha256
import gzip
import json
import re
from zipfile import ZipFile
import subprocess

V4_COMMIT="774b539b68709f5e5cd53259988c9b2f6465af09"

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOCS=ROOT/"docs/commercial"
RECEIPT=DOCS/"EMPIRE_CAR_YARD_BRANDING_V4_BROWSER_ACCEPTANCE_20261023.json"

def data():
    return json.loads(RECEIPT.read_text())

def v4_original(relative):
    return subprocess.run(
        ["git","show",V4_COMMIT+":"+relative],
        cwd=ROOT,check=True,capture_output=True,
    ).stdout
def theme_v4(path):
    return v4_original(
        "prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/"+path)

def test_admin_save_brand_reaches_home_and_stock_header_footer_in_real_wp():
    r=data()
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==58
    assert all(r["browser_checks"].values())
    for name in (
        "branding_admin_page_200", "branding_form_registered",
        "wordpress_admin_branding_saved","configured_brand_name_rendered",
        "configured_brand_strapline_rendered","configured_hero_headline_rendered",
        "configured_accent_tailwind_applied","configured_contact_remains_internal",
        "external_contact_path_rejected_on_save",
        "configured_stock_page_200","configured_stock_header_uses_saved_brand",
        "configured_stock_footer_uses_saved_brand",
        "configured_stock_accent_from_tailwind",
        "configured_stock_contact_link_stays_internal",
        "inventory_still_available_after_brand_change",
        "real_three_js_webgl_canvas_rendered","offscreen_scene_unmounted_to_save_gpu",
        "returning_to_hero_restores_scene","desktop_no_horizontal_overflow",
        "mobile_no_horizontal_overflow","staff_hold_receipt",
        "staff_confirmation_receipt","staff_cancel_receipt",
    ):
        assert r["browser_checks"][name] is True,name
    assert r["wordPress_mysql_same_runtime"] is True
    assert r["mariadb_unix_socket_only"] is True
    assert r["loopback_only_http"] is True
    assert r["production_changes"] is False
    assert r["synthetic_data_only"] is True
    assert r["customer_bookings_enabled"] is False
    assert r["outbound_or_payments_enabled"] is False
    assert r["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["restore_verified"]["booking_audit_events"]==3

def test_exact_v4_source_and_screenshot_receipts():
    r=data()
    assert len(r["source_manifest_sha256"])>=16
    for rel,hash_expected in r["source_manifest_sha256"].items():
        assert sha256(v4_original(rel)).hexdigest()==hash_expected,rel
    assert len(r["screenshots"])==4
    for name,metadata in r["screenshots"].items():
        screenshot=DOCS/"car_yard_react_browser_evidence_v4"/name
        assert screenshot.is_file(),name
        assert screenshot.stat().st_size==metadata["bytes"]
        assert sha256(screenshot.read_bytes()).hexdigest()==metadata["sha256"]

def test_native_wordpress_admin_registration_and_no_external_contact():
    php=theme_v4("functions.php").decode()
    assert "register_setting('empire_yard_branding', 'empire_yard_brand_v1'" in php
    assert "add_theme_page('Showroom Branding'" in php
    assert "current_user_can('edit_theme_options')" in php
    assert "settings_fields('empire_yard_branding')" in php
    assert "sanitize_text_field" in php and "sanitize_textarea_field" in php
    assert "preg_match" in php
    assert "JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT" in php
    assert "type=\"application/json\"" in php
    assert "wp_enqueue_script_module" in php
    assert "show_in_rest' => false" in php
    assert "wp_mail(" not in php and "register_rest_route(" not in php
    assert "wp_remote_post(" not in php
    assert "empire_yard_site_nav" in php
    assert "empire_yard_site_footer" in php
    assert "[empire_yard_site_nav]" in theme_v4("parts/header.html").decode()
    assert "[empire_yard_site_footer]" in theme_v4("parts/footer.html").decode()

def test_react_brand_sanitization_and_static_tailwind_palettes():
    source=theme_v4("src/main.jsx").decode()
    assert "getBrandSettings()" in source
    assert "brandPalettes" in source
    assert "data-brand-accent" in source
    assert "brand.contact_path" in source
    assert "Object.prototype.hasOwnProperty.call(brandPalettes" in source
    assert "document.getElementById('empire-yard-brand-settings')" in source
    for name in ("gold:", "ice:", "copper:"):
        assert name in source
    css=theme_v4("style.css").decode()
    assert re.sub(r"/\\*.*?\\*/", "", css, flags=re.DOTALL).strip()==""
    assert theme_v4("src/tailwind.css").decode().splitlines()==[
        '@import "tailwindcss";','@source "../templates";',
        '@source "../parts";','@source "../functions.php";',
    ]
    main=theme_v4("dist/yard-main-CTmQ-F4H.js")
    scene=theme_v4("dist/yard-ShowroomScene-1n8hcRFt.js")
    assert len(gzip.compress(main,mtime=0))<200000
    assert b"data-react-showroom" in main
    assert b"showroom-webgl" in scene

def test_installable_wordpress_v4_preview_has_modules_and_theme_parts():
    artifact=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-branding-v4-preview.zip"
    assert artifact.is_file()
    with ZipFile(artifact) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert all(n.startswith("empire-yard-atelier/") for n in names)
        for item in ("functions.php","style.css","dist/yard.js","dist/yard.css",
                     "parts/header.html","parts/footer.html"):
            assert "empire-yard-atelier/"+item in names
        assert len([n for n in names if "yard-main-" in n])==1
        assert len([n for n in names if "yard-ShowroomScene-" in n])==1
        assert not any("node_modules" in n or "private-key" in n for n in names)
