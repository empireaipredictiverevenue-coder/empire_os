"""WordPress theme source preflight: no simulated client-ready claim."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import shutil
import pytest

from empire_os.jev_wp_delivery_capability import (
    THEME_REQUIRED,review_wordpress_delivery,validate_blocks,
)
from scripts.review_jev_wordpress_delivery_20261022 import run

ROOT=Path(__file__).resolve().parents[1]
THEME=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-local-services"
RESEARCH=ROOT/"docs/commercial/JEV_DIRECT_B2B_PURCHASE_NEED_PRIORITY_20261022.json"
RECEIPT=ROOT/"docs/commercial/JEV_WORDPRESS_SERVICE_HANDOVER_PREFLIGHT_20261022.json"


def demand():
    return json.loads(RESEARCH.read_text())


def staged(tmp_path:Path)->Path:
    dst=tmp_path/"staged-wordpress-theme"
    shutil.copytree(THEME,dst)
    return dst


def assess(root=None,source=None):
    return review_wordpress_delivery(
        THEME if root is None else root,
        research=demand() if source is None else source,
    )


def test_actual_theme_has_all_five_native_page_routes():
    report=assess()
    assert report["status"]=="WORDPRESS_BLOCK_THEME_STATIC_PREFLIGHT_PASS_RUNTIME_REQUIRED"
    assert report["theme_files_count"]==13
    assert set(report["theme_file_sha256"])==set(THEME_REQUIRED)
    assert report["five_page_local_service_source_layout_verified"] is True
    assert report["wordpress_theme_json_v3_verified"] is True
    assert report["responsive_css_static_rules_present"] is True
    assert report["keyboard_focus_style_present"] is True
    assert report["template_block_comment_balance_verified"] is True


def test_car_yard_inventory_booking_not_misrepresented_by_service_site():
    report=assess()
    assert report["native_vehicle_inventory_post_type_implemented"] is False
    assert report["native_repair_booking_backend_implemented"] is False
    assert report["car_yard_complete_fulfilment_verified"] is False
    assert report["agency_client_site_complete_fulfilment_verified"] is False
    assert report["commercial_proposals_ready"]==0


def test_no_fake_wordpress_runtime_or_live_enquiry_flow():
    report=assess()
    for key in ("wp_php_runtime_available_or_tested",
                "wp_core_admin_editor_and_preview_tested",
                "wp_plugin_dependency_compatibility_tested",
                "wp_seo_metadata_lighthouse_accessibility_audited",
                "wp_mail_delivery_spam_rate_limit_consent_tested",
                "hosting_ssl_backups_update_and_rollback_tested",
                "client_content_asset_ownership_and_transfer_verified",
                "website_client_handover_authorized"):
        assert report[key] is False
    assert report["no_active_contact_or_person_data_form"] is True
    assert report["outbound_sent"]==0
    assert report["database_writes"] is False
    assert report["production_changes"] is False


@pytest.mark.parametrize("remove",[
    "theme.json","style.css","parts/header.html","parts/footer.html",
    "templates/front-page.html","templates/page-about.html",
    "templates/page-contact.html","templates/404.html",
])
def test_essential_theme_files_must_exist(tmp_path,remove):
    root=staged(tmp_path)
    (root/remove).unlink()
    with pytest.raises(ValueError):
        assess(root=root)


def test_unbalanced_nested_native_wp_blocks_fail(tmp_path):
    root=staged(tmp_path)
    path=root/"templates/page-services.html"
    path.write_text(path.read_text().replace("<!-- /wp:group -->","",1))
    with pytest.raises(ValueError,match="unclosed|closing"):
        assess(root=root)


def test_malformed_wp_block_attributes_fail(tmp_path):
    root=staged(tmp_path)
    path=root/"templates/front-page.html"
    path.write_text(path.read_text().replace('"tagName":"header"','"tagName":',1))
    with pytest.raises(ValueError,match="attribute"):
        assess(root=root)


def test_missing_service_navigation_route_fails(tmp_path):
    root=staged(tmp_path)
    path=root/"parts/header.html"
    path.write_text(path.read_text().replace("/services/","/offer/"))
    with pytest.raises(ValueError,match="routes"):
        assess(root=root)


def test_unverified_form_submissions_fail_source_preflight(tmp_path):
    root=staged(tmp_path)
    path=root/"templates/page-contact.html"
    path.write_text(path.read_text().replace(
        "Enquiry collection is not enabled","Enquiry collection is enabled, wp:form"))
    with pytest.raises(ValueError,match="collection"):
        assess(root=root)


def test_missing_accessibility_focus_fails(tmp_path):
    root=staged(tmp_path)
    path=root/"style.css"
    path.write_text(path.read_text().replace("a:focus-visible","a:fake-focus"))
    with pytest.raises(ValueError,match="mobile/a11y"):
        assess(root=root)


def test_missing_wordpress_theme_version_fails(tmp_path):
    root=staged(tmp_path)
    path=root/"theme.json"
    config=json.loads(path.read_text())
    config["version"]=1
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError,match="theme.json"):
        assess(root=root)


@pytest.mark.parametrize("flag,value",[
    ("verified_business_buyers",1),("officially_awarded_business_orders",1),
    ("live_bids_submitted",1),("outbound_sent",1),
    ("crm_writes",True),("execution_authority","execute"),
])
def test_source_cannot_fake_commercial_approval(flag,value):
    s=demand()
    s[flag]=value
    with pytest.raises(ValueError):
        assess(source=s)


def test_public_request_no_manual_bid_authority():
    s=demand()
    s["cases"][0]["applicant_contact_or_bid_approved"]=True
    with pytest.raises(ValueError,match="WordPress buyer request"):
        assess(source=s)


def test_client_claims_not_laundered_by_theme_file(tmp_path):
    root=staged(tmp_path)
    path=root/"templates/page-about.html"
    path.write_text(path.read_text().replace("No fabricated customer reviews","2000+ satisfied clients"))
    with pytest.raises(ValueError,match="unsupported claims"):
        assess(root=root)


def test_readonly_receipt_pinned_without_external_contact_data():
    report=json.loads(RECEIPT.read_text())
    assert report==run() or (
        # Captured observation timestamps may differ on a fresh run.
        report["theme_file_sha256"]==run()["theme_file_sha256"]
        and report["status"]==run()["status"])
    assert report["original_demand_receipt_sha256"]==sha256(RESEARCH.read_bytes()).hexdigest()
    assert report["theme_files_count"]==13
    assert report["php_executable_observed_on_host"] is False
    assert report["docker_user_daemon_access_observed"] is False
    assert report["wordpress_run_or_browser_rendering_performed"] is False
    assert report["website_team_only_internal_source_package"] is True
    assert report["existing_empire_public_site_replaced"] is False
    assert report["approved_marketplace_bids"]==0
    assert report["outbound_sent"]==0
    assert report["execution_authority"]=="none"
    body=RECEIPT.read_text()
    assert "@" not in body
    assert "contact_email" not in body
    assert "personal_phone" not in body


def test_offline_theme_zip_contains_only_the_verified_source(tmp_path):
    from zipfile import ZipFile
    from scripts.package_agency_wp_capability_20261022 import validate_and_pack
    path=tmp_path/"empire-local-services-demo.zip"
    result=validate_and_pack(destination=path)
    assert result["status"]=="OFFLINE_WORDPRESS_SOURCE_PACKAGE_ONLY"
    assert result["theme_files"]==13
    assert result["wordpress_runtime_or_plugin_compatibility_tested"] is False
    assert result["current_client_delivery_ready"] is False
    assert result["production_changes"] is False
    assert result["zip_sha256"]==sha256(path.read_bytes()).hexdigest()
    with ZipFile(path,"r") as z:
        assert set(z.namelist())=={"empire-local-services/"+item for item in THEME_REQUIRED}
        assert all(".." not in item and not item.startswith("/") for item in z.namelist())
        assert all(z.read("empire-local-services/"+item)==(THEME/item).read_bytes()
                   for item in THEME_REQUIRED)


def test_offline_packaging_refuses_silent_package_replacement(tmp_path):
    from scripts.package_agency_wp_capability_20261022 import validate_and_pack
    path=tmp_path/"same.zip"
    validate_and_pack(destination=path)
    with pytest.raises(ValueError,match="overwrite"):
        validate_and_pack(destination=path)


def test_reproducible_offline_zip_hash(tmp_path):
    from scripts.package_agency_wp_capability_20261022 import validate_and_pack
    one=validate_and_pack(destination=tmp_path/"a.zip")
    two=validate_and_pack(destination=tmp_path/"b.zip")
    assert one["zip_sha256"]==two["zip_sha256"]
    assert one["zip_bytes"]==two["zip_bytes"]


def test_handover_document_never_claims_approved_live_wordpress_or_client_portfolio():
    p=ROOT/"docs/commercial/EMPIRE_JEV_WORDPRESS_DELIVERY_CAPABILITY_OWNER_HANDOFF_20261022.md"
    t=p.read_text().lower()
    assert "not implemented" in t
    assert "not tested" in t
    assert "no marketing mail, bids" in t
    assert "car-yard inventory" in t
    assert "wordpress runtime" in t
