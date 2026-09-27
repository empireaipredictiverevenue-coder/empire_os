import pytest

from empire_os.data_cloud_copy_verifier import (
    TableCopyEvidence,
    build_table_digest_query,
    verify_copy_manifest,
    verify_table_copy,
)


GOOD = "a" * 64
OTHER = "b" * 64


def test_digest_query_is_read_only_and_ordered():
    query = build_table_digest_query(
        "public.prospects",
        order_columns=("id",),
    )
    assert query.startswith("WITH digest_settings")
    assert "FROM public.\"prospects\" AS t" in query
    assert "ORDER BY t.\"id\"" in query
    assert "digest(to_jsonb(t)::text, 'sha256')" in query
    assert "set_config('TimeZone', 'UTC', true)" in query
    assert "set_config('bytea_output', 'hex', true)" in query


def test_digest_query_rejects_unsafe_identifiers():
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        build_table_digest_query(
            "prospects; drop table prospects",
            order_columns=("id",),
        )


def test_digest_query_requires_deterministic_order():
    with pytest.raises(ValueError, match="deterministic order"):
        build_table_digest_query("prospects", order_columns=())


def test_matching_copy_is_verified():
    result = verify_table_copy(
        TableCopyEvidence("prospects", 10, 10, GOOD, GOOD)
    )
    assert result["verified"] is True
    assert result["findings"] == []


def test_row_or_content_mismatch_fails():
    result = verify_table_copy(
        TableCopyEvidence("prospects", 10, 9, GOOD, OTHER)
    )
    assert result["verified"] is False
    assert "row_count_mismatch" in result["findings"]
    assert "content_digest_mismatch" in result["findings"]


def test_manifest_requires_every_table_to_match():
    result = verify_copy_manifest(
        (
            TableCopyEvidence("prospects", 10, 10, GOOD, GOOD),
            TableCopyEvidence("commercial_events", 5, 5, GOOD, OTHER),
        )
    )
    assert result["verified"] is False
    assert result["failed_tables"] == ["commercial_events"]
    assert result["authority"]["canonical_promotion"] is False


def test_empty_manifest_is_not_verified():
    result = verify_copy_manifest(())
    assert result["verified"] is False
    assert result["table_count"] == 0
