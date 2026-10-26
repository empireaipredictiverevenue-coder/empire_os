"""Original Buyer Network public research expansion: never reclassify as buyers."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import stat

import pytest

from empire_os.heat_pump_market_expansion import (
    SCHEMA, SEED, REL, DEST, materialize, run,
)

NOW=datetime(2026,10,26,21,20,tzinfo=timezone.utc)
STAGE=Path(__file__).resolve().parents[1]
ORIGINAL=Path("/srv/empire_os")

@pytest.fixture()
def source():
    return (STAGE/SEED).read_bytes()

@pytest.fixture()
def commercial():
    p=ORIGINAL/REL
    return (
        json.loads((p/"commercial_relationship_registry_latest.json").read_text()),
        json.loads((p/"candidate_queue_latest.json").read_text()),
    )

def test_34_source_backed_companies_with_original_contact_overlay(source,commercial):
    result=materialize(source,*commercial,now=NOW)
    assert result["schema_version"]==SCHEMA
    assert result["candidate_count"]==34
    assert result["lane_counts"]=={
        "A_B2B_TERMS_RESEARCH":4,
        "B_INSTALLER_QUALIFICATION":11,
        "B_NETWORK_PARTNERSHIP_RESEARCH":9,
        "C_SUPPLY_EXCHANGE_RESEARCH":10,
    }
    assert sum(x["original_registry_or_scout_present"] for x in result["companies"]) >= 2
    assert all(x["outreach_authorized"] is False and
        x["lead_purchase_terms_verified"] is False and
        x["buyer_acceptance_verified"] is False
        for x in result["companies"])
    assert result["crm_buyer_records_inserted"]==0
    assert result["eligible_payable_agreements"]==0
    assert result["prior_four_live_heat_pump_sent_threads_preserved"]==4

def test_recontact_flags_for_known_heat_pump_lead_supplier(source,commercial):
    result=materialize(source,*commercial,now=NOW)
    lead=next(x for x in result["companies"] if x["domain"]=="leadpronto.co.uk")
    assert lead["original_contact_state"]=="PRIOR_OUTBOUND_REVIEW_THREAD_NO_DUPLICATE"
    newpower=next(x for x in result["companies"] if x["domain"]=="newpoweruk.co.uk")
    assert newpower["original_contact_state"]=="POSSIBLE_NEWPOWER_ADVANCED_ALIAS_VERIFY_NO_DUPLICATE"

def test_consumers_are_never_assumed_b2b_partner_programmes(source,commercial):
    result=materialize(source,*commercial,now=NOW)
    cb=next(x for x in result["companies"] if x["domain"]=="cbheating.co.uk")
    assert cb["commercial_research_lane"]=="B_INSTALLER_QUALIFICATION"
    assert "existing customers" in cb["public_terms_limitation"]
    power=next(x for x in result["companies"] if x["domain"]=="poweredleads.co.uk")
    assert power["commercial_research_lane"]=="C_SUPPLY_EXCHANGE_RESEARCH"
    assert power["buyer_acceptance_verified"] is False

def test_secondary_sources_do_not_become_first_party(source,commercial):
    result=materialize(source,*commercial,now=NOW)
    boxt=next(x for x in result["companies"] if x["domain"]=="boxt.co.uk")
    assert boxt["source_class"]=="SECONDARY_PUBLIC_EVIDENCE_CONFIRM_WITH_FIRST_PARTY"
    good=next(x for x in result["companies"] if x["domain"]=="goodenergy.co.uk")
    assert good["source_class"]=="FIRST_PARTY_OR_SAME_BRAND_PUBLISHED"

@pytest.mark.parametrize("replacement",[
    "http://example.com/no-https",
    "https://bad_host.example.com/path",
])
def test_reject_invalid_public_sources(source,commercial,replacement):
    text=source.decode().replace("https://www.newpoweruk.co.uk/partners",replacement,1)
    with pytest.raises(ValueError):
        materialize(text.encode(),*commercial,now=NOW)

def test_duplicate_domain_rejected(source,commercial):
    lines=source.decode().splitlines()
    lines.append(lines[1])
    with pytest.raises(ValueError,match="DUPLICATE"):
        materialize(("\n".join(lines)+"\n").encode(),*commercial,now=NOW)

def test_suppressed_original_record_not_promoted(source,commercial):
    registry,queue=copy.deepcopy(commercial)
    registry["relationships"].append({"identity_domains":["goodenergy.co.uk"],
        "stage":"DELIVERY_HOLD","do_not_pursue":True,"gmail_thread_ids":[]})
    result=materialize(source,registry,queue,now=NOW)
    good=next(x for x in result["companies"] if x["domain"]=="goodenergy.co.uk")
    assert good["original_contact_state"]=="SUPPRESSED_OR_BOUNCED_DO_NOT_SEND"
    assert good["outreach_authorized"] is False

def test_private_batch_snapshot_inside_original_buyer_directory(tmp_path,source,commercial):
    (tmp_path/SEED.parent).mkdir(parents=True)
    (tmp_path/SEED).write_bytes(source)
    (tmp_path/REL).mkdir(parents=True)
    registry,queue=commercial
    (tmp_path/REL/"commercial_relationship_registry_latest.json").write_text(json.dumps(registry))
    (tmp_path/REL/"candidate_queue_latest.json").write_text(json.dumps(queue))
    out=run(tmp_path,now=NOW,write=True)
    assert out["candidate_count"]==34
    target=tmp_path/DEST
    assert target.is_file() and stat.S_IMODE(target.stat().st_mode)==0o600
    again=run(tmp_path,now=NOW,write=True)
    assert again["source_sha256"]==out["source_sha256"]

def test_unsafe_input_symlink_held(tmp_path,source,commercial):
    (tmp_path/SEED.parent).mkdir(parents=True)
    outside=tmp_path/"outside.csv"
    outside.write_bytes(source)
    (tmp_path/SEED).symlink_to(outside)
    (tmp_path/REL).mkdir(parents=True)
    registry,queue=commercial
    (tmp_path/REL/"commercial_relationship_registry_latest.json").write_text(json.dumps(registry))
    (tmp_path/REL/"candidate_queue_latest.json").write_text(json.dumps(queue))
    with pytest.raises(ValueError,match="SOURCE_MISSING_OR_UNSAFE"):
        run(tmp_path,now=NOW,write=True)
    assert not (tmp_path/DEST).exists()
