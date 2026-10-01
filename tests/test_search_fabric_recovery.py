import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

search_module = importlib.import_module("empire_os.search_fabric.search")


@pytest.fixture(autouse=True)
def isolated_health(monkeypatch):
    monkeypatch.setattr(search_module, "_engine_health", {})


def test_auto_search_uses_existing_recovery_engine(monkeypatch):
    monkeypatch.setattr(search_module, "BRAVE_API_KEY", "")
    monkeypatch.setattr(search_module, "_get_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_set_cache", lambda *args: None)

    calls = []

    def fake_fetch(engine, query, num):
        calls.append(engine["name"])
        if engine["name"] != "bing_rss":
            return None
        return """
        <rss><channel>
          <item>
            <title>Best Denver Roofing Companies</title>
            <link>https://comparison.example/denver-roofing</link>
            <description>
              Compare Denver roofing companies and contractors.
            </description>
          </item>
        </channel></rss>
        """

    monkeypatch.setattr(search_module, "_fetch", fake_fetch)

    result = search_module.search("Denver roofing", num=5)

    assert result["organic"]
    assert result["searchParameters"]["engine"] == "bing_rss"
    assert result["searchParameters"]["quality_gate"] == "lexical_v2"
    assert "bing_html" in calls
    assert "duckduckgo_html" in calls
    assert "bing_rss" in calls


def test_explicit_engine_does_not_expand_to_recovery_chain(monkeypatch):
    monkeypatch.setattr(search_module, "_get_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_set_cache", lambda *args: None)

    calls = []

    def fake_fetch(engine, query, num):
        calls.append(engine["name"])
        return None

    monkeypatch.setattr(search_module, "_fetch", fake_fetch)

    result = search_module.search(
        "Denver roofing",
        num=5,
        engine="bing_html",
    )

    assert result["organic"] == []
    assert calls == ["bing_html"]



def test_rejection_diagnostic_writes_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(search_module, "_get_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_set_cache", lambda *args: None)
    monkeypatch.setattr(search_module, "_fetch", lambda *args: "raw")
    monkeypatch.setitem(
        search_module.PARSERS,
        "bing_html",
        lambda raw: [{
            "title": "Completely unrelated result",
            "link": "https://example.com/unrelated",
            "snippet": "Nothing about the requested market.",
            "position": 1,
        }],
    )

    result = search_module.search(
        "Denver roofing",
        num=5,
        engine="bing_html",
    )

    captured = capsys.readouterr()

    assert result["organic"] == []
    assert "bing_html rejected" in captured.err



def test_domain_query_does_not_match_on_com_token_only():
    result = {
        "title": "Brandon Sanderson White Sand",
        "link": "https://brandonsanderson.com/white-sand",
        "snippet": "Fantasy graphic novel.",
    }

    score = search_module._result_relevance(
        result,
        '"goldenspikeroofing.com"',
    )

    assert score == 0.0



def test_public_fetch_fails_fast_on_timeout(monkeypatch):
    monkeypatch.setattr(search_module, "_polite", lambda *args: None)
    monkeypatch.setattr(search_module, "_next_proxy", lambda: None)
    monkeypatch.setattr(search_module, "SEARCH_PUBLIC_TIMEOUT", 4.0)
    monkeypatch.setattr(search_module, "SEARCH_PUBLIC_ATTEMPTS", 1)

    calls = []

    def timeout_get(*args, **kwargs):
        calls.append(kwargs.get("timeout"))
        raise search_module.requests.exceptions.Timeout()

    monkeypatch.setattr(search_module.requests, "get", timeout_get)

    engine = next(
        row for row in search_module.ENGINES
        if row["name"] == "bing_html"
    )
    result = search_module._fetch(
        engine,
        "Denver roofing",
        5,
    )

    assert result is None
    assert calls == [4.0]



