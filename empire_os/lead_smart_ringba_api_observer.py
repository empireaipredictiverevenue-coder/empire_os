from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.ringba.com/v2"

EXPECTED_CAMPAIGN_ID = (
    "CA8278ed3f26e9495b881fe3833174d007"
)

EXPECTED_TRACKING_NUMBER = "+18883579305"

MAX_CALL_ROWS = 50

SCHEMA_VERSION = (
    "empire.lead_smart."
    "ringba_api_observation.v1"
)


class RingbaApiError(RuntimeError):
    pass


def _json_request(
    *,
    token: str,
    method: str,
    url: str,
    payload: Mapping[str, Any] | None = None,
) -> tuple[int, Any]:
    if not token:
        raise RingbaApiError(
            "Ringba API token missing"
        )

    body = None

    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
        "User-Agent":
            "EmpireAI-RingbaObserver/1.0",
    }

    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = (
            "application/json"
        )

    request = Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(
            request,
            timeout=30,
        ) as response:
            raw = response.read().decode(
                "utf-8",
                errors="replace",
            )

            return (
                response.status,
                json.loads(raw)
                if raw.strip()
                else None,
            )

    except HTTPError as exc:
        raw = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "body_excerpt":
                    raw[:500]
            }

        raise RingbaApiError(
            f"Ringba HTTP {exc.code}: "
            f"{json.dumps(parsed)[:800]}"
        ) from exc

    except URLError as exc:
        raise RingbaApiError(
            f"Ringba network error: "
            f"{exc.reason}"
        ) from exc


def _walk_account_ids(
    value: Any,
) -> set[str]:
    result: set[str] = set()

    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()

            if (
                lower
                in {
                    "accountid",
                    "account_id",
                    "ringbaaccountid",
                    "id",
                }
                and isinstance(
                    item,
                    str,
                )
                and re.fullmatch(
                    r"RA[A-Za-z0-9]+",
                    item,
                )
            ):
                result.add(item)

            result.update(
                _walk_account_ids(item)
            )

    elif isinstance(value, list):
        for item in value:
            result.update(
                _walk_account_ids(item)
            )

    return result


def discover_accounts(
    token: str,
) -> list[str]:
    status, payload = _json_request(
        token=token,
        method="GET",
        url=f"{BASE_URL}/ringbaaccounts",
    )

    if status != 200:
        raise RingbaApiError(
            f"unexpected account status {status}"
        )

    return sorted(
        _walk_account_ids(payload)
    )


def choose_account(
    accounts: list[str],
    configured: str | None,
) -> str:
    configured = str(
        configured or ""
    ).strip()

    if configured:
        if (
            accounts
            and configured
            not in accounts
        ):
            raise RingbaApiError(
                "configured account ID is not "
                "present in authenticated accounts"
            )

        return configured

    if len(accounts) != 1:
        raise RingbaApiError(
            "account selection ambiguous; "
            f"authenticated_account_count="
            f"{len(accounts)}"
        )

    return accounts[0]


