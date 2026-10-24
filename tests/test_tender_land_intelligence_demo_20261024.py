"""Unit tests for bounded private CA18567 land-intelligence demonstrator."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import pytest

from empire_os.tender_land_intelligence_demonstrator import (
    build_report, render_html, write_private_demo, JSON_NAME, HTML_NAME,
)

NOW=datetime(2026,10,24,14,0,tzinfo=timezone.utc)

def test_evidence_cannot_become_bid_or_investment_proof():
    r=build_report(NOW)
    assert r["tender_ref"]=="CA18567"
    assert r["investment_ready_sites"]==0
    assert r["supplier_credentials_verified"] is False
    assert r["bid_authorized"] is False
    assert r["outbound_sent"] is False
    assert r["db_writes"] is False and r["crm_writes"] is False
    assert r["external_data_fetched_by_script"] is False
    assert r["map_layers_used"] is False
    assert len(r["published_examples"])==4
    for x in r["published_examples"]:
        assert x["ready_for_investor_guide"] is False
        assert x["investment_recommendation"]=="NOT_EVALUATED"
        assert x["title"]=="UNVERIFIED"
        assert x["source"].startswith("https://")
        assert x["not_verified"]

def test_negative_control_cannot_be_marketed_as_land():
    r=build_report(NOW)
    office=next(x for x in r["published_examples"] if "Office" in x["name"])
    assert office["kind"]=="EXISTING_BUILDING"
    assert office["evidence_class"]=="PUBLISHED_BUILDING_EXCLUDE_FROM_VACANT_LAND"
    old=next(x for x in r["published_examples"] if x["kind"]=="HISTORICAL_LANDBANK")
    assert old["current_availability"]=="UNVERIFIED"

def test_private_outputs_and_safe_html(tmp_path:Path):
    folder=tmp_path/"runtime"/"acquisition_research"
    folder.mkdir(parents=True,mode=0o700)
    os.chmod(folder,0o700)
    r=write_private_demo(tmp_path, now=NOW)
    assert len(r["published_examples"])==4
    for name in (JSON_NAME,HTML_NAME):
        p=folder/name
        assert stat.S_IMODE(p.stat().st_mode)==0o600
        assert p.stat().st_size>1000
    actual=json.loads((folder/JSON_NAME).read_text())
    assert actual["investment_ready_sites"]==0
    html=(folder/HTML_NAME).read_text()
    assert "Private Research" in html
    assert "Giant" in html and "Dundalk" in html
    assert "No parcel title verified" in html
    assert "rel=\"noopener noreferrer\"" in html

def test_insecure_directory_rejected(tmp_path:Path):
    folder=tmp_path/"runtime"/"acquisition_research"
    folder.mkdir(parents=True)
    os.chmod(folder,0o755)
    with pytest.raises(ValueError, match="REQUIRES_EXISTING_PRIVATE"):
        write_private_demo(tmp_path,now=NOW)

def test_naive_time_rejected():
    with pytest.raises(ValueError,match="TIMEZONE_REQUIRED"):
        build_report(datetime(2026,10,24,14,0))

def test_symlink_target_rejected(tmp_path:Path):
    folder=tmp_path/"runtime"/"acquisition_research"
    folder.mkdir(parents=True,mode=0o700)
    os.chmod(folder,0o700)
    victim=tmp_path/"victim"
    victim.write_text("leave-me")
    (folder/JSON_NAME).symlink_to(victim)
    with pytest.raises(ValueError,match="UNSAFE_PRIVATE_DEMO_TARGET"):
        write_private_demo(tmp_path,now=NOW)
    assert victim.read_text()=="leave-me"
