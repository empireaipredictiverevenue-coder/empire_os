"""The flagship routes existing buyer field gaps, NOT inferred buyers."""
from datetime import datetime, timezone
import json

import pytest

from empire_os.flagship_buyer_enrichment_triage import (
    SCHEMA, summarize_buyer_enrichment_triage, held_buyer_enrichment_triage,
)

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def buyer(**changes):
    row = {
        "id": "private-buyer-444",
        "buyer_name": "Private Buyer Corp",
        "niche": "solar",
        "metro": "Bolton",
        "destination_phone": "+441234456789",
        "commercial_terms_reference": "private-agreement-789",
        "per_lead_rate": 1500,
        "daily_cap": 100,
        "tenant_id": None,
        "org_id": None,
    }
    row.update(changes)
    return row


def test_partition_exactly_once_and_next_existing_team(tmp_path):
    rows = [
        buyer(), buyer(id="niche-absent", niche=""),
        buyer(id="metro-absent", metro=None),
        buyer(id="both-absent", niche="", metro=""),
        buyer(id="tenant-row", tenant_id="secret-tenant"),
        buyer(id="invalid-niche", niche="solar|sensitive@example.com"),
    ]
    result = summarize_buyer_enrichment_triage(rows, as_of=NOW)
    assert result["schema_version"] == SCHEMA
    assert result["source_records_observed"] == 6
    assert result["market_fields_complete"] == 1
    assert result["market_fields_incomplete_or_held"] == 5
    assert result["coverage_percent_of_observed_records"] == 16.7
    assert result["source_market_state_buckets"] == {
        "BOTH_MARKET_FIELDS_PRESENT": "ONE_TO_FOUR",
        "NICHE_ONLY_MISSING": "ONE_TO_FOUR",
        "METRO_ONLY_MISSING": "ONE_TO_FOUR",
        "BOTH_MARKET_FIELDS_MISSING": "ONE_TO_FOUR",
        "INVALID_MARKET_FIELD_FORMAT": "ONE_TO_FOUR",
        "TENANT_SCOPE_HELD": "ONE_TO_FOUR",
    }
    assert result["observed_vertical_family_buckets"]["solar"] == "ONE_TO_FOUR"
    assert result["current_exact_match_count_verified"] is False
    assert result["independent_first_party_buying_intent_verified"] is False
    assert result["canonical_buyer_rows_mutated"] is False
    assert result["external_outbound_authorized"] is False
    assert result["paid_research_authorized"] is False
    for item in result["workload"]:
        assert item["automatic_enrichment_authorized"] is False
        assert item["commercial_buyer_proof_established"] is False
        assert item["first_party_source_required"] is True
    serialized = json.dumps(result)
    for secret in (
        "private-buyer-444", "Private Buyer Corp", "secret-tenant",
        "+441234456789", "private-agreement-789",
        "sensitive@example.com", "Bolton",
    ):
        assert secret not in serialized
    assert not (tmp_path/"runtime").exists()


def test_populated_unverified_commercial_fields_are_not_buying_intent():
    value = summarize_buyer_enrichment_triage(
        [buyer(commercial_terms_reference="agreement-claimed", daily_cap=800)],
        as_of=NOW,
    )
    assert value["market_fields_complete"] == 1
    assert value["independent_first_party_buying_intent_verified"] is False
    assert value["commercial_terms_activated"] is False
    assert value["observed_vertical_family_buckets"]["solar"] == "ONE_TO_FOUR"
    assert value["workload"][-1]["next_internal_action"] == "VERIFY_FIRST_PARTY_BUYING_TERMS"


def test_niche_taxonomy_existing_aliases_reused_for_aggregate_research():
    result = summarize_buyer_enrichment_triage(
        [buyer(niche="roof_repair"), buyer(niche="Solar", id="2"),
         buyer(niche="mass_tort", id="3")],
        as_of=NOW,
    )
    # No fabricated legal mapping to new proprietary taxonomy.
    assert result["observed_vertical_family_buckets"]["roofing"] == "ONE_TO_FOUR"
    assert result["observed_vertical_family_buckets"]["solar"] == "ONE_TO_FOUR"
    assert result["observed_vertical_family_buckets"]["legal"] == "ZERO"
    assert result["source_market_state_buckets"]["BOTH_MARKET_FIELDS_PRESENT"] == "ONE_TO_FOUR"


@pytest.mark.parametrize("field,value",[
    ("niche", ["roofing"]), ("metro", 1234),
    ("niche", "solar,email@example.com"),
    ("metro", "<script>alert(1)</script>"),
    ("niche", "    "),
])
def test_invalid_or_missing_market_fields_do_not_promote_record(field,value):
    result = summarize_buyer_enrichment_triage(
        [buyer(**{field:value})], as_of=NOW,
    )
    assert result["market_fields_complete"] == 0
    assert result["independent_first_party_buying_intent_verified"] is False
    assert result["workload"][1]["owner"] == "buyer_qualifier"


