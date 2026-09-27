from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import empire_os.data_cloud_shadow_dump_import as module
from empire_os.data_cloud_shadow_copy import ShadowTable
from empire_os.data_cloud_shadow_dump_import import (
    _decode_copy_text,
    build_plan,
    scan_dump,
)


def test_decode_copy_text_escapes() -> None:
    assert _decode_copy_text(b"abc\\tdef") == "abc\tdef"
    assert _decode_copy_text(b"abc\\\\def") == "abc\\def"
    assert _decode_copy_text(b"\\N") is None


def test_scan_dump_counts_rows_and_hashes_primary_key(tmp_path: Path) -> None:
    dump = tmp_path / "data.sql"
    dump.write_bytes(
        b"COPY public.parent (id, note) FROM stdin;\n"
        b"00000000-0000-0000-0000-000000000002\tsecond\n"
        b"00000000-0000-0000-0000-000000000001\tfirst\n"
        b"\\.\n"
        b"COPY public.child (id, parent_id) FROM stdin;\n"
        b"00000000-0000-0000-0000-000000000003\t"
        b"00000000-0000-0000-0000-000000000001\n"
        b"\\.\n"
    )
    tables = (
        ShadowTable("parent"),
        ShadowTable("child", parents=("parent",)),
    )
    blocks = scan_dump(dump, tables)
    assert blocks["parent"].row_count == 2
    assert blocks["child"].row_count == 1
    assert blocks["parent"].columns == ("id", "note")
    assert blocks["parent"].data_start < blocks["parent"].data_end


def test_scan_dump_requires_every_manifest_table(tmp_path: Path) -> None:
    dump = tmp_path / "data.sql"
    dump.write_bytes(
        b"COPY public.parent (id) FROM stdin;\n"
        b"00000000-0000-0000-0000-000000000001\n"
        b"\\.\n"
    )
    with pytest.raises(RuntimeError, match="missing required COPY"):
        scan_dump(
            dump,
            (
                ShadowTable("parent"),
                ShadowTable("child", parents=("parent",)),
            ),
        )


class _Target:
    def connect(self):
        return _Connection()

    @staticmethod
    def columns(connection, table: str):
        return ("id",)

    @staticmethod
    def count(connection, table: str):
        return 1


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_plan_blocks_nonempty_target() -> None:
    from empire_os.data_cloud_shadow_dump_import import CopyBlock

    block = CopyBlock(
        table="example",
        columns=("id",),
        data_start=0,
        data_end=0,
        row_count=1,
        primary_key_sha256="abc",
    )
    report = build_plan(
        {"example": block},
        _Target(),
        (ShadowTable("example"),),
    )
    assert report["all_targets_empty"] is False
    assert report["schema_compatible"] is True


def test_dump_importer_has_no_destructive_authority() -> None:
    source = inspect.getsource(module)
    upper = source.upper()
    assert "DELETE FROM" not in upper
    assert "TRUNCATE TABLE" not in upper
    assert "SUPABASE_" not in source
    assert '"production_cutover_authority": False' in source
    assert 'choices=("plan", "copy")' in source
