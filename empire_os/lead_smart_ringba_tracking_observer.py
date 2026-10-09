from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.lead_smart_ringba_api_observer import (
    BASE_URL,
    EXPECTED_CAMPAIGN_ID,
    EXPECTED_TRACKING_NUMBER,
    RingbaApiError,
    _json_request,
    choose_account,
    discover_accounts,
)


SCHEMA_VERSION = (
    "empire.lead_smart."
    "ringba_tracking_object_observation.v1"
)


def _digits(value: Any) -> str:
    return re.sub(
        r"\D",
        "",
        str(value or ""),
    )


EXPECTED_DIGITS = _digits(
    EXPECTED_TRACKING_NUMBER
)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from _walk(child)

    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _contains_exact_campaign(
    value: Any,
) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_exact_campaign(item)
            for item in value.values()
        )

    if isinstance(value, list):
        return any(
            _contains_exact_campaign(item)
            for item in value
        )

    return (
        str(value or "").strip()
        == EXPECTED_CAMPAIGN_ID
    )


def _contains_tracking_number(
    value: Any,
) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_tracking_number(item)
            for item in value.values()
        )

    if isinstance(value, list):
        return any(
            _contains_tracking_number(item)
            for item in value
        )

    digits = _digits(value)

    if not digits:
        return False

    return (
        digits == EXPECTED_DIGITS
        or (
            len(digits) >= 10
            and digits[-10:]
            == EXPECTED_DIGITS[-10:]
        )
    )


def _first_scalar(
    row: Mapping[str, Any],
    names: tuple[str, ...],
) -> Any:
    lowered = {
        str(key).casefold(): value
        for key, value in row.items()
    }

    for name in names:
        value = lowered.get(
            name.casefold()
        )

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


def _hash_identifier(
    value: Any,
) -> str | None:
    raw = str(value or "").strip()

    if not raw:
        return None

    return hashlib.sha256(
        raw.encode()
    ).hexdigest()


