import json
from copy import deepcopy
from unittest.mock import Mock

import pytest

from empire_os import agent_web_snapshot as snapshot
from scripts import build_agent_web_snapshot as wrapper

MARKETS = [{'niche': 'roofing', 'metro': 'Denver', 'prospect_count': 2}]


def fresh(**params):
    return {'searchParameters': {'cache': False, 'engine': 'mojeek', **params},
            'organic': [{'link': 'https://example.org/roofing', 'position': 1}]}


def test_auto_routing_and_observe_contract():
    search = Mock(return_value=fresh())
    result = snapshot.build_snapshot(MARKETS, search_fn=search)
    search.assert_called_once_with('roofing Denver', num=5, engine=None, use_cache=False)
    assert result['search_observations'][0]['engine'] == 'mojeek'
    assert result['execution_authority'] == 'none'
    assert result['outreach_enabled'] is False
    assert result['buyer_intent_inferred'] is False
    assert result['revenue_inferred'] is False
    assert result['seo_keyword_metrics_status'] == 'unknown'


@pytest.mark.parametrize('response', [
    fresh(cache=True), fresh(cache=None), fresh(cache=0), fresh(stale=True),
    {**fresh(), 'stale': True}, {**fresh(), 'error': 'secret-fixture'},
    {**fresh(), 'organic': []}, {**fresh(), 'organic': None},
    fresh(synthetic=True), {**fresh(), 'synthetic': True},
    {**fresh(), 'organic': [{'link': 'https://example.org', 'synthetic': True}]},
    {'organic': fresh()['organic']}, None,
])
def test_invalid_evidence_preserves_old_snapshot(tmp_path, monkeypatch, response):
    monkeypatch.setattr(snapshot, 'observe_markets', lambda writer: MARKETS)
    path = tmp_path / 'snapshot.json'
    path.write_text('old-evidence')
    with pytest.raises(snapshot.FreshPublicSearchUnavailable):
        snapshot.refresh_snapshot(path, object(), search_fn=Mock(return_value=response))
    assert path.read_text() == 'old-evidence'


@pytest.mark.parametrize('url', [
    'javascript:alert(1)', '/relative', 'https://', 'https://user:secret@example.org',
    'https://[broken', 'https://example.org:bad', 'https://bad host/', None,
])
def test_invalid_organic_urls_fail_closed(url):
    response = fresh()
    response['organic'] = [{'link': url}]
    with pytest.raises(snapshot.FreshPublicSearchUnavailable):
        snapshot.build_snapshot(MARKETS, search_fn=Mock(return_value=response))


def test_one_failed_market_allows_partial_replacement(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, 'observe_markets', lambda writer: MARKETS * 2)
    path = tmp_path / 'snapshot.json'
    path.write_text('old-evidence')
    result = snapshot.refresh_snapshot(
        path, object(), search_fn=Mock(side_effect=[fresh(), RuntimeError('secret')]))
    assert json.loads(path.read_text()) == result
    assert result['counts'] == {
        'markets': 2, 'search_queries': 1, 'search_attempts': 2, 'search_unavailable': 1}


def ordered_markets(count):
    # Deterministic test fixtures only; the producer receives canonical markets.
    return [{**MARKETS[0], 'metro': f'Market {index}'} for index in range(count)]


def test_failed_and_empty_markets_are_skipped_in_order_until_three_successes():
    markets = ordered_markets(100)
    original = deepcopy(markets)
    search = Mock(side_effect=[RuntimeError('unavailable'), fresh(),
                               {**fresh(), 'organic': []}, fresh(), fresh()])
    result = snapshot.build_snapshot(markets, search_fn=search)
    assert [row['query'] for row in result['search_observations']] == [
        'roofing Market 1', 'roofing Market 3', 'roofing Market 4']
    assert result['counts'] == {
        'markets': 100, 'search_queries': 3, 'search_attempts': 5, 'search_unavailable': 2}
    assert search.call_count == 5
    for index, call in enumerate(search.call_args_list):
        assert call.args == (f'roofing Market {index}',)
        assert call.kwargs == {'num': 5, 'engine': None, 'use_cache': False}
    assert result['markets'] == original
    assert markets == original


