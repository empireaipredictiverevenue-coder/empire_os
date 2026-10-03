"""Stable sender/domain infrastructure attestation and drift detection."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


_ATTESTED_KEYS = (
    "domain",
    "nameservers",
    "spf_record",
    "dkim_selectors",
    "dmarc_record",
    "mx_records",
    "transport_key",
    "tracking_domain",
    "return_path_domain",
)


def configuration_fingerprint(context: Mapping[str, Any]) -> dict[str, Any]:
    canonical = {key: context.get(key) for key in _ATTESTED_KEYS}
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return {
        "fingerprint": hashlib.sha256(encoded).hexdigest(),
        "canonical": canonical,
        "algorithm": "sha256",
    }


def detect_configuration_drift(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    old = configuration_fingerprint(previous)
    new = configuration_fingerprint(current)

    changed = [
        key
        for key in _ATTESTED_KEYS
        if old["canonical"].get(key) != new["canonical"].get(key)
    ]

    critical_keys = {
        "nameservers",
        "spf_record",
        "dkim_selectors",
        "dmarc_record",
        "transport_key",
        "return_path_domain",
    }
    critical = sorted(set(changed).intersection(critical_keys))

    if critical:
        posture = "HOLD"
    elif changed:
        posture = "REMEDIATE"
    else:
        posture = "STABLE"

    return {
        "posture": posture,
        "changed_fields": changed,
        "critical_changes": critical,
        "previous_fingerprint": old["fingerprint"],
        "current_fingerprint": new["fingerprint"],
    }
