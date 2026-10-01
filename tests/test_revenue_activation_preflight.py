from pathlib import Path


def test_gateway_a2a_dropin_is_env_only():
    text = Path(
        "deploy/systemd/empire-public-gateway.service.d/20-a2a-runtime.conf"
    ).read_text()
    assert "[Service]" in text
    assert "EnvironmentFile=-/etc/empire_a2a.env" in text
    assert "ExecStart" not in text
    assert "Environment=EMPIRE_" not in text


def test_a2a_env_template_has_no_real_secret():
    text = Path("deploy/env/empire_a2a.env.example").read_text()
    assert "EMPIRE_A2A_TRUSTED_ED25519_KEYS_JSON=" in text
    assert "EMPIRE_A2A_IDENTITY_DSN=" in text
    assert "EMPIRE_A2A_INTENT_DSN=" in text
    assert "REPLACE" in text
    assert "postgresql://REPLACE" in text


def test_preflight_is_read_only_contract():
    text = Path("scripts/preflight_revenue_activation.py").read_text()
    assert '"database_mutation": False' in text
    assert '"service_restart": False' in text
    assert '"traffic_publication": False' in text
    assert '"outbound_send": False' in text
    assert '"payment": False' in text
    assert '"execution_authority": "none"' in text
