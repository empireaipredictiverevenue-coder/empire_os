from empire_os.data_cloud_extension_plan import (
    ExtensionClass,
    ExtensionObservation,
    classify_extension,
    extension_cutover_blockers,
    plan_extensions,
)


def test_known_postgres_extensions_are_portable_or_core():
    assert classify_extension("plpgsql") is ExtensionClass.CORE
    assert classify_extension("pgcrypto") is ExtensionClass.PORTABLE
    assert classify_extension("postgis") is ExtensionClass.PORTABLE
    assert classify_extension("vector") is ExtensionClass.PORTABLE


def test_supabase_vault_is_vendor_specific():
    assert classify_extension("supabase_vault") is ExtensionClass.VENDOR_SPECIFIC


def test_required_vendor_extension_blocks_cutover_until_replaced():
    plans = plan_extensions(
        (
            ExtensionObservation("pgcrypto", "1.3"),
            ExtensionObservation("supabase_vault", "0.3.1"),
        ),
        required_by_schema=("pgcrypto", "supabase_vault"),
    )

    by_name = {plan.name: plan for plan in plans}
    assert by_name["pgcrypto"].action == "install_and_verify"
    assert by_name["pgcrypto"].cutover_blocked is False
    assert by_name["supabase_vault"].action == "replace_with_empire_capability"
    assert by_name["supabase_vault"].cutover_blocked is True
    assert extension_cutover_blockers(plans) == ("supabase_vault",)


def test_vendor_extension_not_used_by_schema_is_not_a_cutover_blocker():
    plans = plan_extensions(
        (ExtensionObservation("supabase_vault", "0.3.1"),),
        required_by_schema=(),
    )
    assert plans[0].action == "replace_with_empire_capability"
    assert plans[0].cutover_blocked is False


def test_unknown_required_extension_fails_to_manual_review():
    plans = plan_extensions(
        (ExtensionObservation("mystery_ext", "1.0"),),
        required_by_schema=("mystery_ext",),
    )
    assert plans[0].action == "manual_compatibility_review"
    assert plans[0].cutover_blocked is True
