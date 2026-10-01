import os
from pathlib import Path

import pytest

from empire_os.runtime_env import load_runtime_env


def test_exported_environment_wins_over_file(tmp_path, monkeypatch):
    p=tmp_path/"runtime.env"
    p.write_text("SUPABASE_URL=file-url\nSUPABASE_SERVICE_KEY=file-key\n")
    monkeypatch.setenv("SUPABASE_URL","exported-url")
    env=load_runtime_env(p,required=("SUPABASE_URL","SUPABASE_SERVICE_KEY"))
    assert env["SUPABASE_URL"]=="exported-url"
    assert env["SUPABASE_SERVICE_KEY"]=="file-key"


def test_unreadable_or_missing_file_is_ok_when_env_exported(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL","https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY","secret-present")
    env=load_runtime_env(
        tmp_path/"missing.env",
        required=("SUPABASE_URL","SUPABASE_SERVICE_KEY"),
    )
    assert env["SUPABASE_SERVICE_KEY"]=="secret-present"


def test_missing_required_values_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL",raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY",raising=False)
    with pytest.raises(RuntimeError,match="missing required runtime env"):
        load_runtime_env(
            tmp_path/"missing.env",
            required=("SUPABASE_URL","SUPABASE_SERVICE_KEY"),
        )


@pytest.fixture
def production_files(monkeypatch):
    monkeypatch.setattr(os, "environ", {})
    files = {
        Path('/etc/empire_os.env'): 'EMPIRE_DATA_BACKEND=empiredb\n',
        Path('/etc/empiredb.env'): 'EMPIREDB_DSN=test-only-dsn\n',
    }

    def read_text(path, **kwargs):
        value = files.get(path, FileNotFoundError())
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(Path, 'read_text', read_text)
    return files


def test_production_companion_constructs_canonical_gateway(production_files):
    from empire_os.canonical_data_gateway import gateway_from_environment
    from empire_os.data_cloud_contract import DataBackend

    env = load_runtime_env('/etc/empire_os.env', required=('EMPIREDB_DSN',))
    assert env['EMPIREDB_DSN'] == 'test-only-dsn'
    assert gateway_from_environment(env).backend is DataBackend.EMPIREDB


def test_production_precedence(production_files, monkeypatch):
    production_files[Path('/etc/empire_os.env')] += 'EMPIREDB_DSN=primary-test-dsn\n'
    assert load_runtime_env('/etc/empire_os.env')['EMPIREDB_DSN'] == 'primary-test-dsn'
    monkeypatch.setenv('EMPIREDB_DSN', 'exported-test-dsn')
    assert load_runtime_env('/etc/empire_os.env')['EMPIREDB_DSN'] == 'exported-test-dsn'


@pytest.mark.parametrize('failure', [FileNotFoundError(), PermissionError()])
def test_missing_companion_fails_closed(production_files, failure):
    from empire_os.canonical_data_gateway import DataGatewayUnavailable, gateway_from_environment

    production_files[Path('/etc/empiredb.env')] = failure
    env = load_runtime_env('/etc/empire_os.env')
    with pytest.raises(DataGatewayUnavailable, match='runtime provider is not configured'):
        gateway_from_environment(env)
    with pytest.raises(RuntimeError, match='missing required runtime env: EMPIREDB_DSN'):
        load_runtime_env('/etc/empire_os.env', required=('EMPIREDB_DSN',))


def test_exported_service_configuration_needs_no_file_access(production_files, monkeypatch):
    for path in production_files:
        production_files[path] = PermissionError()
    monkeypatch.setenv('EMPIRE_DATA_BACKEND', 'empiredb')
    monkeypatch.setenv('EMPIREDB_DSN', 'exported-test-dsn')
    assert load_runtime_env('/etc/empire_os.env', required=('EMPIREDB_DSN',))['EMPIREDB_DSN'] == 'exported-test-dsn'


def test_custom_file_does_not_load_production_companion(production_files):
    production_files[Path('/tmp/custom.env')] = 'EMPIRE_DATA_BACKEND=empiredb\n'
    assert 'EMPIREDB_DSN' not in load_runtime_env('/tmp/custom.env')


def test_readiness_default_entrypoint_uses_shared_companion(production_files, monkeypatch):
    from empire_os.data_backends.empiredb import EmpireDbProvider
    from scripts.build_buyer_capacity_readiness import fetch_all_buyers

    calls = []

    def query(self, table, columns, **kwargs):
        calls.append((table, kwargs['offset']))
        return []

    monkeypatch.setattr(EmpireDbProvider, 'query', query)
    assert fetch_all_buyers() == []
    assert calls == [('buyers', 0)]
