"""Read-only systemd health unit for the existing conversation collector.

The department cycle must remain operational during an inbox/read outage.
This standalone oneshot fails visibly in systemd without blocking the cycle.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

ROOT = Path("/srv/empire_os")


def _iso(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def verify(root: Path, now: datetime) -> str:
    if now.tzinfo is None:
        return "INVALID_CLOCK"
    path = root / "runtime/conversations_replies_control/collector_health_latest.json"
    evidence = root / "runtime/conversations_replies_control/latest.json"
    try:
        h = json.loads(path.read_text(encoding="utf-8"))
        snap = json.loads(evidence.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "COLLECTOR_EVIDENCE_MISSING"
    if not isinstance(h, dict) or not isinstance(snap, dict):
        return "COLLECTOR_EVIDENCE_INVALID"
    checktime = _iso(h.get("observed_at"))
    source_time = _iso(snap.get("generated_at"))
    if not checktime or not source_time:
        return "COLLECTOR_UNDATED"
    now = now.astimezone(timezone.utc)
    if not (timedelta(minutes=-2) <= now - checktime <= timedelta(minutes=15)):
        return "COLLECTOR_HEALTH_STALE"
    if abs((checktime - source_time).total_seconds()) > 120:
        return "COLLECTOR_SOURCE_UNCORRELATED"
    if (
        h.get("status") != "READ_SUCCESS"
        or h.get("source_query_completed") is not True
        or type(h.get("database_table_count")) is not int
        or h["database_table_count"] < 1
    ):
        return "COLLECTOR_READ_UNVERIFIED"
    return "PASS"


def main():
    from datetime import datetime, timezone
    status = verify(ROOT, datetime.now(timezone.utc))
    print(json.dumps({
        "schema": "empire.conversation_collector_systemd_health.v1",
        "status": status,
        "execution_authority": "none",
        "authenticated_buyer_intent": False,
    }))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
