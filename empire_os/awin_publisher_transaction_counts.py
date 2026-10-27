"""Awin 7-day publisher conversion counts: original cycle, read-only, PII-free.

Runs only after the authenticated Awin programme snapshot says JOINED.
Never stores orders, clickrefs, customer data, transaction IDs, raw API bodies,
commission amounts or any financial settlement/earned revenue assertions.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Callable
from urllib import parse, request

from empire_os.awin_publisher_api import (
    AwinAPIHold, _NoRedirect, _private_token, PUBLISHER_ID, PROGRAMMES,
    TOKEN_PATH, SNAPSHOT_PATH,
)

DEST = Path("/srv/empire_os/runtime/buyer_network_intelligence/awin_publisher_transaction_counts_latest.json")
SCHEMA = "empire.awin.publisher_conversion_count_evidence.v1"
VALID = frozenset({"pending", "approved", "declined", "deleted"})
MAX_ROWS = 200


def _private_membership(path: Path, now: datetime) -> tuple[list[str], str]:
    if (path.is_symlink() or not path.is_file()
            or stat.S_IMODE(path.stat().st_mode) != 0o600
            or not 300 <= path.stat().st_size <= 64000):
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_SOURCE_UNSAFE")
    try:
        member = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_SOURCE_INVALID") from exc
    if (not isinstance(member, dict)
            or member.get("schema_version") != "empire.awin.publisher_programme_membership.v1"
            or member.get("status") != "AWIN_API_MEMBERSHIP_REVIEW_VERIFIED"
            or member.get("publisher_id") != PUBLISHER_ID
            or member.get("api_live_verified") is not True
            or member.get("affiliate_publication_authorized") is not False
            or member.get("commission_earned_verified") is not False
            or member.get("commission_paid_verified") is not False
            or member.get("outbound_sent") is not False
            or member.get("database_writes") is not False):
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_AUTHORITY_INVALID")
    try:
        observed = datetime.fromisoformat(member["observed_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_CLOCK_INVALID") from exc
    if observed.utcoffset() is None:
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_CLOCK_INVALID")
    elapsed = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    if not -90 <= elapsed <= 1800:
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_STALE")
    rows = member.get("programmes")
    if not isinstance(rows, list) or len(rows) != 2:
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_PROGRAMMES_MISSING")
    statuses = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_ROW_INVALID")
        ident = row.get("advertiser_id")
        if (ident not in PROGRAMMES or ident in statuses
                or row.get("membership_status") not in ("PENDING", "JOINED", "REJECTED", "SUSPENDED", "NOT_JOINED")
                or row.get("membership_verified_by_authenticated_awin_api") is not True
                or row.get("publisher_authorised_to_use_tracking_link") is not False):
            raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_ROW_UNVERIFIED")
        statuses[ident] = row["membership_status"]
    if set(statuses) != set(PROGRAMMES):
        raise AwinAPIHold("AWIN_TRANSACTION_MEMBERSHIP_IDENTITY_INVALID")
    return [ident for ident,status in statuses.items() if status == "JOINED"], member["observed_at"]


def _fetch_transactions(url: str, token: str) -> list[dict]:
    root = "https://api.awin.com/publishers/" + PUBLISHER_ID + "/transactions/?"
    if not url.startswith(root):
        raise AwinAPIHold("AWIN_TRANSACTION_ENDPOINT_UNAUTHORIZED")
    req = request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "EmpireAI-Transaction-Counts-ReadOnly/1",
    }, method="GET")
    try:
        with request.build_opener(_NoRedirect()).open(req, timeout=9) as response:
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise AwinAPIHold("AWIN_TRANSACTION_RESPONSE_UNSUPPORTED")
            body = response.read(262145)
            if not 2 <= len(body) <= 262144:
                raise AwinAPIHold("AWIN_TRANSACTION_RESPONSE_SIZE_UNSAFE")
            rows = json.loads(body)
    except AwinAPIHold:
        raise
    except Exception as exc:
        raise AwinAPIHold("AWIN_TRANSACTION_NETWORK_OR_RESPONSE_HELD") from exc
    if not isinstance(rows, list) or len(rows) >= MAX_ROWS:
        raise AwinAPIHold("AWIN_TRANSACTION_FORMAT_OR_PAGINATION_UNVERIFIED")
    return rows


def _summary(rows: list[dict], advertiser_id: str) -> dict:
    if not isinstance(rows, list) or len(rows) >= MAX_ROWS:
        raise AwinAPIHold("AWIN_TRANSACTION_ROWS_OVER_LIMIT")
    states = Counter()
    ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or str(row.get("advertiserId")) != advertiser_id:
            raise AwinAPIHold("AWIN_TRANSACTION_ADVERTISER_MISMATCH")
        state = row.get("commissionStatus")
        if not isinstance(state, str) or state.casefold() not in VALID:
            raise AwinAPIHold("AWIN_TRANSACTION_COMMISSION_STATUS_UNKNOWN")
        transaction_id = row.get("id")
        if (type(transaction_id) not in (int, str) or not str(transaction_id).isdigit()
                or str(transaction_id) in ids):
            raise AwinAPIHold("AWIN_TRANSACTION_ROW_ID_MISSING_OR_DUPLICATE")
        ids.add(str(transaction_id))
        states[state.casefold()] += 1
    return {
        "advertiser_id": advertiser_id,
        "advertiser": PROGRAMMES[advertiser_id],
        "record_count": len(rows),
        "status_counts": {key: states[key] for key in ("pending", "approved", "declined", "deleted")},
        "approved_transactions_not_settled_payouts": True,
        "raw_orders_stored": False,
        "commission_earned_or_paid_recognized": False,
    }


def review(*, now: datetime | None = None, membership_path: Path = SNAPSHOT_PATH,
           token_path: Path = TOKEN_PATH, output: Path = DEST,
           transport: Callable[[str, str], list[dict]] = _fetch_transactions,
           write: bool = False) -> dict:
    held = {
        "status": "HELD_AWIN_TRANSACTION_EVIDENCE_UNAVAILABLE",
        "publisher_id": PUBLISHER_ID,
        "api_requests_made": 0, "snapshot_written": False,
        "outbound_sent": False, "database_writes": False,
        "execution_authority": "NONE", "revenue_verified": False,
    }
    calls=0
    try:
        current = now or datetime.now(timezone.utc)
        if not isinstance(current, datetime) or current.utcoffset() is None:
            raise AwinAPIHold("AWIN_TRANSACTION_CLOCK_INVALID")
        joined, membership_observed = _private_membership(membership_path, current)
        if not joined:
            return {**held, "status": "AWIN_TRANSACTIONS_WAITING_FOR_JOINED_PROGRAMME",
                    "membership_source_observed_at": membership_observed}
        secret = _private_token(token_path)
        start = current.astimezone(timezone.utc) - timedelta(days=7)
        end = current.astimezone(timezone.utc)
        rows=[]
        for advertiser_id in joined:
            url = "https://api.awin.com/publishers/" + PUBLISHER_ID + "/transactions/?" + parse.urlencode({
                "advertiserId": advertiser_id,
                "dateType": "transaction", "timezone": "UTC",
                "showBasketProducts": "false",
                "startDate": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "endDate": end.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            calls+=1
            rows.append(_summary(transport(url, secret), advertiser_id))
        result = {
            "schema_version": SCHEMA,
            "status": "AWIN_JOINED_PROGRAMME_TRANSACTION_COUNTS_OBSERVED",
            "publisher_id": PUBLISHER_ID,
            "observed_at": end.isoformat(),
            "date_window_start_utc": start.isoformat(),
            "date_window_end_utc": end.isoformat(),
            "date_type": "transaction",
            "membership_source_observed_at": membership_observed,
            "joined_programmes_checked": joined,
            "programme_results": rows,
            "api_requests_made": calls,
            "complete_bounded_response_verified": True,
            "raw_transaction_rows_persisted": False,
            "transaction_counts_are_not_payout_proof": True,
            "revenue_verified": False,
            "payout_verified": False,
            "outbound_sent": False, "database_writes": False,
            "execution_authority": "NONE",
        }
        if write:
            if (output.is_symlink() or output.parent.is_symlink()
                    or not output.parent.is_dir()
                    or (output.exists() and (not output.is_file()
                        or stat.S_IMODE(output.stat().st_mode) != 0o600))):
                raise AwinAPIHold("AWIN_TRANSACTION_OUTPUT_UNSAFE")
            fd,temp = tempfile.mkstemp(prefix=".awin_conversion_count_",dir=output.parent)
            try:
                with os.fdopen(fd,"w",encoding="utf-8") as stream:
                    os.fchmod(stream.fileno(),0o600)
                    json.dump(result,stream,sort_keys=True,indent=2)
                    stream.write("\n")
                    stream.flush();os.fsync(stream.fileno())
                os.replace(temp,output)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return {**result,"snapshot_written":write}
    except Exception:
        # Fail closed on unexpected provider exceptions without logging sensitive data.
        return {**held, "api_requests_made": calls}
