"""Safely compose the two hash-pinned DBA SQL parts into ONE transaction.

PREPARE ONLY. Never connects to a database or executes SQL.
Production execution remains a separate founder-authorised DBA action.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "docs/integrations/sql"
SOURCE_PARTS = (
    ("MAUTIC_CRM_INBOX_WRITER_ROLE_PREPARED_ONLY_20261119.sql",
     "e0aa864737ba9fdb50e125d859f56c1891b5c8e8df47f0bd6598ce8f3f30cf89"),
    ("MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql",
     "1c87e222790c329f820a8150aec77e0af25092b84b445527bdb856f18c249ae6"),
)


def build_atomic_sql() -> str:
    pieces = []
    for filename, expected in SOURCE_PARTS:
        path = ROOT / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"source SQL missing or linked: {filename}")
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError(f"source SQL hash drift: {filename}")
        source = raw.decode("utf-8")
        for keyword in ("BEGIN", "COMMIT"):
            pattern = rf"(?m)^{keyword};\s*$"
            if len(re.findall(pattern, source)) != 1:
                raise ValueError(f"source SQL transaction shape changed: {filename}")
            source = re.sub(pattern, "", source, count=1)
        if re.search(r"(?m)^(?:BEGIN|COMMIT);\s*$", source):
            raise ValueError(f"unexpected nested transaction: {filename}")
        pieces.append(source.strip())
    return (
        "-- DBA CONTROLLED MAUTIC INBOX. SOURCE HASHES PINNED. NO USER DATA.\n"
        "-- Role and table are one atomic PostgreSQL transaction.\n"
        "BEGIN;\n"
        "SET LOCAL lock_timeout = '2s';\n"
        "SET LOCAL statement_timeout = '30s';\n"
        + "\n\n".join(pieces)
        + "\nCOMMIT;\n"
    )


def prepare_sql(path: Path) -> None:
    statement = build_atomic_sql().encode("utf-8")
    # Only create a brand-new 0600 file. Caller controls its trusted destination.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(statement)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-sql", type=Path)
    args = parser.parse_args()
    assembled = build_atomic_sql()
    if args.prepare_sql is not None:
        prepare_sql(args.prepare_sql)
        print("MAUTIC_ATOMIC_DBA_SQL=PREPARED_ONLY_NO_DATABASE_WRITE")
    else:
        print("MAUTIC_ATOMIC_DBA_SQL=HASH_PINNED_VALIDATED_NO_DATABASE_WRITE")
    print("MAUTIC_ATOMIC_DBA_SQL_SHA256=" + sha256(assembled.encode()).hexdigest())