def fetch_recent_call_logs(
    *,
    token: str,
    account_id: str,
) -> tuple[Any, dict[str, Any]]:
    """
    Bounded, affiliate-role-safe Ringba reporting read.

    Start with the minimum useful call contract. If Ringba
    explicitly reports that an OPTIONAL value column is unavailable
    for the authenticated role, remove exactly that column and retry.

    Required identity fields are NEVER negotiated away:
      - campaignId
      - inboundCallId
      - number

    No caller ANI is requested.
    No pagination is performed.
    No mutation endpoint is called.
    """

    now = datetime.now(timezone.utc)
    report_start = now - timedelta(days=7)

    required_identity = {
        "campaignId",
        "inboundCallId",
        "number",
    }

    columns = [
        "campaignId",
        "inboundCallId",
        "number",
        "callDt",
        "connectedCallLengthInSeconds",
        "callLengthInSeconds",
        "hasPayout",
        "payoutAmount",
        "isDuplicate",
        "hasConverted",
        "tag:Geo:ZipCode",
        "tag:User:zip",
        "tag:User:zipCode",
    ]

    restricted: list[str] = []
    observed_role: str | None = None
    attempts = 0

    # Strict finite cap. This is compatibility negotiation,
    # not an open-ended polling loop.
    max_attempts = min(
        16,
        len(columns) + 1,
    )

    while attempts < max_attempts:
        attempts += 1

        payload = {
            "reportStart":
                report_start.isoformat(),

            "reportEnd":
                now.isoformat(),

            "orderByColumns": [
                {
                    "column": "callDt",
                    "direction": "desc",
                }
            ],

            "filters": [
                {
                    "anyConditionToMatch": [
                        {
                            "column": "number",
                            "value":
                                EXPECTED_TRACKING_NUMBER,
                            "isNegativeMatch":
                                False,
                            "comparisonType":
                                "EQUALS",
                        }
                    ]
                }
            ],

            "valueColumns": [
                {"column": column}
                for column in columns
            ],

            "formatDateTime":
                False,

            "formatPercentages":
                False,

            "formatTimespans":
                False,

            "formatTimeZone":
                "Etc/GMT",

            "size":
                MAX_CALL_ROWS,

            "offset":
                0,
        }

        try:
            _, response = _json_request(
                token=token,
                method="POST",
                url=(
                    f"{BASE_URL}/"
                    f"{account_id}/calllogs"
                ),
                payload=payload,
            )

        except RingbaApiError as exc:
            message = str(exc)

            match = re.search(
                r"Value column (.+?) "
                r"is not available"
                r"(?: for this role\(([^)]+)\))?",
                message,
                flags=re.I,
            )

            if match is None:
                raise

            field = match.group(1).strip()
            role = (
                match.group(2).strip()
                if match.group(2)
                else None
            )

            if role:
                observed_role = role

            if field not in columns:
                raise RingbaApiError(
                    "Ringba reported an unavailable "
                    "column that was not requested: "
                    f"{field}"
                ) from exc

            if field in required_identity:
                raise RingbaApiError(
                    "required Ringba identity column "
                    "is unavailable for this role: "
                    f"{field}"
                ) from exc

            restricted.append(field)
            columns.remove(field)

            continue

        missing_identity = (
            required_identity
            - set(columns)
        )

        if missing_identity:
            raise RingbaApiError(
                "required identity contract lost: "
                f"{sorted(missing_identity)}"
            )

        return (
            response,
            {
                "api_role":
                    observed_role,

                "compatibility_request_count":
                    attempts,

                "role_restricted_columns":
                    restricted,

                "successful_value_columns":
                    list(columns),

                "required_identity_columns":
                    sorted(
                        required_identity
                    ),

                "minimum_identity_contract_ready":
                    True,

                "caller_ani_requested":
                    False,

                "bounded_negotiation":
                    True,
            },
        )

    raise RingbaApiError(
        "affiliate calllog compatibility "
        "negotiation exhausted safely"
    )

def _path(
    value: Any,
    *parts: str,
) -> Any:
    current = value

    for part in parts:
        if not isinstance(
            current,
            dict,
        ):
            return None

        current = current.get(part)

    return current


def extract_rows(
    payload: Any,
) -> list[Any]:
    candidates = [
        _path(
            payload,
            "result",
            "callLog",
            "data",
        ),
        _path(
            payload,
            "callLog",
            "data",
        ),
        _path(
            payload,
            "report",
            "records",
        ),
        (
            payload.get("data")
            if isinstance(
                payload,
                dict,
            )
            else None
        ),
    ]

    for value in candidates:
        if isinstance(value, list):
            return value

    return []


def _scalar(
    value: Any,
) -> str | int | float | bool | None:
    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    return None


def _group_map(
    value: Any,
) -> dict[str, Any]:
    """
    Ringba report groups can be represented as either
    mappings or arrays of named objects. Convert only
    scalar values for schema discovery.
    """

    result: dict[str, Any] = {}

    if isinstance(value, dict):
        for key, item in value.items():
            scalar = _scalar(item)

            if scalar is not None:
                result[
                    str(key)
                ] = scalar

        return result

    if not isinstance(value, list):
        return result

    for item in value:
        if not isinstance(
            item,
            dict,
        ):
            continue

        key = (
            item.get("name")
            or item.get("column")
            or item.get("key")
            or item.get("tagName")
        )

        if not key:
            continue

        possible = (
            item.get("value")
            if "value" in item
            else item.get(
                "tagValue"
            )
        )

        scalar = _scalar(possible)

        if scalar is not None:
            result[
                str(key)
            ] = scalar

    return result


def _groups(
    row: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[Any],
]:
    columns = _group_map(
        row.get("columns")
        or row.get("Columns")
        or {}
    )

    tags = _group_map(
        row.get("tags")
        or row.get("Tags")
        or {}
    )

    events = (
        row.get("events")
        or row.get("Events")
        or []
    )

    if not isinstance(
        events,
        list,
    ):
        events = []

    return columns, tags, events


