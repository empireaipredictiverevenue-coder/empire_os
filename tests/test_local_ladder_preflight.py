import json
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from empire_os.local_benchmark_preflight import LocalBenchmarkClient, deadline, preflight
from scripts import run_hybrid_compute_local_ladder as ladder


class FakeClient:
    def __init__(self, config, timeout=45, mode='pass'):
        self.model = config['model']
        self.ollama = config['provider'] == 'ollama'
        self.timeout = timeout
        self.mode = mode
        self.calls = []

    def request(self, path, payload=None):
        if self.mode == 'unhealthy':
            raise OSError('offline')
        if path == '/api/tags':
            return {'models': [] if self.mode == 'missing' else [{'name': self.model, 'size': 123}]}
        if path == '/api/ps':
            return {'models': []}
        return {'status': 'ok'}

    def chat(self, messages, system=None, temperature=0, max_tokens=192):
        self.calls.append((messages, max_tokens))
        if self.mode == 'timeout' or (self.mode == 'case_timeout' and max_tokens != 16):
            raise TimeoutError()
        if max_tokens == 16:
            return 'wrong' if self.mode == 'wrong' else 'READY'
        if self.mode == 'quality':
            return 'available'
        return 'route execution authority fail closed observe diagnose test evidence failure idempotency validation retry checkpoint unknown estimation promotion'


def execute(tmp_path, mode='pass', extra=()):
    clients = []
    def factory(config, timeout):
        client = FakeClient(config, timeout, mode)
        clients.append(client)
        return client
    args = ladder.parse_args(['--output', str(tmp_path / 'checkpoint.json'), *extra])
    result = ladder.run(args, client_factory=factory)
    assert json.loads(args.output.read_text()) == result
    return result, clients


@pytest.mark.parametrize('mode,status', [('unhealthy', 'unavailable'), ('missing', 'unavailable'),
                                         ('timeout', 'cold_start_timeout'), ('wrong', 'readiness_failed')])
def test_failed_admission_skips_all_cases(tmp_path, mode, status):
    result, clients = execute(tmp_path, mode, ['--candidate', ladder.CANDIDATES[1]['model_id']])
    assert result['complete'] and result['run_count'] == 4
    assert result['actual_call_count'] == 0
    assert all(r['observation_status'] == 'skipped' and not r['model_call_executed'] for r in result['runs'])
    report = next(iter(result['summaries'].values()))
    assert report['status'] == status
    assert report['sample_count'] == 0 and report['mean_latency_ms'] is None
    assert not report['promotion_ready'] and not report['promotion_eligible']
    assert len(clients[0].calls) == (0 if mode in {'unhealthy', 'missing'} else 1)


def test_success_admits_cases_preserves_registry_and_authority(tmp_path):
    before = Path('config/model_registry.json').read_bytes()
    result, clients = execute(tmp_path)
    assert result['actual_call_count'] == 16
    assert len(clients) == 4 and all(len(c.calls) == 5 for c in clients)
    assert not any(result[k] for k in ('route_applied', 'production_authority', 'commercial_authority', 'business_data_used', 'promotion_ready'))
    for config in ladder.CANDIDATES:
        report = result['summaries'][config['model_id']]
        assert report['registry_status'] == config['registry_status']
        assert report['status'] == 'benchmark_passed'
        assert report['promotion_eligible'] and not report['promotion_ready']
    assert Path('config/model_registry.json').read_bytes() == before


def test_preflight_only(tmp_path):
    result, clients = execute(tmp_path, extra=['--preflight-only'])
    assert result['actual_call_count'] == 0
    assert all(len(c.calls) == 1 for c in clients)
    assert all(r['skipped_reason'] == 'preflight_only' for r in result['runs'])
    assert all(s['status'] == 'viable_not_benchmarked' for s in result['summaries'].values())


def test_selector(tmp_path):
    result, clients = execute(tmp_path, extra=['--candidate', 'local-qwen25-coder-7b'])
    assert len(clients) == result['candidate_count'] == 1
    assert clients[0].model == 'qwen2.5-coder:7b'
    assert result['actual_call_count'] == 4


@pytest.mark.parametrize('mode', ['quality', 'case_timeout'])
def test_quality_and_timeouts_never_promotion_ready(tmp_path, mode):
    result, _ = execute(tmp_path, mode)
    for report in result['summaries'].values():
        assert report['status'] == 'viable_but_quality_failed'
        assert not report['promotion_ready'] and not report['promotion_eligible']


def test_resource_observation_cannot_admit(monkeypatch):
    monkeypatch.setattr('empire_os.local_benchmark_preflight.host_resources', lambda: dict(
        cpu_count=1000, available_memory_bytes=10**15, gpu_detected=False, advisory_only=True))
    result = preflight(FakeClient(ladder.CANDIDATES[1], mode='timeout'))
    assert not result['preflight_ok']
    assert result['resources']['model_size_bytes'] == 123
    assert result['model_loaded'] is False


def test_llamacpp_compatibility_and_prior_quality(tmp_path):
    result, clients = execute(tmp_path, extra=['--candidate', ladder.CANDIDATES[0]['model_id']])
    assert not clients[0].ollama and result['actual_call_count'] == 4
    assert result['prior_1_5b_evidence']['assessment'] == 'available but quality-limited'
    assert result['prior_1_5b_evidence']['production_verification_coverage'] == 0.2


def test_exact_preflight_payload_and_case_limits():
    client = LocalBenchmarkClient(ladder.CANDIDATES[1])
    client.request = Mock(side_effect=[{'models': [{'name': client.model, 'size': 123}]},
                                      {'models': []}, {'message': {'content': 'READY'}}])
    assert preflight(client)['preflight_ok']
    path, payload = client.request.call_args.args
    assert client.base == 'http://127.0.0.1:11434' and path == '/api/chat'
    assert payload['options'] == dict(num_ctx=2048, num_predict=16, temperature=0)
    assert payload['think'] is False and payload['keep_alive'] == '10m'
    assert payload['messages'] == [dict(role='user', content='Reply with exactly: READY')]
    client.request = Mock(return_value={'message': {'content': 'ok'}})
    client.chat([dict(role='user', content='safe')], max_tokens=192)
    assert client.request.call_args.args[1]['options']['num_predict'] == 192


def test_exact_model_required():
    client = FakeClient(ladder.CANDIDATES[1])
    client.request = Mock(return_value={'models': [{'name': 'qwen2.5-coder:7b-other'}]})
    assert preflight(client)['installed'] is False
    assert not client.calls


def test_wall_deadline():
    started = time.monotonic()
    with pytest.raises(TimeoutError), deadline(0.02):
        time.sleep(1)
    assert time.monotonic() - started < 0.5


@pytest.mark.parametrize('flag,value', [('--preflight-timeout', '121'), ('--preflight-timeout', 'nan'),
                                        ('--case-timeout', '91'), ('--case-timeout', '0')])
def test_cli_rejects_unbounded_timeouts(flag, value):
    with pytest.raises(SystemExit):
        ladder.parse_args([flag, value])


def test_historical_gateway_client_contract():
    # Pin discovered truth without executing a route or an inference.
    from empire_os.agent_core import OllamaClient
    from empire_os.llm_gateway import LLMGateway
    client = LLMGateway()._client('ollama', 'qwen2.5-coder:7b', 180)
    assert type(client) is OllamaClient
    assert client.timeout == 180
    assert client.base_url == 'http://127.0.0.1:11434'
