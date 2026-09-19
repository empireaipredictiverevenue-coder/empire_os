from pathlib import Path

from empire_os.astra_preflight import assess_runtime_preflight


def write_env(path: Path, text: str, mode=0o600):
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)


def test_missing_env_and_units_are_explicit(tmp_path):
    result = assess_runtime_preflight(
        env_path=tmp_path / ".env.astra_observer",
        service_installed=False,
        timer_installed=False,
        timer_enabled=False,
    )
    assert result.runtime_ready is False
    assert "observer_env_file_missing" in result.blockers
    assert "observer_dsn_not_configured" in result.blockers
    assert "observer_service_not_installed" in result.blockers
    assert "observer_timer_not_installed" in result.blockers
    assert "observer_timer_not_enabled" in result.blockers


def test_complete_observe_runtime_is_ready(tmp_path):
    env = tmp_path / ".env.astra_observer"
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_OBSERVER_DSN=postgresql://redacted",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=1000",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=true",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is True
    assert result.blockers == ()
    assert result.observe_mode_configured is True
    assert result.observer_dsn_configured is True
    assert result.policy_bindings_complete is True


def test_insecure_secret_file_permissions_block_readiness(tmp_path):
    env = tmp_path / ".env.astra_observer"
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=OBSERVE",
            "EMPIRE_ASTRA_OBSERVER_DSN=postgresql://redacted",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=1000",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=true",
        ]) + "\n",
        mode=0o644,
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is False
    assert "observer_env_permissions_insecure" in result.blockers


def test_non_observe_mode_is_rejected(tmp_path):
    env = tmp_path / ".env.astra_observer"
    write_env(
        env,
        "\n".join([
            "EMPIRE_ASTRA_MODE=EXECUTE",
            "EMPIRE_ASTRA_OBSERVER_DSN=postgresql://redacted",
            "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS=1000",
            "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED=true",
            "EMPIRE_ASTRA_SOURCE_HEALTH_OK=true",
        ]) + "\n",
    )
    result = assess_runtime_preflight(
        env_path=env,
        service_installed=True,
        timer_installed=True,
        timer_enabled=True,
    )
    assert result.runtime_ready is False
    assert "observe_mode_not_configured" in result.blockers
