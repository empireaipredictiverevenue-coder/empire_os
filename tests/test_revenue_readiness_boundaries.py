"""Negative production boundary tests; no live data or commercial writes."""
from types import SimpleNamespace

import pytest

from empire_os import canonical_data_gateway as gateway
from empire_os.lead_sources import court_listener as court


@pytest.mark.parametrize('env', [{}, {'EMPIRE_DATA_BACKEND': 'empiredb'}])
def test_production_reader_selects_empiredb(monkeypatch, env):
    calls = []
    monkeypatch.setattr(gateway, 'gateway_from_environment', lambda value: calls.append(value))
    gateway.empiredb_gateway_from_environment(env)
    assert calls == [{**env, 'EMPIRE_DATA_BACKEND': 'empiredb'}]


def test_production_reader_rejects_legacy_before_connecting(monkeypatch):
    def forbidden(*args):
        raise AssertionError('must not construct legacy provider')
    monkeypatch.setattr(gateway, 'gateway_from_environment', forbidden)
    with pytest.raises(gateway.DataGatewayUnavailable, match='EmpireDB'):
        gateway.empiredb_gateway_from_environment({'EMPIRE_DATA_BACKEND': 'supabase_legacy'})


@pytest.mark.parametrize('response', [
    SimpleNamespace(status_code=403),
    SimpleNamespace(status_code=200, json=lambda: {'detail': 'invalid'}),
])
def test_courtlistener_failed_queries_are_not_empty_success(monkeypatch, response):
    monkeypatch.setattr(court, '_read_token', lambda: '')
    monkeypatch.setattr(court.requests, 'get', lambda *args, **kwargs: response)
    monkeypatch.setattr(court.time, 'sleep', lambda seconds: None)
    with pytest.raises(RuntimeError, match='producer_unavailable'):
        list(court.run())


def test_courtlistener_valid_empty_query_is_not_supply(monkeypatch):
    monkeypatch.setattr(court, '_read_token', lambda: '')
    monkeypatch.setattr(court.requests, 'get', lambda *a, **kw: SimpleNamespace(
        status_code=200, json=lambda: {'results': []}))
    monkeypatch.setattr(court.time, 'sleep', lambda seconds: None)
    assert list(court.run()) == []


def test_courtlistener_uses_runtime_environment(monkeypatch):
    paths = []
    monkeypatch.setattr(court, 'load_runtime_env', lambda path: paths.append(path) or {})
    assert court._read_token() == ''
    assert paths == ['/etc/empire_os.env']


def test_courtlistener_network_loss_is_unavailable(monkeypatch):
    monkeypatch.setattr(court, '_read_token', lambda: '')
    def unavailable(*args, **kwargs):
        raise OSError('offline')
    monkeypatch.setattr(court.requests, 'get', unavailable)
    with pytest.raises(RuntimeError, match='producer_unavailable'):
        list(court.run())


def test_courtlistener_recovery_preserves_real_source_record(monkeypatch):
    record = {'caseName': 'Source docket', 'absolute_url': '/docket/123/', 'id': 123}
    monkeypatch.setattr(court, '_read_token', lambda: '')
    monkeypatch.setattr(court.requests, 'get', lambda *a, **kw: SimpleNamespace(
        status_code=200, json=lambda: {'results': [record]}))
    monkeypatch.setattr(court.time, 'sleep', lambda seconds: None)
    rows = list(court.run())
    assert rows
    assert rows[0].raw == record
    assert rows[0].url == 'https://www.courtlistener.com/docket/123/'
