from empire_os.recall_shadow_readiness import assess_recall_shadow_readiness


def ready_config():
    return {
        "RECALL_REGION": "eu-central-1",
        "RECALL_API_KEY": "redacted-test-key",
        "RECALL_WORKSPACE_VERIFICATION_SECRET": "whsec_dGVzdA==",
        "EMPIRE_RECALL_PUBLIC_REALTIME_URL": (
            "https://empire-ai.co.uk/v1/providers/recall/realtime"
        ),
    }


def test_ready_configuration_still_grants_no_execution_authority():
    result = assess_recall_shadow_readiness(
        config=ready_config(),
        public_gateway_route_ready=True,
        webhook_unit_ready=True,
        worker_unit_ready=True,
        tunnel_route_ready=True,
    )
    assert result.ready_for_activation is True
    assert result.blockers == ()
    assert result.live_join_execution is False
    assert result.speech_execution is False
    assert result.execution_authority == "none"


def test_missing_external_credentials_fail_closed():
    result = assess_recall_shadow_readiness(
        config={},
        public_gateway_route_ready=True,
        webhook_unit_ready=True,
        worker_unit_ready=True,
        tunnel_route_ready=True,
    )
    assert result.ready_for_activation is False
    assert "recall_region_missing" in result.blockers
    assert "recall_api_key_missing" in result.blockers
    assert "recall_workspace_verification_secret_missing" in result.blockers


def test_invalid_region_and_non_https_endpoint_block_activation():
    config = ready_config()
    config["RECALL_REGION"] = "uk-south-1"
    config["EMPIRE_RECALL_PUBLIC_REALTIME_URL"] = "http://localhost/recall"
    result = assess_recall_shadow_readiness(
        config=config,
        public_gateway_route_ready=True,
        webhook_unit_ready=True,
        worker_unit_ready=True,
        tunnel_route_ready=True,
    )
    assert "recall_region_invalid" in result.blockers
    assert "public_realtime_https_url_invalid" in result.blockers


def test_missing_runtime_surface_is_explicit():
    result = assess_recall_shadow_readiness(
        config=ready_config(),
        public_gateway_route_ready=False,
        webhook_unit_ready=False,
        worker_unit_ready=False,
        tunnel_route_ready=False,
    )
    assert result.ready_for_activation is False
    assert "public_gateway_recall_route_not_ready" in result.blockers
    assert "recall_webhook_unit_not_ready" in result.blockers
    assert "recall_shadow_worker_unit_not_ready" in result.blockers
    assert "public_tunnel_route_not_ready" in result.blockers
