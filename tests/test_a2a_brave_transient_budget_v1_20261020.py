"""Bounded Brave access: no persistent result URLs or over-credit usage."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest

from empire_os.a2a_brave_transient_budget_v1 import (
    MAX_PER_DAY,MAX_PER_MONTH,reserve_single_request,
)
from scripts.run_a2a_brave_transient_search_20261020 import execute_once

NOW=datetime(2026,10,20,16,tzinfo=timezone.utc)


def test_dry_run_never_reserves_credit(tmp_path):
    x=reserve_single_request(tmp_path/"ledger",now=NOW,dry_run=True)
    assert x["request_permitted"] is True
    assert x["request_reserved"] is False
    assert x["daily_requests"]==0
    assert not (tmp_path/"ledger"/"brave_transient_request_counters_v1.json").exists()


def test_per_day_limit_and_no_results_in_ledger(tmp_path):
    root=tmp_path/"ledger"
    a=reserve_single_request(root,now=NOW)
    b=reserve_single_request(root,now=NOW)
    c=reserve_single_request(root,now=NOW)
    assert (a["request_reserved"],b["request_reserved"],c["request_reserved"]) == (True,True,False)
    assert c["daily_requests"]==MAX_PER_DAY
    assert c["monthly_requests"]==2
    ledger=(root/"brave_transient_request_counters_v1.json").read_text()
    assert "result" not in ledger and "url" not in ledger and "query" not in ledger
    assert (root/"brave_transient_request_counters_v1.json").stat().st_mode & 0o777 == 0o600


def test_month_resets_counters_without_resetting_daily_record(tmp_path):
    root=tmp_path/"ledger"
    reserve_single_request(root,now=NOW)
    x=reserve_single_request(root,now=NOW+timedelta(days=2))
    assert x["monthly_requests"]==2 and x["daily_requests"]==1
    y=reserve_single_request(root,now=datetime(2026,11,1,tzinfo=timezone.utc))
    assert y["monthly_requests"]==1 and y["daily_requests"]==1
    with pytest.raises(ValueError,match="BUDGET_CLOCK_ROLLBACK"):
        reserve_single_request(root,now=NOW)


def test_transient_results_count_only_and_never_serialized(tmp_path):
    calls=[]
    class Response:
        status_code=200
        content=b'{"web":{"results":[{"title":"Sensitive","url":"https://private.example","description":"secret contact"}]}}'
        def json(self):
            return json.loads(self.content)
    def get(url,**kw):
        calls.append((url,kw))
        return Response()
    root=tmp_path/"ledger"
    value=execute_once("tampa_roofing",root=root,get=get,key="long-secure-synthetic-test-key")
    assert value["state"]=="BRAVE_WEB_RESULTS_USED_TRANSIENTLY"
    assert value["transient_result_count_seen"]==1
    assert value["search_result_records_stored"]==0
    assert value["buyer_scout_writes"]==0
    assert len(calls)==1
    assert calls[0][1]["allow_redirects"] is False
    assert "Sensitive" not in json.dumps(value)
    assert "private.example" not in json.dumps(value)
    files=" ".join(p.read_text() for p in root.glob("*.json"))
    assert "private.example" not in files and "Sensitive" not in files
    assert "roofing contractors" not in files


def test_failures_count_as_use_and_queries_are_never_retried(tmp_path):
    called=[]
    def get(*args,**kwargs):
        called.append(1)
        raise RuntimeError("key=SECRET")
    root=tmp_path/"ledger"
    x=execute_once("nyc_general_contractors",root=root,get=get,key="long-synthetic-api-key-123")
    assert x["state"]=="BRAVE_REQUEST_FAILED"
    assert len(called)==1
    assert x["monthly_requests_used"]==1
    assert "SECRET" not in json.dumps(x)
    assert "SECRET" not in (root/"brave_transient_request_counters_v1.json").read_text()


def test_unknown_market_and_bad_key_cannot_spend(tmp_path):
    called=[]
    def get(*args,**kwargs):
        called.append(True)
    with pytest.raises(ValueError,match="UNAPPROVED_MARKET"):
        execute_once("all worldwide markets",root=tmp_path,get=get,key="long-synthetic-key")
    x=execute_once("tampa_roofing",root=tmp_path,get=get,key="bad")
    assert x["provider_requests_attempted"]==0
    assert called==[]
    assert not (tmp_path/"brave_transient_request_counters_v1.json").exists()
