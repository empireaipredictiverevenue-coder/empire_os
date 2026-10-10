"""Insurance preview must remain local, bounded and OBSERVE-only."""
import json
from pathlib import Path

from scripts import preview_claims_exchange_existing_sources as preview


def write_sources(tmp_path):
    buyer=tmp_path/"buyers.json"
    buyer.write_text(json.dumps({
        "schema_version":"buyer-network-candidate-queue-v1",
        "authority":"OBSERVE",
        "candidates":[{
            "domain":"example-contractors.com",
            "status":"VERIFY_REQUIREMENTS",
            "verticals":["roofing","restoration"],
        }],
    }))
    dfw=tmp_path/"dfw.json"
    dfw.write_text(json.dumps({
        "schema_version":"empire.revenue_strike.storm.v1",
        "outbound_sent":False,
        "market":"Dallas-Fort Worth, TX",
        "prospects":[{"business_name":"Example Roofer",
                     "website":"https://example-roofing.com"}],
    }))
    return buyer,dfw


def argv(buyer,dfw,write=False):
    args=["--buyer-queue",str(buyer),"--dfw-cohort",str(dfw),
          "--as-of","2026-10-10","--top","2"]
    return args+(["--write-private-observe-snapshot"] if write else [])


def test_preview_has_historical_networks_but_no_qualified_claims_buyer(tmp_path,capsys):
    buyer,dfw=write_sources(tmp_path)
    assert preview.main(argv(buyer,dfw))==0
    result=json.loads(capsys.readouterr().out)
    assert result["schema"]=="empire.claims_exchange.existing_sources_preview_v2"
    assert result["summary"]["input_candidates"]==4
    assert result["summary"]["founder_review_ready"]==0
    assert result["summary"]["matches_for_founder_review"]==0
    assert result["source_reports"]["official_network_programs"]["research_rows"]==2
    assert result["source_reports"]["official_network_programs"]["demand_or_capacity_inferred"] is False
    assert result["execution_authority"]=="none"
    assert result["outbound_authorized"] is False
    assert result["actual_revenue"]==0


def test_optional_observe_write_is_private_and_never_grants_claim_authority(tmp_path,monkeypatch,capsys):
    buyer,dfw=write_sources(tmp_path)
    snapshot=tmp_path/"claims" /"research_latest.json"
    monkeypatch.setattr(preview,"OUTPUT_PATH",snapshot)
    assert preview.main(argv(buyer,dfw,write=True))==0
    printed=json.loads(capsys.readouterr().out)
    persisted=json.loads(snapshot.read_text())
    assert printed==persisted
    assert snapshot.stat().st_mode & 0o777 == 0o600
    assert persisted["outbound_sent"]==0
    assert persisted["outbound_authorized"] is False
    assert persisted["execution_authority"]=="none"
    assert persisted["summary"]["settlement_commissions"]==0
    assert persisted["summary"]["actual_revenue"]==0


def test_untrusted_source_rejected_without_snapshot_write(tmp_path,monkeypatch,capsys):
    buyer,dfw=write_sources(tmp_path)
    buyer.write_text(json.dumps({
        "schema_version":"fake-buyer-source","authority":"OBSERVE",
        "candidates":[{"domain":"example.org"}],
    }))
    snapshot=tmp_path/"claims" /"research_latest.json"
    monkeypatch.setattr(preview,"OUTPUT_PATH",snapshot)
    assert preview.main(argv(buyer,dfw,write=True))==2
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="SOURCE_REJECTED"
    assert result["outbound_authorized"] is False
    assert not snapshot.exists()


def test_sensitive_claims_person_data_rejected_no_output(tmp_path,monkeypatch,capsys):
    buyer,dfw=write_sources(tmp_path)
    source=json.loads(buyer.read_text())
    source["candidates"][0]["policyholder_name"]="PRIVATE"
    buyer.write_text(json.dumps(source))
    snapshot=tmp_path/"claims" /"research_latest.json"
    monkeypatch.setattr(preview,"OUTPUT_PATH",snapshot)
    assert preview.main(argv(buyer,dfw,write=True))==2
    assert not snapshot.exists()
    assert "SOURCE_REJECTED" in capsys.readouterr().out
