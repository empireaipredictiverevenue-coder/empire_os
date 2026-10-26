"""Private, idempotent progress cursor for approved canonical v2 archive backfill."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

SCHEMA = "empire.qualification_historical_backfill_cursor.v1"
DEFAULT_CURSOR = Path(
    "/srv/empire_os/runtime/qualification/historical_backfill_cursor.json"
)


def load_cursor(path: Path = DEFAULT_CURSOR) -> int:
    if not path.exists() and not path.is_symlink():
        return 0
    if (
        path.is_symlink() or not path.is_file()
        or path.stat().st_size > 8192 or path.stat().st_mode & 0o077
    ):
        raise ValueError("unsafe qualification backfill cursor")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA:
        raise ValueError("qualification backfill cursor schema mismatch")
    offset = data.get("next_offset")
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid qualification backfill offset")
    return offset


def save_cursor(
    offset: int, *,
    path: Path = DEFAULT_CURSOR,
) -> None:
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid qualification backfill offset")
    if path.is_symlink():
        raise ValueError("unsafe qualification backfill cursor target")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise ValueError("unsafe qualification backfill cursor directory")
    if path.exists() and path.stat().st_mode & 0o077:
        raise ValueError("existing cursor not owner private")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".historical-backfill-", suffix=".json", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            json.dump({
                "schema_version": SCHEMA,
                "next_offset": offset,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "outbound_authorized": False,
                "payment_authorized": False,
            }, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
