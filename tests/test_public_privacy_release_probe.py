"""Public privacy pre-release audit must only report evidence, never claim approval."""
from email.message import Message
from pathlib import Path

from scripts import probe_public_privacy_release_readonly as mod


def fake_headers(**kwargs):
    m = Message()
    for k,v in kwargs.items():
        m[k]=v
    return m


class FakeResponse:
    status=200
    headers=fake_headers(**{"Cache-Control": "no-store"})
    def __enter__(self): return self
    def __exit__(self,*args): return False


def test_origin_reads_have_no_request_body_or_tracking_side_effects():
    requested=[]
    def opener(url,timeout):
        requested.append((url,timeout))
        return FakeResponse()
    result=mod.read_origin("/roofing",opener=opener)
    assert requested==[("http://127.0.0.1/roofing",4)]
    assert result["origin_http_status"]==200
    assert result["no_store_header_observed"] is True
    assert result["set_cookie_header_observed"] is False
    assert result["browser_cookie_absence_globally_proven"] is False


def test_ignored_comment_does_not_invent_configured_retention():
    config=mod.active_journal_retention(
        "#MaxRetentionSec=2week\n"
        "#SystemMaxUse=5G\n"
        "MaxFileSec=1month\n"
        "Storage=persistent\n"
    )
    assert config["explicit_retention_seconds"] is None
    assert config["configured_no_retention_limit_unverified"] is True
    assert config["actual_journal_record_lifetime_verified"] is False
    assert config["max_file_age_config"]=="1month"


def test_explicit_active_retention_is_not_taken_as_actual_deletion_proof():
    config=mod.active_journal_retention("MaxRetentionSec=2week\nSystemMaxUse=3G")
    assert config["explicit_retention_seconds"]=="2week"
    assert config["configured_no_retention_limit_unverified"] is False
    assert config["actual_journal_record_lifetime_verified"] is False


def test_source_inventory_is_bounded_and_never_claims_proxy_absence(tmp_path):
    src=tmp_path/"apps/empire-public-site/src"
    src.mkdir(parents=True)
    (src/"page.tsx").write_text("document.cookie='x';\nlocalStorage.getItem('t')")
    result=mod.static_browser_source_inventory(tmp_path)
    assert result["status"]=="SOURCE_PATTERN_REVIEW_ONLY"
    assert result["source_signal_file_counts"]["localstorage"]==1
    assert result["source_signal_file_counts"]["cookie_api"]==1
    assert result["compiled_js_or_cloudflare_exhaustively_reviewed"] is False
    (src/"huge.js").write_text("a"*1_000_001)
    assert mod.static_browser_source_inventory(tmp_path)["status"]=="OVERSIZE_SOURCE_NOT_REVIEWED"


def test_live_release_never_promoted_from_healthy_pages(tmp_path):
    src=tmp_path/"apps/empire-public-site/src"
    src.mkdir(parents=True)
    (src/"page.tsx").write_text("export default function Page() {}")
    route_calls=[]
    def origin(route):
        route_calls.append(route)
        return {"route":route,"origin_http_status":404 if route in ("/privacy","/terms") else 200,
                "set_cookie_header_observed":False,"no_store_header_observed":True,
                "noindex_header_observed":False,"browser_cookie_absence_globally_proven":False}
    command_calls=[]
    def cmd(args):
        command_calls.append(args)
        if args[0]=="systemd-analyze":
            return "#MaxRetentionSec=1day\n"
        return "Archived and active journals take up 3.8G in the file system."
    report=mod.observe(tmp_path,origin_probe=origin,command=cmd)
    assert route_calls==list(mod.ROUTES)
    assert command_calls==[["systemd-analyze","cat-config","systemd/journald.conf"],
                           ["journalctl","--disk-usage","--no-pager"]]
    assert report["legal_routes_unpublished"]=={"/privacy":True,"/terms":True}
    assert report["legal_release_verified"] is False
    assert report["traffic_authorized"] is False
    assert report["journal_records_read"] is False
    assert report["personal_data_extracted"] is False
    assert report["recording_notice_consent_access_retention_verified"] is False


def test_absent_journal_and_origin_preserve_unknown_not_false_assurance(tmp_path):
    result=mod.observe(tmp_path,
        origin_probe=lambda route:{"route":route,"origin_http_status":None,"result":"LOCAL_ORIGIN_NOT_VERIFIED"},
        command=lambda args:None)
    assert result["journal_config"]["actual_journal_record_lifetime_verified"] is False
    assert result["journal_disk_use_metadata_available"] is False
    assert result["legal_release_verified"] is False
    assert result["cloudflare_or_full_browser_storage_audit_complete"] is False
    assert not any(result["legal_routes_unpublished"].values())