def test_engine_circuit_breaker_opens_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(search_module, "SEARCH_ENGINE_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(search_module, "SEARCH_ENGINE_COOLDOWN_SECONDS", 300.0)
    monkeypatch.setattr(search_module, "_polite", lambda *args: None)
    monkeypatch.setattr(search_module, "_next_proxy", lambda: None)
    monkeypatch.setattr(search_module, "SEARCH_PUBLIC_ATTEMPTS", 1)

    search_module._engine_health.clear()

    class Response:
        status_code = 401

    calls = []

    def blocked_get(*args, **kwargs):
        calls.append(1)
        return Response()

    monkeypatch.setattr(search_module.requests, "get", blocked_get)

    engine = next(
        row for row in search_module.ENGINES
        if row["name"] == "mojeek"
    )

    assert search_module._fetch(engine, "roofing leads", 5) is None
    assert search_module._fetch(engine, "roofing calls", 5) is None
    assert search_module._fetch(engine, "roofing buyers", 5) is None

    assert len(calls) == 2
    assert search_module._engine_available("mojeek") is False


def test_search_domains_retries_without_exact_match_quotes(monkeypatch):
    calls = []

    def fake_search(query, num=20, engine=None):
        calls.append(query)
        if '"' in query:
            return {"organic": []}
        return {
            "organic": [
                {
                    "title": "Austin Roofing Leads",
                    "link": "https://buyer.example/roofing",
                    "snippet": "Roofing leads in Austin Texas.",
                }
            ]
        }

    monkeypatch.setattr(search_module, "search", fake_search)

    domains = search_module.search_domains(
        '"buy roofing leads" Austin TX',
        num=5,
    )

    assert domains == ["buyer.example"]
    assert calls == [
        '"buy roofing leads" Austin TX',
        "buy roofing leads Austin TX",
    ]


def test_broaden_query_only_removes_exact_match_quotes():
    assert search_module._broaden_query(
        '"buy roofing leads" Austin TX'
    ) == "buy roofing leads Austin TX"


def test_high_level_search_registry_has_redundant_keyless_recovery():
    from empire_os.search_fabric.engines import active_engines

    names = {engine.name for engine in active_engines()}

    assert "duckduckgo_html" in names
    assert "bing_rss" in names
    assert "duckduckgo_lite" in names
    assert "mojeek" in names


@pytest.fixture
def public_transport(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(search_module.time, 'time', lambda: clock[0])
    monkeypatch.setattr(search_module, '_polite', lambda *args: None)
    monkeypatch.setattr(search_module, '_next_proxy', lambda: None)
    monkeypatch.setattr(search_module, 'SEARCH_PUBLIC_ATTEMPTS', 2)
    monkeypatch.setattr(search_module, 'SEARCH_ENGINE_FAILURE_THRESHOLD', 2)
    monkeypatch.setattr(search_module, 'SEARCH_ENGINE_COOLDOWN_SECONDS', 300.0)
    monkeypatch.setattr(search_module.time, 'sleep', Mock(side_effect=AssertionError('no retry sleeps')))
    return clock


@pytest.mark.parametrize('status', [202, 403, 429, 503])
@pytest.mark.parametrize('name', ['duckduckgo_html', 'duckduckgo_lite', 'mojeek'])
def test_public_blocks_allow_later_probe_without_retry_storm(monkeypatch, public_transport, status, name):
    engine = next(row for row in search_module.ENGINES if row['name'] == name)
    request = Mock(return_value=SimpleNamespace(status_code=status, headers={}))
    monkeypatch.setattr(search_module.requests, 'get', request)
    monkeypatch.setattr(search_module.requests, 'post', request)
    decode = Mock(side_effect=AssertionError('blocked response is not evidence'))
    monkeypatch.setattr(search_module, '_decode_http_response', decode)
    for failure in range(1, 10):
        assert search_module._fetch(engine, f'roofing market {failure}', 5) is None
        assert request.call_count == failure
        state = search_module._engine_health[name]
        assert state['failures'] == failure
        delay = min(300.0, search_module.RATE_LIMIT[name] * 2 ** (failure - 1))
        assert state['disabled_until'] == public_transport[0] + delay
        # Even a different query cannot bypass the cooldown.
        assert search_module._fetch(engine, 'solar London', 5) is None
        assert request.call_count == failure
        public_transport[0] += delay
    decode.assert_not_called()
    request.return_value = SimpleNamespace(status_code=200)
    monkeypatch.setattr(search_module, '_decode_http_response', lambda response: 'fresh')
    assert search_module._fetch(engine, 'roofing Denver', 5) == 'fresh'
    assert search_module._engine_health[name]['failures'] == 0
    assert search_module._engine_available(name)


@pytest.mark.parametrize('retry_after, delay', [
    ('120', 120), ('Thu, 01 Jan 1970 00:18:40 GMT', 120),
    ('invalid', 1.5), ('-1', 1.5),
])
def test_retry_after_is_respected_without_sleep(monkeypatch, public_transport, retry_after, delay):
    request = Mock(return_value=SimpleNamespace(status_code=429, headers={'Retry-After': retry_after}))
    monkeypatch.setattr(search_module.requests, 'post', request)
    engine = next(row for row in search_module.ENGINES if row['name'] == 'duckduckgo_html')
    assert search_module._fetch(engine, 'roofing Denver', 5) is None
    assert search_module._engine_health[engine['name']]['disabled_until'] == 1000 + delay
    public_transport[0] += delay - .01
    assert search_module._fetch(engine, 'solar London', 5) is None
    assert request.call_count == 1
    public_transport[0] += .01
    assert search_module._engine_available(engine['name'])


def test_public_timeout_can_recover_on_later_query(monkeypatch, public_transport):
    request = Mock(side_effect=search_module.requests.exceptions.Timeout)
    monkeypatch.setattr(search_module.requests, 'get', request)
    engine = next(row for row in search_module.ENGINES if row['name'] == 'bing_html')
    assert search_module._fetch(engine, 'roofing Denver', 5) is None
    assert request.call_count == 1
    assert request.call_args.kwargs['timeout'] == search_module.SEARCH_PUBLIC_TIMEOUT
    public_transport[0] += search_module.RATE_LIMIT['bing_html']
    assert search_module._engine_available('bing_html')


def test_persistent_and_keyed_failures_keep_normal_circuit(public_transport):
    for engine in ['brave', 'mojeek']:
        search_module._record_engine_failure(engine, 'http_401')
        assert search_module._engine_available(engine)
        search_module._record_engine_failure(engine, 'http_401')
        assert not search_module._engine_available(engine)
    public_transport[0] += 299
    assert not search_module._engine_available('brave')
    public_transport[0] += 1
    assert search_module._engine_available('brave')


@pytest.mark.parametrize('status', [202, 403, 429, 503])
def test_agent_web_recovers_fresh_observations_across_markets(monkeypatch, public_transport, status):
    from empire_os import agent_web_snapshot as snapshot

    monkeypatch.setattr(search_module, 'BRAVE_API_KEY', '')
    monkeypatch.setattr(search_module, '_get_cache', Mock(side_effect=AssertionError('fresh only')))
    monkeypatch.setattr(search_module, '_set_cache', lambda *args: None)
    # Canonical locale lookup remains active in the real Bing transport.
    monkeypatch.setattr(search_module.requests, 'get', Mock(return_value=SimpleNamespace(status_code=200)))
    queries = []

    def post(url, **kwargs):
        query = kwargs['data']['q']
        queries.append(query)
        return SimpleNamespace(status_code=status if len(queries) == 1 else 200, query=query, headers={})

    monkeypatch.setattr(search_module.requests, 'post', post)
    monkeypatch.setattr(search_module, '_decode_http_response', lambda response: getattr(response, 'query', 'unrelated'))
    for name in search_module.PARSERS:
        monkeypatch.setitem(search_module.PARSERS, name, lambda raw: [{
            'title': raw, 'link': 'https://example.org/observation', 'snippet': '', 'position': 1}])
    # Limit fixture providers to isolate the actual HTML transport and breaker.
    monkeypatch.setattr(search_module, 'ENGINES', [e for e in search_module.ENGINES if e['name'] in ('bing_html', 'duckduckgo_html')])
    calls = []

    def search(query, **kwargs):
        calls.append(kwargs)
        result = search_module.search(query, **kwargs)
        public_transport[0] += 2  # Virtual elapsed work, no actual sleep.
        return result

    markets = [{'niche': 'roofing', 'metro': city, 'prospect_count': 1}
               for city in ['Denver', 'London', 'Austin', 'Houston', 'Phoenix']]
    result = snapshot.build_snapshot(markets, search_fn=search)
    assert result['counts']['search_attempts'] == 4
    assert result['counts']['search_queries'] == 3
    assert all(call == {'num': 5, 'engine': None, 'use_cache': False} for call in calls)
    assert [row['query'] for row in result['search_observations']] == [
        'roofing London', 'roofing Austin', 'roofing Houston']
    assert all(row['engine'] == 'duckduckgo_html' for row in result['search_observations'])
    assert result['execution_authority'] == 'none'
    search_module._get_cache.assert_not_called()
    assert search_module.requests.get.call_args_list[0].kwargs['params']['cc'] == 'US'
    assert search_module.requests.get.call_args_list[1].kwargs['params']['cc'] == 'GB'


def test_batch_isolates_failed_query_and_uses_fresh_results(monkeypatch, capsys):
    calls = []
    def domains(query, num, *, use_cache):
        calls.append(use_cache)
        if query == 'bad':
            raise RuntimeError('provider unavailable')
        return ['research.example']
    monkeypatch.setattr(search_module, 'search_domains', domains)
    assert search_module.search_domains_parallel(['bad', 'good']) == {
        'bad': [], 'good': ['research.example']}
    assert calls == [False, False]
    assert 'query_failure:RuntimeError' in capsys.readouterr().err
    assert search_module.search_domains_parallel([]) == {}


def test_no_quote_retry_when_all_providers_unavailable(monkeypatch):
    calls = []
    monkeypatch.setattr(search_module, '_engine_available', lambda name: False)
    monkeypatch.setattr(search_module, 'search', lambda q, **kw: calls.append(q) or {'organic': []})
    assert search_module.search_domains('"roofing Denver"', use_cache=False) == []
    assert calls == ['"roofing Denver"']


def test_concurrent_provider_block_is_rechecked_under_lock(monkeypatch, public_transport):
    from concurrent.futures import ThreadPoolExecutor
    request = Mock(return_value=SimpleNamespace(status_code=429, headers={'Retry-After': '120'}))
    monkeypatch.setattr(search_module.requests, 'post', request)
    engine = next(e for e in search_module.ENGINES if e['name'] == 'duckduckgo_html')
    with ThreadPoolExecutor(max_workers=5) as executor:
        assert list(executor.map(lambda i: search_module._fetch(engine, str(i), 5), range(10))) == [None] * 10
    assert request.call_count == 1
