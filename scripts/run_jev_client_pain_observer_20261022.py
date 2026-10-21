#!/usr/bin/env python3
"""Guarded production observer, consuming only existing public-intent evidence.

READS: existing public social community observations and unresolved social
intent from the canonical inbox. WRITES: its own private + aggregate JSON
receipts in a dedicated folder only. It does not crawl, run a model, mutate
EmpireDB, enqueue actor jobs, send messages or call network endpoints.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

from empire_os.jev_client_pain_discovery import (
    discover_client_pains, observations_from_existing_canonical_inbox,
)

HISTORY = Path("/srv/empire_os/runtime/community_intent/observations.json")
SIGNAL_INBOX = Path("/srv/empire_os/runtime/acquisition/signal_inbox.json")
OUTPUT = Path("/srv/empire_os/runtime/jev_client_pain_discovery")
MAX_INPUT_BYTES = 12_000_000
SCHEMA = "empire.jev.client_pain_production_observe.v1"


def _load(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe source path")
    size = path.stat().st_size
    if not 0 < size <= MAX_INPUT_BYTES:
        raise ValueError("source size outside approved bounds")
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_receipt(path: Path, data: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ValueError("unsafe receipt symlink")
    fd, tmp_name = tempfile.mkstemp(prefix=".jev_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def run(*, history: Path = HISTORY, inbox: Path = SIGNAL_INBOX,
        output_dir: Path = OUTPUT, write_private: bool = False,
        now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    community = _load(history)
    canonical = _load(inbox)
    if not isinstance(community, dict) or not isinstance(community.get("observations"), list):
        raise ValueError("invalid canonical community history")
    if not isinstance(canonical, dict):
        raise ValueError("invalid canonical signal inbox")
    social = observations_from_existing_canonical_inbox(canonical)
    original = community["observations"]
    if len(original) > 500 or len(social) > 500 or len(original) + len(social) > 500:
        raise ValueError("review capacity exceeded; no partial promotions")
    result = discover_client_pains([*original, *social], now=now,
                                   include_private_source_links=write_private)
    aggregate = {
        k: v for k, v in result.items() if k != "items"
    }
    aggregate.update({
        "schema_version": SCHEMA,
        "generated_at_utc": now.isoformat(),
        "source_scope": "existing_public_community_and_canonical_social_intent_only",
        "community_rows_loaded": len(original),
        "canonical_social_rows_loaded": len(social),
        "concrete_pain_theme_count": len(result["pain_counts"]),
        "verified_individual_clients": 0,
        "verified_contracts": 0,
        "commercial_action": "none",
        "network_calls": 0,
        "model_calls": 0,
        "source_collection_changed": False,
        "production_collector_modified": False,
        "outreach_sent": 0,
        "crm_writes": False,
        "database_writes": False,
        "execution_authority": "none",
    })
    if write_private:
        os.umask(0o077)
        if output_dir.is_symlink():
            raise ValueError("private output directory cannot be a symlink")
        output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(output_dir, 0o700)
        _atomic_receipt(output_dir / "private_latest.json", result)
        _atomic_receipt(output_dir / "aggregate_latest.json", aggregate)
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--write-private", action="store_true")
    args = parser.parse_args()
    r = run(write_private=args.write_private)
    print(json.dumps({
        "status": r["status"],
        "review_lanes": r["review_lane_counts"],
        "evidence_pain_theme_count": r["concrete_pain_theme_count"],
        "observations": r["observations_submitted"],
        "verified_clients": r["verified_individual_clients"],
        "outreach_sent": r["outreach_sent"],
        "model_calls": r["model_calls"],
        "network_calls": r["network_calls"],
        "private_receipts_written": args.write_private,
        "execution_authority": "none",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