def test_zero_records_is_no_data_not_perfect_coverage():
    result = summarize_buyer_enrichment_triage([], as_of=NOW)
    assert result["source_records_observed"] == 0
    assert result["market_fields_complete"] == 0
    assert result["coverage_percent_of_observed_records"] is None
    assert result["market_fields_incomplete_or_held"] == 0
    assert all(not row["requires_work"] for row in result["workload"])


def test_reject_unbounded_or_untrusted_buyer_rows():
    with pytest.raises(ValueError,match="invalid or truncated"):
        summarize_buyer_enrichment_triage([buyer()]*10000, as_of=NOW)
    with pytest.raises(ValueError,match="invalid or truncated"):
        summarize_buyer_enrichment_triage([None], as_of=NOW)
    with pytest.raises(ValueError,match="aware|time-aware"):
        summarize_buyer_enrichment_triage([buyer()], as_of=NOW.replace(tzinfo=None))


def test_held_response_never_discloses_private_error():
    response = held_buyer_enrichment_triage("dsn=private@example.com")
    assert response["status"] == "BUYER_MARKET_ENRICHMENT_HELD"
    assert response["hold_code"] == "BUYER_ENRICHMENT_UNAVAILABLE"
    assert response["source_records_observed"] is None
    assert response["contacts_or_buyer_names_exported"] is False
    assert "private@example.com" not in json.dumps(response)


def test_existing_root_worker_produces_triage_using_same_one_query(
    tmp_path, monkeypatch
):
    from scripts import build_buyer_capacity_readiness as script
    reads = []
    def one_existing_fetch():
        reads.append("existing_buyer_allocation_data_repository")
        return [buyer(), buyer(id="incomplete", niche="", metro="")]
    monkeypatch.setattr(script, "fetch_all_buyers", one_existing_fetch)
    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "OUT", tmp_path/"runtime/buyer_capacity_readiness/latest.json")
    assert script.main() == 0
    assert reads == ["existing_buyer_allocation_data_repository"]
    saved = json.loads(script.OUT.read_text())
    assert saved["schema_version"] == "empire.buyer_capacity_readiness.v1"
    assert saved["buyers_seen"] == 2
    triage = saved["flagship_buyer_enrichment_triage"]
    assert triage["schema_version"] == SCHEMA
    assert triage["market_fields_complete"] == 1
    assert triage["market_fields_incomplete_or_held"] == 1
    assert triage["external_outbound_authorized"] is False
    assert "Private Buyer Corp" not in json.dumps(saved)
    assert "private-buyer-444" not in json.dumps(saved)


def test_legacy_snapshot_preserved_when_optional_triage_fails(tmp_path, monkeypatch):
    from scripts import build_buyer_capacity_readiness as script
    monkeypatch.setattr(script, "fetch_all_buyers", lambda: [buyer()])
    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "OUT", tmp_path/"runtime/buyer_capacity_readiness/latest.json")
    def fail(*args, **kwargs):
        raise RuntimeError("password=secret-from-DB")
    monkeypatch.setattr(script, "summarize_buyer_enrichment_triage", fail)
    assert script.main() == 0
    saved = json.loads(script.OUT.read_text())
    assert saved["buyers_seen"] == 1
    assert saved["flagship_buyer_enrichment_triage"]["status"] == "BUYER_MARKET_ENRICHMENT_HELD"
    assert "secret-from-DB" not in json.dumps(saved)


def _write_snapshot(tmp_path, triage, *, as_of=NOW, **changes):
    path = tmp_path/"runtime/buyer_capacity_readiness/latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema_version": "empire.buyer_capacity_readiness.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "observed_at": as_of.isoformat(),
        "buyers_seen": triage["source_records_observed"],
        "market_defined": triage["market_fields_complete"],
        "flagship_buyer_enrichment_triage": triage,
    }
    snapshot.update(changes)
    path.write_text(json.dumps(snapshot))
    return path


def test_founder_safe_readback_of_enrichment_recovery_and_completeness(tmp_path):
    from empire_os.flagship_buyer_enrichment_triage import review_enrichment_triage_snapshot
    review = summarize_buyer_enrichment_triage(
        [buyer(), buyer(niche=None), buyer(metro="")], as_of=NOW,
    )
    _write_snapshot(tmp_path, review)
    got = review_enrichment_triage_snapshot(tmp_path, as_of=NOW)
    assert got["status"] == "MARKET_COVERAGE_ENRICHMENT_WORKLOAD_REVIEW"
    assert got["source_records_observed"] == 3
    assert got["market_fields_complete"] == 1
    assert got["market_fields_incomplete_or_held"] == 2
    assert got["original_market_source_independently_authenticated"] is False
    assert got["workload"][1]["owner"] == "buyer_qualifier"


