"""V4.4 original Predictive Revenue: bounded company API/CSV timeline intake.

Real client exports only. No generated observations, network fetching,
database writes, model fitting, inferred cash finality, or live forecasts.
A supplied company export is evidence to review, NOT authenticated truth.
"""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import Any, Callable, Mapping, Sequence
import re

from empire_os.predictive_revenue_universal_margin import (
    _canonical_hash, _string, _utc,
)

SCHEMA = "empire.predictive-revenue-company-timeline.v4.4.read-only"
FIELDS = (
    "event_id", "opportunity_id", "event_type",
    "occurred_at_utc", "published_at_utc", "imported_at_utc",
    "amount_minor",
)
LIFECYCLE = frozenset({
    "OPPORTUNITY_OPENED", "LEAD_QUALIFIED", "ORDER_ACCEPTED",
    "ORDER_LOST", "FULFILMENT_COMPLETED",
})
MONEY = frozenset({
    "SETTLEMENT_REPORTED", "REFUND_REPORTED", "CLAWBACK_REPORTED",
    "ACQUISITION_COST_REPORTED", "FULFILMENT_COST_REPORTED",
    "PROCESSING_COST_REPORTED",
})
EVENT_TYPES = LIFECYCLE | MONEY
KINDS = frozenset({"COMPANY_API_EXPORT", "COMPANY_CSV_EXPORT"})
MAX_ROWS = 10000
MAX_BYTES = 2_000_000
MAX_MINOR = 10**13


def _int_minor(value: Any, *, from_csv: bool) -> int:
    if from_csv:
        if not isinstance(value, str) or re.fullmatch(r"0|[1-9][0-9]{0,13}", value) is None:
            raise ValueError("company_timeline_invalid_csv_minor_units")
        value = int(value)
    if type(value) is not int or not 0 <= value <= MAX_MINOR:
        raise ValueError("company_timeline_invalid_minor_units")
    return value


def _scope(value: Any, name: str) -> str:
    return _string(value, name, r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,100}")


