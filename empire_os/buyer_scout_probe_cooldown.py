"""No-repeat bounded first-party probe cache for the *owned* fallback Scout.

Never turns cached company evidence into a buyer/permission decision.
A missing or invalid ledger holds probes instead of silently clearing
all histories. No file writes from this module; caller explicitly saves
a bounded ledger only AFTER a successful OBSERVE run.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from collections.abc import Mapping
from empire_os.buyer_scout_commercial_awareness import _domain

SCHEMA = "empire.buyer_scout_probe_cooldown.v1"
COOLDOWN = timedelta(hours=24)
MAX_HISTORY = 2000
MAX_BYTES = 250_000


def _timestamp(raw: object, now: datetime) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("probe_timestamp_missing")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("probe_timestamp_invalid") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("probe_timezone_required")
    dt = dt.astimezone(timezone.utc)
    if dt > now + timedelta(minutes=5) or now - dt > timedelta(days=31):
        raise ValueError("probe_timestamp_out_of_window")
    return dt


def load_probe_history(path: Path, *, now: datetime) -> dict[str, str]:
    if path.is_symlink():
        raise ValueError("probe_history_symlink_denied")
    if not path.exists():
        return {}
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("probe_history_untrusted")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("probe_history_unreadable") from exc
    if not isinstance(doc, Mapping) or doc.get("schema_version") != SCHEMA:
        raise ValueError("probe_history_schema_invalid")
    records = doc.get("last_probed_at")
    if not isinstance(records, dict) or len(records) > MAX_HISTORY:
        raise ValueError("probe_history_unbounded")
    selected = {}
    for raw_domain, value in records.items():
        domain = _domain(raw_domain)
        if not domain or domain != raw_domain:
            raise ValueError("probe_history_domain_untrusted")
        dt = _timestamp(value, now)
        if now - dt < COOLDOWN:
            selected[domain] = dt.isoformat()
    return selected


def merge_observed_probes(
    history: Mapping[str, str], scout: Mapping, *,
    now: datetime,
) -> dict[str, str]:
    """Store only domains with positive first-party site evidence."""
    if (not isinstance(scout, Mapping)
            or scout.get("schema_version") != "empire.buyer_acquisition_scout.v1"
            or scout.get("mode") != "OBSERVE"
            or scout.get("execution_authority") != "none"
            or scout.get("outbound_sent") is not False):
        raise ValueError("untrusted_scout_for_probe_cache")
    stamp = _timestamp(scout.get("generated_at"), now)
    candidates = scout.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError("unbounded_scout_candidates")
    merged = {}
    for domain, last in history.items():
        normalized = _domain(domain)
        if normalized != domain:
            raise ValueError("invalid_prior_domain")
        previous = _timestamp(last, now)
        if now - previous < COOLDOWN:
            merged[domain] = previous.isoformat()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("untrusted_candidate")
        domain = _domain(candidate.get("domain"))
        if not domain:
            continue
        # The Scout may include a candidate without a successful site probe.
        # Do NOT cool down an unprobed domain.
        site_score = candidate.get("site_evidence_score")
        if (type(site_score) not in (float, int) or site_score <= 0
                or candidate.get("business_name_source") not in
                ("first_party_site_identity", "canonical_seed_corroborated_by_site")):
            continue
        merged[domain] = stamp.isoformat()
    if len(merged) > MAX_HISTORY:
        raise ValueError("probe_cache_overflow")
    return dict(sorted(merged.items()))


def save_probe_history(path: Path, history: Mapping[str, str]) -> None:
    """Optional owned-runtime atomic file write; no DB or service mutation."""
    import os
    import tempfile
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("unsafe_cache_path")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({"schema_version": SCHEMA,
                          "last_probed_at": dict(sorted(history.items()))},
                         sort_keys=True, separators=(",", ":"))
    if len(content.encode()) > MAX_BYTES:
        raise ValueError("cache_payload_too_large")
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".probe-cache-", text=True)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(content + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)
