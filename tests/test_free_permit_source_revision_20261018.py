"""Re-downloaded official data must teach existing EmpireOS intake, not lose updates."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from empire_os import signal_inbox
from empire_os.permit_source_revision import (
    MAX_EVENT_REVISIONS, trusted_permit_match, refresh_trusted_permit_event,
)
from empire_os.permit_project_intelligence import analyze_permit_project_intelligence


def _source(*, name="Old Owner Corporation", filed="02/09/2007",
            issued=None, status="IN PROCESS", job="402424051",
            run="2026-10-18T00:00:00.000", source="permits_nyc",
            host="a810-biswebportal.nyc.gov"):
    return {
        "source": source,
        "name": name,
        "metro": "NYC",
        "state": "NY",
        "niche": "plumbing",
        "url": f"https://{host}/bisweb/PropertyOverflowDetails.jsp?job={job}",
        "raw": {
            "job__": job, "filing_date": filed, "issuance_date": issued,
            "dobrundate": run, "permit_status": status,
            "filing_status": "INITIAL", "job_type": "A2", "work_type": "PL",
            "bbl": "4006810011", "bin__": "4011278",
            "owner_s_business_name": name, "owner_s_first_name": "Private Person",
            "owner_s_phone__": "5551118899",
            "permittee_s_business_name": "Private Contractor",
            "permittee_s_phone__": "5552228899",
        }
    }


@pytest.fixture()
def _inbox(monkeypatch, tmp_path):
    folder=tmp_path/"runtime/acquisition"
    folder.mkdir(parents=True)
    monkeypatch.setattr(signal_inbox, "ROOT", folder)
    monkeypatch.setattr(signal_inbox, "INBOX", folder/"signal_inbox.json")
    monkeypatch.setattr(signal_inbox, "LOCK", folder/"signal_inbox.lock")
    return folder


def _rows(path):
    return json.loads((path/"signal_inbox.json").read_text())


def test_updated_official_issuance_preserved_with_source_history_not_new_lead(_inbox):
    first = signal_inbox.enqueue_signal(_source())
    assert first["decision"]=="created"
    update = signal_inbox.enqueue_signal(_source(
        name="New Owner Corporation", issued="10/18/2026", status="ISSUED",
        run="2026-10-18T03:00:00.000"))
    assert update["decision"]=="updated_source_event"
    assert update["source_event_revision_added"] is True
    assert update["signal_id"]==first["signal_id"]
    rows=_rows(_inbox)
    assert len(rows)==1
    row=next(iter(rows.values()))
    assert row["created_at"] <= row["last_seen_at"]
    assert row["seen_count"]==2
    assert row["source_event_revision_count"]==1
    assert row["raw"]["issuance_date"]=="10/18/2026"
    assert row["raw"]["permit_status"]=="ISSUED"
    assert row["raw"]["owner_s_business_name"]=="Old Owner Corporation"
    assert row["raw"]["owner_s_phone__"]=="5551118899"
    rev=row["source_event_revisions"][0]
    assert set(rev["changed_event_fields"])=={"issuance_date","permit_status"}
    assert "Owner Corporation" not in json.dumps(rev)
    assert "5551118899" not in json.dumps(rev)
    assert rev["company_or_buyer_verified"] is False
    assert rev["outbound_authorized"] is False


def test_no_duplicate_event_if_only_reobserved_or_source_run_advanced(_inbox):
    initial=signal_inbox.enqueue_signal(_source())
    same=signal_inbox.enqueue_signal(_source(run="2026-10-19T08:00:00.000"))
    assert same["decision"]=="matched"
    assert same["signal_id"]==initial["signal_id"]
    assert same["source_event_revision_added"] is False
    assert len(_rows(_inbox))==1
    assert not next(iter(_rows(_inbox).values())).get("source_event_revisions")
    assert next(iter(_rows(_inbox).values()))["raw"]["dobrundate"].startswith("2026-10-19")


def test_outdated_source_run_cannot_roll_back_newer_issuance(_inbox):
    signal_inbox.enqueue_signal(_source(issued="10/18/2026",status="ISSUED",
                                       run="2026-10-18T15:00:00.000"))
    older=signal_inbox.enqueue_signal(_source(issued=None,status="IN PROCESS",
                                              run="2026-10-17T00:00:00.000"))
    assert older["decision"]=="matched"
    row=next(iter(_rows(_inbox).values()))
    assert row["raw"]["permit_status"]=="ISSUED"
    assert row["raw"]["issuance_date"]=="10/18/2026"
    assert row["seen_count"]==2


def test_forged_url_cannot_merge_or_change_trusted_source(_inbox):
    signal_inbox.enqueue_signal(_source())
    other=signal_inbox.enqueue_signal(_source(
        host="a810-biswebportal.nyc.gov.evil.example",
        issued="10/18/2026",status="ISSUED",
    ))
    assert other["source_event_revision_added"] is False
    rows=_rows(_inbox)
    assert len(rows)==2   # untrusted source kept separate; not merged
    trusted=[r for r in rows.values()
             if r["url"].startswith("https://a810-biswebportal.nyc.gov/")][0]
    assert trusted["raw"]["permit_status"]=="IN PROCESS"


def test_different_official_job_number_never_overwrites(_inbox):
    signal_inbox.enqueue_signal(_source())
    signal_inbox.enqueue_signal(_source(job="402424052",status="ISSUED"))
    assert len(_rows(_inbox))==2
    assert {r["raw"]["job__"] for r in _rows(_inbox).values()}=={"402424051","402424052"}


def test_original_source_event_transition_changes_existing_project_intelligence(tmp_path, _inbox):
    first=signal_inbox.enqueue_signal(_source())
    def dossier():
        return analyze_permit_project_intelligence(tmp_path,max_dossiers=3)
    a=dossier()
    before=a["total_retained_source_semantics_digest"]
    signal_inbox.enqueue_signal(_source(issued="10/18/2026",status="ISSUED"))
    after=dossier()
    assert before != after["total_retained_source_semantics_digest"]
    # Whether the event is recent depends on the current date of the test run:
    # never claim an independent buyer even for a real source update.
    assert after["buyer_matched"] is False
    assert after["automatic_sales_promotion"] is False
    assert after["recognised_revenue_proven"] is False


def test_revision_history_is_bounded_and_contains_no_contacts():
    original={
        "source":"permits_nyc",
        "url":"https://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job=402424051",
        "raw":_source()["raw"],
    }
    for index in range(18):
        data=_source(status="ISSUED" if index%2==0 else "IN PROCESS")
        data["raw"]["filing_status"]="INITIAL" if index%2 else "AMENDMENT"
        out=refresh_trusted_permit_event(
            original,data,observed_at=f"2026-10-18T09:{index:02d}:00+00:00")
        assert out["trusted_job_reference"] is True
    assert original["source_event_revision_count"]>=12
    assert len(original["source_event_revisions"])==MAX_EVENT_REVISIONS
    history=json.dumps(original["source_event_revisions"])
    assert "Private Person" not in history
    assert "5552228899" not in history
    assert "Private Contractor" not in history


def test_unrelated_source_data_behaviour_unchanged(_inbox):
    row=_source(source="overpass_osm")
    row["raw"]={"id":"other-123"}
    first=signal_inbox.enqueue_signal(row)
    second=signal_inbox.enqueue_signal(row)
    assert first["decision"]=="created"
    assert second["decision"]=="matched"
    assert second["source_event_revision_added"] is False


def test_owner_name_change_does_not_create_a_second_official_job(_inbox):
    first=signal_inbox.enqueue_signal(_source(name="Original Holder"))
    second=signal_inbox.enqueue_signal(_source(name="Later Holder"))
    assert first["signal_id"]==second["signal_id"]
    assert len(_rows(_inbox))==1
    assert next(iter(_rows(_inbox).values()))["name"]=="Original Holder"