def _review(*, records: Sequence[Mapping[str, Any]], source_kind: str,
            tenant_scope: str, company_scope: str, currency: str,
            source_system: str, source_reference: str,
            as_of_utc: str, forecast_cutoff_utc: str | None,
            from_csv: bool) -> dict:
    if source_kind not in KINDS:
        raise ValueError("company_timeline_only_company_api_or_csv_exports")
    tenant = _scope(tenant_scope, "tenant_scope")
    company = _scope(company_scope, "company_scope")
    system = _scope(source_system, "source_system")
    reference = _scope(source_reference, "source_reference")
    currency = _string(currency, "currency", r"[A-Z]{3}")
    now = _utc(as_of_utc)
    cutoff = _utc(forecast_cutoff_utc) if forecast_cutoff_utc is not None else now
    if cutoff > now:
        raise ValueError("company_timeline_future_forecast_cutoff")
    if (not isinstance(records, (list, tuple))
        or not 0 < len(records) <= MAX_ROWS):
        raise ValueError("company_timeline_nonempty_bounded_company_records_required")

    event_ids = set()
    accepted = []
    for item in records:
        if not isinstance(item, Mapping) or set(item) != set(FIELDS):
            raise ValueError("company_timeline_exact_privacy_minimal_event_fields")
        event_id = _scope(item["event_id"], "event_id")
        opportunity = _scope(item["opportunity_id"], "opportunity_id")
        if event_id in event_ids:
            raise ValueError("company_timeline_duplicate_source_event_id")
        event_ids.add(event_id)
        kind = item["event_type"]
        if kind not in EVENT_TYPES:
            raise ValueError("company_timeline_unsupported_lifecycle_event")
        amount = _int_minor(item["amount_minor"], from_csv=from_csv)
        if ((kind in LIFECYCLE and amount != 0)
            or (kind in MONEY and amount == 0)):
            raise ValueError("company_timeline_amount_event_mismatch")
        occurred = _utc(item["occurred_at_utc"])
        published = _utc(item["published_at_utc"])
        imported = _utc(item["imported_at_utc"])
        if not occurred <= published <= imported <= now:
            raise ValueError("company_timeline_event_publication_ingest_order_invalid")
        accepted.append({
            "event_id": event_id, "opportunity_id": opportunity,
            "event_type": kind, "amount_minor": amount,
            "occurred_at_utc": occurred, "published_at_utc": published,
            "imported_at_utc": imported,
        })

    # Never pretend that a retrospective export was available before
    # the original ingestion and publication timestamps.
    usable = [r for r in accepted if r["imported_at_utc"] <= cutoff]
    excluded = len(accepted) - len(usable)
    months: dict[str, dict[str, Any]] = {}
    per_opportunity: dict[str, set[str]] = {}
    money_totals = {key: 0 for key in MONEY}
    lifecycle_totals = {key: 0 for key in LIFECYCLE}
    for r in sorted(usable, key=lambda x:(x["occurred_at_utc"], x["event_id"])):
        period = r["occurred_at_utc"].strftime("%Y-%m")
        month = months.setdefault(period, {
            "event_month_utc": period,
            "source_events": 0,
            "unique_opportunities": set(),
            "opportunities_opened_events": 0,
            "orders_accepted_events": 0,
            "orders_lost_events": 0,
            "settlement_reported_minor": 0,
            "refund_reported_minor": 0,
            "clawback_reported_minor": 0,
            "cost_reported_minor": 0,
        })
        month["source_events"] += 1
        month["unique_opportunities"].add(r["opportunity_id"])
        per_opportunity.setdefault(r["opportunity_id"], set()).add(r["event_type"])
        t = r["event_type"]
        if t in MONEY:
            money_totals[t] += r["amount_minor"]
        else:
            lifecycle_totals[t] += 1
        if t == "OPPORTUNITY_OPENED":
            month["opportunities_opened_events"] += 1
        elif t == "ORDER_ACCEPTED":
            month["orders_accepted_events"] += 1
        elif t == "ORDER_LOST":
            month["orders_lost_events"] += 1
        elif t == "SETTLEMENT_REPORTED":
            month["settlement_reported_minor"] += r["amount_minor"]
        elif t == "REFUND_REPORTED":
            month["refund_reported_minor"] += r["amount_minor"]
        elif t == "CLAWBACK_REPORTED":
            month["clawback_reported_minor"] += r["amount_minor"]
        elif t in {"ACQUISITION_COST_REPORTED", "FULFILMENT_COST_REPORTED",
                   "PROCESSING_COST_REPORTED"}:
            month["cost_reported_minor"] += r["amount_minor"]
    missing_open = sum("OPPORTUNITY_OPENED" not in types
                       for types in per_opportunity.values())
    inconsistent = sum("ORDER_LOST" in types and
                       ("ORDER_ACCEPTED" in types or "SETTLEMENT_REPORTED" in types)
                       for types in per_opportunity.values())
    settlement_without_order = sum(
        "SETTLEMENT_REPORTED" in types and "ORDER_ACCEPTED" not in types
        for types in per_opportunity.values()
    )
    chronological = []
    for period in sorted(months):
        value = months[period]
        value["unique_opportunities"] = len(value["unique_opportunities"])
        value["reported_period_net_minor_not_verified_cash"] = (
            value["settlement_reported_minor"] - value["refund_reported_minor"]
            - value["clawback_reported_minor"] - value["cost_reported_minor"]
        )
        chronological.append(value)
    net_candidate = (
        money_totals["SETTLEMENT_REPORTED"]
        - money_totals["REFUND_REPORTED"]
        - money_totals["CLAWBACK_REPORTED"]
        - money_totals["ACQUISITION_COST_REPORTED"]
        - money_totals["FULFILMENT_COST_REPORTED"]
        - money_totals["PROCESSING_COST_REPORTED"]
    )
    problems = []
    if excluded:
        problems.append("BACKFILLED_EVENTS_UNAVAILABLE_AT_FORECAST_CUTOFF")
    if missing_open:
        problems.append("MISSING_OPPORTUNITY_ORIGINATION_EVENTS")
    if inconsistent:
        problems.append("CONFLICTING_LOSS_AND_ACCEPTANCE_EVENT_HISTORY")
    if settlement_without_order:
        problems.append("REPORTED_SETTLEMENT_WITHOUT_ACCEPTED_ORDER_HISTORY")
    if len(chronological) < 3:
        problems.append("FEWER_THAN_THREE_EVENT_MONTHS")
    problems.extend([
        "COMPANY_EXPORT_AUTHENTICITY_AND_DATA_RIGHTS_NOT_INDEPENDENTLY_VERIFIED",
        "FULL_OPPORTUNITY_AND_FINANCIAL_EVENT_POPULATION_NOT_PROVEN",
        "NO_PREEXISTING_AUTHENTICATED_FORECAST_ISSUANCES",
    ])
    report = {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_COMPANY_EXPORT_REVIEW",
        "original_platform": "EmpireOS / EmpireDB / Smart CRM",
        "tenant_scope": tenant, "company_scope": company, "currency": currency,
        "source_kind": source_kind, "source_system": system,
        "source_reference_supplied_not_attested": reference,
        "as_of_utc": now.isoformat(), "forecast_cutoff_utc": cutoff.isoformat(),
        "received_company_export_rows_not_independently_authenticated": len(accepted),
        "timeline_rows_available_by_cutoff_unverified": len(usable),
        "rows_excluded_due_to_later_ingestion": excluded,
        "distinct_opportunities_in_timeline_not_complete_census": len(per_opportunity),
        "lifecycle_event_counts_not_independently_verified": lifecycle_totals,
        "reported_money_totals_minor_not_bank_reconciled": money_totals,
        "reported_net_minor_not_recognized_or_realized_revenue": net_candidate,
        "monthly_event_time_timeline_not_issued_forecasts": chronological,
        "opportunities_missing_opening_event": missing_open,
        "opportunities_with_conflicting_close_events": inconsistent,
        "settlement_opportunities_missing_accepted_order": settlement_without_order,
        "source_rows_not_anonymous": True,
        "company_export_source_and_rights_verified": False,
        "complete_canonical_population_verified": False,
        "bank_settlement_and_cost_reconciliation_verified": False,
        "historical_forecast_issuances_verified": False,
        "source_ingestion_receipts_independently_attested": False,
        "forecast_training_or_model_promotion_authorized": False,
        "live_forecasts_or_predictions_issued": False,
        "empiredb_or_crm_read_or_written": False,
        "paid_media_outbound_trades_or_funds_authorized": False,
        "execution_authority": "none",
        "hold_reasons": sorted(problems),
        "decision": "HOLD_UNVERIFIED_COMPANY_HISTORY_NO_LIVE_PREDICTION",
    }
    report["snapshot_sha256_not_external_attestation"] = _canonical_hash(report)
    return report


