"""V4.4 intake contract tests: test-only fixtures, never production data."""
from __future__ import annotations

import csv
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest

from empire_os.predictive_revenue_company_timeline_v44 import (
    FIELDS, review_company_api_export, review_company_csv_export,
)
from empire_os.predictive_revenue_universal_margin import _canonical_hash

NOW = datetime(2026, 10, 25, 20, tzinfo=timezone.utc)
TENANT = "tenant:demo_contract"
COMPANY = "company:demo_contract"


def event(i, kind, amount=0, month=7, opportunity="opportunity-0001"):
    observed = datetime(2026, month, 5, tzinfo=timezone.utc)
    return {
        "event_id": f"source-event-{i:04d}",
        "opportunity_id": opportunity,
        "event_type": kind,
        "occurred_at_utc": observed.isoformat(),
        "published_at_utc": (observed+timedelta(hours=1)).isoformat(),
        "imported_at_utc": (observed+timedelta(days=1)).isoformat(),
        "amount_minor": amount,
    }


def records():
    return [
        event(1, "OPPORTUNITY_OPENED", month=7),
        event(2, "LEAD_QUALIFIED", month=7),
        event(3, "ORDER_ACCEPTED", month=8),
        event(4, "SETTLEMENT_REPORTED", 13000, month=9),
        event(5, "ACQUISITION_COST_REPORTED", 900, month=8),
        event(6, "FULFILMENT_COST_REPORTED", 1300, month=9),
        event(7, "PROCESSING_COST_REPORTED", 300, month=9),
        event(8, "REFUND_REPORTED", 1400, month=10),
        event(9, "OPPORTUNITY_OPENED", month=7, opportunity="opportunity-0002"),
        event(10, "ORDER_LOST", month=8, opportunity="opportunity-0002"),
    ]


def review(items=None, **params):
    return review_company_api_export(
        records=items if items is not None else records(),
        tenant_scope=TENANT, company_scope=COMPANY, currency="GBP",
        source_system="crm-export", source_reference="export-20261025",
        as_of_utc=NOW.isoformat(), **params,
    )


