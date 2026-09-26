from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PI_BOOTSTRAP = ROOT / "scripts/bootstrap_pi_agent.sh"
REACH_BOOTSTRAP = ROOT / "scripts/bootstrap_agent_reach.sh"
SPACE_BOOTSTRAP = ROOT / "scripts/bootstrap_space_agent.sh"
SPACE_SERVICE = ROOT / "deploy/systemd/empire-space-agent.service"


def test_pi_bootstrap_is_pinned_and_local_model_only():
    text = PI_BOOTSTRAP.read_text(encoding="utf-8")
    assert "@earendil-works/pi-coding-agent@0.87.1" in text
    assert "127.0.0.1:11435" in text
    assert "PI_TELEMETRY=0" in text
    assert "/opt/empire/pi-agent/bin/node" in text or 'PREFIX/bin/node' in text
    assert '"supportsDeveloperRole": false' in text
    assert '"maxTokensField": "max_tokens"' in text


def test_agent_reach_bootstrap_is_pinned_and_does_not_system_install_channels():
    text = REACH_BOOTSTRAP.read_text(encoding="utf-8")
    assert "a19a171fa980a0785849596492e0af4db800c82f" in text
    assert "--env=server --safe" in text
    assert "--system" not in text
    assert "BrowserCookieReusePerformed=false" in text


def test_space_agent_is_pinned_loopback_and_non_guest():
    bootstrap = SPACE_BOOTSTRAP.read_text(encoding="utf-8")
    service = SPACE_SERVICE.read_text(encoding="utf-8")
    assert "10f4ffdaf50a8136cf8450d17c11286178fd58e6" in bootstrap
    assert "HOST=127.0.0.1" in service
    assert "ALLOW_GUEST_USERS=false" in service
    assert "CLOUD_SHARE_ALLOWED=false" in service
    assert "127.0.0.1:11435/v1/chat/completions" in bootstrap
    assert "IPAddressDeny=any" in service
    assert "IPAddressAllow=localhost" in service
    assert "InaccessiblePaths=/etc/empire_os.env" in service


def test_pi_bootstrap_uses_writable_runtime_check_config():
    text = PI_BOOTSTRAP.read_text(encoding="utf-8")
    assert 'CHECK_CONFIG="$STATE/check-config"' in text
    assert 'PI_CODING_AGENT_DIR="$CHECK_CONFIG"' in text


def test_space_agent_relocates_mutable_server_state():
    bootstrap = SPACE_BOOTSTRAP.read_text(encoding="utf-8")
    service = SPACE_SERVICE.read_text(encoding="utf-8")
    assert 'AUTH_DATA="$STATE/server-data"' in bootstrap
    assert 'SERVER_TMP="$STATE/server-tmp"' in bootstrap
    assert 'ln -s "$SERVER_TMP" "$SOURCE/server/tmp"' in bootstrap
    assert (
        "Environment=SPACE_AUTH_DATA_DIR="
        "/var/lib/empire/space-agent/server-data"
    ) in service
