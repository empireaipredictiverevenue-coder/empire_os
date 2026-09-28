from pathlib import Path


SERVICES = (
    "empire-closer-reply-worker",
    "empire-gtm-pipeline",
    "empire-outbound-followup",
    "empire-outbound-governor",
)


def test_outbound_services_load_canonical_empiredb_runtime():
    for service in SERVICES:
        text = (
            Path("deploy/systemd")
            / f"{service}.service"
        ).read_text()

        outbound = (
            "EnvironmentFile="
            "/srv/empire_os/runtime/secrets/outbound.env"
        )
        platform = "EnvironmentFile=/etc/empire_os.env"
        database = "EnvironmentFile=/etc/empiredb.env"

        assert text.count(outbound) == 1
        assert text.count(platform) == 1
        assert text.count(database) == 1

        # Canonical runtime configuration deliberately follows the
        # outbound secret file so stale DB selection cannot override it.
        assert text.index(outbound) < text.index(platform)
        assert text.index(platform) < text.index(database)
