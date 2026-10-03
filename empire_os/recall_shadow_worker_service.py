"""Low-latency OBSERVE worker for verified Recall meeting events."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import signal
import time
from typing import Any

from empire_os.recall_lifecycle_ingest_worker import (
    process_verified_lifecycle_spool,
)
from empire_os.recall_meeting_runtime_state import (
    refresh_recall_meeting_runtime_state,
)
from empire_os.recall_meeting_state_snapshot import (
    materialize_recall_meeting_state_snapshot,
)
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
STATUS_SPOOL_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_STATUS_SPOOL",
        "/srv/empire_os/runtime/digital_avatar/recall_status_ingress",
    )
)
LIFECYCLE_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_LIFECYCLE_ROOT",
        "/srv/empire_os/runtime/digital_avatar/meeting_lifecycle",
    )
)
LIFECYCLE_LATEST_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_LIFECYCLE_LATEST_ROOT",
        "/srv/empire_os/runtime/digital_avatar/lifecycle_latest",
    )
)
RUNTIME_STATE_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_RUNTIME_STATE_ROOT",
        "/srv/empire_os/runtime/digital_avatar/runtime_state",
    )
)
MEETING_STATE_ROOT = Path(
    os.getenv(
        "EMPIRE_RECALL_MEETING_STATE_ROOT",
        "/srv/empire_os/runtime/digital_avatar/meeting_state",
    )
)
CLOSE_READINESS_ROOT = Path(
    os.getenv(
        "EMPIRE_AVATAR_CLOSE_READINESS_ROOT",
        "/srv/empire_os/runtime/digital_avatar/close_readiness",
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
    lifecycle = process_verified_lifecycle_spool(
        spool_root=STATUS_SPOOL_ROOT,
        event_root=LIFECYCLE_ROOT,
        latest_root=LIFECYCLE_LATEST_ROOT,
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

    runtime_state_refreshed = 0
    runtime_state_failed = 0
    for meeting_id in lifecycle.get("meetings") or []:
        try:
            refresh_recall_meeting_runtime_state(
                lifecycle_root=LIFECYCLE_ROOT,
                meeting_id=meeting_id,
                output_path=RUNTIME_STATE_ROOT / f"{meeting_id}.json",
            )
            runtime_state_refreshed += 1
        except Exception:
            runtime_state_failed += 1

    meeting_state_refreshed = 0
    meeting_state_failed = 0
    touched_meetings = set(result.get("meetings") or ())
    touched_meetings.update(lifecycle.get("meetings") or ())
    for meeting_id in sorted(touched_meetings):
        try:
            materialize_recall_meeting_state_snapshot(
                meeting_id=meeting_id,
                guidance_root=GUIDANCE_ROOT,
                runtime_state_root=RUNTIME_STATE_ROOT,
                close_readiness_root=CLOSE_READINESS_ROOT,
                output_root=MEETING_STATE_ROOT,
            )
            meeting_state_refreshed += 1
        except Exception:
            meeting_state_failed += 1

    return {
        **result,
        "guidance_refreshed": refreshed,
        "guidance_failed": guidance_failed,
        "lifecycle_processed": lifecycle.get("processed", 0),
        "lifecycle_failed": lifecycle.get("failed", 0),
        "lifecycle_duplicates": lifecycle.get("duplicates", 0),
        "lifecycle_meetings": lifecycle.get("meetings", []),
        "runtime_state_refreshed": runtime_state_refreshed,
        "runtime_state_failed": runtime_state_failed,
        "meeting_state_refreshed": meeting_state_refreshed,
        "meeting_state_failed": meeting_state_failed,
        "polling_performed": False,
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
        if result.get("failed") or result.get("lifecycle_failed"):
            logger.warning(
                "Recall shadow worker failures realtime=%s lifecycle=%s",
                result.get("failed"),
                result.get("lifecycle_failed"),
            )
        if (
            not result.get("processed")
            and not result.get("failed")
            and not result.get("lifecycle_processed")
            and not result.get("lifecycle_failed")
        ):
            time.sleep(POLL_SECONDS)

    logger.info("Recall shadow worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_forever()
