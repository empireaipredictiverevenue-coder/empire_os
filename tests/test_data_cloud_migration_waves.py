from empire_os.data_cloud_migration_waves import (
    MigrationWave,
    build_wave_plan,
    classify_table,
)


def test_core_truth_tables_are_not_classified_as_legacy():
    for table in (
        "prospects",
        "business_entities",
        "prospect_entity_links",
        "prospect_qualifications",
        "commercial_events",
    ):
        assert classify_table(table) is MigrationWave.CORE_TRUTH


def test_payment_and_outbound_schema_are_commercial_even_when_empty():
    for table in (
        "outbound_intents",
        "bsc_payment_requests",
        "bsc_payment_evidence",
        "fulfilment_orders",
    ):
        assert classify_table(table) is MigrationWave.COMMERCIAL


def test_unknown_tables_are_preserved_as_legacy_not_dropped():
    plan = build_wave_plan(["old_table"])
    assert plan[0].wave is MigrationWave.LEGACY
    assert plan[0].preserve_schema is True
    assert plan[0].copy_data is True


def test_schema_prefix_is_normalized():
    assert classify_table("public.prospects") is MigrationWave.CORE_TRUTH
