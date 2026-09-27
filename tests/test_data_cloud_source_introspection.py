import pytest

from empire_os.data_cloud_source_introspection import (
    queries_are_read_only,
    schema_introspection_queries,
)


def test_introspection_covers_migration_critical_semantics():
    queries = schema_introspection_queries(["prospects", "commercial_events"])
    assert set(queries) == {
        "tables",
        "columns",
        "constraints",
        "indexes",
        "policies",
        "triggers",
        "trigger_routines",
        "extensions",
    }
    assert "relrowsecurity" in queries["tables"]
    assert "pg_get_constraintdef" in queries["constraints"]
    assert "indexdef" in queries["indexes"]
    assert "with_check" in queries["policies"]
    assert "information_schema.triggers" in queries["triggers"]
    assert "pg_get_functiondef" in queries["trigger_routines"]


def test_introspection_queries_are_read_only():
    queries = schema_introspection_queries(["prospects"])
    assert queries_are_read_only(queries) is True


def test_unsafe_table_names_are_rejected():
    with pytest.raises(ValueError, match="unsafe table name"):
        schema_introspection_queries(["prospects'); drop table prospects; --"])


def test_public_prefix_is_normalized():
    queries = schema_introspection_queries(["public.prospects"])
    assert "('prospects')" in queries["tables"]
    assert "public.prospects" not in queries["tables"]
