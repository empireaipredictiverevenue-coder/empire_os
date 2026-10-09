"""Benchmark-only loopback admission. No router, registry or authority writes.

Historical ladder: LLMGateway._client -> agent_core.OllamaClient, timeout=180,
provider endpoint is supplied by the canonical model fabric; no num_ctx/num_predict/think overrides.
This isolated client bounds loading + inference together; no retries/unloads.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
from time import monotonic
from urllib import request


@contextmanager
def deadline(seconds):
    """CLI/main-thread wall deadline, including connection and response reads."""
    def expired(signum, frame):
        raise TimeoutError("benchmark_deadline")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def host_resources():
    available = None
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                available = int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    # PCI display-class evidence only; never infer VRAM or acceleration support.
    gpu = False
    try:
        gpu = any(p.read_text().strip().startswith('0x03')
                  for p in Path('/sys/bus/pci/devices').glob('*/class'))
    except OSError:
        pass
    return dict(cpu_count=os.cpu_count(), available_memory_bytes=available,
                gpu_detected=gpu, gpu_detection_method='pci_display_class',
                model_size_bytes=None, advisory_only=True)


class LocalBenchmarkClient:
    def __init__(self, config, timeout=45):
        self.model = config['model']
        self.ollama = config['provider'] == 'ollama'
        self.base = 'http://127.0.0.1:' + ('11434' if self.ollama else '11435')
        self.timeout = timeout

    def request(self, path, payload=None):
        req = request.Request(self.base + path,
                              data=None if payload is None else json.dumps(payload).encode(),
                              headers={'Content-Type': 'application/json'})
        # Ignore proxy environment: these are explicitly local benchmarks.
        with request.build_opener(request.ProxyHandler({})).open(req, timeout=self.timeout) as response:
            body = json.load(response)
        if not isinstance(body, dict) or body.get('error'):
            raise ValueError('invalid_or_error_response')
        return body

    def chat(self, messages, system=None, temperature=0, max_tokens=192):
        messages = ([dict(role='system', content=system)] if system else []) + messages
        if self.ollama:
            payload = dict(model=self.model, messages=messages, stream=False,
                           think=False, keep_alive='10m',
                           options=dict(num_ctx=2048, num_predict=max_tokens, temperature=temperature))
            path = '/api/chat'
        else:
            payload = dict(model=self.model, messages=messages, stream=False,
                           temperature=temperature, max_tokens=max_tokens)
            path = '/v1/chat/completions'
        with deadline(self.timeout):
            body = self.request(path, payload)
        if self.ollama:
            return body.get('message', {}).get('content', '')
        return body.get('choices', [{}])[0].get('message', {}).get('content', '')


def preflight(client, timeout=25):
    """Verify local model readiness without confusing cold start with quality.

    Discovery/residency are observations.  The supplied timeout is the
    readiness-generation budget, not evidence of model quality.
    """
    if not 0 < timeout <= 120:
        raise ValueError(
            'preflight timeout must be >0 and <=120 seconds'
        )

    started = monotonic()
    result = dict(
        preflight_ok=False,
        preflight_latency_ms=None,
        preflight_error=None,
        installed=None,
        api_healthy=False,
        model_loaded=None,
        was_loaded=None,
        readiness_mode=None,
        readiness_latency_ms=None,
        cold_load_latency_ms=None,
        skipped_reason=None,
        resources=host_resources(),
    )

    original_timeout = client.timeout

    try:
        if client.ollama:
            # Discovery is deliberately separate from generation readiness.
            client.timeout = min(5, timeout)
            tags = client.request('/api/tags')
            result['api_healthy'] = True

            models = tags.get('models', [])
            match = next(
                (m for m in models if m.get('name') == client.model),
                None,
            )
            result['installed'] = match is not None

            if match is None:
                raise ValueError('model_not_installed')

            result['resources']['model_size_bytes'] = match.get('size')

            # Residency is an observation, not an admission requirement.
            try:
                running = client.request('/api/ps')
                loaded = any(
                    m.get('name') == client.model
                    for m in running.get('models', [])
                )
                result['model_loaded'] = loaded
                result['was_loaded'] = loaded
            except (OSError, ValueError, TimeoutError):
                result['model_loaded'] = None
                result['was_loaded'] = None

            result['readiness_mode'] = (
                'warm' if result['was_loaded'] else 'cold'
            )

        else:
            client.timeout = min(5, timeout)
            health = client.request('/health')
            result['api_healthy'] = (
                health.get('status') in {'ok', 'ready'}
            )

            if not result['api_healthy']:
                raise ValueError('api_unhealthy')

            # llama.cpp exposes a single already-served model.
            result['installed'] = True
            result['model_loaded'] = True
            result['was_loaded'] = True
            result['readiness_mode'] = 'warm'

        readiness_started = monotonic()
        client.timeout = timeout

        output = client.chat(
            [dict(
                role='user',
                content='Reply with exactly: READY',
            )],
            max_tokens=16,
        )

        readiness_ms = round(
            (monotonic() - readiness_started) * 1000,
            3,
        )
        result['readiness_latency_ms'] = readiness_ms

        if result['readiness_mode'] == 'cold':
            result['cold_load_latency_ms'] = readiness_ms

        if output.strip() != 'READY':
            raise ValueError('ready_response_mismatch')

        result.update(
            preflight_ok=True,
            model_loaded=True,
            skipped_reason=None,
        )

    except TimeoutError:
        result['preflight_error'] = 'TimeoutError:readiness_timeout'

        if result['installed'] is True:
            result['skipped_reason'] = (
                'cold_start_timeout'
                if result['was_loaded'] is False
                else 'readiness_timeout'
            )
        else:
            result['skipped_reason'] = 'unavailable'

    except Exception as exc:
        result['preflight_error'] = (
            type(exc).__name__
            + ':'
            + (
                str(exc)
                if isinstance(exc, ValueError)
                else 'request_failed'
            )
        )

        if result['installed'] is False:
            result['skipped_reason'] = 'unavailable'
        elif result['api_healthy']:
            result['skipped_reason'] = 'readiness_failed'
        else:
            result['skipped_reason'] = 'unavailable'

    finally:
        client.timeout = original_timeout

    result['preflight_latency_ms'] = round(
        (monotonic() - started) * 1000,
        3,
    )
    return result