def _all_scalar_text(
    value: Any,
) -> list[str]:
    result: list[str] = []

    if isinstance(value, dict):
        for item in value.values():
            result.extend(
                _all_scalar_text(item)
            )

    elif isinstance(value, list):
        for item in value:
            result.extend(
                _all_scalar_text(item)
            )

    elif isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        result.append(str(value))

    return result


def _first(
    maps: list[Mapping[str, Any]],
    names: tuple[str, ...],
) -> Any:
    lowered = {
        str(key).casefold(): value
        for mapping in maps
        for key, value
        in mapping.items()
    }

    for name in names:
        if name.casefold() in lowered:
            return lowered[
                name.casefold()
            ]

    return None


def sanitize_matching_row(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    columns, tags, events = _groups(
        row
    )

    event_names: list[str] = []

    event_key_union: set[str] = set()

    for event in events:
        if not isinstance(
            event,
            dict,
        ):
            continue

        event_key_union.update(
            str(key)
            for key in event
        )

        name = (
            event.get("name")
            or event.get("eventName")
            or event.get("type")
            or event.get("eventType")
        )

        if name:
            event_names.append(
                str(name)
            )

    call_id = _first(
        [columns, tags, row],
        (
            "inboundCallId",
            "callId",
            "callSid",
            "call_id",
        ),
    )

    dialed_number = _first(
        [columns, tags, row],
        (
            "number",
            "dialedNumber",
            "inboundNumber",
            "trackingNumber",
        ),
    )

    connected_seconds = _first(
        [columns, tags, row],
        (
            "callConnectionLength",
            "connectedCallLength",
            "connectedCallLengthInSeconds",
            "connectedSeconds",
        ),
    )

    total_seconds = _first(
        [columns, tags, row],
        (
            "callLengthInSeconds",
            "callLength",
            "duration",
        ),
    )

    zip_code = _first(
        [columns, tags, row],
        (
            "zip",
            "zipCode",
            "postalCode",
            "tag:Geo:ZipCode",
            "tag:User:zip",
            "tag:User:zipCode",
            "tag:Address:Zip 5",
            "InboundNumber:Zip",
            "Caller:Zip",
        ),
    )

    payout = _first(
        [columns, tags, row],
        (
            "payout",
            "publisherPayout",
            "publisherPayoutAmount",
            "payoutAmount",
            "commission",
        ),
    )

    dt_stamp = _first(
        [columns, tags, row],
        (
            "dtStamp",
            "callDt",
            "startedAt",
            "startTime",
        ),
    )

    return {
        # No caller ANI is persisted.
        "call_id":
            call_id,

        "dialed_number":
            dialed_number,

        "connected_seconds":
            connected_seconds,

        "total_seconds":
            total_seconds,

        "zip":
            zip_code,

        "payout_candidate":
            payout,

        "started_at_candidate":
            dt_stamp,

        "column_keys":
            sorted(
                columns.keys()
            ),

        "tag_keys":
            sorted(
                tags.keys()
            ),

        "event_names":
            sorted(
                set(event_names)
            ),

        "event_keys":
            sorted(
                event_key_union
            ),

        "raw_persisted":
            False,
    }


def build_schema_observation(
    *,
    account_id: str,
    payload: Any,
) -> dict[str, Any]:
    rows = extract_rows(payload)

    column_keys: set[str] = set()
    tag_keys: set[str] = set()
    event_keys: set[str] = set()
    event_names: set[str] = set()
    top_keys: set[str] = set()

    tracking_candidates = []
    campaign_candidates = []
    exact_candidates = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        top_keys.update(
            str(key)
            for key in row
        )

        columns, tags, events = _groups(
            row
        )

        column_keys.update(
            columns.keys()
        )

        tag_keys.update(
            tags.keys()
        )

        for event in events:
            if not isinstance(
                event,
                dict,
            ):
                continue

            event_keys.update(
                str(key)
                for key in event
            )

            name = (
                event.get("name")
                or event.get("eventName")
                or event.get("type")
                or event.get("eventType")
            )

            if name:
                event_names.add(
                    str(name)
                )

        scalar_values = set(
            _all_scalar_text(row)
        )

        expected_digits = re.sub(
            r"\D",
            "",
            EXPECTED_TRACKING_NUMBER,
        )

        observed_digits = {
            re.sub(
                r"\D",
                "",
                value,
            )
            for value in scalar_values
        }

        tracking_match = (
            EXPECTED_TRACKING_NUMBER
            in scalar_values
            or expected_digits
            in observed_digits
            or expected_digits[-10:]
            in {
                value[-10:]
                for value
                in observed_digits
                if len(value) >= 10
            }
        )

        campaign_match = (
            EXPECTED_CAMPAIGN_ID
            in scalar_values
        )

        if tracking_match:
            tracking_candidates.append(
                sanitize_matching_row(row)
            )

        if campaign_match:
            campaign_candidates.append(
                sanitize_matching_row(row)
            )

        if (
            tracking_match
            and campaign_match
        ):
            exact_candidates.append(
                sanitize_matching_row(row)
            )

    return {
        "schema_version":
            SCHEMA_VERSION,

        "mode":
            "OBSERVE",

        "provider":
            "Ringba",

        "api_contract":
            "POST /v2/{accountId}/calllogs",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "account_id_sha256":
            hashlib.sha256(
                account_id.encode()
            ).hexdigest(),

        "campaign_id_expected":
            EXPECTED_CAMPAIGN_ID,

        "tracking_number_expected":
            EXPECTED_TRACKING_NUMBER,

        "raw_call_row_count":
            len(rows),

        "top_level_row_keys":
            sorted(top_keys),

        "column_keys":
            sorted(column_keys),

        "tag_keys":
            sorted(tag_keys),

        "event_keys":
            sorted(event_keys),

        "event_names":
            sorted(event_names),

        "tracking_number_match_count":
            len(tracking_candidates),

        "campaign_id_match_count":
            len(campaign_candidates),

        "exact_campaign_and_number_match_count":
            len(exact_candidates),

        "exact_matches":
            exact_candidates,

        "raw_response_persisted":
            False,

        "caller_phone_persisted":
            False,

        "api_token_persisted":
            False,

        "normalization_performed":
            False,

        "payout_truth_promoted":
            False,

        "tracking_verified_change":
            False,

        "routing_verified_change":
            False,

        "traffic_enabled":
            False,

        "revenue_recognized":
            False,

        "economic_memory_write":
            False,

        "execution_authority":
            "NONE",
    }


def observe_from_environment() -> dict[str, Any]:
    token = str(
        os.getenv(
            "RINGBA_API_TOKEN",
            "",
        )
    ).strip()

    if not token:
        return {
            "schema_version":
                SCHEMA_VERSION,

            "mode":
                "OBSERVE",

            "status":
                "BLOCKED_MISSING_API_TOKEN",

            "api_token_present":
                False,

            "api_token_persisted":
                False,

            "network_request_performed":
                False,

            "execution_authority":
                "NONE",
        }

    accounts = discover_accounts(
        token
    )

    account_id = choose_account(
        accounts,
        os.getenv(
            "RINGBA_ACCOUNT_ID"
        ),
    )

    payload, negotiation = fetch_recent_call_logs(
        token=token,
        account_id=account_id,
    )

    result = build_schema_observation(
        account_id=account_id,
        payload=payload,
    )

    result["api_role"] = negotiation[
        "api_role"
    ]

    result[
        "compatibility_request_count"
    ] = negotiation[
        "compatibility_request_count"
    ]

    result[
        "role_restricted_columns"
    ] = negotiation[
        "role_restricted_columns"
    ]

    result[
        "successful_value_columns"
    ] = negotiation[
        "successful_value_columns"
    ]

    result[
        "required_identity_columns"
    ] = negotiation[
        "required_identity_columns"
    ]

    result[
        "minimum_identity_contract_ready"
    ] = negotiation[
        "minimum_identity_contract_ready"
    ]

    result[
        "caller_ani_requested"
    ] = negotiation[
        "caller_ani_requested"
    ]

    result[
        "bounded_negotiation"
    ] = negotiation[
        "bounded_negotiation"
    ]

    result.update({
        "status":
            "OBSERVED",

        "api_token_present":
            True,

        "authenticated_account_count":
            len(accounts),

        "account_selection_resolved":
            True,

        "network_request_performed":
            True,
    })

    # Token is never included in result.
    serialized = json.dumps(
        result
    )

    if token in serialized:
        raise RuntimeError(
            "API token leakage detected"
        )

    return result
