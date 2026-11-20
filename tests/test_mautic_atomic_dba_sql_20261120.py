"""Offline safety checks for the pinned Mautic/CRM atomic DBA SQL builder."""
from __future__ import annotations

from pathlib import Path
import os
import re
import stat

import pytest

from scripts import build_mautic_atomic_dba_sql_20261120 as mod


def test_one_transaction_role_then_inbox_and_no_customer_mutation():
    sql = mod.build_atomic_sql()
    assert len(re.findall(r"(?m)^BEGIN;$", sql)) == 1
    assert len(re.findall(r"(?m)^COMMIT;$", sql)) == 1
    assert sql.index("CREATE ROLE empire_mautic_crm_inbox_writer") < sql.index(
        "CREATE TABLE public.empire_crm_mautic_event_inbox"
    )
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "SET LOCAL ROLE empiredb_migrator" in sql
    assert "CREATE ROLE empire_mautic_tenant_" not in sql
    assert "INSERT INTO public.prospects" not in sql
    assert "UPDATE public.prospects" not in sql
    assert "send_authorized=false" in sql


def test_source_mutation_blocks_assembly(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    for filename, _expected in mod.SOURCE_PARTS:
        (tmp_path / filename).write_text("BEGIN;\nCOMMIT;\n")
    with pytest.raises(ValueError, match="hash drift"):
        mod.build_atomic_sql()


def test_source_symlink_is_not_trusted(tmp_path, monkeypatch):
    for filename, _expected in mod.SOURCE_PARTS:
        (tmp_path / filename).symlink_to(mod.ROOT / filename)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="linked"):
        mod.build_atomic_sql()


def test_prepare_only_exclusive_0600_file(tmp_path):
    target = tmp_path / "atomic-release.sql"
    mod.prepare_sql(target)
    info = target.lstat()
    assert stat.S_ISREG(info.st_mode)
    assert stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_uid == os.getuid()
    assert target.read_text() == mod.build_atomic_sql()
    with pytest.raises(FileExistsError):
        mod.prepare_sql(target)
