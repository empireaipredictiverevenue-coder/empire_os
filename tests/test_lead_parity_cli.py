import importlib.util
import sqlite3
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "lead_parity_report.py"
)
SPEC = importlib.util.spec_from_file_location(
    "lead_parity_report",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            create table crm_leads(
              lead_uid text,
              business_name text,
              niche text,
              metro text,
              phone text,
              created_at text
            );
            create table lane_leads(
              prospect_id text,
              name text,
              niche text,
              metro text,
              status text,
              created_at text
            );
            insert into crm_leads values(
              'crm-1',
              'Acme Ltd',
              'roofing',
              'London',
              '+442000000000',
              '2026-09-19T09:00:00Z'
            );
            insert into lane_leads values(
              'lane-1',
              'Beta Ltd',
              'hvac',
              'Leeds',
              'pending',
              '2026-09-19T09:01:00Z'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_read_legacy_rows_maps_lane_name_without_writing(tmp_path):
    db = tmp_path / "empire.db"
    make_db(db)
    before = db.stat().st_mtime_ns

    crm, lane = MODULE.read_legacy_rows(
        db,
        limit=100,
    )

    after = db.stat().st_mtime_ns
    assert crm[0]["lead_uid"] == "crm-1"
    assert lane[0]["prospect_id"] == "lane-1"
    assert lane[0]["business_name"] == "Beta Ltd"
    assert before == after


def test_read_only_mode_does_not_create_missing_database(tmp_path):
    missing = tmp_path / "missing.db"

    with pytest.raises(sqlite3.OperationalError):
        MODULE.read_legacy_rows(
            missing,
            limit=100,
        )

    assert missing.exists() is False


def test_limit_is_bounded(tmp_path):
    db = tmp_path / "empire.db"
    make_db(db)

    with pytest.raises(ValueError):
        MODULE.read_legacy_rows(db, limit=0)

    with pytest.raises(ValueError):
        MODULE.read_legacy_rows(db, limit=10001)
