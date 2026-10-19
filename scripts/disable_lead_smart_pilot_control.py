"""Operator emergency STOP for the existing supervised Lead Smart site handoff.

This command only changes an existing, recognized control from enabled=true to
enabled=false. It cannot activate the pilot, create an active config, mutate a
buyer route, change a lead or access caller information. Dry-run is the default.

The control is checked on every site handoff, so disabling it prevents FUTURE
admissions. Existing displayed phone numbers, dialled calls and buyer-side
routes cannot be recalled or stopped by this first-party control alone.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from empire_os.lead_smart_site_handoff import (
    CAMPAIGN, CONFIG, NUMBER, SCHEMA, MAX_CONFIGURED_HANDOFFS,
)

MAX_BYTES = 16_384
# The existing reserve_site_handoff() acquires this exact advisory lock
# before its second verification and atomic permit ledger increment.
# A stop must acquire the SAME lock before disabling the control, so when
# stop returns all earlier reservations have either committed or failed.
_HANDOFF_LOCK = "site_handoffs.lock"


class UnsafeControl(ValueError):
    pass


def _read_known_control(path: Path) -> tuple[dict | None, bytes | None]:
    parent = path.parent
    try:
        pst = parent.lstat()
    except FileNotFoundError:
        return None, None
    if not stat.S_ISDIR(pst.st_mode) or stat.S_ISLNK(pst.st_mode):
        raise UnsafeControl("untrusted control directory")
    if pst.st_mode & 0o022:
        raise UnsafeControl("writable-by-others control directory")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        raise UnsafeControl("unreadable control") from exc
    try:
        fst = os.fstat(fd)
        if (not stat.S_ISREG(fst.st_mode) or fst.st_nlink != 1
                or fst.st_size > MAX_BYTES or fst.st_mode & 0o022
                or fst.st_uid not in (os.geteuid(), 0)):
            raise UnsafeControl("unsafe control file metadata")
        with os.fdopen(fd, "rb") as src:
            fd = -1
            raw = src.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise UnsafeControl("oversize control")
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        def pairs(items):
            out = {}
            seen = set()
            for k, v in items:
                if k in seen:
                    raise UnsafeControl("duplicate control key")
                seen.add(k)
                out[k] = v
            return out
        # A recognized stop target must be a single existing campaign. Neither
        # a malformed nor an unrelated file will be silently rewritten.
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise UnsafeControl("invalid control content") from exc
    if not isinstance(obj, dict) or not (
        obj.get("schema_version") == SCHEMA
        and obj.get("campaign_id") == CAMPAIGN
        and obj.get("tracking_number") == NUMBER
        and obj.get("stop_method") == "atomic_site_handoff_gate"
        and type(obj.get("max_site_handoffs")) is int
        and 1 <= obj["max_site_handoffs"] <= MAX_CONFIGURED_HANDOFFS
        and type(obj.get("enabled")) is bool
    ):
        raise UnsafeControl("unrecognized control identity")
    return obj, raw


def stop_control(*, control_path: Path = CONFIG, apply: bool = False) -> dict:
    """Apply only a disabling state transition, or preview with zero writes."""
    status = "NO_CONTROL_HELD"
    changed = False
    digest = None
    previous_digest = None
    try:
        obj, raw = _read_known_control(control_path)
        if obj is not None:
            previous_digest = hashlib.sha256(raw).hexdigest()
            digest = previous_digest
            if obj["enabled"] is False:
                status = "ALREADY_DISABLED"
            elif not apply:
                status = "WOULD_DISABLE"
            else:
                # Never use an independent operator lock: it would not serialize
                # with ongoing reservations of the first-party permit.
                lockpath = control_path.parent / _HANDOFF_LOCK
                lock_fd = os.open(
                    lockpath, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
                )
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX)
                    # Re-read under the same exclusive lock used by reservation.
                    obj, raw = _read_known_control(control_path)
                    if obj is None:
                        status = "NO_CONTROL_HELD"
                    elif obj["enabled"] is False:
                        status = "ALREADY_DISABLED"
                        digest = hashlib.sha256(raw).hexdigest()
                    else:
                        previous_digest = hashlib.sha256(raw).hexdigest()
                        obj["enabled"] = False
                        payload = (json.dumps(obj, sort_keys=True, indent=2)
                                   + "\n").encode("utf-8")
                        fd, tmp = tempfile.mkstemp(
                            prefix=".pilot-stop-", dir=control_path.parent
                        )
                        try:
                            os.fchmod(fd, 0o600)
                            with os.fdopen(fd, "wb") as dest:
                                dest.write(payload)
                                dest.flush()
                                os.fsync(dest.fileno())
                            os.replace(tmp, control_path)
                            dir_fd = os.open(control_path.parent, os.O_RDONLY)
                            try:
                                os.fsync(dir_fd)
                            finally:
                                os.close(dir_fd)
                        finally:
                            if os.path.exists(tmp):
                                os.unlink(tmp)
                        digest = hashlib.sha256(payload).hexdigest()
                        changed = True
                        status = "DISABLED"
                finally:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
    except (UnsafeControl, OSError):
        status = "UNTRUSTED_CONTROL_HELD"
    return {
        "schema_version": "empire.lead_smart.disable_only_operator.v1",
        "status": status,
        "mode": "DISABLE_ONLY" if apply else "OBSERVE",
        "state_changed": changed,
        "control_sha256_before": previous_digest,
        "control_sha256_after": digest,
        "pilot_activation_authorized": False,
        "calls_in_progress_stopped": False,
        "buyer_routing_modified": False,
        "ledger_modified": False,
        "buyer_recording_modified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Disable a matching, already existing control; never enable"
    )
    args = parser.parse_args()
    print(json.dumps(stop_control(apply=args.apply), sort_keys=True))


if __name__ == "__main__":
    main()
