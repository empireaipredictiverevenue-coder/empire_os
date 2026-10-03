"""Tamper-evident Reputation Passport evidence chaining."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


GENESIS = "0" * 64


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def chain_evidence(
    evidence: Mapping[str, Any],
    *,
    previous_hash: str = GENESIS,
) -> dict[str, Any]:
    previous_hash = str(previous_hash or GENESIS).lower()
    if len(previous_hash) != 64 or any(ch not in "0123456789abcdef" for ch in previous_hash):
        raise ValueError("previous_hash_must_be_sha256_hex")

    canonical = _canonical_json(evidence)
    digest = hashlib.sha256(
        (previous_hash + "\n" + canonical).encode("utf-8")
    ).hexdigest()

    return {
        "evidence": dict(evidence),
        "previous_evidence_hash": previous_hash,
        "evidence_hash": digest,
        "algorithm": "sha256",
    }


def verify_chain(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    expected_previous = GENESIS
    checked = 0

    for raw in records:
        row = dict(raw)
        evidence = row.get("evidence")
        if not isinstance(evidence, Mapping):
            return {"valid": False, "checked": checked, "reason": "invalid_evidence"}

        previous = str(row.get("previous_evidence_hash") or "")
        digest = str(row.get("evidence_hash") or "")
        if previous != expected_previous:
            return {"valid": False, "checked": checked, "reason": "chain_link_mismatch"}

        calculated = chain_evidence(evidence, previous_hash=previous)["evidence_hash"]
        if calculated != digest:
            return {"valid": False, "checked": checked, "reason": "evidence_hash_mismatch"}

        expected_previous = digest
        checked += 1

    return {
        "valid": True,
        "checked": checked,
        "head_hash": expected_previous,
    }
