from pathlib import Path


def test_021_serializes_all_outbound_daily_cap_checks():
    text = Path(
        "migrations/empiredb/"
        "021_outbound_daily_cap_and_confidence_hardening.sql"
    ).read_text()

    assert text.count("pg_advisory_xact_lock") == 3
    assert text.count("empire_outbound_daily_cap") == 3


def test_021_confidence_check_is_null_safe():
    text = Path(
        "migrations/empiredb/"
        "021_outbound_daily_cap_and_confidence_hardening.sql"
    ).read_text()

    assert (
        "jsonb_typeof(contact->'confidence') IS DISTINCT FROM 'number'"
        in text
    )

    assert (
        "jsonb_typeof(contact->'confidence') <> 'number'"
        not in text
    )


def test_blueprint_declares_empiredb_canonical():
    text = Path("docs/BLUEPRINT_V6.md").read_text()

    assert "EmpireDB PostgreSQL is the canonical production" in text
    assert "Supabase project `owbeinlfcfdtwcwrttjy`" in text
    assert "legacy/recovery evidence only" in text