def test_readback_unknown_when_source_not_released_or_stale(tmp_path):
    from empire_os.flagship_buyer_enrichment_triage import review_enrichment_triage_snapshot
    empty=review_enrichment_triage_snapshot(tmp_path,as_of=NOW)
    assert empty["status"] == "BUYER_MARKET_ENRICHMENT_HELD"
    assert empty["market_fields_complete"] is None
    from datetime import timedelta
    review=summarize_buyer_enrichment_triage([buyer()],as_of=NOW)
    _write_snapshot(tmp_path,review)
    old=review_enrichment_triage_snapshot(tmp_path,as_of=NOW+timedelta(hours=7))
    assert old["status"]=="BUYER_MARKET_ENRICHMENT_HELD"
    assert old["source_records_observed"] is None


def test_tampered_count_and_arbitrary_buyer_contact_in_workflow_held(tmp_path):
    from empire_os.flagship_buyer_enrichment_triage import review_enrichment_triage_snapshot
    original=summarize_buyer_enrichment_triage([buyer(),buyer(niche=None)],as_of=NOW)
    forged=dict(original)
    forged["market_fields_complete"]=2
    _write_snapshot(tmp_path,forged)
    held=review_enrichment_triage_snapshot(tmp_path,as_of=NOW)
    assert held["status"]=="BUYER_MARKET_ENRICHMENT_HELD"
    forged=summarize_buyer_enrichment_triage([buyer(),buyer(niche=None)],as_of=NOW)
    forged["workload"][0]["next_internal_action"]="POST_PRIVATE@example.org"
    _write_snapshot(tmp_path,forged)
    result=review_enrichment_triage_snapshot(tmp_path,as_of=NOW)
    assert result["status"] == "BUYER_MARKET_ENRICHMENT_HELD"
    assert "PRIVATE@example.org" not in json.dumps(result)


def test_false_bucket_sizes_or_new_source_states_rejected(tmp_path):
    from empire_os.flagship_buyer_enrichment_triage import review_enrichment_triage_snapshot
    original=summarize_buyer_enrichment_triage([buyer()],as_of=NOW)
    original["source_market_state_buckets"]["BOTH_MARKET_FIELDS_PRESENT"]="ZERO"
    _write_snapshot(tmp_path,original)
    held=review_enrichment_triage_snapshot(tmp_path,as_of=NOW)
    assert held["status"]=="BUYER_MARKET_ENRICHMENT_HELD"
    original=summarize_buyer_enrichment_triage([buyer()],as_of=NOW)
    original["source_market_state_buckets"]["NEW_BUCKET"]="ONE_TO_FOUR"
    _write_snapshot(tmp_path,original)
    held=review_enrichment_triage_snapshot(tmp_path,as_of=NOW)
    assert held["status"]=="BUYER_MARKET_ENRICHMENT_HELD"


def test_canonical_org_scope_missing_is_held_not_assumed_global():
    with pytest.raises(ValueError, match="organisation scope"):
        summarize_buyer_enrichment_triage(
            [{k:v for k,v in buyer().items() if k != "org_id"}], as_of=NOW
        )


def test_canonical_org_scoped_buyer_not_reclassified_as_global_market():
    report=summarize_buyer_enrichment_triage(
        [buyer(org_id="tenant-private-org-uuid")], as_of=NOW
    )
    assert report["source_market_state_buckets"]["TENANT_SCOPE_HELD"] == "ONE_TO_FOUR"
    assert report["market_fields_complete"] == 0
    assert report["observed_vertical_family_buckets"]["solar"] == "ZERO"
    assert "tenant-private-org" not in json.dumps(report)


def test_existing_worker_org_scope_unavailable_does_not_export_private_contact(
    tmp_path, monkeypatch
):
    from scripts import build_buyer_capacity_readiness as script
    legacy={k:v for k,v in buyer().items() if k!="org_id"}
    monkeypatch.setattr(script,"fetch_all_buyers",lambda:[legacy])
    monkeypatch.setattr(script,"ROOT",tmp_path)
    monkeypatch.setattr(script,"OUT",tmp_path/"runtime/buyer_capacity_readiness/latest.json")
    assert script.main()==0
    output=json.loads(script.OUT.read_text())
    assert output["buyers_seen"]==1
    assert output["flagship_exact_market_coverage"]["status"]=="EXACT_MARKET_COVERAGE_HELD"
    assert output["flagship_buyer_enrichment_triage"]["status"]=="BUYER_MARKET_ENRICHMENT_HELD"
    assert output["flagship_buyer_enrichment_triage"]["hold_code"]=="BUYER_MARKET_FIELDS_UNTRUSTED"
    assert "Private Buyer Corp" not in json.dumps(output)
    assert "private-buyer-444" not in json.dumps(output)
