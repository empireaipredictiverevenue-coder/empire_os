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
