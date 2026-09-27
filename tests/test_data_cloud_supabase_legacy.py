import io
import urllib.error

from empire_os.data_backends.supabase_legacy import (
    SupabaseLegacyConfig,
    SupabaseLegacyProvider,
)
from empire_os.data_query import ConflictAction, DataFilter, OrderSpec
from empire_os.data_values import JsonValue
from empire_os.legacy_data_egress import (
    LegacyDataEgressGovernor,
    LegacyEgressConfig,
)


class FakeEgress:
    def __init__(self):
        self.reserved = 0
        self.successes = 0

    def reserve(self, *, allow_probe=False):
        self.reserved += 1

    def success(self, *, recovery_probe=False):
        self.successes += int(bool(recovery_probe))

    def observe_http_error(self, code, body):
        return False


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
        egress=FakeEgress(),
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
        egress=FakeEgress(),
    )

    assert provider.count("prospects") == 42
    assert seen["prefer"] == "count=exact"


def test_neutral_query_maps_to_postgrest_filters_and_order():
    seen = {}

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'[{"prospect_id":"p1"}]')

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
        egress=FakeEgress(),
    )

    rows = provider.query(
        "prospect_qualifications",
        "prospect_id,scored_at",
        filters=(
            DataFilter.eq("status", "scored"),
            DataFilter.in_("tier", ("hot", "warm")),
            DataFilter.is_null("entity_id"),
        ),
        order=(OrderSpec("scored_at", descending=True),),
        limit=25,
    )

    assert rows == [{"prospect_id": "p1"}]
    assert "status=eq.scored" in seen["url"]
    assert "tier=in.%28hot%2Cwarm%29" in seen["url"]
    assert "entity_id=is.null" in seen["url"]
    assert "order=scored_at.desc" in seen["url"]


def test_targeted_merge_upsert_uses_on_conflict_and_prefer():
    seen = {}

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["prefer"] = request.get_header("Prefer")
        return Response(b'[{"prospect_id":"p1"}]')

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
        egress=FakeEgress(),
    )

    rows = provider.upsert(
        "prospect_qualifications",
        {
            "prospect_id": "p1",
            "scoring_engine": "engine",
            "scoring_version": "v2",
        },
        conflict_columns=("prospect_id", "scoring_engine", "scoring_version"),
        action=ConflictAction.MERGE,
        return_repr=True,
    )

    assert rows[0]["prospect_id"] == "p1"
    assert "on_conflict=prospect_id%2Cscoring_engine%2Cscoring_version" in seen["url"]
    assert seen["prefer"] == "resolution=merge-duplicates,return=representation"


def test_untargeted_ignore_conflicts_has_no_on_conflict_target():
    seen = {}

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["prefer"] = request.get_header("Prefer")
        return Response(b'')

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
        egress=FakeEgress(),
    )

    assert provider.insert_ignore_conflicts(
        "commercial_events",
        {"idempotency_key": "k1"},
    ) == ()

    assert "on_conflict" not in seen["url"]
    assert seen["prefer"] == "resolution=ignore-duplicates,return=minimal"


def test_402_opens_shared_egress_circuit_and_blocks_repeat_calls(tmp_path):
    now = [1000.0]
    governor = LegacyDataEgressGovernor(
        LegacyEgressConfig(
            state_path=tmp_path / "state.json",
            lock_path=tmp_path / "state.lock",
            hourly_budget=100,
            component_hourly_budget=100,
            daily_budget=1000,
            probe_seconds=60,
        ),
        environ={"EMPIRE_COMPONENT": "test"},
        now=lambda: now[0],
    )
    calls = []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(
            request.full_url,
            402,
            "Payment Required",
            hdrs=None,
            fp=io.BytesIO(
                b'{"message":"restricted due to the following violations: exceed_egress_quota"}'
            ),
        )

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
        egress=governor,
    )

    try:
        provider.select("prospects", "id", limit=1)
    except RuntimeError as exc:
        assert "HTTP 402" in str(exc)
    else:
        raise AssertionError("402 must open the shared circuit")

    assert governor.is_contained() is True
    assert len(calls) == 1

    try:
        provider.select("prospects", "id", limit=1)
    except RuntimeError as exc:
        assert "Legacy data egress circuit open locally" in str(exc)
    else:
        raise AssertionError("open circuit must block repeat traffic")

    assert len(calls) == 1


def test_extended_query_operators_preserve_bus_semantics():
    seen = {}

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        return Response(b'[]')

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
        egress=FakeEgress(),
    )

    provider.query(
        "prospects",
        "id,status,metro,buy_signal_score",
        filters=(
            DataFilter.ne("status", "archived"),
            DataFilter.ilike("metro", "denver"),
            DataFilter.gte("buy_signal_score", 50),
            DataFilter.not_in("status", ("rejected", "cancelled")),
        ),
        order=(
            OrderSpec("buy_signal_score", descending=True, nulls_last=True),
            OrderSpec("created_at"),
        ),
        limit=5,
    )

    assert "status=not.eq.archived" in seen["url"]
    assert "metro=ilike.denver" in seen["url"]
    assert "buy_signal_score=gte.50" in seen["url"]
    assert "status=not.in.%28rejected%2Ccancelled%29" in seen["url"]
    assert "order=buy_signal_score.desc.nullslast%2Ccreated_at.asc" in seen["url"]


def test_legacy_write_unwraps_explicit_json_values():
    seen = {}

    def urlopen(request, timeout):
        seen["body"] = request.data.decode("utf-8")
        return Response(b'[{"id":"1"}]')

    provider = SupabaseLegacyProvider(
        SupabaseLegacyConfig("https://example.supabase.co", "key"),
        urlopen=urlopen,
        egress=FakeEgress(),
    )

    provider.insert(
        "prospect_qualifications",
        {
            "id": "1",
            "observed_dimensions": JsonValue(["market_fit"]),
        },
    )

    assert '"observed_dimensions": ["market_fit"]' in seen["body"]
    assert "JsonValue" not in seen["body"]
