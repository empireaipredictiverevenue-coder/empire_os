from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "deploy/systemd/empire-omniroute.service"
BOOTSTRAP = ROOT / "scripts/bootstrap_omniroute.sh"
EXPORTER = ROOT / "scripts/export_omniroute_provider_env.py"
HERMES_SERVICE = ROOT / "deploy/systemd/empire-hermes-control.service"


def test_omniroute_service_is_docker_pinned_and_loopback_only():
    text = SERVICE.read_text()

    assert "Requires=docker.service" in text
    assert "diegosouzapw/omniroute:3.8.50" in text
    assert "-p 127.0.0.1:20128:20128" in text
    assert "-v empire-omniroute-data:/app/data" in text
    assert "--stop-timeout 40" in text
    assert "ProtectHome=read-only" in text
    assert "NoNewPrivileges=true" in text

    assert "diegosouzapw/omniroute:latest" not in text
    assert "npm install" not in text
    assert "0.0.0.0:20128:20128" not in text


def test_bootstrap_uses_docker_not_broken_npm_package():
    text = BOOTSTRAP.read_text()

    assert "docker.io" in text
    assert "systemctl enable --now docker" in text
    assert "empire-omniroute.service" in text
    assert "export_omniroute_provider_env.py" in text
    assert "OPENAI_BASE_URL=http://127.0.0.1:20128/v1" in text
    assert "EMPIRE_HERMES_PROVIDER=custom" in text
    assert "EMPIRE_HERMES_MODEL=auto" in text
    assert "enable --now empire-hermes-control.timer" in text
    assert "VERIFY LISTEN IS LOOPBACK-ONLY" in text
    assert "npm install -g omniroute" not in text


def test_bootstrap_normalizes_old_native_env_for_container():
    text = BOOTSTRAP.read_text()

    assert "set_env DATA_DIR /app/data" in text
    assert "set_env HOSTNAME 0.0.0.0" in text
    assert "set_env OMNIROUTE_SERVER_HOST 0.0.0.0" in text
    assert "set_env STORAGE_ENCRYPTION_KEY_VERSION v1" in text
    assert "OMNIROUTE_WS_BRIDGE_SECRET" in text


def test_exporter_is_allowlisted_and_never_prints_secrets():
    text = EXPORTER.read_text()

    assert "ALLOWED_KEYS" in text
    assert "GEMINI_API_KEY" in text
    assert "NVIDIA_API_KEY" in text
    assert "GROQ_API_KEY" in text
    assert "OPENROUTER_API_KEY" in text
    assert '"secrets_printed": False' in text
    assert "print(value" not in text
    assert "print(secret" not in text


def test_hermes_service_depends_on_omniroute_and_loads_local_env():
    text = HERMES_SERVICE.read_text()

    assert "After=network-online.target empire-omniroute.service" in text
    assert "Wants=network-online.target" in text
    assert "Requires=empire-omniroute.service" in text
    assert "EnvironmentFile=-/etc/empire_os/omniroute-hermes.env" in text