def review_company_api_export(*, records: Sequence[Mapping[str, Any]],
                              tenant_scope: str, company_scope: str, currency: str,
                              source_system: str, source_reference: str,
                              as_of_utc: str, forecast_cutoff_utc: str | None = None) -> dict:
    """Review a *previously obtained* API JSON array; do not fetch an endpoint."""
    return _review(
        records=records, source_kind="COMPANY_API_EXPORT",
        tenant_scope=tenant_scope, company_scope=company_scope,
        currency=currency, source_system=source_system,
        source_reference=source_reference, as_of_utc=as_of_utc,
        forecast_cutoff_utc=forecast_cutoff_utc, from_csv=False,
    )


def review_company_csv_export(*, csv_content: str | bytes,
                              tenant_scope: str, company_scope: str, currency: str,
                              source_system: str, source_reference: str,
                              as_of_utc: str, forecast_cutoff_utc: str | None = None) -> dict:
    """Review supplied CSV bytes, with a strict privacy-minimal header."""
    if not isinstance(csv_content, (str, bytes)):
        raise ValueError("company_timeline_csv_text_or_bytes_required")
    if isinstance(csv_content, bytes):
        if len(csv_content) > MAX_BYTES:
            raise ValueError("company_timeline_csv_size_exceeded")
        csv_content = csv_content.decode("utf-8-sig")
    if len(csv_content.encode("utf-8")) > MAX_BYTES:
        raise ValueError("company_timeline_csv_size_exceeded")
    reader = csv.DictReader(StringIO(csv_content, newline=""), strict=True)
    if reader.fieldnames != list(FIELDS):
        raise ValueError("company_timeline_exact_csv_header_required")
    records = []
    for row in reader:
        if len(records) >= MAX_ROWS:
            raise ValueError("company_timeline_csv_row_limit")
        if None in row or any(value is None for value in row.values()):
            raise ValueError("company_timeline_csv_columns_malformed")
        records.append(row)
    return _review(
        records=records, source_kind="COMPANY_CSV_EXPORT",
        tenant_scope=tenant_scope, company_scope=company_scope,
        currency=currency, source_system=source_system,
        source_reference=source_reference, as_of_utc=as_of_utc,
        forecast_cutoff_utc=forecast_cutoff_utc, from_csv=True,
    )


