import importlib
import sys


def test_search_fabric_import_does_not_create_runtime_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "search" / "cache"
    monkeypatch.setenv("EMPIRE_SEARCH_CACHE", str(cache_dir))

    sys.modules.pop("empire_os.search_fabric.search", None)
    module = importlib.import_module("empire_os.search_fabric.search")

    assert module.CACHE_DIR == cache_dir
    assert cache_dir.exists() is False
