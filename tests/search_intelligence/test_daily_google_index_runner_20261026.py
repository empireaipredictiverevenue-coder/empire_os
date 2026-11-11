from datetime import datetime,timezone
from pathlib import Path
import json
from unittest.mock import patch
import scripts.review_daily_original_google_index_20261026 as mod

def test_first_journal_appearance_reports_missing_provider_not_zeros(capsys):
    with patch.object(mod,"execute",side_effect=OSError("unavailable")):
        with patch("sys.argv",["s","--write-daily"]):
            assert mod.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="ORIGINAL_DAILY_GOOGLE_INDEX_SOURCE_UNAVAILABLE"
    assert result["indexed_verified"] is None
    assert result["unknown_to_google"] is None
    assert result["google_indexing_submissions"]==0

def test_prior_date_is_read_without_rewriting(tmp_path):
    previous={"schema_version":"empire.search.google_index_daily_watch.v1","status":"GOOGLE_INDEX_WATCH_RECORDED"}
    (tmp_path/"google-index-2026-10-24.json").write_text(json.dumps(previous))
    (tmp_path/"irrelevant.log").write_text("other")
    assert mod.scan_previous(tmp_path,"2026-10-26")==previous

def test_private_source_directory_fail_closed(tmp_path):
    # mode 0755 must never store Search Console observations
    tmp_path.chmod(0o755)
    try:
        import pytest
        with pytest.raises(PermissionError):mod.private_dir(tmp_path,create=False)
    finally:
        tmp_path.chmod(0o700)

def test_repeat_current_day_does_not_call_provider(tmp_path):
    tmp_path.chmod(0o700)
    baseline={"schema_version":"empire.search.google_index_daily_watch.v1",
              "scope_checked":5,"indexed_verified":3,"unknown_to_google":2}
    (tmp_path/"google-index-2026-10-26.json").write_text(json.dumps(baseline))
    with patch.object(mod,"urlopen",side_effect=AssertionError("unexpected API call")):
        result=mod.execute(root=tmp_path,write_daily=True,
                           observed=datetime(2026,10,26,20,tzinfo=timezone.utc))
    assert result["status"]=="ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED"
    assert result["indexed_verified"]==3
    assert result["source_updated"] is False



def _roofing_provider(*, verdicts=("NEUTRAL","NEUTRAL"),
                      coverages=("URL is unknown to Google","URL is unknown to Google"),
                      crawls=(None,None),observed="2026-11-11T22:23:56+00:00"):
    return {"schema_version":"empire.search.owned_roofing_guide_index_inspection.v1",
      "status":"ROOFING_GUIDES_INDEXED_VERSION_INSPECTION_RECORDED",
      "mode":"OBSERVE","site":"sc-domain:empire-ai.co.uk",
      "observed_at":observed,"count":2,
      "items":[{"url":url,"verdict":v,"coverageState":c,
                "lastCrawlTime":at,"google_indexed_version_only":True,
                "live_url_test_performed":False}
                for url,v,c,at in zip(mod.ROOFING_GUIDE_URLS,verdicts,coverages,crawls)],
      "google_live_test_performed":False,"google_indexing_request_sent":False,
      "production_database_writes":False,"website_changed":False,
      "execution_authority":"none"}


class _Response:
    status=200
    def __init__(self,packet):self.packet=packet
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return json.dumps(self.packet).encode()


def test_roofing_guide_daily_watch_records_initial_unknown_without_sales(tmp_path):
    tmp_path.chmod(0o700)
    observed=datetime(2026,11,11,23,30,tzinfo=timezone.utc)
    calls=[]
    def fetch(url,timeout):
        calls.append((url,timeout))
        return _Response(_roofing_provider())
    with patch.object(mod,"urlopen",side_effect=fetch):
        d=mod.review_daily_published_roofing_guides(
          tmp_path,write_daily=True,observed=observed)
    assert d["status"]=="GOOGLE_ROOFING_GUIDE_INDEX_DAILY_RECORDED"
    assert d["scope_checked"]==2 and d["changes_detected"]==0
    assert d["google_reported_indexed_count"]==0
    assert calls==[(mod.GUIDE_API,74)]
    p=tmp_path/"google-roofing-guides-2026-11-11.json"
    assert p.exists() and p.stat().st_mode & 0o077 == 0
    packet=json.loads(p.read_text())
    assert packet["exact_url_states"][mod.ROOFING_GUIDE_URLS[0]]["verdict"]=="NEUTRAL"
    assert packet["actual_search_clicks_verified"] is False
    assert packet["qualified_enquiries_verified"] is False
    assert packet["settled_revenue_verified"] is False
    assert packet["google_indexing_submissions"]==0
    assert packet["execution_authority"]=="none"


def test_roofing_guide_daily_repeat_does_not_request_google_or_overwrite(tmp_path):
    tmp_path.chmod(0o700)
    observed=datetime(2026,11,11,23,30,tzinfo=timezone.utc)
    with patch.object(mod,"urlopen",return_value=_Response(_roofing_provider())):
        mod.review_daily_published_roofing_guides(tmp_path,write_daily=True,observed=observed)
    p=tmp_path/"google-roofing-guides-2026-11-11.json"
    before=p.read_bytes()
    with patch.object(mod,"urlopen",side_effect=AssertionError("duplicate_google_call")):
        d=mod.review_daily_published_roofing_guides(tmp_path,write_daily=True,observed=observed)
    assert d["status"]=="ROOFING_GUIDES_DAILY_ALREADY_RECORDED"
    assert d["provider_requested"] is False
    assert p.read_bytes()==before