def test_all_successes_stop_after_three():
    search = Mock(return_value=fresh())
    result = snapshot.build_snapshot(ordered_markets(100), search_fn=search)
    assert search.call_count == 3
    assert result['counts']['search_queries'] == 3
    assert result['counts']['search_attempts'] == 3
    assert result['counts']['search_unavailable'] == 0


@pytest.mark.parametrize('successes', [0, 1, 2])
def test_attempt_budget_with_zero_or_partial_success(successes):
    assert snapshot.MAX_SEARCH_MARKET_ATTEMPTS == 10
    responses = [fresh()] * successes + [RuntimeError('unavailable')] * (10 - successes)
    search = Mock(side_effect=responses)
    if successes:
        result = snapshot.build_snapshot(ordered_markets(100), search_fn=search)
        assert result['counts'] == {
            'markets': 100, 'search_queries': successes, 'search_attempts': 10,
            'search_unavailable': 10 - successes}
    else:
        with pytest.raises(snapshot.FreshPublicSearchUnavailable):
            snapshot.build_snapshot(ordered_markets(100), search_fn=search)
    assert search.call_count == 10


def test_cached_stale_and_synthetic_evidence_never_count_as_success():
    search = Mock(side_effect=[fresh(cache=True), fresh(stale=True),
                               fresh(synthetic=True), {**fresh(), 'synthetic': True},
                               {**fresh(), 'organic': [
                                   {'link': 'https://example.org', 'synthetic': True}]},
                               fresh()])
    result = snapshot.build_snapshot(ordered_markets(6), search_fn=search)
    assert result['counts'] == {
        'markets': 6, 'search_queries': 1, 'search_attempts': 6, 'search_unavailable': 5}
    assert [row['query'] for row in result['search_observations']] == ['roofing Market 5']


def test_empty_canonical_inventory_fails_before_search():
    search = Mock()
    with pytest.raises(snapshot.MarketObservationsUnavailable):
        snapshot.build_snapshot([], search_fn=search)
    search.assert_not_called()


@pytest.mark.parametrize('stage, reason', [
    ('env', 'dedicated_empiredb_unavailable'),
    ('db', 'dedicated_empiredb_unavailable'),
    ('empty_db', 'dedicated_empiredb_unavailable'),
    ('search', 'fresh_public_search_unavailable'),
    ('write', 'snapshot_production_failed'),
])
def test_wrapper_classifies_failures_without_secrets(stage, reason, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(wrapper, 'load_materializer_env', Mock(
        return_value={'EMPIRE_INTELLIGENCE_MATERIALIZER_DSN': 'test-only'},
        side_effect=RuntimeError('secret-fixture') if stage == 'env' else None))
    monkeypatch.setattr(wrapper, 'PostgresIntelligenceMaterializer', Mock(return_value=object()))
    monkeypatch.setattr(snapshot, 'observe_markets', Mock(
        return_value=[] if stage == 'empty_db' else MARKETS,
        side_effect=RuntimeError('secret-fixture') if stage == 'db' else None))
    path = tmp_path / 'snapshot.json'
    path.write_text('old-evidence')
    monkeypatch.setattr(wrapper, 'SNAPSHOT_PATH', path)
    search = Mock(side_effect=RuntimeError('secret-fixture')) if stage == 'search' else Mock(return_value=fresh())
    monkeypatch.setattr(wrapper, 'refresh_snapshot', lambda path, writer: snapshot.refresh_snapshot(path, writer, search_fn=search))
    if stage == 'write':
        monkeypatch.setattr(snapshot.tempfile, 'NamedTemporaryFile', Mock(side_effect=OSError('secret-fixture')))
    assert wrapper.main() == 1
    output = capsys.readouterr()
    assert 'secret-fixture' not in output.out + output.err
    assert json.loads(output.out)['reason'] == reason
    assert json.loads(output.out)['snapshot_replaced'] is False
    assert path.read_text() == 'old-evidence'
