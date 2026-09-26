from empire_os.foundation_contracts import (
    AuthorizationCheck,
    DenyAllAuthorizationProvider,
    DisabledEventBus,
    DisabledFeatureFlagProvider,
    DisabledWorkflowEngine,
    EventEnvelope,
    FeatureFlagCheck,
    WorkflowRequest,
    external_foundation_authority_contract,
)


def test_event_bus_default_is_inert():
    result = DisabledEventBus().publish(EventEnvelope(
        event_type="buyer.replied",
        event_id="evt-1",
        aggregate_ref="intent:1",
        payload={"classification": "positive"},
    ))
    assert result["published"] is False
    assert result["execution_authority"] == "none"


def test_workflow_default_cannot_start():
    result = DisabledWorkflowEngine().start(WorkflowRequest(
        workflow_type="buyer_conversation",
        workflow_id="wf-1",
        input_ref="intent:1",
        input_payload={"intent_id": "1"},
    ))
    assert result["started"] is False
    assert result["execution_authority"] == "none"


def test_authorization_default_denies():
    result = DenyAllAuthorizationProvider().check(AuthorizationCheck(
        subject="agent:closer",
        relation="accept_terms",
        resource="conversation:1",
        tenant_ref="tenant:1",
    ))
    assert result["allowed"] is False


def test_feature_flag_default_never_enables():
    result = DisabledFeatureFlagProvider().is_enabled(FeatureFlagCheck(
        flag_key="outbound.auto_send",
        context={"tenant": "tenant:1"},
        default=True,
    ))
    assert result["enabled"] is False


def test_external_foundations_never_replace_empire_authority():
    contract = external_foundation_authority_contract()
    assert contract["event_bus_can_grant_execution"] is False
    assert contract["workflow_engine_can_grant_execution"] is False
    assert contract["authorization_provider_can_move_funds"] is False
    assert contract["feature_flags_can_bypass_revenue_truth"] is False
    assert contract["feature_flags_can_bypass_outbound_approval"] is False
    assert contract["feature_flags_can_bypass_payment_authority"] is False
    assert contract["canonical_revenue_truth_remains_empire"] is True
