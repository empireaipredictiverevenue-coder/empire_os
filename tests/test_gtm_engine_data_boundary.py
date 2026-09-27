import inspect

import empire_os.gtm_engine as gtm


class FakeRepository:
    def fetch_all(self, table, columns, *, batch_size=1000):
        return [{"id": "1"}]

    def count(self, table):
        return {"business_entities": 3, "prospect_entity_links": 4, "business_entity_conflicts": 5}[table]

    def snapshot(self):
        return {
            "backend": "supabase_legacy",
            "configured": True,
            "repository_authority": "read_only",
        }


def test_gtm_engine_contains_no_direct_vendor_transport():
    source = inspect.getsource(gtm)
    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "/rest/v1/" not in source
    assert "urllib.request" not in source
    assert "supabase_select" not in source


def test_gtm_identity_counts_use_repository(monkeypatch):
    repo = FakeRepository()
    monkeypatch.setattr(gtm, "_data_repository", lambda: repo)

    assert gtm.fetch_identity_counts() == {
        "business_entities": 3,
        "prospect_entity_links": 4,
        "business_entity_conflicts": 5,
    }


def test_gtm_fetch_all_delegates_to_repository(monkeypatch):
    repo = FakeRepository()
    monkeypatch.setattr(gtm, "_data_repository", lambda: repo)

    assert gtm.fetch_all("prospects", "id") == [{"id": "1"}]


def test_runtime_env_mapping_is_passed_to_gateway(monkeypatch):
    seen = {}
    fake_gateway = object()
    fake_repo = object()

    monkeypatch.setattr(gtm, "load_runtime_env", lambda path: {"X": "1"})
    def gateway_factory(env):
        seen["env"] = env
        return fake_gateway

    def repository_factory(gateway):
        seen["gateway"] = gateway
        return fake_repo

    monkeypatch.setattr(gtm, "gateway_from_environment", gateway_factory)
    monkeypatch.setattr(gtm, "GTMDataRepository", repository_factory)

    result = gtm._data_repository()

    assert seen["env"] == {"X": "1"}
    assert seen["gateway"] is fake_gateway
    assert result is fake_repo
