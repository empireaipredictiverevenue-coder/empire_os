"""No-PII, read-only Lead Smart Ringba call-to-cash proof.

An affiliate call-log row is not an answered buyer call. A displayed payout
column is not a finalized accepted invoice, and not settled cash. This
review never activates calls, mutates provider settings, or creates sales.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from empire_os import lead_smart_ringba_api_observer as observer

SCHEMA = "empire.lead_smart.call_to_cash_proof.v1"
LATEST = Path("/srv/empire_os/runtime/revenue/lead_smart/commercial_pulse/call_to_cash_latest.json")
EXPECTED = observer.EXPECTED_CAMPAIGN_ID
NUMBER = observer.EXPECTED_TRACKING_NUMBER


def safe_seconds(value: Any) -> int | None:
    if type(value) in (int, float, str):
        try:
            number = float(value)
        except ValueError:
            return None
        if math.isfinite(number) and 0 <= number <= 86400 and number.is_integer():
            return int(number)
    return None


def opaque_id(value: Any) -> str | None:
    if not isinstance(value, str) or not 4 <= len(value) <= 128:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def prove_from_observation(report: Mapping[str, Any], *,
                           known_site_handoffs: int | None,
                           ledger_present: bool = False) -> dict[str, Any]:
    if (
        report.get("schema_version") != observer.SCHEMA_VERSION
        or report.get("campaign_id_expected") != EXPECTED
        or report.get("tracking_number_expected") != NUMBER
        or report.get("execution_authority") != "NONE"
        or report.get("revenue_recognized") is not False
    ):
        raise ValueError("untrusted source observation")
    if type(known_site_handoffs) is not int or known_site_handoffs < 0:
        raise ValueError("site handoff ledger not independently available")
    rows = report.get("exact_matches")
    if not isinstance(rows, list) or len(rows) > observer.MAX_CALL_ROWS:
        raise ValueError("invalid provider exact-match rows")
    if type(report.get("exact_campaign_and_number_match_count")) is not int or (
        report["exact_campaign_and_number_match_count"] != len(rows)
    ):
        raise ValueError("provider exact-match count disagreement")
    calls = []
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("bad provider row")
        ref = opaque_id(row.get("call_id"))
        if ref is not None:
            if ref in ids:
                raise ValueError("duplicate provider call ID")
            ids.add(ref)
        # connected_seconds is an affiliate reported field; it does not
        # prove a reached/answered buyer destination. Never upgrade it.
        calls.append({
            "call_id_sha256": ref,
            "provider_started_at_candidate": row.get("started_at_candidate")
                if isinstance(row.get("started_at_candidate"), str) else None,
            "provider_reported_connected_seconds": safe_seconds(row.get("connected_seconds")),
            "provider_reported_total_seconds": safe_seconds(row.get("total_seconds")),
            # The provider's payout column is an observation only, never a
            # final accepted amount or a paid invoice. Do not assume currency.
            "provider_payout_candidate_unconfirmed": (
                float(row["payout_candidate"])
                if (type(row.get("payout_candidate")) in (int, float)
                    and math.isfinite(float(row["payout_candidate"]))
                    and 0 <= float(row["payout_candidate"]) <= 100_000)
                else None
            ),
            "source_provenance": "UNATTRIBUTED_RINGBA_ROW",
            "test_call_possible": True,
            "buyer_leg_connection_verified": False,
            "buyer_accepted_payable_call_verified": False,
            "qualification_verified": False,
            "duplicate_30d_status_verified": False,
            "agreed_payable_amount_usd": None,
            "paid_amount_usd": None,
            "settlement_received_verified": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY",
        "buyer": "Lead Smart",
        "campaign_id": EXPECTED,
        "tracking_number": NUMBER,
        "provider_exact_matches_in_bounded_window": len(calls),
        "first_party_site_handoffs_recorded": known_site_handoffs,
        "site_handoff_ledger_present": ledger_present,
        "provider_rows_not_matched_to_site_handoffs": len(calls),
        "provider_buyer_leg_connections_verified": 0,
        "verified_accepted_payable_calls": 0,
        "verified_cash_payments": 0,
        "provider_reported_row_summaries": calls,
        "payout_rate_type": "VARIABLE_LIVE_BID_UNCONFIRMED_FOR_ROWS",
        "settled_revenue_usd_verified": None,
        "consumer_personal_information_persisted": False,
        "call_details_authenticated_as_buyer_connected": False,
        "customer_calls_activated": False,
        "no_account_or_token_output": True,
        "execution_authority": "NONE",
    }


def run() -> dict[str, Any]:
    # The existing securely configured Ringba API account is used read-only.
    # Only a privileged process can inspect root-owned token material.
    from scripts.probe_lead_smart_ringba_root_readonly import read_root_config
    from empire_os.lead_smart_site_handoff import LEDGER
    conf = read_root_config()
    token = conf["RINGBA_API_TOKEN"]
    account = observer.choose_account(observer.discover_accounts(token),
                                      conf.get("RINGBA_ACCOUNT_ID"))
    provider, _columns = observer.fetch_recent_call_logs(token=token, account_id=account)
    report = observer.build_schema_observation(account_id=account, payload=provider)
    ledger_present = LEDGER.exists()
    if ledger_present:
        ledger = json.loads(LEDGER.read_text())
        handoffs = ledger.get("site_handoffs")
    else:
        handoffs = 0
    return prove_from_observation(
        report, known_site_handoffs=handoffs,
        ledger_present=ledger_present,
    )


def write_latest(result: Mapping[str, Any], *, path: Path = LATEST) -> None:
    # Root-owned observation is read-only with respect to Ringba and
    # admission controls. Never persist tokens, ANI or raw provider rows.
    if os.geteuid() != 0 or result.get("schema_version") != SCHEMA:
        raise PermissionError("root-owned verified observation required")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists()
                            and (path.stat().st_uid != 0
                                 or path.stat().st_mode & 0o077)):
        raise PermissionError("unsafe existing observation path")
    fd, tmp = tempfile.mkstemp(prefix=".call-to-cash-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-latest", action="store_true",
                        help="persist privacy-safe observation with root-only permissions")
    args = parser.parse_args()
    try:
        result = run()
        result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
        if args.write_latest:
            write_latest(result)
            print(json.dumps({
                "status": "CALL_TO_CASH_OBSERVATION_SAVED",
                "provider_exact_matches": result["provider_exact_matches_in_bounded_window"],
                "accepted_payable_calls_verified": result["verified_accepted_payable_calls"],
                "cash_payments_verified": result["verified_cash_payments"],
                "execution_authority": "NONE",
            }))
            return 0
    except Exception as exc:
        # Exception messages can contain Ringba raw private responses.
        print(json.dumps({"schema_version": SCHEMA,
                          "status": "EVIDENCE_UNAVAILABLE",
                          "error_class": type(exc).__name__,
                          "call_activity_verified": False,
                          "execution_authority": "NONE"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
