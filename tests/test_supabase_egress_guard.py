import json
import subprocess

import empire_os.supabase_egress_guard as guard


def _result(args, code=0, stdout=""):
    return subprocess.CompletedProcess(args, code, stdout=stdout, stderr="")


def test_guard_contains_only_allowlisted_timers_on_egress_block(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        guard,
        "STATUS_PATH",
        tmp_path / "supabase_egress_guard.json",
    )
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(tuple(args))
        if args[1] == "is-enabled":
            return _result(args, 0, "enabled\n")
        return _result(args)

    def blocked(*_args, **_kwargs):
        raise RuntimeError(
            "GET /rest/v1/prospects -> HTTP 402: exceed_egress_quota"
        )

    result = guard.run_guard(
        request=blocked,
        run=fake_run,
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "contained"
    assert result["contained"] is True
    assert set(result["managed_timers"]) == set(guard.MANAGED_TIMERS)
    stopped = {
        call[2]
        for call in calls
        if len(call) >= 3 and call[1] == "stop"
    }
    assert set(guard.MANAGED_TIMERS).issubset(stopped)
    assert "empire-resend-inbound.service" not in stopped
    assert result["inbound_mail_touched"] is False
    assert result["revenue_mutation"] is False


def test_guard_restores_only_recorded_still_enabled_timers(
    monkeypatch,
    tmp_path,
):
    status = tmp_path / "supabase_egress_guard.json"
    monkeypatch.setattr(guard, "STATUS_PATH", status)
    status.write_text(
        json.dumps({
            "managed_timers": [
                "empire-gtm-pipeline.timer",
                "empire-outbound-governor.timer",
            ],
        }),
        encoding="utf-8",
    )
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(tuple(args))
        if args[1] == "is-enabled":
            if args[2] == "empire-outbound-governor.timer":
                return _result(args, 1, "disabled\n")
            return _result(args, 0, "enabled\n")
        return _result(args)

    result = guard.run_guard(
        request=lambda *_args, **_kwargs: [],
        run=fake_run,
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "healthy"
    assert result["restored_timers"] == ["empire-gtm-pipeline.timer"]
    starts = [
        call[2]
        for call in calls
        if len(call) >= 3 and call[1] == "start"
    ]
    assert starts == ["empire-gtm-pipeline.timer"]


def test_guard_does_not_contain_on_unrelated_probe_error(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        guard,
        "STATUS_PATH",
        tmp_path / "supabase_egress_guard.json",
    )
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(tuple(args))
        return _result(args)

    def failed(*_args, **_kwargs):
        raise RuntimeError("temporary DNS failure")

    result = guard.run_guard(
        request=failed,
        run=fake_run,
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "probe_error"
    assert result["contained"] is False
    assert calls == []



def test_guard_requests_the_explicit_recovery_probe_slot(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        guard,
        "STATUS_PATH",
        tmp_path / "supabase_egress_guard.json",
    )
    seen = {}

    def healthy(method, path, **kwargs):
        seen["method"] = method
        seen["path"] = path
        seen.update(kwargs)
        return []

    result = guard.run_guard(
        request=healthy,
        run=lambda args, **_kwargs: _result(args, 1, "disabled\n"),
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "healthy"
    assert seen["method"] == "GET"
    assert seen["path"] == "/rest/v1/prospects?select=id&limit=1"
    assert seen["allow_egress_probe"] is True
