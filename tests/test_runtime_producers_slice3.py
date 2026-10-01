import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from empire_os import agent_web_snapshot as snapshot
from empire_os import crawler_data_repository as repository
from empire_os.prospect_ingest import ProspectIngestError
from scripts import run_acquisition_cycle as cycle
from scripts.provision_intelligence_materializer import env_text


MARKETS = [{'niche': 'roofing', 'metro': 'Denver', 'prospect_count': 2, 'avg_rating': None}]


def live_search(*args, **kwargs):
    assert kwargs['use_cache'] is False
    assert kwargs['engine'] is None
    return {'searchParameters': {'cache': False, 'engine': 'bing_html'}, 'organic': [
        {'link': 'https://example.org/roofing', 'title': 'Roofing', 'position': 1},
    ]}


def test_snapshot_has_observations_without_invented_keyword_metrics():
    result = snapshot.build_snapshot(MARKETS, search_fn=live_search)
    assert result['markets'][0]['avg_rating'] is None
    assert result['seo_keywords'] == []
    assert result['search_observations'][0]['results'][0]['position'] == 1
    assert 'total_revenue' not in json.dumps(result)


@pytest.mark.parametrize('response', [
    {'error': 'unavailable'},
    {'searchParameters': {'cache': True}, 'organic': [{'link': 'https://example.org'}]},
    {'searchParameters': {'cache': False}, 'organic': []},
])
def test_failed_refresh_preserves_previous_snapshot(tmp_path, monkeypatch, response):
    output = tmp_path / 'snapshot.json'
    output.write_text('{"generated_at":"old"}')
    monkeypatch.setattr(snapshot, 'observe_markets', lambda writer: MARKETS)
    with pytest.raises(ValueError, match='fresh public search unavailable'):
        snapshot.refresh_snapshot(output, object(), search_fn=lambda *a, **kw: response)
    assert output.read_text() == '{"generated_at":"old"}'


def test_successful_refresh_replaces_old_data(tmp_path, monkeypatch):
    output = tmp_path / 'snapshot.json'
    output.write_text('{"markets":[{"fabricated":true}]}')
    monkeypatch.setattr(snapshot, 'observe_markets', lambda writer: MARKETS)
    snapshot.refresh_snapshot(output, object(), search_fn=live_search)
    assert json.loads(output.read_text())['markets'] == MARKETS


def test_crawler_defaults_to_empiredb_without_legacy_fallback(monkeypatch):
    monkeypatch.setattr(repository, 'load_runtime_env', lambda path: {})
    gateway = Mock(return_value=object())
    monkeypatch.setattr(repository, 'gateway_from_environment', gateway)
    repository.CrawlerProspectRepository.from_environment()
    assert gateway.call_args.args[0]['EMPIRE_DATA_BACKEND'] == 'empiredb'


def test_crawler_rejects_explicit_legacy_backend(monkeypatch):
    monkeypatch.setattr(repository, 'load_runtime_env', lambda path: {'EMPIRE_DATA_BACKEND': 'supabase_legacy'})
    gateway = Mock()
    monkeypatch.setattr(repository, 'gateway_from_environment', gateway)
    with pytest.raises(ProspectIngestError, match='EmpireDB'):
        repository.CrawlerProspectRepository.from_environment()
    gateway.assert_not_called()


def test_cycle_timeout_is_recorded_and_does_not_replace_success(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, 'RUNTIME', tmp_path)
    for key, file in [('STATE','state.json'),('LATEST','latest.json'),('LAST_SUCCESS','success.json'),('LOCK','lock')]:
        monkeypatch.setattr(cycle, key, tmp_path / file)
    cycle.LAST_SUCCESS.write_text('old-success')
    monkeypatch.setattr(cycle.subprocess, 'run', Mock(side_effect=subprocess.TimeoutExpired('crawler',630)))
    result = cycle.run_cycle(max_candidates=1)
    assert result['ok'] is False
    assert result['returncode'] == 124
    assert result['canonical_store'] is None
    assert cycle.LAST_SUCCESS.read_text() == 'old-success'
    assert json.loads(cycle.STATE.read_text())['last_ok'] is False


