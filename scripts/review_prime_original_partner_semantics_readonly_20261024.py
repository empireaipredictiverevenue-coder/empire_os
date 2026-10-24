#!/usr/bin/env python3
"""Observe already-owned private Gmail metadata; never query Gmail or EmpireDB.

Does not persist message, contact or hashed identity data; per-run HMAC key is
ephemeral. Outputs source-owner-reported aggregate research and mandatory HOLD
flags. No outbound, model training, source admission or financial actions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import argparse

from empire_os.prime_original_partner_index_adapter import (
    PrimeIndexHold, SCHEMA, review_original_partner_index,
)
from scripts.import_connected_gmail_buyer_metadata import (
    _private, THREADS, SOURCE, INDEX,
)


def inspect(root: Path, *, now: datetime) -> dict:
    try:
        original = _private(root / SOURCE, 2_500_000)
        index = _private(root / INDEX, 900_000)
        return review_original_partner_index(
            original=original,
            index=index,
            known_threads=THREADS,
            as_of=now,
            ephemeral_hmac_key=secrets.token_bytes(32),
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Exception reasons are intentionally not exposed: private metadata
        # and file paths must never enter stdout/stderr or Founder reports.
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": "ORIGINAL_OWNER_PRIVATE_METADATA_UNAVAILABLE_OR_HELD",
            "semantic_occurrences_not_enquiries": None,
            "inbound_semantic_occurrences_not_buyer_enquiries": None,
            "outbound_semantic_occurrences_not_buyer_enquiries": None,
            "original_provider_and_tenant_live_authenticated": False,
            "real_buyer_intent_verified": False,
            "signed_owner_receipts_admitted": False,
            "atomic_nonce_replay_registry_verified": False,
            "realized_revenue_cents": None,
            "database_writes": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/srv/empire_os")
    args = parser.parse_args()
    print(json.dumps(inspect(Path(args.root), now=datetime.now(timezone.utc)),
                     sort_keys=True))


if __name__ == "__main__":
    main()
