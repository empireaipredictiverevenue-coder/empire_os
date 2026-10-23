"""Founder acquisition: five-account *internal samples* from existing US source evidence.

This is NOT a buyer list, lead qualification, outreach, quote, or fulfilment.
Uses the original 20 US seed hypotheses and original bounded source-monitor
snapshot. No HTTP requests, email, CRM, database access, or systemd changes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any

from empire_os.founder_acquisition_us_market import (
    ALLOWED_CLIENTS, load_us_inputs, SCHEMA as US_SCHEMA,
)
from empire_os.workspace_solar_reply_tracking import EvidenceHeld

DEFAULT_ROOT = Path("/srv/empire_os")
SOURCE_EVIDENCE = Path("runtime/founder_acquisition/us_market_evidence_latest.json")
PRIVATE_SAMPLE = Path("runtime/founder_acquisition/five_account_pilot_internal_latest.json")
STATUS_READY = "INTERNAL_SOURCE_SAMPLES_READY_NOT_BUYER_VERIFIED"
STATUS_HELD = "HELD_ORIGINAL_SOURCE_EVIDENCE_UNVERIFIED"
SOURCE_CONFIRMED = "PUBLISHED_EVENT_CLAIM_OBSERVED_NOT_BUYER_VERIFIED"


def _trusted_evidence(root: Path, now: datetime) -> dict[str, Any]:
    source = root / SOURCE_EVIDENCE
    if (source.is_symlink() or not source.is_file()
            or not 300 <= source.stat().st_size <= 180_000
            or stat.S_IMODE(source.stat().st_mode) != 0o600):
        raise EvidenceHeld("SOURCE_SNAPSHOT_UNSAFE")
    evidence = json.loads(source.read_text(encoding="utf-8"))
    if (not isinstance(evidence, dict)
            or evidence.get("schema_version") != US_SCHEMA
            or evidence.get("status") != "US_PUBLIC_EVENT_EVIDENCE_REVIEW_ONLY"
            or evidence.get("market") != "US"
            or evidence.get("actual_buyers_verified") != 0
            or evidence.get("revenue_verified") is not False
            or evidence.get("outbound_sent") is not False
            or evidence.get("crm_writes") is not False
            or evidence.get("automatic_send_authorized") is not False
            or evidence.get("execution_authority") != "none"
            or evidence.get("approved_price") is not False):
        raise EvidenceHeld("SOURCE_SNAPSHOT_AUTHORITY_UNVERIFIED")
    return evidence


def prepare_internal_samples(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc) if now.tzinfo else None
    if now is None:
        raise EvidenceHeld("AWARE_CLOCK_REQUIRED")
    records = load_us_inputs(root)
    if len(records) != 20:
        raise EvidenceHeld("ORIGINAL_TWENTY_ACCOUNT_UNIVERSE_REQUIRED")
    evidence = _trusted_evidence(root, now)
    snapshots = evidence.get("sources")
    if not isinstance(snapshots, list) or len(snapshots) != 17:
        raise EvidenceHeld("ALL_ORIGINAL_SOURCES_REQUIRED")
    by_url = {}
    for observed in snapshots:
        if not isinstance(observed, dict):
            raise EvidenceHeld("INVALID_SOURCE_OBSERVATION")
        url = observed.get("source_url")
        if not isinstance(url, str) or url in by_url:
            raise EvidenceHeld("DUPLICATE_OR_INVALID_SOURCE_OBSERVATION")
        if (observed.get("source_status") != SOURCE_CONFIRMED
                or observed.get("actual_customer_demand") is not False
                or observed.get("outbound_authorized") is not False
                or not re.fullmatch(r"[a-f0-9]{64}", str(observed.get("source_sha256") or ""))):
            raise EvidenceHeld("PUBLISHER_CORROBORATION_INCOMPLETE")
        try:
            checked = datetime.fromisoformat(observed["observed_at_utc"])
        except (KeyError, ValueError, TypeError):
            raise EvidenceHeld("SOURCE_OBSERVED_TIME_UNVERIFIED") from None
        if (checked.tzinfo is None or checked > now
                or now - checked > timedelta(days=7)):
            raise EvidenceHeld("SOURCE_OBSERVATION_EXPIRED_OR_FUTURE")
        by_url[url] = observed
    if set(by_url) != {row["source_url"] for row in records}:
        raise EvidenceHeld("SNAPSHOT_DOES_NOT_MATCH_ORIGINAL_SOURCES")

    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in sorted(ALLOWED_CLIENTS)}
    for row in records:
        observed = by_url[row["source_url"]]
        if observed.get("source_role") != row["source_role"]:
            raise EvidenceHeld("SOURCE_ROLE_OR_ORIGIN_UNVERIFIED")
        # The original seed's hypothesis and gap are research assumptions,
        # not a claim that the company has a real software purchase need.
        account = {
            "account": row["account"],
            "geography": row["market"],
            "event_date": row["event_date"],
            "event_date_precision": row["date_precision"],
            "original_publisher_url": row["source_url"],
            "publisher_evidence_anchors": [row["anchor_a"], row["anchor_b"]],
            "source_type": row["source_role"],
            "last_source_observed_utc": observed["observed_at_utc"],
            "source_sha256": observed["source_sha256"],
            "research_fit_hypothesis": row["hypothesis"],
            "key_disqualification_risk": row["gap"],
            "buyer_intent": "NOT_VERIFIED",
            "procurement_contact": "NOT_VERIFIED",
            "buyer_permission_to_contact": "NOT_VERIFIED",
            "delivery_action": "HUMAN_RESEARCH_REVIEW_ONLY",
        }
        groups[row["startup"]].append(account)
    if (len(groups) != 4
            or any(len(items) != 5 or len({a["account"].casefold() for a in items}) != 5
                   for items in groups.values())):
        raise EvidenceHeld("EXACT_FIVE_DISTINCT_ACCOUNTS_PER_ORIGINAL_VERTICAL_REQUIRED")
    return {
        "schema_version": "empire.founder_five_account_internal_sample.v1",
        "status": STATUS_READY,
        "created_utc": now.isoformat(),
        "source": "ORIGINAL_US_MARKET_SOURCE_EVIDENCE",
        "vertical_count": 4,
        "per_vertical_account_count": 5,
        "source_verified_hypotheses": 20,
        "verified_buyers": 0,
        "authentic_buyer_response_verified": False,
        "pilot_quote_approved": False,
        "pilot_customer_accepted": False,
        "pilot_payment_verified": False,
        "pilot_delivered": False,
        "new_contact_approved": False,
        "outbound_governor_activate": False,
        "auto_followups": False,
        "outbound_sent": False,
        "crm_writes": False,
        "payment_actions": False,
        "groups": groups,
    }


def write_private_sample(root: Path, sample: dict[str, Any]) -> Path:
    root = Path(root).resolve(strict=True)
    path = root / PRIVATE_SAMPLE
    folder = path.parent
    if (folder.is_symlink() or not folder.is_dir()
            or stat.S_IMODE(folder.stat().st_mode) != 0o700
            or path.is_symlink()):
        raise EvidenceHeld("PRIVATE_OUTPUT_LOCATION_UNSAFE")
    if path.exists() and (
        not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600
    ):
        raise EvidenceHeld("PREVIOUS_SAMPLE_UNSAFE")
    fd, temp = tempfile.mkstemp(prefix=".five-account-", suffix=".json", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(sample, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Existing source-backed internal five-account samples; no sending")
    parser.add_argument("--repo-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--write-private", action="store_true")
    args = parser.parse_args()
    summary: dict[str, Any] = {
        "status": STATUS_HELD,
        "new_sends": 0, "crm_writes": 0, "payment_actions": 0,
        "outbound_governor_activate": False,
    }
    try:
        root = Path(args.repo_root).resolve(strict=True)
        sample = prepare_internal_samples(root)
        if args.write_private:
            write_private_sample(root, sample)
        summary.update({
            "status": STATUS_READY,
            "vertical_count": sample["vertical_count"],
            "per_vertical_account_count": 5,
            "sample_account_count": sample["source_verified_hypotheses"],
            "verified_buyers": 0,
            "pilot_sold": False,
            "private_sample_written": args.write_private,
        })
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception:
        summary["private_sample_written"] = False
        print(json.dumps(summary, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