def review_company_export_file(*, source_root: str, relative_path: str,
                               export_format: str, tenant_scope: str,
                               company_scope: str, currency: str,
                               source_system: str, source_reference: str,
                               as_of_utc: str,
                               forecast_cutoff_utc: str | None = None) -> dict:
    """Review one stable bounded local company export, without network or DB."""
    import json
    from pathlib import Path

    root = Path(source_root).resolve()
    relative = Path(relative_path)
    if (relative.is_absolute() or ".." in relative.parts
        or not relative.parts or export_format not in {"csv", "json"}):
        raise ValueError("company_timeline_unsafe_export_locator_or_format")
    path = root / relative
    if (path.is_symlink() or not path.is_file()
        or not path.resolve().is_relative_to(root)):
        raise ValueError("company_timeline_source_not_regular_bounded_file")
    before = path.stat()
    if not 0 < before.st_size <= MAX_BYTES:
        raise ValueError("company_timeline_source_size_invalid")
    content = path.read_bytes()
    after = path.stat()
    if (len(content) != before.st_size or len(content) != after.st_size
        or before.st_ino != after.st_ino
        or before.st_mtime_ns != after.st_mtime_ns):
        raise ValueError("company_timeline_source_changed_during_read")
    args = dict(
        tenant_scope=tenant_scope, company_scope=company_scope,
        currency=currency, source_system=source_system,
        source_reference=source_reference, as_of_utc=as_of_utc,
        forecast_cutoff_utc=forecast_cutoff_utc,
    )
    if export_format == "csv":
        return review_company_csv_export(csv_content=content, **args)
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError("company_timeline_api_export_exact_json_array_required")
    return review_company_api_export(records=payload, **args)


