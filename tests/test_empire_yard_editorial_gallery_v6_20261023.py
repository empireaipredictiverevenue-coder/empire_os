"""V6 real photographic editorial gallery and native WordPress media override."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier"
DOC=ROOT/"docs/commercial"
RECEIPT=DOC/"EMPIRE_CAR_YARD_EDITORIAL_V6_BROWSER_ACCEPTANCE_20261023.json"

def receipt():
    return json.loads(RECEIPT.read_text())

# Each historic V6 acceptance receipt is fixed to its actual upstream commit,
# never rewritten to pretend today's theme must still equal yesterday's V6.
V6_COMMIT="2166bf8fa87221390043e80c6c9cd7d3763baaa9"
def original_v6(relative_path):
    return subprocess.run(
        ["git","show",V6_COMMIT+":"+relative_path],cwd=ROOT,
        check=True,capture_output=True,
    ).stdout

def test_real_wp_browser_photography_media_picker_and_existing_business_functions():
    r=receipt()
    assert r["status"]=="WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS"
    assert r["browser_check_count"]==len(r["browser_checks"])==84
    assert all(r["browser_checks"].values())
    for key in (
        "v6_real_editorial_photos_loaded",
        "v6_photos_locally_served_in_child_theme",
        "v6_photo_alt_text_and_lazy_decode",
        "v6_photo_credits_visible_and_link_to_real_sources",
        "v6_desktop_scene_restored_before_screenshot",
        "v6_hero_real_3d_canvas_visible_when_captured",
        "v6_mobile_editorial_photographs_rendered_before_screenshot",
        "v6_wp_media_picker_controls_rendered",
        "v6_media_picker_script_enqueued_in_wp_admin",
        "v6_native_wordpress_media_modal_opens",
        "v6_wp_selected_media_replaced_second_photo",
        "v6_remaining_fallback_photo_sources_still_local",
        "v6_replaced_media_has_no_false_unsplash_credit",
        "v5_mobile_opt_in_avoids_automatic_3d_download",
        "v5_mobile_3d_chunk_load_recorded_after_opt_in",
        "external_contact_path_rejected_on_save",
        "staff_hold_receipt","staff_confirmation_receipt","staff_cancel_receipt",
        "all_external_browser_requests_blocked",
    ):
        assert r["browser_checks"][key] is True,key
    assert r["restore_verified"]["status"]=="NATIVE_WP_MYSQL_RESTORE_PASS"
    assert r["restore_verified"]["booking_audit_events"]==3
    assert r["production_changes"] is False
    assert r["customer_bookings_enabled"] is False
    assert r["synthetic_data_only"] is True
    assert r["outbound_or_payments_enabled"] is False

def test_real_local_photo_bytes_provenance_and_original_author_credit():
    manifest=json.loads((THEME/"assets/editorial/PHOTO_PROVENANCE.json").read_text())
    assert manifest["schema"]=="empire.agency.editorial_photo_sources.v1"
    assert manifest["license_url"]=="https://unsplash.com/license"
    assert manifest["production_release"].startswith("HOLD")
    assert len(manifest["photos"])==3
    seen=set()
    for photo in manifest["photos"]:
        assert photo["photographer"] and photo["photo_page"].startswith("https://unsplash.com/photos/")
        assert photo["file"] not in seen
        seen.add(photo["file"])
        image=THEME/"assets/editorial"/photo["file"]
        assert image.is_file()
        data=image.read_bytes()
        assert data[0:4]==b"RIFF" and data[8:12]==b"WEBP"
        assert len(data)==photo["local_bytes"]
        assert sha256(data).hexdigest()==photo["local_sha256"]
        assert image.stat().st_size<350000
        assert photo["width"]>=1200 and photo["height"]>=850

def test_immutable_v6_runtime_hashes_and_actual_screenshots():
    r=receipt()
    assert len(r["source_manifest_sha256"])>=20
    for rel,expected in r["source_manifest_sha256"].items():
        assert sha256(original_v6(rel)).hexdigest()==expected,rel
    assert len(r["screenshots"])==5
    for name,meta in r["screenshots"].items():
        file=DOC/"car_yard_react_browser_evidence_v6"/name
        assert file.is_file()
        assert file.stat().st_size==meta["bytes"]
        assert sha256(file.read_bytes()).hexdigest()==meta["sha256"]

def test_wp_media_is_admin_only_and_no_external_image_urls_can_be_stored():
    php=(THEME/"functions.php").read_text()
    assert "wp_attachment_is_image" in php
    assert "FILTER_VALIDATE_INT" in php
    assert "get_stylesheet_directory_uri()" in php
    assert "wp_get_attachment_image_url" in php
    assert "wp_parse_url(home_url('/'), PHP_URL_HOST)" in php
    assert "current_user_can('edit_theme_options')" in php
    assert "admin_enqueue_scripts" in php
    assert "wp_enqueue_media();" in php
    assert "'show_in_rest' => false" in php
    assert "JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT" in php
    assert "register_rest_route(" not in php and "wp_mail(" not in php
    admin=(THEME/"src/brand-media-picker.js").read_text()
    assert "window.wp.media" in admin
    assert "library: { type: 'image' }" in admin
    assert "url.origin !== location.origin" in admin
    main=(THEME/"src/main.jsx").read_text()
    assert "data-editorial-gallery" in main
    assert "data-editorial-photo" in main
    assert "object-cover" in main
    assert 'loading="lazy"' in main and 'decoding="async"' in main
    assert "editorial_media_urls" in main
    assert "url.origin === location.origin" in main
    assert "src={url}" in main
    assert "Photography reference — not a stock listing" in main
    assert "stock" in main
    css=(THEME/"style.css").read_text()
    assert re.sub(r"/\\*.*?\\*/","",css,flags=re.DOTALL).strip()==""

def test_installable_preview_includes_nonremote_media_and_original_runtime():
    archive=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/dist/empire-yard-atelier-editorial-v6-preview.zip"
    assert archive.exists()
    with ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        names=zipped.namelist()
        assert all(x.startswith("empire-yard-atelier/") for x in names)
        for rel in ("functions.php","src/brand-media-picker.js",
                    "assets/editorial/PHOTO_PROVENANCE.json","assets/editorial/studio-red.webp",
                    "assets/editorial/studio-silver.webp","assets/editorial/studio-detail.webp",
                    "dist/yard.js","dist/yard.css"):
            assert "empire-yard-atelier/"+rel in names,rel
        assert len([x for x in names if "yard-main-" in x])==1
        assert len([x for x in names if "yard-ShowroomScene-" in x])==1
        assert not any("node_modules" in x or ".git" in x for x in names)
