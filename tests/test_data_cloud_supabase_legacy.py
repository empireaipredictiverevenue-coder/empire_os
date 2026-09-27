from empire_os.data_backends.supabase_legacy import (
    SupabaseLegacyConfig,
    SupabaseLegacyProvider,
)


class Response:
    def __init__(self, payload=b"[]", headers=None):
        self.payload = payload
        self.headers = headers or {}
        self.closed = False

    def read(self):
        return self.payload

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def test_config_snapshot_never_contains_service_key_or_url():
    config = SupabaseLegacyConfig(
        url="https://secret-project.supabase.co",
        service_key="secret-key",
    )

    snapshot = config.safe_snapshot()

    assert snapshot["configured"] is True
    assert "secret-key" not in str(snapshot)
    assert "secret-project" not in str(snapshot)


def test_select_preserves_legacy_postgrest_semantics():
    seen = {}
    def urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.headers)
        seen["timeout"] = timeout
        return Response(b'[{"id":"1"}]')

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
        aliases={"si_outbox": "outbox_messages"},
    )

    rows = provider.select(
        "si_outbox",
        "id,status",
        {"status": "new"},
        "id.desc",
        10,
        5,
    )

    assert rows == [{"id": "1"}]
    assert "/rest/v1/outbox_messages?" in seen["url"]
    assert "select=id%2Cstatus" in seen["url"]
    assert "status=eq.new" in seen["url"]
    assert "order=id.desc" in seen["url"]


def test_partial_legacy_config_is_rejected():
    try:
        SupabaseLegacyConfig(
            url="https://example.supabase.co",
            service_key="",
        ).validate()
    except ValueError as exc:
        assert "configured together" in str(exc)
    else:
        raise AssertionError("expected partial config rejection")


def test_exact_count_uses_content_range():
    seen = {}

    def urlopen(request, timeout):
        seen["prefer"] = request.get_header("Prefer")
        return Response(b'[]', {"Content-Range": "0-0/42"})

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
    )

    assert provider.count("prospects") == 42
    assert seen["prefer"] == "count=exact"
