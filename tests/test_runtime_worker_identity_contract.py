from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(name: str) -> str:
    return (ROOT / "deploy/systemd" / name).read_text(
        encoding="utf-8"
    )


def test_runtime_refresh_services_run_as_ubuntu():
    for name in (
        "empire-buyer-acquisition-team.service",
        "empire-buyer-acquisition-scout.service",
        "empire-tag-intelligence.service",
    ):
        text = _text(name)
        assert "User=ubuntu" in text
        assert "Group=ubuntu" in text
        assert "ReadWritePaths=/srv/empire_os/runtime" in text


def test_secret_using_workers_get_env_from_systemd():
    scout = _text("empire-buyer-acquisition-scout.service")
    tag = _text("empire-tag-intelligence.service")

    assert "EnvironmentFile=-/etc/empire_os.env" in scout
    assert "EnvironmentFile=-/etc/empire_os.env" in tag
