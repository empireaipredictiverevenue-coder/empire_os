from types import SimpleNamespace

import empire_os.data_cloud_runtime_canary as runtime_canary


class Gateway:
    backend = SimpleNamespace(value="empiredb")

    def __init__(self):
        self.counts = [32899, 32899]

    def count(self, table):
        assert table == "prospects"
        return self.counts.pop(0)


def test_runtime_canary_uses_pgbouncer_and_preserves_canonical(monkeypatch):
    monkeypatch.setattr(
        runtime_canary,
        "pool_dsn",
        lambda dsn: "postgresql://app@127.0.0.1:6432/empiredb",
    )
    seen = {}

    def gateway_factory(env):
        seen["gateway_env"] = dict(env)
        return Gateway()

    def functional_canary(dsn):
        seen["canary_dsn"] = dsn
        return {
            "rollback_only": True,
            "canonical_backend_unchanged": True,
            "verified": True,
        }

    report = runtime_canary.run_runtime_canary(
        {
            "EMPIREDB_DSN": "postgresql://app@127.0.0.1:5432/empiredb",
        },
        gateway_factory=gateway_factory,
        functional_canary=functional_canary,
    )

    assert seen["gateway_env"]["EMPIRE_DATA_BACKEND"] == "empiredb"
    assert ":6432/" in seen["gateway_env"]["EMPIREDB_DSN"]
    assert ":6432/" in seen["canary_dsn"]
    assert report["canonical_backend_before"] == "supabase_legacy"
    assert report["canonical_backend_after"] == "supabase_legacy"
    assert report["canonical_backend_unchanged"] is True
    assert report["representative_read_verified"] is True
    assert report["rollback_only_write_path_verified"] is True
    assert report["commercial_canary_verified"] is True
    assert report["verified"] is True
    assert report["production_cutover_authority"] is False


def test_runtime_canary_fails_if_rollback_canary_not_verified(monkeypatch):
    monkeypatch.setattr(runtime_canary, "pool_dsn", lambda dsn: "pool-dsn")

    report = runtime_canary.run_runtime_canary(
        {"EMPIREDB_DSN": "direct-dsn"},
        gateway_factory=lambda env: Gateway(),
        functional_canary=lambda dsn: {
            "rollback_only": True,
            "verified": False,
        },
    )

    assert report["verified"] is False
    assert report["commercial_canary_verified"] is False


def test_runtime_canary_requires_empiredb_dsn():
    try:
        runtime_canary.run_runtime_canary({})
    except RuntimeError as exc:
        assert "EMPIREDB_DSN" in str(exc)
    else:
        raise AssertionError("expected missing DSN failure")
