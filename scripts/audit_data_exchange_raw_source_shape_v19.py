"""One-shot, bounded raw SOURCE-KEYS inventory; do not log source values.

Reuses V15's fixed three official Planning Data entity IDs and existing
allowlisted HTTPS reader. It inventories raw response *key names only*
before the strict normalizer drops fields. No DB connection, persistence,
outbound, payments, timing loop, rights signoff or privacy clearance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
from typing import Any, Callable, Mapping

from empire_os.data_exchange_construction import (
    build_construction_preview, normalise_official_brownfield_entities,
)
from scripts.operate_data_exchange_observation_custody import PILOT_ENTITY_IDS
from scripts.probe_construction_official_entities import fetch_official_json

SCHEMA="empire.data_exchange.transient_source_key_inventory.v19"
ALLOWED_RAW_KEYS=frozenset({
    "entity", "dataset", "quality", "organisation-entity", "end-date",
    "planning-permission-status", "hectares", "entry-date",
})
SENSITIVE_KEY_TERMS=frozenset({
    "email", "mail", "telephone", "phone", "contact",
    "address", "person", "owner", "name", "notes", "description",
    "comment", "postcode", "mobile",
})
MAX_RAW_FIELDS=256


def audit_source_key_shapes(
    *, now: datetime, fetch_json: Callable[[str], Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware source audit time required")
    key_counts: list[int]=[]
    excluded_counts: list[int]=[]
    sensitive_counts: list[int]=[]
    # This wrapper performs identity validation through the existing
    # normaliser, while retaining only key-class counts, not raw values.
    def observe(url: str) -> Mapping[str, Any]:
        source=fetch_json(url)
        if (
            not isinstance(source,Mapping)
            or len(source)>MAX_RAW_FIELDS
            or any(not isinstance(k,str) or not k or len(k)>128
                   for k in source)
        ):
            raise ValueError("unreviewed raw JSON schema or size")
        keys=set(source)
        key_counts.append(len(keys))
        excluded_counts.append(len(keys-ALLOWED_RAW_KEYS))
        sensitive_counts.append(sum(
            any(term in re.split(
                r"[^a-z0-9]+",re.sub(r"([a-z0-9])([A-Z])",
                    lambda m: m.group(1)+"-"+m.group(2),key).casefold()
            ) for term in SENSITIVE_KEY_TERMS)
            for key in keys
        ))
        # Values exist transiently in the official HTTP JSON parser and
        # the original normalizer; no raw response is persisted/logged here.
        return source

    rows=normalise_official_brownfield_entities(
        list(PILOT_ENTITY_IDS),fetch_json=observe,observed_at=now)
    projection=build_construction_preview(rows,observed_at=now)
    if (
        len(key_counts)!=len(PILOT_ENTITY_IDS)
        or projection["dataset_record_count"]!=len(PILOT_ENTITY_IDS)
        or projection["rejected_counts"]!={}
        or projection["customer_delivery_enabled"] is not False
    ):
        raise ValueError("official raw-shape audit not complete")
    return {
        "schema_version":SCHEMA,
        "status":"TRANSIENT_RAW_KEY_INVENTORY_COMPLETED_NOT_PRIVACY_SIGNOFF",
        "mode":"OBSERVE",
        "official_entity_responses_checked":len(key_counts),
        "raw_json_key_occurrences":sum(key_counts),
        "raw_json_key_occurrences_outside_projection_allowlist":sum(excluded_counts),
        "potentially_sensitive_key_name_occurrences":sum(sensitive_counts),
        "potentially_sensitive_key_names_detected":sum(sensitive_counts)>0,
        "raw_values_analyzed_for_personal_data":False,
        "personal_information_in_raw_payload":"UNKNOWN_NOT_REVIEWED",
        "raw_response_logged_or_persisted_by_audit":False,
        "personal_contact_fields_persisted_in_projection":False,
        "projection_fields_strictly_validated":True,
        "raw_keys_and_values_disclosed":False,
        "independent_privacy_review_completed":False,
        "independent_field_rights_review_completed":False,
        "customer_delivery_enabled":False,
        "data_resale_authorized":False,
        "outbound_enabled":False,
        "payment_execution":False,
        "database_writes":False,
        "execution_authority":"NONE",
    }


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only",action="store_true")
    args=p.parse_args(argv)
    try:
        if not args.read_only:
            raise ValueError("READ_ONLY_FLAG_REQUIRED")
        result=audit_source_key_shapes(
            now=datetime.now(timezone.utc), fetch_json=fetch_official_json)
        print(json.dumps(result,sort_keys=True,allow_nan=False))
        return 0
    except Exception as exc:
        # No exception messages: HTTP and raw data can be sensitive.
        print(json.dumps({
            "schema_version":SCHEMA,"mode":"OBSERVE",
            "status":"HOLD_SOURCE_KEY_INVENTORY_UNVERIFIED",
            "error_type":type(exc).__name__,
            "raw_keys_and_values_disclosed":False,
            "database_writes":False,
            "customer_delivery_enabled":False,
            "execution_authority":"NONE",
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
