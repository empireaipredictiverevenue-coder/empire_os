"""Local-only Search Fabric cache inventory. No live search is executed."""
import hashlib
import json
import time

import pytest

from empire_os.search_intelligence.serp_cache_inventory import (
    SerpCacheInventoryHeld, inspect_cache,
)
from scripts import review_search_fabric_cache_inventory_20261018 as cli


def write_record(root, query="predictive revenue software", engine="bing_html",
                 num=3, ts=1_000_000, rows=1, mutate=None):
    digest=hashlib.sha256(f"{engine}:{query}:{num}".encode()).hexdigest()[:16]
    path=root/f"{engine}_{digest}.json"
    rec={
        "ts":ts,
        "data":{
            "searchParameters":{
                "q":query,"num":num,"engine":engine,"quality_gate":"lexical_v2",
            },
            "organic":[{
                "title":"First-party source title",
                "link":"https://example.test/genuine-page",
                "position":k+1,
            } for k in range(rows)],
        },
    }
    if mutate:
        mutate(rec)
    path.write_text(json.dumps(rec))
    return path


def test_cache_counts_fresh_stale_invalid_without_exposing_queries(tmp_path):
    write_record(tmp_path,query="buyer contact confidential",ts=1_000_000)
    write_record(tmp_path,query="older results",ts=800_000)
    (tmp_path/"invalidbad.json").write_text('{"private":"token"}')
    r=inspect_cache(tmp_path,now=1_000_100)
    assert r["status"]=="CACHE_INVENTORY_OBSERVED"
    assert r["cache_files_seen"]==3
    assert r["cache_envelopes_valid"]==2
    assert r["cache_envelopes_invalid"]==1
    assert r["cache_fresh_candidate_count"]==1
    assert r["cache_stale_candidate_count"]==1
    assert r["cache_fresh_candidates_by_engine"]=={"bing_html":1}
    assert r["independent_google_rank_positions_verified"] is False
    assert r["target_buyer_queries_verified"] is False
    assert r["external_search_queries_sent"] is False
    assert r["paid_api_calls"]==0
    assert "buyer contact confidential" not in json.dumps(r)
    assert "token" not in json.dumps(r)


def test_exact_hash_prevents_cache_spoof_and_fake_position(tmp_path):
    f=write_record(tmp_path,ts=1_000_000)
    f.rename(tmp_path/("bing_html_"+"e"*16+".json"))
    r=inspect_cache(tmp_path,now=1_000_100)
    assert r["cache_envelopes_invalid"]==1
    assert r["cache_fresh_candidate_count"]==0


@pytest.mark.parametrize("mutation",[
    lambda d:d["data"]["organic"][0].update(position=True),
    lambda d:d["data"]["organic"][0].update(position=0),
    lambda d:d["data"]["organic"][0].update(position=9_000),
    lambda d:d["data"]["organic"][0].update(link="javascript:alert(1)"),
    lambda d:d["data"]["searchParameters"].update(engine="google"),
    lambda d:d["data"]["searchParameters"].update(quality_gate="none"),
    lambda d:d.update(ts="now"),
    lambda d:d["data"].update(organic=[]),
])
def test_invalid_cache_envelope_is_counted_not_reported_as_verified(tmp_path,mutation):
    write_record(tmp_path,ts=1_000_000,mutate=mutation)
    r=inspect_cache(tmp_path,now=1_000_100)
    assert r["cache_envelopes_invalid"]==1
    assert r["cache_fresh_candidate_count"]==0
    assert r["independent_google_rank_positions_verified"] is False


def test_future_timestamp_and_ttl_boundary_never_fresh(tmp_path):
    write_record(tmp_path,query="future",ts=1_000_010)
    write_record(tmp_path,query="ttl",ts=1_000_000-86400)
    r=inspect_cache(tmp_path,now=1_000_000)
    assert r["cache_fresh_candidate_count"]==0
    assert r["cache_stale_candidate_count"]==2


def test_no_symlink_files_or_root_are_followed(tmp_path):
    root=tmp_path/"cache";root.mkdir()
    outside=tmp_path/"private.json";outside.write_text('{"secret":"dont read"}')
    (root/"bing_html_0123456789abcdef.json").symlink_to(outside)
    report=inspect_cache(root,now=1_000_000)
    assert report["cache_envelopes_invalid"]==1
    assert "secret" not in json.dumps(report)
    (tmp_path/"link").symlink_to(root,target_is_directory=True)
    with pytest.raises(SerpCacheInventoryHeld,match="ROOT_UNAVAILABLE"):
        inspect_cache(tmp_path/"link",now=1_000_000)


def test_file_count_bound_does_not_scan_unbounded_dir(tmp_path):
    for i in range(2501):
        (tmp_path/f"invalid_{i}.json").write_text("{}")
    with pytest.raises(SerpCacheInventoryHeld,match="FILE_LIMIT"):
        inspect_cache(tmp_path,now=1_000_000)


def test_cli_fails_closed_on_unavailable_cache(monkeypatch,capsys):
    monkeypatch.setattr(cli,"inspect_cache",lambda:(_ for _ in ()).throw(
        RuntimeError("sensitive query should not appear")))
    assert cli.main(["--review-only"])==2
    r=json.loads(capsys.readouterr().out)
    assert r["status"]=="CACHE_SOURCE_HELD"
    assert "sensitive" not in json.dumps(r)
    assert r["independent_google_rank_positions_verified"] is False


def test_cli_rejects_triggering_external_search(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--review-only","--fetch"])
    with pytest.raises(SystemExit):
        cli.main(["--live-scrape"])
