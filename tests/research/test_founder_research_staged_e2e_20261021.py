"""Safety invariants of the isolated synthetic signed-session harness.

The expensive two-service E2E runs through its executable operator, not as a
normal unit-test side effect.
"""
from pathlib import Path
import pytest

from scripts.test_founder_research_staged_session_e2e_20261021 import (
    _safe_state, _verify_stage,
)


def test_successful_synthetic_flow_never_claims_real_founder_authorisation():
    packet = _safe_state({"signed_roundtrip": True, "existing_page_preserved": True})
    assert packet["status"] == "ISOLATED_SIGNED_FOUNDER_RESEARCH_SESSION_E2E_PASS"
    assert packet["synthetic_ephemeral_signer"] is True
    assert packet["real_cloudflare_access_jwks_tested"] is False
    assert packet["real_founder_session_verified"] is False
    assert packet["live_ingress_policy_verified"] is False
    assert packet["production_code_changed"] is False
    assert packet["customer_messages_sent"] is False
    assert packet["user_data_written"] is False
    assert packet["financial_actions_authorized"] is False


def test_any_failed_security_check_holds_and_never_activates():
    packet = _safe_state({"signed_roundtrip": True, "unauthorised_write_refused": False})
    assert packet["status"] == "HOLD_ISOLATED_FOUNDER_E2E_CHECKS_FAILED"
    assert packet["production_code_changed"] is False


@pytest.mark.parametrize("candidate", [
    Path("/srv/empire_os"),
    Path("/home/ubuntu/empire_worktrees"),
    Path("/tmp/other_stage"),
])
def test_executable_harness_refuses_non_ephemeral_stage_roots(candidate):
    with pytest.raises(ValueError, match="UNTRUSTED_EPHEMERAL_APPLICATION_STAGE"):
        _verify_stage(candidate, "empire-research-api-stage-",
                      "empire_os/founder_dashboard_service.py")
