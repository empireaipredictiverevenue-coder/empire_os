"""Empire OS Hub Loop — standalone process entrypoint.

Run separately from the hub so it doesn't compete with uvicorn for asyncio threads
when lead_deliverer / billing_collector hold the SQLite WAL.

Usage:
    /usr/bin/python3 -m empire_os.hub_loop_standalone

Env:
    EMPIRE_DB_PATH       path to empire_os.db (default "empire_os.db")
    HUB_LOOP_ENRICH_SEC  enrich tick cadence (default 90)
    HUB_LOOP_OUTREACH_SEC outreach tick cadence (default 300)
    HUB_LOOP_HEALTH_SEC  heartbeat cadence (default 60)
    HUB_LOOP_ENABLED     master switch (default 1)
"""
from __future__ import annotations

import logging
import os
import signal
import sqlite3
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s hub_loop[%(process)d] %(message)s")
log = logging.getLogger("hub_loop_standalone")


def _emit(level: str, msg: str, **fields) -> None:
    """Emit JSON log line compatible with hub_loop.py's logger."""
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "msg": msg,
        **fields,
    }
    try:
        log.log(
            {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}.get(level, 20),
            "%s %s",
            msg,
            fields,
        )
    except Exception:
        pass


def main() -> int:
    if os.environ.get("HUB_LOOP_ENABLED", "1") != "1":
        _emit("INFO", "hub_loop_disabled")
        return 0

    db_path = os.environ.get("EMPIRE_DB_PATH", "empire_os.db")
    log.info("starting standalone hub_loop on db=%s", db_path)

    # Reuse the same tick fns from the in-process module so any future
    # edits to hub_loop.py automatically apply here.
    from empire_os import hub_loop as hl

    enrich_sec = int(os.environ.get("HUB_LOOP_ENRICH_SEC", "90"))
    outreach_sec = int(os.environ.get("HUB_LOOP_OUTREACH_SEC", "300"))
    health_sec = int(os.environ.get("HUB_LOOP_HEALTH_SEC", "60"))

    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row

    class _BackendShim:
        def __init__(self, c):
            self._conn = c

    backend = _BackendShim(conn)

    stop = False

    def _term(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)

    next_enrich = time.monotonic()
    next_outreach = time.monotonic() + 30
    next_health = time.monotonic()

    while not stop:
        now = time.monotonic()
        try:
            if now >= next_health:
                hl._health_tick()
                _emit("INFO", "health_tick_standalone", alive=True,
                     enrich_sec=enrich_sec, outreach_sec=outreach_sec)
                next_health = now + health_sec
            if now >= next_enrich:
                r = hl._enrich_tick(backend)
                _emit("INFO", "enrich_tick_standalone", **r)
                next_enrich = now + enrich_sec
            if now >= next_outreach:
                r = hl._outreach_tick(backend)
                _emit("INFO", "outreach_tick_standalone", **r)
                next_outreach = now + outreach_sec
        except Exception as e:
            _emit("ERROR", "tick_failed_standalone", error=str(e)[:300])
            time.sleep(2)

        time.sleep(max(0.5, min(next_enrich, next_outreach, next_health) - time.monotonic()))

    log.info("stopping")
    try:
        conn.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())