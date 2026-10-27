"""Governed, keyless Last30Days feed used by the EXISTING Media OS refresh.

No new timer, agent, database, payment, publishing, SEO or outreach. Only the
existing Media OS oneshot, with explicit runtime opt-in, may refresh one
bounded public research topic per cycle. Report references are untrusted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping

from empire_os.media_last30days_demand import build_last30days_media_candidates

ROOT = Path("runtime/media_os/last30days")
CONFIG = ROOT / "config.json"
STATE = ROOT / "state.json"
MAX_TOPICS = 4
MAX_JSON = 2_000_000
RETRY_HOURS = 12
FRESH_HOURS = 24
APPROVED_TOPICS = (
    "AI agents for small businesses",
    "AI lead generation for roofing contractors",
    "AI sales avatars and digital sales agents",
    "first-party revenue intelligence and attribution",
)


def _safe_read(path: Path) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_JSON:
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _stamp(value: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else None


def _save(path: Path, payload: Mapping[str, Any]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("unsafe_last30days_cache_symlink")
    # Fixed non-secret runtime paths, private output, atomic per file.
    fd, name = tempfile.mkstemp(prefix=".last30days-", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _topic_file(topic: str) -> str:
    return hashlib.sha256(topic.encode("utf-8")).hexdigest()[:16] + ".json"


def _run_keyless(repo_root: Path, topic: str) -> dict[str, Any] | None:
    engine = repo_root / "empire_os/skills_library/last30days/scripts/last30days.py"
    if not engine.is_file() or engine.is_symlink():
        return None
    cmd = [
        sys.executable, "-B", str(engine), topic,
        "--search", "reddit,hackernews", "--quick", "--days", "30",
        "--max-results", "12", "--max-per-source", "6",
        "--max-source-fetches", "1", "--no-browser-cookies",
        "--no-verify-freshness", "--emit", "json",
    ]
    env = {
        key: value for key, value in os.environ.items()
        if not any(secret in key.upper() for secret in (
            "API_KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE", "AUTH",
        ))
    }
    env["LAST30DAYS_CONFIG_DIR"] = ""
    env["HOME"] = "/nonexistent"  # no browser profile, account auth or cookies
    try:
        run = subprocess.run(
            cmd, cwd=str(repo_root), capture_output=True, text=True,
            timeout=55, env=env, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if run.returncode != 0 or len(run.stdout.encode("utf-8")) > MAX_JSON:
        return None
    try:
        doc = json.loads(run.stdout)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def read_and_refresh_last30days(
    repo_root: Path, *, now: datetime | None = None,
    enable_fetch: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return validated raw exports and honest status. No setup = no action.

    The existing Media OS timer calls this function. Only one topic is
    refreshed per tick to bound network time, and no source text is executed.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    conf = _safe_read(repo_root / CONFIG)
    if conf is None:
        return [], {"state": "NOT_CONFIGURED", "enabled": False, "reports_accepted": 0}
    if (conf.get("schema_version") != "empire.media.last30days_config.v1"
            or conf.get("enabled") is not True
            or not isinstance(conf.get("topics"), list)
            or not 1 <= len(conf["topics"]) <= MAX_TOPICS
            or len(set(conf["topics"])) != len(conf["topics"])
            or any(t not in APPROVED_TOPICS for t in conf["topics"])):
        return [], {"state": "CONFIG_INVALID_OR_DISABLED", "enabled": False, "reports_accepted": 0}
    base = repo_root / ROOT
    base.mkdir(parents=True, exist_ok=True)
    state = _safe_read(repo_root / STATE) or {}
    attempts = state.get("last_attempts") if isinstance(state.get("last_attempts"), dict) else {}
    attempts = {t: attempts.get(t) for t in conf["topics"]}
    reports: list[dict[str, Any]] = []
    source_health: dict[str, Any] = {}
    refreshed_one = False

    for topic in conf["topics"]:
        cache_path = base / _topic_file(topic)
        cached = _safe_read(cache_path)
        parsed = build_last30days_media_candidates(cached, now=now, expected_topic=topic)
        valid_cache = parsed["source_available"] and parsed["source_state"] in (
            "OBSERVED_CANDIDATES_NOT_VERIFIED_DEMAND",
            "NO_MATCHES_WITH_REPORTED_SOURCE_COVERAGE",
            "NO_VALID_RECENT_SOURCE_ITEMS",
        )
        previous = _stamp(attempts.get(topic))
        due = not previous or now - previous >= timedelta(hours=RETRY_HOURS)
        if valid_cache:
            generated = _stamp(parsed["observed_at"])
            due = due and (not generated or now - generated >= timedelta(hours=FRESH_HOURS))
        if enable_fetch and due and not refreshed_one:
            refreshed_one = True
            attempts[topic] = now.isoformat()
            doc = _run_keyless(repo_root, topic)
            if doc is not None:
                candidate = build_last30days_media_candidates(doc, now=now, expected_topic=topic)
                if (candidate["source_available"]
                        and candidate["source_state"] in (
                            "OBSERVED_CANDIDATES_NOT_VERIFIED_DEMAND",
                            "NO_MATCHES_WITH_REPORTED_SOURCE_COVERAGE",
                            "NO_VALID_RECENT_SOURCE_ITEMS",
                        )):
                    _save(cache_path, doc)
                    cached, parsed, valid_cache = doc, candidate, True
        if valid_cache:
            reports.append(cached)
        source_health[topic] = {
            "status": parsed["source_state"] if valid_cache else "NO_FRESH_VALID_REPORT",
            "source_status": parsed["source_status"] if valid_cache else {},
            "observation_count": parsed["source_observation_count"] if valid_cache else 0,
            "observed_at": parsed["observed_at"] if valid_cache else None,
            "report_accepted": bool(valid_cache),
        }
    if refreshed_one:
        _save(repo_root / STATE, {
            "schema_version": "empire.media.last30days_state.v1",
            "last_attempts": attempts,
        })
    return reports, {
        "schema_version": "empire.media.last30days_source_health.v1",
        "state": "OBSERVE",
        "enabled": True,
        "reports_accepted": len(reports),
        "refresh_attempted": refreshed_one,
        "topics": source_health,
        "commercial_authority": "none",
        "execution_authority": "none",
    }
