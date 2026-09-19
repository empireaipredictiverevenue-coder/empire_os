from empire_os.agi_capabilities import (
    capability_registry,
    review_capability_request,
)


def test_registry_has_no_wildcard_or_unrestricted_shell():
    registry = capability_registry()
    assert registry["wildcard_capabilities"] is False
    assert registry["unrestricted_shell_capability"] is False
    assert registry["unrestricted_database_capability"] is False


def test_observe_read_is_allowed_when_explicitly_granted():
    review = review_capability_request({
        "agent_id": "astra",
        "capability": "evidence.read",
        "authority_mode": "OBSERVE",
        "granted_capabilities": ["evidence.read"],
    })
    assert review["permitted"] is True
    assert review["execution_performed"] is False


def test_reasoning_about_send_does_not_grant_send():
    review = review_capability_request({
        "agent_id": "outreach-planner",
        "capability": "outreach.send",
        "authority_mode": "OBSERVE",
        "granted_capabilities": ["evidence.read"],
        "approval_present": True,
    })
    assert review["permitted"] is False
    assert "capability_not_granted" in review["blockers"]
    assert "authority_mode_too_low" in review["blockers"]


def test_guarded_send_requires_grant_and_approval():
    missing_approval = review_capability_request({
        "agent_id": "sender",
        "capability": "outreach.send",
        "authority_mode": "GUARDED_EXECUTE",
        "granted_capabilities": ["outreach.send"],
        "approval_present": False,
    })
    assert missing_approval["permitted"] is False
    assert "approval_required" in missing_approval["blockers"]

    permitted = review_capability_request({
        "agent_id": "sender",
        "capability": "outreach.send",
        "authority_mode": "GUARDED_EXECUTE",
        "granted_capabilities": ["outreach.send"],
        "approval_present": True,
    })
    assert permitted["permitted"] is True
    assert permitted["execution_performed"] is False
