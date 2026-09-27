from empire_os.data_cloud_schema_compat import (
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    SchemaManifest,
    TableSpec,
    compare_schema,
    manifest_from_rows,
)


def _table(name, *, dtype="uuid", nullable=False, rls=True):
    return TableSpec(
        name=name,
        columns=(ColumnSpec("id", dtype, nullable),),
        primary_key=("id",),
        rls_enabled=rls,
    )


def test_identical_schema_is_compatible():
    source = SchemaManifest((_table("prospects"),))
    target = SchemaManifest((_table("prospects"),))
    result = compare_schema(source, target)
    assert result["compatible"] is True
    assert result["findings"] == []


def test_missing_table_blocks_compatibility():
    result = compare_schema(
        SchemaManifest((_table("commercial_events"),)),
        SchemaManifest(()),
    )
    assert result["compatible"] is False
    assert "missing_table:commercial_events" in result["findings"]


def test_type_primary_key_and_rls_drift_are_detected():
    source = SchemaManifest((_table("prospects"),))
    target = SchemaManifest(
        (
            TableSpec(
                name="prospects",
                columns=(ColumnSpec("id", "text", False),),
                primary_key=(),
                rls_enabled=False,
            ),
        )
    )
    result = compare_schema(source, target)
    assert "type_mismatch:prospects.id" in result["findings"]
    assert "primary_key_mismatch:prospects" in result["findings"]
    assert "rls_missing:prospects" in result["findings"]


def test_defaults_constraints_indexes_and_policies_are_verified():
    source = SchemaManifest(
        (
            TableSpec(
                name="outbound_intents",
                columns=(
                    ColumnSpec("id", "uuid", False, "gen_random_uuid()"),
                    ColumnSpec("buyer_id", "uuid", False),
                ),
                primary_key=("id",),
                unique_constraints=(("buyer_id",),),
                foreign_keys=(
                    ForeignKeySpec(
                        ("buyer_id",),
                        "public.buyers",
                        ("id",),
                    ),
                ),
                indexes=(IndexSpec("idx_outbound_buyer", ("buyer_id",)),),
                rls_enabled=True,
                rls_policies=("tenant_read", "service_insert"),
            ),
        )
    )
    target = SchemaManifest(
        (
            TableSpec(
                name="outbound_intents",
                columns=(
                    ColumnSpec("id", "uuid", False, None),
                    ColumnSpec("buyer_id", "uuid", False),
                ),
                primary_key=("id",),
                unique_constraints=(),
                foreign_keys=(),
                indexes=(),
                rls_enabled=True,
                rls_policies=("tenant_read",),
            ),
        )
    )
    result = compare_schema(source, target)
    assert "default_mismatch:outbound_intents.id" in result["findings"]
    assert "unique_constraint_mismatch:outbound_intents" in result["findings"]
    assert "foreign_key_mismatch:outbound_intents" in result["findings"]
    assert "index_mismatch:outbound_intents" in result["findings"]
    assert (
        "rls_policy_missing:outbound_intents.service_insert"
        in result["findings"]
    )


def test_manifest_builder_normalizes_public_prefix_and_default():
    manifest = manifest_from_rows(
        [
            {
                "table_name": "public.prospects",
                "column_name": "id",
                "data_type": "uuid",
                "is_nullable": "NO",
                "column_default": "gen_random_uuid()",
                "primary_key": True,
                "rls_enabled": True,
            }
        ]
    )
    assert manifest.tables[0].name == "prospects"
    assert manifest.tables[0].primary_key == ("id",)
    assert manifest.tables[0].columns[0].default == "gen_random_uuid()"
    assert manifest.tables[0].rls_enabled is True


def test_extra_target_tables_do_not_destroy_source_compatibility():
    result = compare_schema(
        SchemaManifest((_table("prospects"),)),
        SchemaManifest((_table("prospects"), _table("empire_internal"))),
    )
    assert result["compatible"] is True
    assert result["extra_target_tables"] == ["empire_internal"]