def csv_export(items):
    raw = StringIO()
    writer = csv.DictWriter(raw, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(items)
    return raw.getvalue()


def review_csv(items=None, **params):
    return review_company_csv_export(
        csv_content=csv_export(items if items is not None else records()),
        tenant_scope=TENANT, company_scope=COMPANY, currency="GBP",
        source_system="crm-export", source_reference="export-20261025",
        as_of_utc=NOW.isoformat(), **params,
    )


def test_company_api_historical_timeline_from_only_supplied_source_events():
    rows = records()
    unchanged = deepcopy(rows)
    report = review(rows)
    assert rows == unchanged
    assert report["received_company_export_rows_not_independently_authenticated"] == 10
    assert report["distinct_opportunities_in_timeline_not_complete_census"] == 2
    assert report["lifecycle_event_counts_not_independently_verified"]["ORDER_LOST"] == 1
    assert report["reported_net_minor_not_recognized_or_realized_revenue"] == 9100
    assert [r["event_month_utc"] for r in report["monthly_event_time_timeline_not_issued_forecasts"]] == [
        "2026-07", "2026-08", "2026-09", "2026-10"
    ]
    assert report["monthly_event_time_timeline_not_issued_forecasts"][2][
        "reported_period_net_minor_not_verified_cash"] == 11400
    assert report["bank_settlement_and_cost_reconciliation_verified"] is False
    assert report["forecast_training_or_model_promotion_authorized"] is False
    assert report["live_forecasts_or_predictions_issued"] is False
    assert report["execution_authority"] == "none"
    assert report["snapshot_sha256_not_external_attestation"] == _canonical_hash({
        k: v for k, v in report.items() if k != "snapshot_sha256_not_external_attestation"
    })


def test_csv_same_historical_numbers_as_previously_exported_api_data():
    a = review()
    b = review_csv()
    for key in (
        "received_company_export_rows_not_independently_authenticated",
        "distinct_opportunities_in_timeline_not_complete_census",
        "reported_money_totals_minor_not_bank_reconciled",
        "monthly_event_time_timeline_not_issued_forecasts",
        "reported_net_minor_not_recognized_or_realized_revenue",
    ):
        assert a[key] == b[key]
    assert b["source_kind"] == "COMPANY_CSV_EXPORT"


def test_cutoff_never_uses_a_backfilled_export_to_predict_the_past():
    cutoff = datetime(2026, 8, 8, tzinfo=timezone.utc)
    r = review(forecast_cutoff_utc=cutoff.isoformat())
    assert r["timeline_rows_available_by_cutoff_unverified"] == 6
    assert r["rows_excluded_due_to_later_ingestion"] == 4
    assert r["reported_money_totals_minor_not_bank_reconciled"]["SETTLEMENT_REPORTED"] == 0
    assert r["reported_net_minor_not_recognized_or_realized_revenue"] == -900
    assert "BACKFILLED_EVENTS_UNAVAILABLE_AT_FORECAST_CUTOFF" in r["hold_reasons"]
    assert r["historical_forecast_issuances_verified"] is False


def test_empty_export_holds_instead_of_inventing_revenue():
    with pytest.raises(ValueError,match="company_timeline_nonempty_bounded_company_records_required"):
        review([])
    with pytest.raises(ValueError,match="company_timeline_nonempty_bounded_company_records_required"):
        review_csv([])


def test_duplicate_or_extra_private_columns_rejected():
    e = event(1, "OPPORTUNITY_OPENED")
    with pytest.raises(ValueError,match="company_timeline_duplicate_source_event_id"):
        review([e,e])
    e["email"] = "private@example.invalid"
    with pytest.raises(ValueError,match="company_timeline_exact_privacy_minimal_event_fields"):
        review([e])
    contents = csv_export(records()).replace("event_id,","email,event_id,",1)
    with pytest.raises(ValueError,match="company_timeline_exact_csv_header_required"):
        review_company_csv_export(
            csv_content=contents,tenant_scope=TENANT,company_scope=COMPANY,
            currency="GBP",source_system="crm-export",source_reference="export-20261025",
            as_of_utc=NOW.isoformat(),
        )


@pytest.mark.parametrize("bad_kind",[
    "SYNTHETIC", "MOCK_SETTLEMENT", "PREDICTION", "BANK_VERIFIED",
    "USER_IDENTITY", "CASH_RECONCILED",
])
def test_unverified_or_fabricated_event_types_never_enter_real_company_path(bad_kind):
    e = event(1,"OPPORTUNITY_OPENED")
    e["event_type"] = bad_kind
    with pytest.raises(ValueError,match="company_timeline_unsupported_lifecycle_event"):
        review([e])


@pytest.mark.parametrize("alteration",[
    {"amount_minor": -1}, {"amount_minor": 1.5},
    {"amount_minor": "100"}, {"amount_minor": True},
    {"amount_minor": 1}, {"amount_minor": 10**14},
])
def test_api_minor_amount_is_exact_integer_and_business_event_compatible(alteration):
    e = event(1, "OPPORTUNITY_OPENED")
    e.update(alteration)
    with pytest.raises(ValueError,match="company_timeline_"):
        review([e])


def test_cash_amount_required_only_on_reported_money_events():
    with pytest.raises(ValueError,match="company_timeline_amount_event_mismatch"):
        review([event(1,"SETTLEMENT_REPORTED",0)])
    with pytest.raises(ValueError,match="company_timeline_amount_event_mismatch"):
        review([event(1,"ORDER_LOST",10)])


@pytest.mark.parametrize("field,days",[
    ("occurred_at_utc", 60),("published_at_utc", -4),
    ("imported_at_utc", -4),
])
def test_bad_event_observation_publication_ingestion_order_is_rejected(field,days):
    e = event(1,"OPPORTUNITY_OPENED")
    e[field] = (datetime.fromisoformat(e[field])+timedelta(days=days)).isoformat()
    with pytest.raises(ValueError,match="company_timeline_event_publication_ingest_order_invalid"):
        review([e])


def test_future_ingestion_rejected_no_survivor_only_history():
    e = event(1,"OPPORTUNITY_OPENED")
    e["imported_at_utc"] = (NOW+timedelta(days=1)).isoformat()
    with pytest.raises(ValueError,match="company_timeline_event_publication_ingest_order_invalid"):
        review([e])


def test_conflicts_and_missing_origins_are_not_silently_counted_as_success():
    items = [
        event(1,"ORDER_LOST", opportunity="opportunity-0099"),
        event(2,"ORDER_ACCEPTED", opportunity="opportunity-0099"),
        event(3,"SETTLEMENT_REPORTED",100,opportunity="opportunity-0098"),
    ]
    report = review(items)
    assert report["opportunities_missing_opening_event"] == 2
    assert report["opportunities_with_conflicting_close_events"] == 1
    assert report["settlement_opportunities_missing_accepted_order"] == 1
    assert "FULL_OPPORTUNITY_AND_FINANCIAL_EVENT_POPULATION_NOT_PROVEN" in report["hold_reasons"]


def test_no_historical_fabrication_and_no_live_future_cutoff():
    with pytest.raises(ValueError,match="company_timeline_future_forecast_cutoff"):
        review(forecast_cutoff_utc=(NOW+timedelta(minutes=1)).isoformat())
    r=review([event(1,"OPPORTUNITY_OPENED")])
    assert r["reported_net_minor_not_recognized_or_realized_revenue"] == 0
    assert r["hold_reasons"]
    assert r["decision"] == "HOLD_UNVERIFIED_COMPANY_HISTORY_NO_LIVE_PREDICTION"


def test_csv_bad_units_and_size_rejected():
    items=records()
    items[0]["amount_minor"]="1.00"
    with pytest.raises(ValueError,match="company_timeline_invalid_csv_minor_units"):
        review_csv(items)
    with pytest.raises(ValueError,match="company_timeline_csv_size_exceeded"):
        review_company_csv_export(
            csv_content=b"x"*2_000_001,
            tenant_scope=TENANT,company_scope=COMPANY,currency="GBP",
            source_system="crm-export",source_reference="export-20261025",
            as_of_utc=NOW.isoformat(),
        )


def test_local_file_intake_accepts_only_previously_supplied_company_exports(tmp_path):
    import json
    from empire_os.predictive_revenue_company_timeline_v44 import (
        review_company_export_file,
    )
    contents=records()
    (tmp_path/"company.csv").write_text(csv_export(contents),encoding="utf-8")
    (tmp_path/"api_export.json").write_text(json.dumps(contents),encoding="utf-8")
    common=dict(source_root=str(tmp_path),tenant_scope=TENANT,
                company_scope=COMPANY,currency="GBP",
                source_system="crm-export",source_reference="export-20261025",
                as_of_utc=NOW.isoformat())
    csv_report=review_company_export_file(
        relative_path="company.csv",export_format="csv",**common)
    json_report=review_company_export_file(
        relative_path="api_export.json",export_format="json",**common)
    assert csv_report["reported_net_minor_not_recognized_or_realized_revenue"]==9100
    assert json_report["reported_net_minor_not_recognized_or_realized_revenue"]==9100
    assert json_report["forecast_training_or_model_promotion_authorized"] is False
    assert json_report["empiredb_or_crm_read_or_written"] is False


def test_local_file_refuses_symlinks_absolute_outside_and_wrong_json_shape(tmp_path):
    import json
    from empire_os.predictive_revenue_company_timeline_v44 import (
        review_company_export_file,
    )
    (tmp_path/"raw.json").write_text(json.dumps({"events": records()}))
    (tmp_path/"alias.json").symlink_to(tmp_path/"raw.json")
    args=dict(source_root=str(tmp_path),export_format="json",
              tenant_scope=TENANT,company_scope=COMPANY,currency="GBP",
              source_system="crm-export",source_reference="export-20261025",
              as_of_utc=NOW.isoformat())
    with pytest.raises(ValueError,match="company_timeline_unsafe_export_locator_or_format"):
        review_company_export_file(relative_path="../raw.json",**args)
    with pytest.raises(ValueError,match="company_timeline_source_not_regular_bounded_file"):
        review_company_export_file(relative_path="alias.json",**args)
    with pytest.raises(ValueError,match="company_timeline_api_export_exact_json_array_required"):
        review_company_export_file(relative_path="raw.json",**args)


# Fake signing keys and rows are strictly isolated in tests. They are never
# a production data feed or an authorised real company identity.
def signed_export_fixture():
    import base64
    import hashlib
    import json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat,
    )
    from empire_os.predictive_revenue_company_timeline_v44 import (
        SIGNED_EXPORT_SCHEMA,
    )
    key = Ed25519PrivateKey.generate()
    payload = json.dumps(records()).encode("utf-8")
    trusted = {
        "source_id": "client-source-0001",
        "tenant_scope": TENANT,
        "company_scope": COMPANY,
        "source_system": "crm-export",
        "key_id": "test-signing-key-0001",
        "public_key_b64": base64.b64encode(
            key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode("ascii"),
        "status": "AUTHORIZED",
        "authorized_at_utc": "2026-06-01T00:00:00+00:00",
        "expires_at_utc": "2026-12-01T00:00:00+00:00",
        "allowed_purpose": "PREDICTIVE_REVENUE_OBSERVE",
    }
    manifest = {
        "schema_version": SIGNED_EXPORT_SCHEMA,
        "source_id": trusted["source_id"],
        "tenant_scope": TENANT,
        "company_scope": COMPANY,
        "source_system": trusted["source_system"],
        "source_reference": "export-20261025",
        "currency": "GBP",
        "export_format": "json",
        "created_at_utc": NOW.isoformat(),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "row_count": len(records()),
        "key_id": trusted["key_id"],
        "is_test_fixture": False,
    }

    def signature(document):
        message = json.dumps(
            document, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
        return base64.b64encode(key.sign(message)).decode("ascii")

    return payload, manifest, signature(manifest), trusted, signature


def signed_review(payload, manifest, signature, trusted):
    from empire_os.predictive_revenue_company_timeline_v44 import (
        review_signed_company_export,
    )
    return review_signed_company_export(
        payload=payload, signed_manifest=manifest,
        signature_b64=signature, trusted_source=trusted,
        as_of_utc=NOW.isoformat(),
    )


def test_signed_export_checks_actual_ed25519_not_just_hash_or_flag():
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    report = signed_review(payload, manifest, signature, trusted)
    assert report["signature_mathematically_valid_for_supplied_trusted_key"] is True
    assert report["historical_company_timeline"][
        "reported_net_minor_not_recognized_or_realized_revenue"] == 9100
    assert report["source_registry_and_data_rights_independently_authenticated"] is False
    assert report["financial_settlement_refunds_or_costs_reconciled"] is False
    assert report["eligible_for_training_or_live_prediction"] is False
    assert report["execution_authority"] == "none"
    brain = report["staging_predictive_brain_read_only"]
    assert brain["mode"] == "STAGING_OBSERVE_NO_AUTONOMOUS_ACTIONS"
    assert brain["adaptive_decay"]["weights_computed_for_company_export"] is False
    assert brain["rpc_risk"]["capital_throttle_active_fail_closed"] is True
    assert brain["historical_activity_anomaly"] is None
    assert brain["automatic_data_quarantine_or_deletion_executed"] is False
    assert brain["training_or_model_promotion_authorized"] is False
    cloud = report["v5_predictive_cloud_staging_read_only"]
    assert cloud["usd_rpc_floor_minor"] == 1800
    assert cloud["capital_risk_throttle_active_all_niches"] is True
    assert cloud["issued_forecast_risk_screens_unverified"] == []
    assert cloud["signal_ingest_research_rows_unverified"] == []
    assert cloud["autonomous_bid_approved_or_sent"] is False
    assert cloud["production_migrations_066_071_applied"] is False
    assert report["snapshot_sha256_not_external_attestation"] == _canonical_hash({
        k:v for k,v in report.items() if k!="snapshot_sha256_not_external_attestation"
    })


@pytest.mark.parametrize("tamper", ["amount","bad_signature","changed_manifest"])
def test_signed_export_rejects_mutation_or_false_signature(tamper):
    import json
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    if tamper == "amount":
        changed = json.loads(payload)
        changed[3]["amount_minor"] += 10
        payload = json.dumps(changed).encode()
        error = "company_export_payload_fingerprint_mismatch"
    elif tamper == "bad_signature":
        signature = "AA" * 40
        error = "company_export_signature_verification_failed"
    else:
        manifest["row_count"] += 1
        error = "company_export_signature_verification_failed"
    with pytest.raises(ValueError, match=error):
        signed_review(payload,manifest,signature,trusted)


@pytest.mark.parametrize("status,purpose", [
    ("REVOKED","PREDICTIVE_REVENUE_OBSERVE"),
    ("PENDING_AUTHORIZATION","PREDICTIVE_REVENUE_OBSERVE"),
    ("AUTHORIZED","PAYMENTS_EXECUTE"),
])
def test_signed_export_never_trusts_unsigned_revocation_or_purpose_override(status,purpose):
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    trusted["status"] = status
    trusted["allowed_purpose"] = purpose
    with pytest.raises(ValueError,match="company_export_source_not_authorized_for_this_purpose"):
        signed_review(payload,manifest,signature,trusted)


@pytest.mark.parametrize("tamper", ["tenant","company","key","system"])
def test_signed_export_cannot_cross_verified_registry_scopes(tamper):
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    field = {"tenant":"tenant_scope","company":"company_scope",
             "key":"key_id","system":"source_system"}[tamper]
    trusted[field] = "different-scope-0001"
    with pytest.raises(ValueError,match="company_export_source_registry_scope_mismatch"):
        signed_review(payload,manifest,signature,trusted)


def test_signed_export_rejects_test_fixture_even_with_genuine_test_key_signature():
    payload, manifest, _, trusted, sign = signed_export_fixture()
    manifest["is_test_fixture"] = True
    with pytest.raises(ValueError,match="company_export_test_fixture_or_invalid_source_manifest"):
        signed_review(payload,manifest,sign(manifest),trusted)


def test_signed_export_refuses_expired_source_even_with_valid_signature():
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    trusted["expires_at_utc"] = "2026-10-24T00:00:00+00:00"
    with pytest.raises(ValueError,match="company_export_source_authorization_or_timeline_expired"):
        signed_review(payload,manifest,signature,trusted)


def test_signed_export_rejects_signed_row_count_mismatch():
    payload, manifest, _, trusted, sign = signed_export_fixture()
    manifest["row_count"] = 11
    with pytest.raises(ValueError,match="company_export_signed_row_count_mismatch"):
        signed_review(payload,manifest,sign(manifest),trusted)


def test_signed_export_rejects_self_supplied_untrusted_extra_registry_field():
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    trusted["can_write_to_empiredb"] = True
    with pytest.raises(ValueError,match="company_export_exact_bounded_signed_contract_required"):
        signed_review(payload,manifest,signature,trusted)


def signed_files(tmp_path):
    import json
    payload, manifest, signature, trusted, _ = signed_export_fixture()
    export_root=tmp_path/"company_export"
    registry_root=tmp_path/"owner_registry"
    export_root.mkdir()
    registry_root.mkdir()
    (export_root/"events.json").write_bytes(payload)
    (export_root/"manifest.json").write_text(json.dumps(manifest))
    (export_root/"manifest.sig").write_text(signature+"\n")
    (registry_root/"source.json").write_text(json.dumps(trusted))
    return export_root,registry_root


def review_from_signed_files(export_root,registry_root,**overrides):
    from empire_os.predictive_revenue_company_timeline_v44 import (
        review_signed_company_export_files,
    )
    args=dict(source_root=str(export_root),
              payload_file="events.json",manifest_file="manifest.json",
              signature_file="manifest.sig",trusted_root=str(registry_root),
              trusted_file="source.json",expected_tenant=TENANT,
              expected_company=COMPANY,as_of_utc=NOW.isoformat())
    args.update(overrides)
    return review_signed_company_export_files(**args)


def test_v421_signed_files_staged_integration_is_readonly_and_consistent(tmp_path):
    export_root,registry_root=signed_files(tmp_path)
    report=review_from_signed_files(export_root,registry_root)
    assert report["decision"]=="SIGNED_EXPORT_READ_ONLY_HOLD_UNVERIFIED_BUSINESS_HISTORY"
    assert report["signature_mathematically_valid_for_supplied_trusted_key"] is True
    assert report["historical_company_timeline"][
        "reported_net_minor_not_recognized_or_realized_revenue"]==9100
    assert report["empiredb_or_smart_crm_read_or_written"] is False
    assert report["model_promotion_or_payment_authorized"] is False


@pytest.mark.parametrize("name",["events.json","manifest.json","manifest.sig"])
def test_v421_signed_intake_missing_export_part_fails_closed(tmp_path,name):
    export_root,registry_root=signed_files(tmp_path)
    (export_root/name).unlink()
    with pytest.raises(ValueError,match="company_export_"):
        review_from_signed_files(export_root,registry_root)


def test_v421_signed_intake_requires_independent_registry_path_and_authorized_scope(tmp_path):
    export_root,registry_root=signed_files(tmp_path)
    with pytest.raises(ValueError,match="company_export_source_and_trust_roots_must_differ"):
        review_from_signed_files(export_root,export_root)
    with pytest.raises(ValueError,match="company_export_wrong_requested_company_or_tenant"):
        review_from_signed_files(export_root,registry_root,
                                 expected_company="company:other")
    (registry_root/"source.json").unlink()
    with pytest.raises(ValueError,match="company_export_"):
        review_from_signed_files(export_root,registry_root)


def test_v421_signed_intake_rejects_aliases_and_parent_path_traversal(tmp_path):
    export_root,registry_root=signed_files(tmp_path)
    (export_root/"symlink.json").symlink_to(export_root/"events.json")
    with pytest.raises(ValueError,match="company_export_symlink_not_authorized"):
        review_from_signed_files(export_root,registry_root,
                                 payload_file="symlink.json")
    with pytest.raises(ValueError,match="company_export_unsafe_relative_file"):
        review_from_signed_files(export_root,registry_root,
                                 payload_file="../company_export/events.json")


def test_v421_signed_intake_rejects_changed_payload_even_with_intact_manifest(tmp_path):
    export_root,registry_root=signed_files(tmp_path)
    with (export_root/"events.json").open("ab") as fh:
        fh.write(b" ")
    with pytest.raises(ValueError,match="company_export_payload_fingerprint_mismatch"):
        review_from_signed_files(export_root,registry_root)


def test_v421_signed_cli_requires_signature_trust_root_and_prints_only_aggregates(
    tmp_path, monkeypatch, capsys,
):
    import sys
    import json
    from empire_os.predictive_revenue_company_timeline_v44 import main
    export_root,registry_root=signed_files(tmp_path)
    argv=["-m","--source-root",str(export_root),
          "--relative-file","events.json",
          "--manifest-file","manifest.json",
          "--signature-file","manifest.sig",
          "--trusted-root",str(registry_root),
          "--trusted-file","source.json",
          "--tenant",TENANT,"--company",COMPANY,
          "--as-of-utc",NOW.isoformat()]
    monkeypatch.setattr(sys,"argv",argv)
    assert main()==0
    printed=capsys.readouterr().out
    report=json.loads(printed)
    assert report["historical_company_timeline"][
        "distinct_opportunities_in_timeline_not_complete_census"]==2
    assert report["execution_authority"]=="none"
    assert "source-event-0001" not in printed
    assert "public_key_b64" not in printed
    assert "private_key" not in printed
    # An unsigned invocation of the public entrypoint must fail.
    monkeypatch.setattr(sys,"argv",["-m","--source-root",str(export_root),
                                  "--relative-file","events.json"])
    with pytest.raises(SystemExit) as err:
        main()
    assert err.value.code==2


def test_v421_staged_cli_real_python_module_path(tmp_path):
    import subprocess
    import sys
    import json
    export_root,registry_root=signed_files(tmp_path)
    command=[sys.executable,"-B","-m",
             "empire_os.predictive_revenue_company_timeline_v44",
             "--source-root",str(export_root),
             "--relative-file","events.json",
             "--manifest-file","manifest.json",
             "--signature-file","manifest.sig",
             "--trusted-root",str(registry_root),
             "--trusted-file","source.json",
             "--tenant",TENANT,"--company",COMPANY,
             "--as-of-utc",NOW.isoformat()]
    result=subprocess.run(command,capture_output=True,text=True,
                          check=True,timeout=10)
    parsed=json.loads(result.stdout)
    assert parsed["decision"]=="SIGNED_EXPORT_READ_ONLY_HOLD_UNVERIFIED_BUSINESS_HISTORY"
    assert parsed["financial_settlement_refunds_or_costs_reconciled"] is False
