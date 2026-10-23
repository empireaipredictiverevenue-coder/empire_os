"""USA market source provenance never implies buying intent or sender approval."""
from datetime import datetime,timedelta,timezone
import csv
import json
from pathlib import Path

import pytest

from empire_os.founder_acquisition_us_market import (
    INPUT, EvidenceHeld, safe_original_url, load_us_inputs, assess_source,
    refresh_us_evidence,
)
from scripts.run_founder_acquisition_review import refresh_us_market

CLOCK=datetime(2026,10,23,15,0,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parent.parent


def _rows(tmp_path):
    p=tmp_path/INPUT
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((ROOT/INPUT).read_bytes())
    return load_us_inputs(tmp_path)


def _fake(rows, url):
    matching=[r for r in rows if r["source_url"]==url]
    body="<html><title>Company news</title><body>"
    body+=" ".join(x["anchor_a"]+" "+x["anchor_b"] for x in matching)
    body+=" USA event report from original publisher with relevant company context. </body></html>"
    return {"status_code":200,"final_url":url,"content_type":"text/html","body":body.encode()}


def test_manifest_has_four_verticals_and_deduplicates_sources(tmp_path):
    records=_rows(tmp_path)
    assert len(records)==20
    assert {r["startup"] for r in records}=={"Alloovium","Libra Robotics","Andco","Plena Health"}
    assert all(r["country"]=="US" for r in records)
    assert len({r["source_url"] for r in records})==17


def test_us_source_url_exact_host_and_https_only():
    original="https://www.jacobs.com/newsroom/press-release/example"
    assert safe_original_url(original)
    for unsafe in ("http://www.jacobs.com/newsroom/press-release/example",
                   "https://www.jacobs.com.evil.example/news/anything",
                   "https://127.0.0.1/private",
                   "https://www.jacobs.com/newsroom/press-release/example?secret=1",
                   "https://person@www.jacobs.com/sales",
                   "https://www.jacobs.com/"):
        assert safe_original_url(unsafe) is False


def test_uk_in_us_manifest_is_rejected(tmp_path):
    records=_rows(tmp_path)
    p=tmp_path/INPUT
    with p.open() as handle:
        reader=csv.DictReader(handle);keys=reader.fieldnames;data=list(reader)
    data[0]["country"]="UK"
    with p.open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=keys)
        writer.writeheader();writer.writerows(data)
    with pytest.raises(EvidenceHeld,match="US_SEGMENT_SCOPE_MISMATCH"):
        load_us_inputs(tmp_path)


def test_two_us_sources_per_cycle_and_true_deduplication(tmp_path):
    rows=_rows(tmp_path);calls=[]
    def fetch(url):
        calls.append(url)
        return _fake(rows,url)
    one=refresh_us_evidence(rows,previous=None,now=CLOCK,fetch=fetch,max_fetch=2)
    assert len(calls)==2 and len(set(calls))==2
    assert one["distinct_original_source_count"]==17
    assert one["distinct_observed_source_count"]==2
    assert one["curated_opportunity_hypotheses"]==20
    assert one["observed_account_hypotheses"]>=2
    assert one["actual_buyers_verified"]==0
    assert one["outbound_sent"] is False
    assert one["automatic_send_authorized"] is False
    again=refresh_us_evidence(rows,previous=one,now=CLOCK+timedelta(minutes=5),fetch=fetch,max_fetch=2)
    assert len(calls)==4 and again["distinct_observed_source_count"]==4
    assert all("@" not in json.dumps(x) for x in again["sources"])


def test_source_http_403_and_redirect_held_not_counted(tmp_path):
    rows=_rows(tmp_path)
    def broken(url):
        d=_fake(rows,url)
        d["status_code"]=403
        return d
    v=refresh_us_evidence(rows,previous=None,now=CLOCK,fetch=broken)
    assert v["distinct_observed_source_count"]==0
    assert all(x["source_status"]=="HELD_SOURCE_NOT_CORROBORATED" for x in v["sources"])
    assert v["observed_account_hypotheses"]==0


def test_missing_project_anchor_is_not_original_source_corroboration(tmp_path):
    rows=_rows(tmp_path)
    url=rows[0]["source_url"]
    with pytest.raises(EvidenceHeld,match="US_CLAIM_ANCHORS_NOT_CORROBORATED"):
        assess_source(url,[("Fisk","prefabrication")],
            response={"status_code":200,"final_url":url,"content_type":"text/html",
                      "body":b"<html><body>Completely unrelated description of an event occurring in a city, no specified supplier or contract details are in this source.</body></html>"},
            now=CLOCK,source_role=rows[0]["source_role"])


def test_no_repeat_fetch_until_interval_and_lost_old_sources_hold(tmp_path):
    rows=_rows(tmp_path);calls=[]
    def source(url):
        calls.append(url)
        return _fake(rows,url)
    old=refresh_us_evidence(rows,previous=None,now=CLOCK,fetch=source)
    new=refresh_us_evidence(rows,previous=old,now=CLOCK+timedelta(minutes=5),fetch=source)
    assert len(calls)==4
    assert new["sources"][0]["source_url"]==old["sources"][0]["source_url"]
    with pytest.raises(EvidenceHeld,match="US_PREVIOUS_EVENT_REMOVED"):
        refresh_us_evidence(rows[2:5],previous=new,now=CLOCK+timedelta(minutes=10),fetch=source)


