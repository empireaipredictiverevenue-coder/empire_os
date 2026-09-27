from empire_os.data_cloud_schema_compat import (
    CheckConstraintSpec,
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    PolicySpec,
    RoutineSpec,
    SchemaManifest,
    TableSpec,
    TriggerSpec,
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
    source = SchemaManifest((_table("prospects"),), extensions=(("pgcrypto", "1.3"),))
    target = SchemaManifest((_table("prospects"),), extensions=(("pgcrypto", "1.3"),))
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
    assert "rls_state_mismatch:prospects" in result["findings"]


def test_payment_protection_semantics_are_all_verified():
    source = SchemaManifest(
        (
            TableSpec(
                name="bsc_payment_requests",
                columns=(
                    ColumnSpec("id", "uuid", False, "gen_random_uuid()"),
                    ColumnSpec("amount_usdt", "numeric", False),
                ),
                primary_key=("id",),
                unique_constraints=(("idempotency_key",),),
                check_constraints=(
                    CheckConstraintSpec(
                        "bsc_payment_requests_amount_usdt_check",
                        "CHECK (amount_usdt > 0::numeric)",
                    ),
                ),
                foreign_keys=(
                    ForeignKeySpec(
                        ("buyer_id",),
                        "public.buyers",
                        ("id",),
                        "FOREIGN KEY (buyer_id) REFERENCES buyers(id) ON DELETE RESTRICT",
                    ),
                ),
                indexes=(
                    IndexSpec(
                        "bsc_payment_requests_one_open_order_uidx",
                        ("fulfilment_order_id",),
                        True,
                        "CREATE UNIQUE INDEX bsc_payment_requests_one_open_order_uidx "
                        "ON public.bsc_payment_requests USING btree "
                        "(fulfilment_order_id) WHERE status = 'pending'::text",
                    ),
                ),
                rls_enabled=True,
                force_rls=True,
                rls_policies=(
                    PolicySpec(
                        "service_insert",
                        "INSERT",
                        ("service_role",),
                        None,
                        "approved_by IS NOT NULL",
                    ),
                ),
                triggers=(
                    TriggerSpec(
                        "payment_audit",
                        "EXECUTE FUNCTION record_payment_audit()",
                    ),
                ),
            ),
        ),
        extensions=(("pgcrypto", "1.3"),),
    )
    target = SchemaManifest(
        (
            TableSpec(
                name="bsc_payment_requests",
                columns=(
                    ColumnSpec("id", "uuid", False, None),
                    ColumnSpec("amount_usdt", "numeric", False),
                ),
                primary_key=("id",),
                unique_constraints=(),
                check_constraints=(),
                foreign_keys=(),
                indexes=(),
                rls_enabled=True,
                force_rls=False,
                rls_policies=(),
                triggers=(),
            ),
        ),
        extensions=(),
    )

    result = compare_schema(source, target)

    assert "default_mismatch:bsc_payment_requests.id" in result["findings"]
    assert "unique_constraint_mismatch:bsc_payment_requests" in result["findings"]
    assert "check_constraint_mismatch:bsc_payment_requests" in result["findings"]
    assert "foreign_key_mismatch:bsc_payment_requests" in result["findings"]
    assert "index_mismatch:bsc_payment_requests" in result["findings"]
    assert "force_rls_mismatch:bsc_payment_requests" in result["findings"]
    assert "rls_policy_mismatch:bsc_payment_requests" in result["findings"]
    assert "trigger_mismatch:bsc_payment_requests" in result["findings"]
    assert result["extension_compatibility_owner"] == "data_cloud_extension_plan"


def test_sql_whitespace_and_public_prefix_do_not_create_false_drift():
    source = TableSpec(
        name="events",
        columns=(ColumnSpec("id", "uuid", False),),
        indexes=(
            IndexSpec(
                "events_idx",
                definition="CREATE INDEX events_idx ON public.events USING btree (id)",
            ),
        ),
    )
    target = TableSpec(
        name="events",
        columns=(ColumnSpec("id", "uuid", False),),
        indexes=(
            IndexSpec(
                "events_idx",
                definition=" CREATE   INDEX events_idx ON events USING btree (id) ",
            ),
        ),
    )
    assert compare_schema(
        SchemaManifest((source,)),
        SchemaManifest((target,)),
    )["compatible"] is True


def test_manifest_builder_normalizes_public_prefix_and_defaults():
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
                "force_rls": False,
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


def test_trigger_routine_body_drift_blocks_schema_compatibility():
    source = SchemaManifest(
        (_table("commercial_events"),),
        routines=(
            RoutineSpec(
                "guard_commercial_events_integrity",
                "",
                "CREATE FUNCTION public.guard_commercial_events_integrity() "
                "RETURNS trigger LANGUAGE plpgsql SET search_path TO '' "
                "AS $$ BEGIN RAISE EXCEPTION 'append-only'; END; $$",
            ),
        ),
    )
    target = SchemaManifest(
        (_table("commercial_events"),),
        routines=(
            RoutineSpec(
                "guard_commercial_events_integrity",
                "",
                "CREATE FUNCTION public.guard_commercial_events_integrity() "
                "RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RETURN NEW; END; $$",
            ),
        ),
    )

    result = compare_schema(source, target)

    assert result["compatible"] is False
    assert "routine_mismatch" in result["findings"]


def test_routine_whitespace_only_drift_is_ignored():
    source = SchemaManifest(
        (_table("outbound_events"),),
        routines=(RoutineSpec("guard_outbound", "", "BEGIN  RETURN NEW; END;"),),
    )
    target = SchemaManifest(
        (_table("outbound_events"),),
        routines=(RoutineSpec("guard_outbound", "", " BEGIN RETURN NEW; END; "),),
    )
    assert compare_schema(source, target)["compatible"] is True