def _sanitize_target_number_record(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Persist only target-number metadata.

    No unrelated phone numbers, people, publisher names,
    account IDs, credentials or raw response.
    """

    number = _first_scalar(
        row,
        (
            "number",
            "phoneNumber",
            "phone",
            "e164",
            "numberE164",
        ),
    )

    record_id = _first_scalar(
        row,
        (
            "id",
            "numberId",
            "number_id",
        ),
    )

    status = _first_scalar(
        row,
        (
            "status",
            "state",
        ),
    )

    paused = _first_scalar(
        row,
        (
            "paused",
            "isPaused",
        ),
    )

    enabled = _first_scalar(
        row,
        (
            "enabled",
            "isEnabled",
            "active",
            "isActive",
        ),
    )

    return {
        "target_number":
            EXPECTED_TRACKING_NUMBER,

        "observed_number_matches":
            _contains_tracking_number(
                number
            ),

        "number_object_id_sha256":
            _hash_identifier(
                record_id
            ),

        "status_candidate":
            (
                str(status)
                if status is not None
                else None
            ),

        "paused_candidate":
            (
                paused
                if type(paused) is bool
                else None
            ),

        "enabled_candidate":
            (
                enabled
                if type(enabled) is bool
                else None
            ),

        "object_keys":
            sorted(
                str(key)
                for key in row.keys()
            ),

        "raw_record_persisted":
            False,
    }


def locate_target_number(
    payload: Any,
) -> tuple[
    Mapping[str, Any] | None,
    str | None,
]:
    matches = []

    for row in _walk(payload):
        if _contains_tracking_number(
            row
        ):
            matches.append(row)

    # Deduplicate by JSON identity.
    unique = {}

    for row in matches:
        key = json.dumps(
            row,
            sort_keys=True,
            default=str,
        )

        unique[key] = row

    matches = list(
        unique.values()
    )

    if len(matches) != 1:
        return None, (
            "target_number_not_unique:"
            f"{len(matches)}"
        )

    row = matches[0]

    record_id = _first_scalar(
        row,
        (
            "id",
            "numberId",
            "number_id",
        ),
    )

    if not record_id:
        return row, (
            "target_number_object_id_missing"
        )

    return row, str(record_id)


def _probe_get(
    *,
    token: str,
    url: str,
) -> dict[str, Any]:
    try:
        status, payload = _json_request(
            token=token,
            method="GET",
            url=url,
        )

        return {
            "status": status,
            "accessible": True,
            "payload": payload,
        }

    except RingbaApiError as exc:
        text = str(exc)

        status = None

        match = re.search(
            r"Ringba HTTP (\d+)",
            text,
        )

        if match:
            status = int(
                match.group(1)
            )

        return {
            "status": status,
            "accessible": False,
            "error_class": (
                "FORBIDDEN"
                if status == 403
                else
                "NOT_FOUND"
                if status == 404
                else
                "HTTP_ERROR"
            ),
            "payload": None,
        }


def observe_tracking_objects(
    *,
    token: str,
    account_id: str,
) -> dict[str, Any]:
    """
    Bounded read-only object verification.

    We do not treat endpoint accessibility as proof.
    Verification requires the expected number AND expected
    campaign to be linked in provider-returned evidence.
    """

    endpoints = {
        "campaign_detail":
            (
                f"{BASE_URL}/"
                f"{account_id}/campaigns/"
                f"{EXPECTED_CAMPAIGN_ID}"
            ),

        "campaign_list":
            (
                f"{BASE_URL}/"
                f"{account_id}/campaigns"
            ),

        "number_list":
            (
                f"{BASE_URL}/"
                f"{account_id}/numbers"
            ),
    }

    results = {
        name: _probe_get(
            token=token,
            url=url,
        )
        for name, url
        in endpoints.items()
    }

    campaign_detail = results[
        "campaign_detail"
    ]["payload"]

    campaign_detail_proves_id = (
        _contains_exact_campaign(
            campaign_detail
        )
    )

    campaign_detail_contains_number = (
        _contains_tracking_number(
            campaign_detail
        )
    )

    number_list = results[
        "number_list"
    ]["payload"]

    target_row = None
    target_id = None
    locate_reason = None

    if number_list is not None:
        target_row, found = (
            locate_target_number(
                number_list
            )
        )

        if (
            target_row is not None
            and found is not None
            and not found.startswith(
                "target_"
            )
        ):
            target_id = found
        else:
            locate_reason = found

    sanitized_number = (
        _sanitize_target_number_record(
            target_row
        )
        if target_row is not None
        else None
    )

    inbound_reference = None

    if target_id:
        inbound_reference = _probe_get(
            token=token,
            url=(
                f"{BASE_URL}/"
                f"{account_id}/numbers/"
                f"{target_id}/"
                "InboundReferences"
            ),
        )

    inbound_payload = (
        inbound_reference[
            "payload"
        ]
        if inbound_reference
        else None
    )

    inbound_reference_contains_campaign = (
        _contains_exact_campaign(
            inbound_payload
        )
    )

    # Strongest verification routes:
    #
    # A) campaign object itself contains both exact
    #    campaign identity and target number.
    #
    # B) exact target number object exists and its
    #    provider inbound-reference object contains
    #    expected campaign id.
    direct_campaign_binding = (
        campaign_detail_proves_id
        and campaign_detail_contains_number
    )

    inbound_reference_binding = (
        target_row is not None
        and target_id is not None
        and inbound_reference_contains_campaign
    )

    provider_binding_verified = (
        direct_campaign_binding
        or inbound_reference_binding
    )

    return {
        "schema_version":
            SCHEMA_VERSION,

        "mode":
            "OBSERVE",

        "observed_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "provider":
            "Ringba",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "campaign_id":
            EXPECTED_CAMPAIGN_ID,

        "tracking_number":
            EXPECTED_TRACKING_NUMBER,

        "endpoint_observations": {
            name: {
                "status":
                    result["status"],
                "accessible":
                    result["accessible"],
                "error_class":
                    result.get(
                        "error_class"
                    ),
            }
            for name, result
            in results.items()
        },

        "campaign_detail_proves_id":
            campaign_detail_proves_id,

        "campaign_detail_contains_number":
            campaign_detail_contains_number,

        "number_object_found":
            target_row is not None,

        "number_object":
            sanitized_number,

        "number_lookup_reason":
            locate_reason,

        "inbound_reference_probed":
            inbound_reference
            is not None,

        "inbound_reference_status":
            (
                inbound_reference[
                    "status"
                ]
                if inbound_reference
                else None
            ),

        "inbound_reference_contains_campaign":
            inbound_reference_contains_campaign,

        "direct_campaign_binding":
            direct_campaign_binding,

        "inbound_reference_binding":
            inbound_reference_binding,

        "provider_binding_verified":
            provider_binding_verified,

        # This is the ONLY tracking verification
        # candidate emitted by this observer.
        "tracking_verification_candidate":
            provider_binding_verified,

        # Never automatically changes runtime authority.
        "tracking_verified_change":
            False,

        "routing_verified_change":
            False,

        "routing_enabled":
            False,

        "traffic_enabled":
            False,

        "commercial_activation":
            False,

        "revenue_recognized":
            False,

        "raw_provider_payload_persisted":
            False,

        "api_token_persisted":
            False,

        "account_id_persisted":
            False,

        "execution_authority":
            "NONE",
    }


def observe_from_environment() -> dict[str, Any]:
    import os

    token = str(
        os.getenv(
            "RINGBA_API_TOKEN",
            "",
        )
    ).strip()

    if not token:
        raise RuntimeError(
            "RINGBA_API_TOKEN missing"
        )

    accounts = discover_accounts(
        token
    )

    account_id = choose_account(
        accounts,
        os.getenv(
            "RINGBA_ACCOUNT_ID"
        ),
    )

    result = observe_tracking_objects(
        token=token,
        account_id=account_id,
    )

    result[
        "authenticated_account_count"
    ] = len(accounts)

    return result
