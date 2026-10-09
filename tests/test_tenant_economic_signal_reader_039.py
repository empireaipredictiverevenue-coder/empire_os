from pathlib import Path


PATH = Path(
    "migrations/empiredb/"
    "039_tenant_economic_signal_reader.sql"
)


def text():
    return " ".join(
        PATH.read_text().lower().split()
    )


def test_exists():
    assert PATH.exists()


def test_security_definer():
    s = text()
    assert "security definer" in s
    assert "set search_path = ''" in s


def test_tenant_derived_internally():
    s = text()

    assert (
        "v_tenant_id := "
        "public.empire_current_tenant_id()"
        in s
    )

    # Caller must never supply tenant identity.
    start = s.index(
        "public.empire_read_economic_signals("
    )
    end = s.index(") returns table", start)
    signature = s[start:end]

    assert "p_tenant" not in signature


def test_active_binding_required():
    s = text()

    assert (
        "public.tenant_business_entity_bindings b"
        in s
    )
    assert "b.entity_id = s.entity_id" in s
    assert "b.tenant_id = v_tenant_id" in s
    assert "b.active is true" in s
    assert "b.valid_from <= p_as_of" in s
    assert "b.valid_until > p_as_of" in s


def test_only_economic_signal_types():
    s = text()

    for value in (
        "revenue_leak",
        "idle_asset",
        "market_gap",
        "idle_waste",
    ):
        assert f"'{value}'" in s


def test_source_and_time_guards():
    s = text()

    assert "src.enabled is true" in s
    assert "s.observed_at <= p_as_of" in s
    assert "s.expires_at is null" in s
    assert "s.expires_at > p_as_of" in s


def test_public_and_app_revoked():
    s = text()

    assert "from public" in s
    assert "from empiredb_app" in s


def test_only_tenant_reader_granted():
    s = text()

    assert "to empiredb_tenant_reader" in s


def test_no_signal_or_binding_mutation():
    s = PATH.read_text().upper()

    forbidden = (
        "INSERT INTO PUBLIC.INTELLIGENCE_SIGNALS",
        "UPDATE PUBLIC.INTELLIGENCE_SIGNALS",
        "DELETE FROM PUBLIC.INTELLIGENCE_SIGNALS",
        "INSERT INTO PUBLIC."
        "TENANT_BUSINESS_ENTITY_BINDINGS",
        "UPDATE PUBLIC."
        "TENANT_BUSINESS_ENTITY_BINDINGS",
        "DELETE FROM PUBLIC."
        "TENANT_BUSINESS_ENTITY_BINDINGS",
    )

    for value in forbidden:
        assert value not in s
