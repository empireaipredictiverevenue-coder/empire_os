"""Static WordPress capability preflight for explicit B2B website requests.

A WordPress block-theme source package is *not* proof of a client-ready
WordPress instance. This read-only reviewer never deploys, emails, creates
leads, pretends a PHP/DB integration test ran, or changes live EmpireOS.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import re

SCHEMA="empire.jev.wordpress_delivery_capability_preflight.v1"
BUYER_SCHEMA="empire.jev.direct_b2b_buying_need_review.v1"
THEME_REQUIRED=(
    "style.css","theme.json","parts/header.html","parts/footer.html",
    "templates/front-page.html","templates/page-services.html",
    "templates/page-about.html","templates/page-areas.html",
    "templates/page-contact.html","templates/page.html",
    "templates/index.html","templates/single.html","templates/404.html",
)
PAGES={
    "home":"front-page.html",
    "services":"page-services.html",
    "about":"page-about.html",
    "areas":"page-areas.html",
    "contact":"page-contact.html",
}
LINKS=("/", "/services/", "/about/", "/areas/", "/contact/")
BLOCK_PATTERN=re.compile(r"<!--\s*(/?)wp:([a-zA-Z0-9-]+)(.*?)-->",re.DOTALL)
JSON_DECODER=json.JSONDecoder()


def validate_blocks(content:str,name:str)->dict[str,Any]:
    stack=[]
    opened=0
    for match in BLOCK_PATTERN.finditer(content):
        closing,slug,trailing=match.groups()
        payload=trailing.strip()
        single=payload.endswith("/")
        if single:
            payload=payload[:-1].strip()
        if payload:
            try:
                obj,remaining=JSON_DECODER.raw_decode(payload)
            except json.JSONDecodeError as e:
                raise ValueError("invalid WordPress block attribute JSON") from e
            if remaining!=len(payload) or not isinstance(obj,dict):
                raise ValueError("invalid block settings")
        if closing:
            if single or payload or not stack or stack.pop()!=slug:
                raise ValueError("unbalanced closing WordPress block in "+name)
        elif not single:
            stack.append(slug)
            opened+=1
        else:
            opened+=1
    if stack or opened==0:
        raise ValueError("open/unclosed or empty block template "+name)
    if "<script" in content.lower() or "<?php" in content.lower():
        raise ValueError("unexpected executable code inside static theme")
    return {"blocks_checked":opened,"balanced":True}


def review_wordpress_delivery(
    source_dir:Path, *, research:Mapping[str,Any]
)->dict[str,Any]:
    root=Path(source_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("missing isolated WordPress block theme")
    if (not isinstance(research,Mapping)
        or research.get("schema_version")!=BUYER_SCHEMA
        or research.get("status")!="EXPLICIT_B2B_SERVICE_REQUESTS_NONCONTACT_OWNER_REVIEW"
        or research.get("verified_business_buyers")!=0
        or research.get("officially_awarded_business_orders")!=0
        or research.get("live_bids_submitted")!=0
        or research.get("outbound_sent")!=0
        or research.get("crm_writes") is not False
        or research.get("execution_authority")!="none"):
        raise ValueError("request evidence cannot be promoted to contract")
    needed={
        "freelancer_40778550":"PLATFORM_SCOPED_APPLICATION_OWNER_REVIEW",
        "reddit_wp_1woeuix":"WEB_BUILD_PORTFOLIO_AND_AGENCY_IDENTITY_GATE",
    }
    rows=research.get("cases")
    if not isinstance(rows,list) or len(rows)!=5:
        raise ValueError("unsupported public source review")
    for case_id,lane in needed.items():
        matches=[r for r in rows if isinstance(r,Mapping) and r.get("case_id")==case_id]
        if (len(matches)!=1 or matches[0].get("research_lane")!=lane
            or matches[0].get("applicant_contact_or_bid_approved") is not False
            or matches[0].get("empire_technical_fulfilment_proven") is not False
            or matches[0].get("purchase_or_payment_contract_verified") is not False):
            raise ValueError("untrusted WordPress buyer request or owner gate")
    manifest={}
    for relative in THEME_REQUIRED:
        path=root/relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size>100000:
            raise ValueError("missing or unsafe theme source: "+relative)
        text=path.read_text(encoding="utf-8")
        manifest[relative]=sha256(text.encode("utf-8")).hexdigest()
        if relative.endswith(".html"):
            validate_blocks(text,relative)
    config=json.loads((root/"theme.json").read_text())
    if (config.get("version")!=3
        or "templateParts" not in config
        or "settings" not in config
        or len(config["templateParts"])!=2):
        raise ValueError("incompatible WordPress theme.json")
    css=(root/"style.css").read_text()
    if (not css.startswith("/*\nTheme Name:")
        or "Requires at least:" not in css
        or "@media(max-width:680px)" not in css
        or "a:focus-visible" not in css
        or "prefers-reduced-motion" not in css):
        raise ValueError("WordPress metadata/mobile/a11y CSS missing")
    nav=(root/"parts/header.html").read_text()
    if "wp:navigation" not in nav or any(('"url":"'+link+'"') not in nav for link in LINKS):
        raise ValueError("all five page routes must have explicit accessible nav")
    for page,template in PAGES.items():
        txt=(root/"templates"/template).read_text()
        if ("wp:template-part" not in txt or '"slug":"header"' not in txt
            or '"slug":"footer"' not in txt):
            raise ValueError("missing shared header/footer on "+page)
        if page!="home" and '"level":1' not in txt:
            raise ValueError("missing page heading for "+page)
    contact=(root/"templates/page-contact.html").read_text()
    lower=contact.lower()
    if (not all(word in lower for word in ("not enabled","privacy","consent"))
        or any(word in lower for word in (
            "method=\"post\"","wp:form","wp_mail(","mailto:","type=\"email\""))):
        raise ValueError("unapproved collection or marketing channel enabled")
    parts=(root/"parts/footer.html").read_text()
    if "Fictional" not in parts and "fictional" not in parts:
        raise ValueError("must mark sample as not a real client case study")
    for rel in THEME_REQUIRED:
        lower=(root/rel).read_text().lower()
        if any(token in lower for token in (
            "guaranteed leads","verified reviews","2000+ satisfied",
            "wordpress.org/plugins/woocommerce","checkout live")):
            raise ValueError("unsupported claims or paid checkout in prototype")
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"WORDPRESS_BLOCK_THEME_STATIC_PREFLIGHT_PASS_RUNTIME_REQUIRED",
        "five_page_local_service_source_layout_verified":True,
        "wordpress_theme_json_v3_verified":True,
        "template_block_comment_balance_verified":True,
        "responsive_css_static_rules_present":True,
        "keyboard_focus_style_present":True,
        "no_active_contact_or_person_data_form":True,
        "theme_file_sha256":dict(sorted(manifest.items())),
        "theme_files_count":len(manifest),
        "source_scope":"FICTIONAL_LOCAL_SERVICE_BLOCK_THEME",
        "wp_php_runtime_available_or_tested":False,
        "wp_core_admin_editor_and_preview_tested":False,
        "wp_plugin_dependency_compatibility_tested":False,
        "wp_seo_metadata_lighthouse_accessibility_audited":False,
        "wp_mail_delivery_spam_rate_limit_consent_tested":False,
        "hosting_ssl_backups_update_and_rollback_tested":False,
        "client_content_asset_ownership_and_transfer_verified":False,
        "native_vehicle_inventory_post_type_implemented":False,
        "native_repair_booking_backend_implemented":False,
        "car_yard_complete_fulfilment_verified":False,
        "agency_client_site_complete_fulfilment_verified":False,
        "sales_claims_or_actual_client_references_proven":0,
        "verified_company_buyers":0,
        "approved_marketplace_bids":0,
        "website_client_handover_authorized":False,
        "commercial_proposals_ready":0,
        "source_customer_contacts_processed":0,
        "outbound_sent":0,
        "database_writes":False,
        "production_changes":False,
        "execution_authority":"none",
    }
