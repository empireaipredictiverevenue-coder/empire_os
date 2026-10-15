"""V20 boundary tests: capture receives minimum official fields only."""
from datetime import datetime, timezone
import json
import pytest

from scripts import probe_construction_official_entities as probe
from scripts import operate_data_exchange_observation_custody as custody
from scripts import audit_data_exchange_raw_source_shape_v19 as auditor

NOW=datetime(2026,10,15,12,15,tzinfo=timezone.utc)
IDS=(1722645,1739516,1739547)
PRIVATE="NEVER_SHARE_PRIVATE_SOURCE_VALUE"


def complete_source(url):
    number=int(url.rsplit("/",1)[-1].removesuffix(".json"))
    return {
        "entity":number,
        "dataset":"brownfield-land",
        "quality":"authoritative",
        "organisation-entity":207,
        "end-date":None,
        "planning-permission-status":"non-permissioned",
        "hectares":"0.1",
        "entry-date":"2024-11-29",
        "email":PRIVATE,
        "owner":PRIVATE,
        "site-address":PRIVATE,
        "contactPoint":PRIVATE,
        "notes":PRIVATE,
        "extraField":PRIVATE,
    }


def test_projected_fetch_drops_all_other_raw_values_before_normalisation(monkeypatch):
    raw_urls=[]
    def raw(url):
        raw_urls.append(url)
        return complete_source(url)
    monkeypatch.setattr(probe,"fetch_official_json",raw)
    for i in IDS:
        result=probe.fetch_projected_official_json(
            f"https://www.planning.data.gov.uk/entity/{i}.json")
        assert set(result)==probe.APPROVED_SOURCE_INPUT_KEYS
        assert PRIVATE not in repr(result)
        assert "email" not in result
        assert "site-address" not in result
        assert result["entity"]==i
    assert len(raw_urls)==3


def test_default_custody_fetch_uses_minimized_projection_and_keeps_schema(monkeypatch):
    monkeypatch.setattr(probe,"fetch_official_json",complete_source)
    result=custody.capture(now=NOW)
    assert result["dataset_record_count"]==3
    assert {r["record_id"] for r in result["records"]}==set(map(str,IDS))
    assert PRIVATE not in json.dumps(result)
    assert result["customer_delivery_enabled"] is False
    assert result["rights_review_eligible"] is False


def test_raw_key_inventory_can_still_count_excluded_keys(monkeypatch):
    monkeypatch.setattr(probe,"fetch_official_json",complete_source)
    outcome=auditor.audit_source_key_shapes(now=NOW,fetch_json=probe.fetch_official_json)
    assert outcome["raw_json_key_occurrences_outside_projection_allowlist"]==18
    assert outcome["raw_json_key_occurrences"]==42
    assert outcome["raw_values_analyzed_for_personal_data"] is False
    assert PRIVATE not in json.dumps(outcome)


@pytest.mark.parametrize("url",[
    "https://www.planning.data.gov.uk/entity/private.json",
    "https://www.planning.data.gov.uk/entity/123.json/../123.json",
    "https://www.planning.data.gov.uk/entity/123.json?query=sensitive",
    "https://www.planning.data.gov.uk/entity/123%2Fprivate.json",
    "https://www.planning.data.gov.uk/entity/-5.json",
    "https://www.planning.data.gov.uk/entity/0.json",
    "https://www.planning.data.gov.uk/entity/0005.json",
    "https://www.planning.data.gov.uk/entity/123.JSON",
    "https://user:password@www.planning.data.gov.uk/entity/123.json",
    "https://attacker.example/entity/123.json",
])
def test_numeric_official_url_only_and_no_network_on_rejection(monkeypatch,url):
    def blocked(*a,**kw):raise AssertionError("unexpected HTTP request")
    monkeypatch.setattr(probe,"build_opener",blocked)
    with pytest.raises(ValueError,match="non-official URL rejected"):
        probe.fetch_official_json(url)


def test_canonical_raw_allowlist_shared_with_source_auditor():
    assert auditor.ALLOWED_RAW_KEYS is probe.APPROVED_SOURCE_INPUT_KEYS
    assert len(probe.APPROVED_SOURCE_INPUT_KEYS)==8
    assert "email" not in probe.APPROVED_SOURCE_INPUT_KEYS
    assert "owner" not in probe.APPROVED_SOURCE_INPUT_KEYS


def test_custody_capture_stays_explicit_three_entity_source_scope():
    with pytest.raises(ValueError,match="LOCKED_OFFICIAL_SOURCE_PILOT_IDS_REQUIRED"):
        custody.capture(now=NOW,entity_ids=(1722645,))


def test_exact_numeric_official_path_is_accepted_before_network():
    for ident in IDS:
        assert probe.OFFICIAL_ENTITY_PATH.fullmatch(f"/entity/{ident}.json")
    assert probe.OFFICIAL_ENTITY_PATH.fullmatch("/entity/3.json")
    assert not probe.OFFICIAL_ENTITY_PATH.fullmatch("/entity/3.json/extra")
    assert not probe.OFFICIAL_ENTITY_PATH.fullmatch("/entity/numeric.json")


def test_snapshot_and_custody_digest_unchanged_after_boundary_minimisation(monkeypatch):
    from empire_os.data_exchange_observation_custody import plan_custody_append
    monkeypatch.setattr(probe,"fetch_official_json",complete_source)
    full_source=custody.capture(now=NOW,fetch_json=complete_source)
    minimized=custody.capture(now=NOW)
    assert minimized==full_source
    original_receipt=plan_custody_append(
        full_source,previous=None,assessed_at=NOW)["row"]
    new_receipt=plan_custody_append(
        minimized,previous=None,assessed_at=NOW)["row"]
    assert new_receipt==original_receipt
    assert new_receipt["sequence"]==0
    assert new_receipt["snapshot_sha256"]==original_receipt["snapshot_sha256"]
    assert new_receipt["chain_sha256"]==original_receipt["chain_sha256"]
