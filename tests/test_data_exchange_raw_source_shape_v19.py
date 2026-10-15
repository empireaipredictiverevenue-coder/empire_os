"""V19 privacy surface: bounded live JSON key audit, never log raw values."""
from datetime import datetime, timezone
import json
import pytest
from scripts import audit_data_exchange_raw_source_shape_v19 as audit

NOW=datetime(2026,10,15,12,tzinfo=timezone.utc)
IDS=(1722645,1739516,1739547)


def source(url):
    ident=int(url.split("/")[-1].removesuffix(".json"))
    return {
        "entity":ident,"dataset":"brownfield-land",
        "quality":"authoritative","organisation-entity":207,
        "end-date":None,"planning-permission-status":"non-permissioned",
        "hectares":"1.25","entry-date":"2022-03-01",
        "email":"PRIVATE_PERSON@example.invalid",
        "owner":"PRIVATE_NAME_MUST_NOT_PRINT",
        "site-address":"PRIVATE_ADDRESS_MUST_NOT_PRINT",
        "notes":"PRIVATE_NOTES_MUST_NOT_PRINT",
        "contactPoint":"PRIVATE_CONTACT_MUST_NOT_PRINT",
    }


def test_traces_live_source_keys_without_leaking_any_payload():
    urls=[]
    def fetch(url):
        urls.append(url)
        return source(url)
    r=audit.audit_source_key_shapes(now=NOW,fetch_json=fetch)
    assert urls==[
        f"https://www.planning.data.gov.uk/entity/{i}.json"
        for i in IDS
    ]
    assert r["status"]=="TRANSIENT_RAW_KEY_INVENTORY_COMPLETED_NOT_PRIVACY_SIGNOFF"
    assert r["official_entity_responses_checked"]==3
    assert r["raw_json_key_occurrences"]==39
    assert r["raw_json_key_occurrences_outside_projection_allowlist"]==15
    assert r["potentially_sensitive_key_name_occurrences"]>=12
    assert r["potentially_sensitive_key_names_detected"] is True
    assert r["personal_information_in_raw_payload"]=="UNKNOWN_NOT_REVIEWED"
    assert r["raw_values_analyzed_for_personal_data"] is False
    assert r["raw_response_logged_or_persisted_by_audit"] is False
    assert r["personal_contact_fields_persisted_in_projection"] is False
    assert r["customer_delivery_enabled"] is False
    serialized=json.dumps(r)
    for secret in ("PRIVATE_PERSON","PRIVATE_NAME","PRIVATE_ADDRESS","PRIVATE_NOTES","PRIVATE_CONTACT"):
        assert secret not in serialized


def test_raw_source_minimal_schema_still_valid_but_no_privacy_clearance():
    def minimal(url):
        data=source(url)
        for key in ("email","owner","site-address","notes","contactPoint"):
            data.pop(key)
        return data
    r=audit.audit_source_key_shapes(now=NOW,fetch_json=minimal)
    assert r["raw_json_key_occurrences_outside_projection_allowlist"]==0
    assert r["potentially_sensitive_key_names_detected"] is False
    assert r["personal_information_in_raw_payload"]=="UNKNOWN_NOT_REVIEWED"
    assert r["independent_privacy_review_completed"] is False


@pytest.mark.parametrize("mutation",[
    lambda d:d.update({"entity":9999}),
    lambda d:d.update({"quality":"unknown"}),
    lambda d:d.update({"organisation-entity":9999}),
])
def test_invalid_raw_source_never_returns_pass(mutation):
    def fetch(url):
        d=source(url)
        mutation(d)
        return d
    with pytest.raises(ValueError):
        audit.audit_source_key_shapes(now=NOW,fetch_json=fetch)


def test_more_than_256_top_level_fields_is_held_without_dumping_any_values():
    def fetch(url):
        d=source(url)
        d.update({f"extra-field-{i}":"PRIVATE_UNREVIEWED" for i in range(300)})
        return d
    with pytest.raises(ValueError):
        audit.audit_source_key_shapes(now=NOW,fetch_json=fetch)


def test_cli_requires_explicit_readonly_flag(monkeypatch,capsys):
    monkeypatch.setattr(audit,"fetch_official_json",
        lambda url:(_ for _ in ()).throw(AssertionError("network prohibited")))
    assert audit.main([])==2
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="HOLD_SOURCE_KEY_INVENTORY_UNVERIFIED"
    assert result["customer_delivery_enabled"] is False


def test_cli_reports_aggregate_counts_only(monkeypatch,capsys):
    monkeypatch.setattr(audit,"fetch_official_json",source)
    assert audit.main(["--read-only"])==0
    output=capsys.readouterr().out
    assert "PRIVATE_" not in output
    assert "PRIVATE_PERSON" not in output
    assert "owner" not in output
    assert json.loads(output)["database_writes"] is False


def test_exception_is_redacted_not_leaked(monkeypatch,capsys):
    monkeypatch.setattr(audit,"fetch_official_json",
        lambda url:(_ for _ in ()).throw(
            RuntimeError("PRIVATE_EMAIL@EXAMPLE.INVALID password=SECRET")))
    assert audit.main(["--read-only"])==2
    raw=capsys.readouterr().out
    assert "PRIVATE_EMAIL" not in raw
    assert "SECRET" not in raw
    assert json.loads(raw)["raw_keys_and_values_disclosed"] is False