def test_us_runtime_private_snapshot_and_denied_sending(tmp_path):
    _rows(tmp_path)
    rows=load_us_inputs(tmp_path)
    result=refresh_us_market(tmp_path,now=CLOCK,fetch=lambda url:_fake(rows,url))
    assert result["us_market_status"]=="US_PUBLIC_EVENT_EVIDENCE_REVIEW_ONLY"
    assert result["us_market_distinct_sources_observed"]==2
    assert result["us_market_verified_buyers"]==0
    p=tmp_path/"runtime/founder_acquisition/us_market_evidence_latest.json"
    assert p.stat().st_mode & 0o077==0
    body=json.loads(p.read_text())
    assert body["outbound_sent"] is False and body["crm_writes"] is False
    assert body["market"]=="US"


def test_us_runtime_missing_seed_fails_without_outbound(tmp_path):
    result=refresh_us_market(tmp_path,now=CLOCK,fetch=lambda url:None)
    assert result["us_market_status"]=="HELD_US_SOURCE_REFRESH"
    assert result["us_market_verified_buyers"]==0


def test_reviewed_html_replacement_preserves_original_pdf_hold(tmp_path):
    rows=_rows(tmp_path)
    retired="https://investors.cardinalinfrastructuregroup.com/node/6631/pdf"
    replacement="https://investors.cardinalinfrastructuregroup.com/news-releases/news-release-details/cardinal-infrastructure-group-awarded-contract-large-scale-data"
    legacy=[dict(r) for r in rows]
    cardinal=next(r for r in legacy if r["account"]=="Cardinal Infrastructure Group")
    cardinal["source_url"]=retired
    cardinal["source_role"]="PDF_PRIMARY_REPORT"
    cardinal["anchor_a"]="Cardinal"
    cardinal["anchor_b"]="project"
    previous=None
    for i in range(9):
        previous=refresh_us_evidence(
            legacy, previous=previous, now=CLOCK+timedelta(minutes=5*i),
            fetch=lambda url:_fake(legacy,url),
        )
    assert previous["distinct_observed_source_count"]==16
    assert any(s["source_url"]==retired and s["source_status"]=="HELD_SOURCE_NOT_CORROBORATED"
               for s in previous["sources"])
    corrected=refresh_us_evidence(
        rows, previous=previous, now=CLOCK+timedelta(minutes=45),
        fetch=lambda url:_fake(rows,url),
    )
    assert corrected["distinct_original_source_count"]==17
    assert corrected["distinct_observed_source_count"]==17
    assert corrected["observed_account_hypotheses"]==20
    assert corrected["actual_buyers_verified"]==0
    assert corrected["outbound_sent"] is False
    history=corrected["retired_held_source_history"]
    assert len(history)==1
    assert history[0]["retired_url"]==retired
    assert history[0]["replacement_url"]==replacement
    assert history[0]["prior_source_status"]=="HELD_SOURCE_NOT_CORROBORATED"
    # No additional request on repeated native cycles and no provenance lost.
    next_state=refresh_us_evidence(
        rows, previous=corrected, now=CLOCK+timedelta(minutes=50),
        fetch=lambda url: (_ for _ in ()).throw(AssertionError("should be cached"))
    )
    assert next_state["retired_held_source_history"]==history
    assert next_state["http_checks_this_cycle"]==0


def test_refuse_unreviewed_source_migration_even_if_url_is_valid(tmp_path):
    rows=_rows(tmp_path)
    before=refresh_us_evidence(rows,previous=None,now=CLOCK,
                               fetch=lambda url:_fake(rows,url))
    before=refresh_us_evidence(rows,previous=before,now=CLOCK+timedelta(minutes=5),
                               fetch=lambda url:_fake(rows,url))
    assert any("jacobs.com" in x["source_url"] for x in before["sources"])
    mutated=[dict(r) for r in rows]
    mutated[2]["source_url"]="https://www.jacobs.com/newsroom/new-unreviewed-url"
    with pytest.raises(EvidenceHeld,match="US_PREVIOUS_EVENT_REMOVED"):
        refresh_us_evidence(
            mutated,previous=before,now=CLOCK+timedelta(minutes=10),
            fetch=lambda url:_fake(mutated,url)
        )


def test_never_migrate_original_verified_event_source(tmp_path):
    rows=_rows(tmp_path)
    before=refresh_us_evidence(rows,previous=None,now=CLOCK,
                               fetch=lambda url:_fake(rows,url))
    before["sources"][0]["source_url"]="https://investors.cardinalinfrastructuregroup.com/node/6631/pdf"
    before["sources"][0]["source_status"]="PUBLISHED_EVENT_CLAIM_OBSERVED_NOT_BUYER_VERIFIED"
    with pytest.raises(EvidenceHeld,match="US_PREVIOUS_EVENT_REMOVED"):
        refresh_us_evidence(rows,previous=before,now=CLOCK+timedelta(minutes=5),
                            fetch=lambda url:_fake(rows,url))
