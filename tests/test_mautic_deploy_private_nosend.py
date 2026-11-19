"""Prevent accidental public exposure or marketing execution on stage-one Mautic.

The manifest uses only official prebuilt Mautic and MariaDB images, stays
separate from canonical EmpireDB, and has no cron/queue worker until source,
consent and founder approvals are independently verified. All checks are
static/offline: never start Docker or touch tenant/customer data.
"""
from __future__ import annotations

from pathlib import Path
import yaml

MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "deploy/mautic/compose.mautic7.private-nosend.yaml"
)


def test_must_be_private_no_send_and_no_customer_import():
    text = MANIFEST.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    services = data["services"]
    assert set(services) == {"db", "mautic_web"}
    assert services["db"]["image"] == ("mariadb:11.4.13@"
        "sha256:5e73baf8179b29f115101bb102763a47a017361f3e9792daccba6646c3ab1532")
    assert services["mautic_web"]["image"] == (
        "mautic/mautic:7.2.2-20261026-apache@"
        "sha256:83461b9ec7c109413281490180e1f96c379aa935bd92f80c68294f98487a9015"
    )
    assert services["mautic_web"]["ports"] == ["127.0.0.1:18784:80"]
    assert not services["db"].get("ports")
    assert all(item["networks"] == ["private_review"] for item in services.values())
    assert data["networks"]["private_review"]["internal"] is True
    assert services["mautic_web"]["environment"]["DOCKER_MAUTIC_ROLE"] == "mautic_web"
    assert services["mautic_web"]["environment"]["DOCKER_MAUTIC_LOAD_TEST_DATA"] == "false"
    assert not any(
        "smtp" in key.casefold() or "send" in key.casefold()
        for key in services["mautic_web"]["environment"]
    )
    assert "mautic_cron:" not in text
    assert "mautic_worker:" not in text
    assert "latest" not in text
    assert services["db"]["environment"]["MARIADB_DATABASE"] == "mautic_review"
    assert services["mautic_web"]["environment"]["MAUTIC_DB_DATABASE"] == "mautic_review"
    assert not any("empiredb" in str(v).lower() for v in services.values())
    assert set(data["volumes"]) == {
        "mautic_db", "mautic_config", "mautic_logs",
        "mautic_media_files", "mautic_media_images",
    }


def test_requires_external_passwords_and_no_credentials_in_git():
    services = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["services"]
    db = services["db"]["environment"]
    app = services["mautic_web"]["environment"]
    assert db["MARIADB_ROOT_PASSWORD"] == (
        "${EMPIRE_MAUTIC_DB_ROOT_PASSWORD:?external-secret-required}"
    )
    assert db["MARIADB_PASSWORD"] == (
        "${EMPIRE_MAUTIC_DB_PASSWORD:?external-secret-required}"
    )
    assert db["MARIADB_PASSWORD"] == app["MAUTIC_DB_PASSWORD"]
