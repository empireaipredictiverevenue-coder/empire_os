from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "deploy/systemd/empire-omniroute.service"
BOOTSTRAP = ROOT / "scripts/bootstrap_omniroute.sh"
RUNNER = ROOT / "scripts/run_omniroute.sh"
IMPORTER = ROOT / "scripts/import_omniroute_provider_keys.py"
HERMES_SERVICE = ROOT / "deploy/systemd/empire-hermes-control.service"


def test_omniroute_service_is_loopback_only_and_unprivileged():
    text = SERVICE.read_text()

    assert "User=ubuntu" in text
    assert "Group=ubuntu" in text
    assert "OMNIROUTE_SERVER_HOST=127.0.0.1" in text
    assert "HOSTNAME=127.0.0.1" in text
    assert "PORT=20128" in text
    assert "NoNewPrivileges=true" in text
    assert "ProtectSystem=strict" in text
    assert "ProtectHome=read-only" in text
    assert "ReadWritePaths=/home/ubuntu/.omniroute" in text
    assert "Restart=on-failure" in text

    assert "0.0.0.0" not in text
    assert "Cloudflare" not in text
    assert "REQUIRE_API_KEY=false" in text


def test_bootstrap_generates_secrets_and_never_commits_them():
    text = BOOTSTRAP.read_text()

    assert "openssl rand -base64 48" in text
    assert "openssl rand -hex 32" in text
    assert "/home/ubuntu" not in text
    assert "omniroute@latest" in text
    assert "/etc/empire_os/omniroute-hermes.env" in text
    assert "OPENAI_BASE_URL=http://127.0.0.1:20128/v1" in text
    assert "EMPIRE_HERMES_PROVIDER=custom" in text
    assert "EMPIRE_HERMES_MODEL=auto" in text


def test_runner_uses_documented_noninteractive_entrypoint():
    text = RUNNER.read_text()

    assert "omniroute --no-open" in text
    assert "NVM_DIR" in text
    assert "sudo" not in text


def test_provider_importer_is_allowlisted_and_does_not_print_secrets():
    text = IMPORTER.read_text()

    assert "KEY_TO_PROVIDER" in text
    assert "GEMINI_API_KEY" in text
    assert "NVIDIA_API_KEY" in text
    assert "GROQ_API_KEY" in text
    assert "OPENROUTER_API_KEY" in text
    assert '"secrets_printed": False' in text
    assert "print(secret" not in text


def test_hermes_service_depends_on_omniroute_and_loads_local_env():
    text = HERMES_SERVICE.read_text()

    assert "After=network-online.target empire-omniroute.service" in text
    assert "Wants=network-online.target empire-omniroute.service" in text
    assert "EnvironmentFile=-/etc/empire_os/omniroute-hermes.env" in text
