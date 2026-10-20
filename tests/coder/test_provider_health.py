from datetime import datetime, timedelta, timezone

from empire_os.coder.provider_health import ProviderHealth


def test_failure_excludes_route_until_cooldown(tmp_path):
    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=300)
    health.record_failure("ollama", "small", "TimeoutError")
    assert ("ollama", "small") in health.excluded_routes()


def test_success_clears_route_cooldown(tmp_path):
    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=300)
    health.record_failure("ollama", "small", "TimeoutError")
    health.record_success("ollama", "small")
    assert health.excluded_routes() == ()


def test_expired_cooldown_is_not_excluded(tmp_path):
    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=30)
    health.record_failure("ollama", "small", "TimeoutError")
    future = datetime.now(timezone.utc) + timedelta(minutes=2)
    assert health.excluded_routes(now=future) == ()


def test_timeout_backoff_and_recovery(tmp_path, monkeypatch):
    from empire_os.coder import provider_health as module

    health = ProviderHealth(tmp_path / "health.json", cooldown_seconds=300)
    start = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    for index, expected in enumerate((300, 600, 1200, 2400, 3600, 3600)):
        now = start + timedelta(seconds=10 * index)
        monkeypatch.setattr(module, "_now", lambda now=now: now)
        health.record_failure("ollama", "writer", "ollama_request_failed:TimeoutError")
        row = health.snapshot()["routes"]["ollama:writer"]
        assert row["cooldown_seconds_applied"] == expected
    health.record_success("ollama", "writer")
    health.record_failure("ollama", "writer", "TimeoutError")
    assert health.snapshot()["routes"]["ollama:writer"]["cooldown_seconds_applied"] == 300



def test_malformed_routes_json_never_breaks_provider_recovery(tmp_path):
    import json

    for bad in (None, [], [{"provider": "ollama"}], 7, True, "invalid"):
        source = tmp_path / "health.json"
        source.write_text(json.dumps({
            "schema_version": "empire.coder_model_health.v1",
            "routes": bad,
            "existing_metadata": "preserved",
        }), encoding="utf-8")
        health = ProviderHealth(source, cooldown_seconds=30)
        assert health.excluded_routes() == ()
        assert health.snapshot()["routes"] == {}
        assert health.snapshot()["existing_metadata"] == "preserved"
        health.record_failure("ollama", "writer", "TimeoutError")
        assert ("ollama", "writer") in health.excluded_routes()
        health.record_success("ollama", "writer")
        assert health.excluded_routes() == ()


def test_missing_routes_json_uses_empty_mapping_without_mutating_source(tmp_path):
    import json

    source = tmp_path / "health.json"
    original = json.dumps({"schema_version": "empire.coder_model_health.v1"})
    source.write_text(original, encoding="utf-8")
    health = ProviderHealth(source)
    assert health.snapshot()["routes"] == {}
    assert source.read_text(encoding="utf-8") == original



def test_invalid_consecutive_failure_counter_cannot_break_model_health(tmp_path):
    import json

    now = datetime.now(timezone.utc)
    for malformed in ("not-a-number", [], {}, float("inf"), -3):
        path = tmp_path / "health.json"
        path.write_text(json.dumps({
            "schema_version": "empire.coder_model_health.v1",
            "routes": {
                "ollama:writer": {
                    "provider": "ollama",
                    "model": "writer",
                    "consecutive_failures": malformed,
                    "last_failure_at": now.isoformat(),
                },
            },
        }), encoding="utf-8")
        health = ProviderHealth(path, cooldown_seconds=30)
        health.record_failure("ollama", "writer", "TimeoutError")
        assert health.snapshot()["routes"]["ollama:writer"]["consecutive_failures"] == 1
        assert ("ollama", "writer") in health.excluded_routes()
        health.record_success("ollama", "writer")
        assert health.excluded_routes() == ()
