from pathlib import Path
import subprocess

from empire_os.coder.context import ContextPack
from empire_os.coder.hermes_provider import HermesProvider
from empire_os.coder.models import ModelRoute
from empire_os.coder.provider import ModelRequest


def request(tmp_path: Path) -> ModelRequest:
    return ModelRequest(
        task_id="coder_test",
        instruction="Return a safe patch proposal.",
        context=ContextPack(
            objective="Add a read-only health evaluator.",
            task_state={"status": "RUNNING"},
            documents=(),
            symbols=(),
            token_budget_chars=4000,
        ),
        route=ModelRoute(
            provider="hermes",
            model="nvidia/nemotron-3.5-lightning:free",
            reason="test",
            local=False,
            cost_tier=0,
        ),
        max_output_chars=200,
    )


def test_hermes_provider_uses_safe_mode_and_workspace(
    tmp_path,
    monkeypatch,
):
    seen = {}

    monkeypatch.setattr(
        "empire_os.coder.hermes_provider.shutil.which",
        lambda _name: "/usr/bin/hermes",
    )

    def run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="SAFE RESULT",
            stderr="",
        )

    monkeypatch.setattr(
        "empire_os.coder.hermes_provider.subprocess.run",
        run,
    )
    provider = HermesProvider(tmp_path, timeout_seconds=90)
    result = provider.complete(request(tmp_path))

    assert result.error is None
    assert result.text == "SAFE RESULT"
    assert result.provider == "hermes"
    assert "--safe-mode" in seen["argv"]
    assert "-z" in seen["argv"]
    assert "--in" in seen["argv"]
    assert str(tmp_path.resolve()) in seen["argv"]
    assert seen["kwargs"].get("shell", False) is False
    assert seen["kwargs"]["cwd"] == tmp_path.resolve()


def test_hermes_provider_fails_closed_when_missing(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "empire_os.coder.hermes_provider.shutil.which",
        lambda _name: None,
    )
    provider = HermesProvider(tmp_path)
    result = provider.complete(request(tmp_path))
    assert result.error == "hermes_not_installed"
    assert result.text == ""


def test_hermes_provider_reports_timeout(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "empire_os.coder.hermes_provider.shutil.which",
        lambda _name: "/usr/bin/hermes",
    )

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="hermes", timeout=60)

    monkeypatch.setattr(
        "empire_os.coder.hermes_provider.subprocess.run",
        timeout,
    )
    provider = HermesProvider(tmp_path, timeout_seconds=60)
    result = provider.complete(request(tmp_path))
    assert result.error == "hermes_request_failed:TimeoutExpired"