def test_environment_preserves_existing_configuration_and_refuses_rotation():
    assert env_text('OTHER=value\n', 'test-only') == 'OTHER=value\nEMPIRE_INTELLIGENCE_MATERIALIZER_DSN=test-only\n'
    with pytest.raises(ValueError):
        env_text('EMPIRE_INTELLIGENCE_MATERIALIZER_DSN=existing', 'test-only')


def test_search_cache_bypass_fetches_again(monkeypatch):
    import importlib
    search = importlib.import_module('empire_os.search_fabric.search')
    cached = Mock(side_effect=AssertionError('cache must not be read'))
    fetch = Mock(return_value=None)
    monkeypatch.setattr(search, '_get_cache', cached)
    monkeypatch.setattr(search, '_fetch', fetch)
    result = search.search('roofing Denver', engine='bing_html', use_cache=False)
    assert result['error']
    fetch.assert_called_once()
    cached.assert_not_called()


def test_bootstrap_contract_has_no_generic_app_grant_or_global_rls_change():
    sql = Path('deploy/empiredb/intelligence_materializer.sql').read_text()
    assert 'TO empiredb_app' not in sql
    assert 'ENABLE ROW LEVEL SECURITY' not in sql
    assert 'NOBYPASSRLS' in sql
    assert 'SECURITY DEFINER' not in sql
    assert 'PUBLIC authority audit required' in sql


def test_crawler_loads_canonical_database_environment(monkeypatch):
    def env(path):
        return {'EMPIREDB_DSN': 'test-only'} if path == '/etc/empiredb.env' else {}
    monkeypatch.setattr(repository, 'load_runtime_env', env)
    gateway = Mock(return_value=object())
    monkeypatch.setattr(repository, 'gateway_from_environment', gateway)
    repository.CrawlerProspectRepository.from_environment()
    assert gateway.call_args.args[0] == {'EMPIRE_DATA_BACKEND': 'empiredb', 'EMPIREDB_DSN': 'test-only'}


@pytest.mark.parametrize('dsn', [
    'postgresql://empiredb_app@localhost/empiredb',
    'postgresql://postgres@localhost/empiredb',
    'postgresql://empire_intelligence_materializer_login@localhost/postgres',
])
def test_materializer_configuration_rejects_privileged_or_legacy_dsn(monkeypatch, dsn):
    from empire_os import intelligence_materializer_env as env
    monkeypatch.setattr(env, 'load_runtime_env', lambda path: {env.KEY: dsn})
    with pytest.raises(ValueError, match='dedicated EmpireDB'):
        env.load_materializer_env()


def test_materializer_configuration_accepts_dedicated_empiredb(monkeypatch):
    from empire_os import intelligence_materializer_env as env
    dsn = 'postgresql://empire_intelligence_materializer_login@localhost/empiredb'
    monkeypatch.setattr(env, 'load_runtime_env', lambda path: {env.KEY: dsn})
    assert env.load_materializer_env() == {env.KEY: dsn}


@pytest.mark.parametrize('returncode', [0, 1])
def test_provisioning_keeps_secrets_off_argv_and_preserves_env_on_failure(tmp_path, monkeypatch, returncode):
    from scripts import provision_intelligence_materializer as provision
    env_file = tmp_path / 'runtime.env'
    env_file.write_text('EXISTING=preserved\n')
    monkeypatch.setattr(provision.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(provision, 'load_runtime_env', lambda path: {
        'EMPIREDB_DSN': 'postgresql://empiredb_app@127.0.0.1:5432/empiredb',
    })
    monkeypatch.setattr(provision.secrets, 'token_urlsafe', lambda size: 'test-fixture-password')
    runner = Mock(return_value=subprocess.CompletedProcess([], returncode))
    monkeypatch.setattr(provision.subprocess, 'run', runner)
    if returncode:
        with pytest.raises(ValueError, match='bootstrap failed'):
            provision.provision(env_file)
        assert env_file.read_text() == 'EXISTING=preserved\n'
    else:
        provision.provision(env_file)
        assert env_file.read_text().startswith('EXISTING=preserved\n')
        assert env_file.stat().st_mode & 0o777 == 0o600
    assert 'test-fixture-password' not in repr(runner.call_args.args)
    assert 'test-fixture-password' in runner.call_args.kwargs['input']
    assert not list(tmp_path.glob('.intelligence-env-*'))
