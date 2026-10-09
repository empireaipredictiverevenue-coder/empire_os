from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.lead_smart_ringba_api_observer import (
    BASE_URL,
    EXPECTED_CAMPAIGN_ID,
    RingbaApiError,
    _json_request,
    choose_account,
    discover_accounts,
)


SCHEMA_VERSION = (
    "empire.lead_smart."
    "ringba_routing_observation.v1"
)


def _hash(
    value: Any,
) -> str | None:
    raw = str(value or "").strip()

    if not raw:
        return None

    return hashlib.sha256(
        raw.encode()
    ).hexdigest()


def _contains_exact(
    value: Any,
    expected: str,
) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_exact(
                child,
                expected,
            )
            for child
            in value.values()
        )

    if isinstance(value, list):
        return any(
            _contains_exact(
                child,
                expected,
            )
            for child in value
        )

    return (
        str(value or "").strip()
        == expected
    )


def _bool_candidate(
    row: Mapping[str, Any],
    *names: str,
) -> bool | None:
    lowered = {
        str(key).casefold(): value
        for key, value
        in row.items()
    }

    for name in names:
        value = lowered.get(
            name.casefold()
        )

        if type(value) is bool:
            return value

    return None


def _identifier_candidate(
    row: Mapping[str, Any],
) -> Any:
    lowered = {
        str(key).casefold(): value
        for key, value
        in row.items()
    }

    for name in (
        "id",
        "routeid",
        "route_id",
        "callrouteid",
    ):
        value = lowered.get(
            name.casefold()
        )

        if isinstance(
            value,
            (
                str,
                int,
            ),
        ):
            return value

    return None


def _sanitize_route(
    *,
    path: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    keys = sorted(
        str(key)
        for key in row.keys()
    )

    lowered = {
        key.casefold()
        for key in keys
    }

    return {
        "path":
            path,

        "route_id_sha256":
            _hash(
                _identifier_candidate(
                    row
                )
            ),

        "enabled_candidate":
            _bool_candidate(
                row,
                "enabled",
                "isEnabled",
                "active",
                "isActive",
            ),

        "priority_present":
            "priority" in lowered,

        "call_target_present":
            (
                "calltarget" in lowered
                or "call_target" in lowered
            ),

        "target_group_present":
            (
                "calltargetgroup"
                in lowered
                or "call_target_group"
                in lowered
                or "targetgroup"
                in lowered
            ),

        "ping_tree_present":
            (
                "callpingtree" in lowered
                or "call_ping_tree" in lowered
                or "pingtree" in lowered
            ),

        "conversion_settings_present":
            (
                "conversionsettings"
                in lowered
                or "conversion_settings"
                in lowered
            ),

        # Key names are structure, not provider content.
        "object_keys":
            keys,

        "raw_object_persisted":
            False,
    }


def collect_route_objects(
    value: Any,
    *,
    path: str = "$",
) -> list[dict[str, Any]]:
    result: list[
        dict[str, Any]
    ] = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (
                f"{path}.{key}"
            )

            if "route" in str(
                key
            ).casefold():

                if isinstance(
                    child,
                    dict,
                ):
                    result.append(
                        _sanitize_route(
                            path=
                                child_path,
                            row=child,
                        )
                    )

                elif isinstance(
                    child,
                    list,
                ):
                    for index, item in enumerate(
                        child
                    ):
                        if isinstance(
                            item,
                            dict,
                        ):
                            result.append(
                                _sanitize_route(
                                    path=(
                                        f"{child_path}"
                                        f"[{index}]"
                                    ),
                                    row=item,
                                )
                            )

            result.extend(
                collect_route_objects(
                    child,
                    path=child_path,
                )
            )

    elif isinstance(value, list):
        for index, child in enumerate(
            value
        ):
            result.extend(
                collect_route_objects(
                    child,
                    path=(
                        f"{path}[{index}]"
                    ),
                )
            )

    # Deduplicate sanitized structural observations.
    unique = {}

    for row in result:
        key = json.dumps(
            row,
            sort_keys=True,
        )

        unique[key] = row

    return list(
        unique.values()
    )


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
            "status":
                status,

            "accessible":
                True,

            "error_class":
                None,

            "payload":
                payload,
        }

    except RingbaApiError as exc:
        message = str(exc)

        match = re.search(
            r"Ringba HTTP (\d+)",
            message,
        )

        status = (
            int(
                match.group(1)
            )
            if match
            else None
        )

        return {
            "status":
                status,

            "accessible":
                False,

            "error_class":
                (
                    "FORBIDDEN"
                    if status == 403
                    else
                    "NOT_FOUND"
                    if status == 404
                    else
                    "HTTP_ERROR"
                ),

            "payload":
                None,
        }


def observe_routing_objects(
    *,
    token: str,
    account_id: str,
) -> dict[str, Any]:
    """
    Observe Ringba route configuration.

    Configuration evidence is NOT treated as proof that
    an actual consumer call will connect successfully.
    """

    campaign_url = (
        f"{BASE_URL}/"
        f"{account_id}/campaigns/"
        f"{EXPECTED_CAMPAIGN_ID}"
    )

    routes_url = (
        f"{BASE_URL}/"
        f"{account_id}/CallRoutes"
    )

    campaign = _probe_get(
        token=token,
        url=campaign_url,
    )

    global_routes = _probe_get(
        token=token,
        url=routes_url,
    )

    campaign_payload = (
        campaign["payload"]
    )

    global_payload = (
        global_routes["payload"]
    )

    campaign_identity_verified = (
        campaign["accessible"]
        and _contains_exact(
            campaign_payload,
            EXPECTED_CAMPAIGN_ID,
        )
    )

    campaign_route_objects = (
        collect_route_objects(
            campaign_payload
        )
        if campaign_payload
        is not None
        else []
    )

    global_route_objects = (
        collect_route_objects(
            global_payload
        )
        if global_payload
        is not None
        else []
    )

    enabled_campaign_routes = [
        row
        for row
        in campaign_route_objects
        if row[
            "enabled_candidate"
        ]
        is True
    ]

    configuration_observed = (
        campaign_identity_verified
        and bool(
            campaign_route_objects
        )
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

        "campaign_detail": {
            "status":
                campaign["status"],

            "accessible":
                campaign[
                    "accessible"
                ],

            "error_class":
                campaign[
                    "error_class"
                ],

            "campaign_identity_verified":
                campaign_identity_verified,
        },

        "call_routes_endpoint": {
            "status":
                global_routes[
                    "status"
                ],

            "accessible":
                global_routes[
                    "accessible"
                ],

            "error_class":
                global_routes[
                    "error_class"
                ],
        },

        "campaign_route_object_count":
            len(
                campaign_route_objects
            ),

        "campaign_enabled_route_candidate_count":
            len(
                enabled_campaign_routes
            ),

        "global_route_object_count":
            len(
                global_route_objects
            ),

        "campaign_route_structure":
            campaign_route_objects,

        "routing_configuration_observed":
            configuration_observed,

        # Configuration existence is not end-to-end proof.
        "routing_runtime_verified":
            False,

        "test_call_performed":
            False,

        "call_connect_observed":
            False,

        "route_mutation_performed":
            False,

        "raw_campaign_payload_persisted":
            False,

        "raw_routes_payload_persisted":
            False,

        "api_token_persisted":
            False,

        "account_id_persisted":
            False,

        "routing_enabled":
            False,

        "traffic_enabled":
            False,

        "commercial_activation":
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

    result = (
        observe_routing_objects(
            token=token,
            account_id=account_id,
        )
    )

    result[
        "authenticated_account_count"
    ] = len(accounts)

    return result
