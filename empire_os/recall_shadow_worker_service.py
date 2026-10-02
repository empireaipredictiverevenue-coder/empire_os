"""Low-latency OBSERVE worker for verified Recall meeting events."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import signal
import time
from typing import Any

from empire_os.recall_shadow_guidance_worker import (
    refresh_recall_shadow_guidance,
)
from empire_os.recall_shadow_ingest_worker import process_verified_spool


logger = logging.getLogger("empire.recall_shadow_worker")
SPOOL_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_VERIFIED_SPOOL",
        "/srv/empire_os/runtime/digital_avatar/recall_ingress",
    )
)
OBSERVATION_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_OBSERVATION_ROOT",
        "/srv/empire_os/runtime/digital_avatar/observations",
    )
)
SESSION_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_SESSION_ROOT",
        "/srv/empire_os/runtime/digital_avatar/sessions",
    )
)
GUIDANCE_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_GUIDANCE_ROOT",
        "/srv/empire_os/runtime/digital_avatar/guidance",
    )
)
POLL_SECONDS = float(os.getenv("EMPIRE_RECALL_WORKER_POLL_SECONDS", "0.25"))
MAX_ITEMS = int(os.getenv("EMPIRE_RECALL_WORKER_MAX_ITEMS", "100"))


def run_once() -> dict[str, Any]:
    result = process_verified_spool(
        spool_root=SPOOL_ROOT,
        observation_root=OBSERVATION_ROOT,
        max_items=MAX_ITEMS,
    )
    refreshed = 0
    guidance_failed = 0
    for meeting_id in result.get("meetings") or []:
        session_path = SESSION_ROOT / f"{meeting_id}.json"
        if not session_path.is_file():
            guidance_failed += 1
            continue
        try:
            refresh_recall_shadow_guidance(
                session_path=session_path,
                observation_root=OBSERVATION_ROOT,
                output_path=GUIDANCE_ROOT / f"{meeting_id}.json",
            )
            refreshed += 1
        except Exception:
            guidance_failed += 1
    return {
        **result,
        "guidance_refreshed": refreshed,
        "guidance_failed": guidance_failed,
    }


def run_forever() -> None:
    if POLL_SECONDS <= 0:
        raise ValueError("EMPIRE_RECALL_WORKER_POLL_SECONDS must be positive")

    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logger.info(
        "Recall shadow worker starting mode=OBSERVE spool=%s observations=%s",
        SPOOL_ROOT,
        OBSERVATION_ROOT,
    )
    while not stopping:
        result = run_once()
        if result.get("failed"):
            logger.warning(
                "Recall shadow worker batch failures=%s",
                result.get("failed"),
            )
        if not result.get("processed") and not result.get("failed"):
            time.sleep(POLL_SECONDS)

    logger.info("Recall shadow worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_forever()
