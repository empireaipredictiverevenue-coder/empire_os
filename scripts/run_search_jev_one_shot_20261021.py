"""Manually triggered, credential-protected ONE REAL Jev SEO shadow request."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
from typing import Any

from empire_os.search_intelligence.jev_live_pilot import (
    JevPilotHeld, build_jev_one_shot_plan, evaluate_jev_one_shot,
)

KEY_FILE = Path("/etc/empire_os/llm_secrets/openrouter.env")
OUTPUT_DIR = Path("/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021")
RECEIPT = OUTPUT_DIR / "seo_jev_one_shot_receipt_v1.json"


def _read_key() -> str:
    if KEY_FILE.is_symlink() or not KEY_FILE.is_file():
        raise JevPilotHeld("openrouter_credential_file_unavailable")
    if KEY_FILE.stat().st_mode & 0o077:
        raise JevPilotHeld("openrouter_credential_file_permissions_too_broad")
    matches = []
    for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[len("export "):].strip()
        if stripped.startswith("OPENROUTER_API_KEY="):
            val = stripped.split("=", 1)[1].strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
                val = val[1:-1]
            matches.append(val)
    if (len(matches) != 1 or len(matches[0]) < 20
            or any(c.isspace() for c in matches[0])
            or matches[0].startswith("$" + "{")):
        raise JevPilotHeld("openrouter_key_not_available")
    return matches[0]


def run(*, live: bool) -> dict[str, Any]:
    plan = build_jev_one_shot_plan()
    if not live:
        return {
            "status": "JEV_REAL_INFERENCE_DRY_RUN",
            "model": plan["expected_model"],
            "endpoint": plan["expected_endpoint"],
            "source_sha256": plan["source_sha256"],
            "outbound_state": plan["state"],
            "questions": list(plan["request"]["questions"]),
            "network_requests": 0,
            "actual_jev_predictions": 0,
            "execution_authority": "NONE",
        }
    OUTPUT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if OUTPUT_DIR.is_symlink() or OUTPUT_DIR.stat().st_mode & 0o077:
        raise JevPilotHeld("private_receipt_directory_not_secure")
    lock = OUTPUT_DIR / "pilot.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if RECEIPT.exists() or RECEIPT.is_symlink():
            raise JevPilotHeld("pilot_already_completed_no_repeat_billing")
        result = evaluate_jev_one_shot(plan, key=_read_key())
        encoded = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
        out_fd = os.open(str(RECEIPT), os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
        with os.fdopen(out_fd, "wb") as f:
            f.write(encoded)
        return {"status": "JEV_REAL_SEO_SHADOW_INFERENCE_OBSERVED", **result,
                "private_receipt": str(RECEIPT)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-one-shot", action="store_true")
    parser.add_argument("--owner-approved-no-publication", action="store_true")
    args = parser.parse_args()
    if args.live_one_shot and not args.owner_approved_no_publication:
        parser.error("explicit bounded live pilot approval flag required")
    if args.owner_approved_no_publication and not args.live_one_shot:
        parser.error("approval flag requires --live-one-shot")
    try:
        result = run(live=args.live_one_shot)
    except (JevPilotHeld, OSError) as exc:
        result = {"status": "JEV_REAL_INFERENCE_HELD",
                  "reason": str(exc) if isinstance(exc, JevPilotHeld)
                            else "secure_receipt_or_credential_unavailable",
                  "requests_automatically_retried": False,
                  "publishing_authorized": False,
                  "execution_authority": "NONE"}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