def test_roofing_guide_daily_detects_real_indexed_transition_only(tmp_path):
    tmp_path.chmod(0o700)
    prev=datetime(2026,11,11,23,30,tzinfo=timezone.utc)
    with patch.object(mod,"urlopen",return_value=_Response(_roofing_provider())):
        mod.review_daily_published_roofing_guides(tmp_path,write_daily=True,observed=prev)
    changed=_roofing_provider(
        verdicts=("PASS","NEUTRAL"),
        coverages=("Submitted and indexed","URL is unknown to Google"),
        crawls=("2026-11-12T00:12:00Z",None),
        observed="2026-11-12T01:00:00+00:00",
    )
    with patch.object(mod,"urlopen",return_value=_Response(changed)):
        d=mod.review_daily_published_roofing_guides(
          tmp_path,write_daily=True,
          observed=datetime(2026,11,12,1,30,tzinfo=timezone.utc))
    assert d["changes_detected"]==1
    assert d["google_reported_indexed_count"]==1
    packet=json.loads((tmp_path/"google-roofing-guides-2026-11-12.json").read_text())
    assert packet["previous_watch_exists"] is True
    assert packet["change_count"]==1
    change=packet["changes_since_previous_review"][0]
    assert change["url"]==mod.ROOFING_GUIDE_URLS[0]
    assert change["new_google_indexed_version_observed"] is True
    assert packet["qualified_enquiries_verified"] is False
    assert packet["settled_revenue_verified"] is False


def test_roofing_guide_monitor_rejects_wrong_provider_scope_and_no_writes(tmp_path):
    tmp_path.chmod(0o700)
    bad=_roofing_provider()
    bad["items"][1]["url"]="https://attacker.example/not-owned"
    with patch.object(mod,"urlopen",return_value=_Response(bad)):
        import pytest
        with pytest.raises(ValueError,match="ONLY_TWO_PUBLISHED"):
            mod.review_daily_published_roofing_guides(
              tmp_path,write_daily=True,
              observed=datetime(2026,11,11,23,30,tzinfo=timezone.utc))
    assert not list(tmp_path.glob("google-roofing-guides-*.json"))


def test_roofing_guide_monitor_unavailable_does_not_write_false_zero(tmp_path):
    tmp_path.chmod(0o700)
    with patch.object(mod,"urlopen",side_effect=OSError("source_down")):
        import pytest
        with pytest.raises(OSError):
            mod.review_daily_published_roofing_guides(
              tmp_path,write_daily=True,
              observed=datetime(2026,11,11,23,30,tzinfo=timezone.utc))
    assert not list(tmp_path.glob("google-roofing-guides-*.json"))


def test_roofing_guide_monitor_rejects_stale_google_source(tmp_path):
    tmp_path.chmod(0o700)
    with patch.object(mod,"urlopen",return_value=_Response(_roofing_provider())):
        import pytest
        with pytest.raises(ValueError,match="STALE"):
            mod.review_daily_published_roofing_guides(
              tmp_path,write_daily=False,
              observed=datetime(2026,11,12,9,30,tzinfo=timezone.utc))



def test_original_daily_owner_invokes_guide_index_once(capsys):
    base={"status":"ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED",
          "indexed_verified":1,"unknown_to_google":4}
    calls=[]
    with patch.object(mod,"execute",return_value=base):
        with patch.object(
            mod,"review_daily_published_roofing_guides",
            side_effect=lambda **kw: calls.append(kw) or {
              "status":"GOOGLE_ROOFING_GUIDE_INDEX_DAILY_RECORDED",
              "scope_checked":2,"changes_detected":0,
              "new_timer_or_service":False,
            }):
            with patch("sys.argv",["seo-original","--write-daily"]):
                assert mod.main()==0
    packet=json.loads(capsys.readouterr().out)
    assert calls==[{"write_daily":True}]
    assert packet["seo_published_roofing_guide_index"]["scope_checked"]==2
    assert packet["status"]=="ORIGINAL_DAILY_INDEX_WATCH_ALREADY_RECORDED"


def test_guide_source_failure_does_not_break_original_daily_owner(capsys):
    base={"status":"ORIGINAL_DAILY_GOOGLE_INDEX_SOURCE_UNAVAILABLE",
          "reason_code":"OSError",
          "indexed_verified":None,"unknown_to_google":None}
    with patch.object(mod,"execute",return_value=base):
        with patch.object(mod,"review_daily_published_roofing_guides",
                          side_effect=OSError("google temporarily down")):
            with patch("sys.argv",["seo-original","--write-daily"]):
                assert mod.main()==0
    packet=json.loads(capsys.readouterr().out)
    assert packet["status"]=="ORIGINAL_DAILY_GOOGLE_INDEX_SOURCE_UNAVAILABLE"
    guide=packet["seo_published_roofing_guide_index"]
    assert guide["status"]=="ROOFING_GUIDE_GOOGLE_INDEX_SOURCE_UNAVAILABLE"
    assert guide["google_reported_indexed_count"] is None
    assert guide["changes_detected"] is None
    assert guide["google_indexing_submissions"]==0