def main() -> int:
    """V4.21 staged signed-export CLI, deliberately without a live writer."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Verify a signed company timeline export; read-only HOLD")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--relative-file", required=True)
    parser.add_argument("--manifest-file", required=True)
    parser.add_argument("--signature-file", required=True)
    parser.add_argument("--trusted-root", required=True)
    parser.add_argument("--trusted-file", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--as-of-utc", required=True)
    parser.add_argument("--forecast-cutoff-utc")
    opts = parser.parse_args()
    report = review_signed_company_export_files(
        source_root=opts.source_root, payload_file=opts.relative_file,
        manifest_file=opts.manifest_file,
        signature_file=opts.signature_file,
        trusted_root=opts.trusted_root, trusted_file=opts.trusted_file,
        expected_tenant=opts.tenant, expected_company=opts.company,
        as_of_utc=opts.as_of_utc,
        forecast_cutoff_utc=opts.forecast_cutoff_utc,
    )
    # Only aggregate pseudonymous timeline diagnostics leave the CLI.
    # The raw records, signing key and OAuth credentials are never printed.
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


# V4.21 signed-export evidence boundary. A caller must obtain the trusted
# source registry entry through a separate, authorised owner-controlled lane.
# Never trust keys, permissions or test-fixture claims embedded in the export.
SIGNED_EXPORT_SCHEMA = "empire.predictive-revenue-company-export.v4.21"
SIGNED_MANIFEST_FIELDS = frozenset({
    "schema_version", "source_id", "tenant_scope", "company_scope",
    "source_system", "source_reference", "currency", "export_format",
    "created_at_utc", "payload_sha256", "row_count", "key_id",
    "is_test_fixture",
})
TRUSTED_SOURCE_FIELDS = frozenset({
    "source_id", "tenant_scope", "company_scope", "source_system",
    "key_id", "public_key_b64", "status", "authorized_at_utc",
    "expires_at_utc", "allowed_purpose",
})


def review_signed_company_export(*, payload: bytes,
    signed_manifest: Mapping[str, Any], signature_b64: str,
    trusted_source: Mapping[str, Any], as_of_utc: str,
    forecast_cutoff_utc: str | None = None,
    signal_rows: Sequence[Mapping[str, Any]] = (),
    issued_forecast_rows: Sequence[Mapping[str, Any]] = ()) -> dict:
    """Verify Ed25519 source signature and report an untrusted company timeline.

    Cryptographic validity is conditional on the independently supplied trusted
    registry entry. It proves neither client data rights nor settlement truth.
    No production write, forecast, network request or fitted model occurs.
    """
    import base64
    import binascii
    from hashlib import sha256
    import json

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )

    if (not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES
        or not isinstance(signed_manifest, Mapping)
        or set(signed_manifest) != SIGNED_MANIFEST_FIELDS
        or not isinstance(trusted_source, Mapping)
        or set(trusted_source) != TRUSTED_SOURCE_FIELDS):
        raise ValueError("company_export_exact_bounded_signed_contract_required")

    manifest = dict(signed_manifest)
    trusted = dict(trusted_source)
    if (manifest["schema_version"] != SIGNED_EXPORT_SCHEMA
        or type(manifest["is_test_fixture"]) is not bool
        or manifest["is_test_fixture"] is not False
        or manifest["export_format"] not in {"csv", "json"}
        or type(manifest["row_count"]) is not int
        or not 1 <= manifest["row_count"] <= MAX_ROWS):
        raise ValueError("company_export_test_fixture_or_invalid_source_manifest")

    for key in ("source_id", "tenant_scope", "company_scope",
                "source_system", "key_id"):
        value = _scope(manifest[key], key)
        if trusted[key] != value:
            raise ValueError("company_export_source_registry_scope_mismatch")
    _scope(manifest["source_reference"], "source_reference")
    _string(manifest["currency"], "currency", r"[A-Z]{3}")
    if (trusted["status"] != "AUTHORIZED"
        or trusted["allowed_purpose"] != "PREDICTIVE_REVENUE_OBSERVE"):
        raise ValueError("company_export_source_not_authorized_for_this_purpose")

    now = _utc(as_of_utc)
    created = _utc(manifest["created_at_utc"])
    allowed_from = _utc(trusted["authorized_at_utc"])
    allowed_until = _utc(trusted["expires_at_utc"])
    if not allowed_from <= created <= now <= allowed_until:
        raise ValueError("company_export_source_authorization_or_timeline_expired")
    if (type(manifest["payload_sha256"]) is not str
        or not re.fullmatch(r"[a-f0-9]{64}", manifest["payload_sha256"])
        or manifest["payload_sha256"] != sha256(payload).hexdigest()):
        raise ValueError("company_export_payload_fingerprint_mismatch")

    try:
        if not isinstance(signature_b64, str):
            raise ValueError("company_export_signature_missing")
        raw_signature = base64.b64decode(signature_b64, validate=True)
        raw_public_key = base64.b64decode(trusted["public_key_b64"], validate=True)
        if len(raw_signature) != 64 or len(raw_public_key) != 32:
            raise ValueError("company_export_invalid_key_or_signature_length")
        signed_bytes = json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        Ed25519PublicKey.from_public_bytes(raw_public_key).verify(
            raw_signature, signed_bytes
        )
    except (ValueError, TypeError, binascii.Error, InvalidSignature) as exc:
        raise ValueError("company_export_signature_verification_failed") from exc

    args = dict(
        tenant_scope=manifest["tenant_scope"],
        company_scope=manifest["company_scope"],
        currency=manifest["currency"],
        source_system=manifest["source_system"],
        source_reference=manifest["source_reference"],
        as_of_utc=as_of_utc,
        forecast_cutoff_utc=forecast_cutoff_utc,
    )
    if manifest["export_format"] == "csv":
        timeline = review_company_csv_export(csv_content=payload, **args)
    else:
        try:
            items = json.loads(payload)
        except (UnicodeError, ValueError, TypeError) as exc:
            raise ValueError("company_export_invalid_json_payload") from exc
        if not isinstance(items, list):
            raise ValueError("company_export_expected_json_array")
        timeline = review_company_api_export(records=items, **args)
    if (timeline[
            "received_company_export_rows_not_independently_authenticated"]
        != manifest["row_count"]):
        raise ValueError("company_export_signed_row_count_mismatch")

    result = {
        "schema_version": "empire.predictive-revenue-company-export-review.v4.21",
        "mode": "SIGNED_COMPANY_EXPORT_REVIEW_ONLY",
        "source_id": manifest["source_id"],
        "tenant_scope": timeline["tenant_scope"],
        "company_scope": timeline["company_scope"],
        "source_system": manifest["source_system"],
        "source_reference": manifest["source_reference"],
        "currency": timeline["currency"],
        "as_of_utc": timeline["as_of_utc"],
        "export_created_at_utc": created.isoformat(),
        "payload_sha256": manifest["payload_sha256"],
        "signed_manifest_sha256": sha256(signed_bytes).hexdigest(),
        "signature_mathematically_valid_for_supplied_trusted_key": True,
        "source_registry_and_data_rights_independently_authenticated": False,
        "provider_api_oauth_credential_verified": False,
        "replay_protection_against_prior_batches_verified": False,
        "export_not_a_canonical_issuance_or_bank_receipt": True,
        "historical_company_timeline": timeline,
        "company_event_population_complete_verified": False,
        "financial_settlement_refunds_or_costs_reconciled": False,
        "eligible_for_training_or_live_prediction": False,
        "model_promotion_or_payment_authorized": False,
        "empiredb_or_smart_crm_read_or_written": False,
        "execution_authority": "none",
        "decision": "SIGNED_EXPORT_READ_ONLY_HOLD_UNVERIFIED_BUSINESS_HISTORY",
    }
    # V4.21 original staging brain: only after signed source and history
    # validation; do not smuggle a raw/unverified export into this path.
    from empire_os.predictive_revenue_brain_staging_v421 import (
        inspect_signed_company_brain,
    )
    result["snapshot_sha256_not_external_attestation"] = _canonical_hash(result)
    result["staging_predictive_brain_read_only"] = inspect_signed_company_brain(
        signed_review=result
    )
    result["snapshot_sha256_not_external_attestation"] = _canonical_hash({
        k: v for k, v in result.items()
        if k != "snapshot_sha256_not_external_attestation"
    })
    # V5 reuses the ORIGINAL V4.21 maths and signed-source review;
    # supplied observations and issued rows remain unverified research.
    # Empty inputs remain the backward-compatible default; no issuance occurs.
    from empire_os.predictive_revenue_brain_staging_v421 import (
        review_v5_cloud_staging,
    )
    result["v5_predictive_cloud_staging_read_only"] = review_v5_cloud_staging(
        signed_company_review=result, signal_rows=signal_rows,
        issued_forecast_rows=issued_forecast_rows,
    )
    result["snapshot_sha256_not_external_attestation"] = _canonical_hash({
        k: v for k, v in result.items()
        if k != "snapshot_sha256_not_external_attestation"
    })
    return result


def build_authorized_company_review(
    *, resolve_membership: Callable, authorize_company_review: Callable,
    load_review_inputs: Callable, now: Callable[[], datetime],
) -> Callable:
    """Prepare an unmounted server-side adapter for the EXISTING intake.

    Dependencies must be installed by the existing API/auth owners, never
    supplied by an HTTP caller. resolve_membership must authenticate the
    principal afresh. A generic CRM read token is insufficient: the separate
    company/purpose authorizer must grant this exact source review. The loader
    must use original permitted repositories; it receives no caller file paths,
    keys, DSNs, tenant IDs, evidence flags, or forecast bodies.

    This factory does not mount a route, activate auth, or claim independent
    source rights. Production wiring remains held until those owners provide
    these dependencies. All returned V5 rows remain research-only.
    """
    from empire_os.saas_scale import TenantMembership

    if not all(callable(fn) for fn in
               (resolve_membership, authorize_company_review, load_review_inputs, now)):
        raise ValueError("company_review_trusted_server_dependencies_required")

    def review(request: Any, *, company_scope: str, source_id: str) -> dict:
        company = _scope(company_scope, "company_scope")
        source = _scope(source_id, "source_id")
        try:
            member = resolve_membership(request)
            if not isinstance(member, TenantMembership) or not member.can("read"):
                raise PermissionError
            tenant = _scope(member.tenant_id, "tenant_scope")
            authorized = authorize_company_review(
                member, company_scope=company, source_id=source,
                purpose="PREDICTIVE_REVENUE_OBSERVE",
            )
            if authorized is not True:
                raise PermissionError
        except Exception:
            raise PermissionError("company_review_access_denied") from None

        moment = now()
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise ValueError("company_review_server_clock_required")
        inputs = load_review_inputs(
            tenant_scope=tenant, company_scope=company, source_id=source,
        )
        expected = {"payload", "signed_manifest", "signature_b64", "trusted_source",
                    "signal_rows", "issued_forecast_rows"}
        if not isinstance(inputs, Mapping) or set(inputs) != expected:
            raise ValueError("company_review_exact_server_input_bundle_required")
        for name in ("signed_manifest", "trusted_source"):
            binding = inputs[name]
            if (not isinstance(binding, Mapping)
                or binding.get("tenant_scope") != tenant
                or binding.get("company_scope") != company
                or binding.get("source_id") != source):
                raise PermissionError("company_review_source_scope_mismatch")
        # Existing cryptography, temporal validation and V5 exact row checks
        # remain authoritative. Never manufacture an issued forecast here.
        return review_signed_company_export(
            **dict(inputs), as_of_utc=moment.isoformat(),
        )

    return review


def build_company_review_file_loader(bindings: Mapping) -> Callable:
    """Use owner-configured existing export/trust roots, not HTTP file paths.

    This is application wiring, not a new source registry. Configuration must
    come from the original source owner. Hashes bind the exact reviewed signal
    and issuance files; they do not independently attest their business truth.
    Trust metadata is reread on every request so revocation is not cached.
    """
    import json
    from pathlib import Path
    from hashlib import sha256

    fields = {"source_root", "trusted_root", "payload_file", "manifest_file",
              "signature_file", "trusted_file", "signal_file", "forecast_file",
              "signal_sha256", "forecast_sha256"}
    if not isinstance(bindings, Mapping) or not bindings:
        raise ValueError("company_review_owner_bindings_required")
    configured = {}
    for key, value in bindings.items():
        if (not isinstance(key, tuple) or len(key) != 3
            or not isinstance(value, Mapping) or set(value) != fields):
            raise ValueError("company_review_exact_owner_binding_required")
        for name in key:
            _scope(name, "binding_scope")
        cfg = dict(value)
        if any(not isinstance(v, str) or not v for v in cfg.values()):
            raise ValueError("company_review_invalid_owner_binding")
        for field in ("signal_sha256", "forecast_sha256"):
            if not re.fullmatch(r"[a-f0-9]{64}", cfg[field]):
                raise ValueError("company_review_pinned_input_digest_required")
        source, trust = Path(cfg["source_root"]), Path(cfg["trusted_root"])
        if not source.is_absolute() or not trust.is_absolute():
            raise ValueError("company_review_absolute_owner_roots_required")
        a, b = source.resolve(), trust.resolve()
        if a.is_relative_to(b) or b.is_relative_to(a):
            raise ValueError("company_review_separate_trust_root_required")
        configured[key] = cfg

    def parse(raw: bytes):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("company_review_duplicate_json_key")
                result[key] = value
            return result
        def reject_constant(value):
            raise ValueError("company_review_nonfinite_json")
        return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)

    def load(*, tenant_scope: str, company_scope: str, source_id: str) -> dict:
        cfg = configured.get((tenant_scope, company_scope, source_id))
        if cfg is None:
            raise PermissionError("company_review_source_not_configured")
        def read(field, maximum, *, trust=False):
            return _read_scoped_export_part(
                source_root=cfg["trusted_root" if trust else "source_root"],
                relative_path=cfg[field], max_bytes=maximum)
        manifest = parse(read("manifest_file", 8192))
        trusted = parse(read("trusted_file", 4096, trust=True))
        for obj in (manifest, trusted):
            if (not isinstance(obj, dict) or obj.get("tenant_scope") != tenant_scope
                or obj.get("company_scope") != company_scope or obj.get("source_id") != source_id):
                raise PermissionError("company_review_source_scope_mismatch")
        rows = {}
        for kind, maximum_rows in (("signal", 500), ("forecast", 1500)):
            raw = read(kind + "_file", MAX_BYTES)
            if sha256(raw).hexdigest() != cfg[kind + "_sha256"]:
                raise ValueError("company_review_input_digest_mismatch")
            items = parse(raw)
            if not isinstance(items, list) or len(items) > maximum_rows:
                raise ValueError("company_review_bounded_row_array_required")
            rows[kind] = items
        return {
            "payload": read("payload_file", MAX_BYTES), "signed_manifest": manifest,
            "trusted_source": trusted,
            "signature_b64": read("signature_file", 512).decode("ascii").strip(),
            "signal_rows": rows["signal"], "issued_forecast_rows": rows["forecast"],
        }
    return load


def create_company_review_read_router(*, review: Callable | None = None):
    """Uninstalled route for the existing Founder API owner to mount explicitly.

    Only pass build_authorized_company_review with trusted server dependencies.
    Missing wiring returns 503. Never falls back to the aggregate demo or accepts
    client tenant IDs, trusted keys, source paths, or evidence payloads.
    """
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import JSONResponse

    if review is not None and not callable(review):
        raise ValueError("company_review_server_adapter_required")
    router = APIRouter(prefix="/v1/predictive-revenue")
    headers = {"Cache-Control": "no-store", "Vary": "Authorization, Cookie"}

    def company_review(request, company_scope: str, source_id: str):
        if review is None:
            raise HTTPException(503, "company_review_not_configured", headers=headers)
        try:
            result = review(request, company_scope=company_scope, source_id=source_id)
        except PermissionError:
            raise HTTPException(403, "company_review_access_denied", headers=headers) from None
        except Exception:
            # Source paths, key material and database errors never reach clients.
            raise HTTPException(503, "company_review_evidence_unavailable", headers=headers) from None
        return JSONResponse(result, headers=headers)

    company_review.__annotations__["request"] = Request
    router.add_api_route("/company-review", company_review, methods=["GET"])
    return router


def _read_scoped_export_part(*, source_root: str, relative_path: str,
                             max_bytes: int) -> bytes:
    """Bounded no-symlink file read from one operator-selected scope."""
    from pathlib import Path

    root = Path(source_root)
    if (not root.is_absolute() or root.is_symlink()
        or not root.is_dir()):
        raise ValueError("company_export_root_must_be_existing_absolute_directory")
    root = root.resolve()
    relative = Path(relative_path)
    if (relative.is_absolute() or not relative.parts
        or any(part in ("..", ".") for part in relative.parts)):
        raise ValueError("company_export_unsafe_relative_file")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("company_export_symlink_not_authorized")
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("company_export_file_outside_authorized_root")
    before = path.stat()
    if not 0 < before.st_size <= max_bytes:
        raise ValueError("company_export_file_missing_or_oversized")
    with path.open("rb") as fd:
        # Prevent a changed symlink from swapping in a different path.
        opened = fd.fileno()
        import os
        during = os.fstat(opened)
        if not __import__("stat").S_ISREG(during.st_mode):
            raise ValueError("company_export_nonregular_file")
        if during.st_ino != before.st_ino or during.st_dev != before.st_dev:
            raise ValueError("company_export_changed_during_read")
        data = fd.read(max_bytes + 1)
        after = os.fstat(opened)
    after_path = path.stat()
    if (len(data) != before.st_size or len(data) > max_bytes
        or after.st_ino != before.st_ino or after.st_dev != before.st_dev
        or after.st_mtime_ns != before.st_mtime_ns
        or after_path.st_ino != before.st_ino
        or after_path.st_mtime_ns != before.st_mtime_ns):
        raise ValueError("company_export_changed_during_read")
    return data


def review_signed_company_export_files(*,
    source_root: str, payload_file: str, manifest_file: str,
    signature_file: str, trusted_root: str, trusted_file: str,
    expected_tenant: str, expected_company: str, as_of_utc: str,
    forecast_cutoff_utc: str | None = None) -> dict:
    """Stage V4.21 with a separate owner-managed public-key trust root.

    No default production writer exists. This review never treats local
    metadata as proof of independent rights, payment or complete history.
    """
    import json
    from pathlib import Path

    source = Path(source_root).resolve()
    trusted_path = Path(trusted_root).resolve()
    if source == trusted_path:
        raise ValueError("company_export_source_and_trust_roots_must_differ")
    payload = _read_scoped_export_part(
        source_root=source_root, relative_path=payload_file,
        max_bytes=MAX_BYTES,
    )
    def json_document(*, root: str, relative: str, size: int) -> dict:
        raw = _read_scoped_export_part(
            source_root=root, relative_path=relative, max_bytes=size,
        )
        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError("company_export_duplicate_json_key")
                obj[key] = value
            return obj
        try:
            result = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
        except (UnicodeError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("company_export_invalid_metadata_json") from exc
        if not isinstance(result, dict):
            raise ValueError("company_export_metadata_object_required")
        return result

    manifest = json_document(
        root=source_root, relative=manifest_file, size=8192,
    )
    trusted = json_document(
        root=trusted_root, relative=trusted_file, size=4096,
    )
    signature = _read_scoped_export_part(
        source_root=source_root, relative_path=signature_file, max_bytes=512,
    ).decode("ascii").strip()
    if (manifest.get("tenant_scope") != expected_tenant
        or manifest.get("company_scope") != expected_company):
        raise ValueError("company_export_wrong_requested_company_or_tenant")
    return review_signed_company_export(
        payload=payload, signed_manifest=manifest, signature_b64=signature,
        trusted_source=trusted, as_of_utc=as_of_utc,
        forecast_cutoff_utc=forecast_cutoff_utc,
    )


if __name__ == "__main__":
    raise SystemExit(main())
