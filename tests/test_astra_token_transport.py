from pathlib import Path

import empire_os.astra_token_transport as legacy
from empire_os.outcome_role_transport import ROLE_FUNCTIONS


def test_legacy_astra_transport_is_retired():
    assert legacy.RETIRED is True
    assert legacy.CANONICAL_TRANSPORT == (
        "empire_os.outcome_role_transport.PostgresOutcomeRpc"
    )


def test_astra_observer_role_is_read_only():
    assert set(ROLE_FUNCTIONS["empire_astra_observer"]) == {
        "get_commercial_outcome_feedback",
        "get_astra_operational_evidence",
    }


def test_astra_runtime_has_no_hosted_token_transport():
    cli = Path("scripts/astra_observer.py").read_text()
    preflight = Path("empire_os/astra_preflight.py").read_text()

    assert "SupabaseTokenAstraRpc" not in cli
    assert "astra_token_transport" not in cli

    assert "SUPABASE" not in cli.upper()

    # Legacy keys may only exist in preflight as explicit rejection markers.
    assert "token_rpc_ok" not in preflight
    assert "observer_token_rpc_configured" not in preflight
