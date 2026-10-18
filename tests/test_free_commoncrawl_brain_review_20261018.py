"""FREE 2026 Common Crawl historic research is evidence, not live backlinks."""
from datetime import datetime, timezone
from pathlib import Path
import json

from empire_os.free_dataset_intelligence import (
    SOURCE_REPORT_SCHEMA, inspect_free_commoncrawl_dataset,
)
from empire_os import source_intelligence_handoff as router
from empire_os.department_work_queue import DepartmentWorkQueue


def _report():
    rows=[
        {"source_domain":"example-one.org"},
        {"source_domain":"example-two.org"},
    ]
    return {
        "schema_version":SOURCE_REPORT_SCHEMA,
        "source":"commoncrawl_2026_domain_webgraph",
        "mode":"OBSERVE",
        "empiredb_writes":False,
        "paid_api_calls":0,
        "outbound_sent":False,
        "manual_review_required_for_all":True,
        "no_page_level_backlink_proof":True,
        "verified_live_backlink_count":0,
        "distinct_historical_source_domains":2,
        "historical_domain_relationships":3,
        "cross_target_source_domain_count":1,
        "reviewed_at_utc":"2026-10-16T18:37:07.273294+00:00",
        "candidates_by_target":{
            "nationsroof.com":1,"sunrun.com":1,
            "tectaamerica.com":0,"freedomforever.com":1,
        },
        "manual_review_queue":rows,
    }


def test_approved_existing_graph_summary_is_readable_and_not_a_live_backlink(tmp_path):
    p=tmp_path/"graph.json"
    p.write_text(json.dumps(_report()))
    d=inspect_free_commoncrawl_dataset(p)
    assert d["status"]=="REVIEWED_HISTORICAL_RESEARCH_AVAILABLE"
    assert d["historical_relation_count"]==3
    assert d["distinct_source_domain_count"]==2
    assert d["confirmed_live_backlinks"]==0
    assert d["no_page_level_html_backlink_proven"]
    assert d["empiredb_writes"] is False
    assert d["approved_free_dataset"] is True
    assert "example-one.org" not in json.dumps(d)
    assert d["execution_authority"]=="none"


def test_source_without_provenance_or_claiming_verified_links_is_held(tmp_path):
    for label,changes in (
        ("wrong_source",{"source":"fabricated"}),
        ("unexpected_paid_api",{"paid_api_calls":1}),
        ("unverified_page_claim",{"verified_live_backlink_count":2}),
        ("db_write_claim",{"empiredb_writes":True}),
        ("no_human_review",{"manual_review_required_for_all":False}),
        ("count_tamper",{"historical_domain_relationships":20000}),
        ("other_domain",{"candidates_by_target":{"unknown.com":3}}),
    ):
        r=_report();r.update(changes)
        p=tmp_path/(label+".json")
        p.write_text(json.dumps(r))
        d=inspect_free_commoncrawl_dataset(p)
        assert d["status"]!="REVIEWED_HISTORICAL_RESEARCH_AVAILABLE"
        assert d["empiredb_writes"] is False
        assert d["confirmed_live_backlinks"]==0


def test_missing_file_and_excessive_review_size_both_hold(tmp_path):
    assert inspect_free_commoncrawl_dataset(tmp_path/"missing.json")[
        "status"]=="SOURCE_REVIEW_UNAVAILABLE"
    p=tmp_path/"huge.json"
    p.write_bytes(b" " * 2_000_001)
    assert inspect_free_commoncrawl_dataset(p)["status"]=="SOURCE_REVIEW_UNAVAILABLE"


def test_existing_department_queue_receives_one_marketing_review_without_paid_api(tmp_path, monkeypatch):
    import empire_os.source_intelligence_handoff as mod
    # The optional branch is allowed only for canonical same-root evidence.
    monkeypatch.setattr(mod,"CANONICAL_ROOT",tmp_path)
    p=tmp_path/"free_report.json"
    p.write_text(json.dumps(_report()))
    monkeypatch.setattr(mod,"inspect_free_commoncrawl_dataset",
                        lambda:inspect_free_commoncrawl_dataset(p))
    d=mod.build_source_intelligence_handoffs(
        tmp_path,now=datetime(2026,10,18,9,0,tzinfo=timezone.utc))
    assert d["lane_count"]==6
    graph=[r for r in d["routes"] if r["lane"]=="historical_search_graph"][0]
    assert graph["department"]=="marketing_growth"
    assert graph["counts"]["historical_relationships"]==3
    assert graph["counts"]["confirmed_live_backlinks"]==0
    first=mod.dispatch_source_intelligence_handoffs(
        tmp_path,max_jobs=5,allow_noncanonical_test=True,
        now=datetime(2026,10,18,9,0,tzinfo=timezone.utc))
    second=mod.dispatch_source_intelligence_handoffs(
        tmp_path,max_jobs=5,allow_noncanonical_test=True,
        now=datetime(2026,10,18,9,5,tzinfo=timezone.utc))
    assert first["handoffs_enqueued"]==5
    assert second["handoffs_enqueued"]==1
    third=mod.dispatch_source_intelligence_handoffs(
        tmp_path,max_jobs=5,allow_noncanonical_test=True,
        now=datetime(2026,10,18,9,10,tzinfo=timezone.utc))
    assert third["handoffs_enqueued"]==0
    assert third["handoffs_unchanged"]==6
    assert DepartmentWorkQueue(tmp_path).counts()["ready"]==6
    packet=json.loads((tmp_path/mod.SNAPSHOT).read_text())
    graph=[r for r in packet["routes"] if r["lane"]=="historical_search_graph"][0]
    result=mod.deliver_source_intelligence_review(
        tmp_path,lane="historical_search_graph",
        fingerprint=graph["evidence_fingerprint"],
        department="marketing_growth")
    assert result["historical_free_dataset_brain_review"][
        "confirmed_live_backlinks"]==0
    assert result["payable_buyer_verified"] is False
    assert result["outbound_sent"] is False
    assert result["semantic_model_review_performed"] is False
