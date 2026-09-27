from empire_os.coder.runner import SafeCommandRunner


def test_runner_scrubs_secret_like_output(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    runner = SafeCommandRunner(tmp_path)
    # Use an allowlisted Python module entrypoint that emits a synthetic-looking
    # secret-shaped string; the runner must redact it before returning/storing.
    script = tmp_path / "emit_secret.py"
    script.write_text(
        'print("OPENAI_API_KEY=sk-" + "x" * 30)\n',
        encoding="utf-8",
    )
    # Direct Python scripts require approval by policy; explicit approval here
    # exercises scrubbing, not authority bypass.
    result = runner.run(
        ("python3", str(script)),
        task_id="coder_test",
        approved=True,
    )
    assert "sk-" not in result.stdout
    assert "[REDACTED]" in result.stdout
    log = (tmp_path / "runtime" / "coder" / "tool_runs" / "coder_test.jsonl").read_text()
    assert "sk-" not in log
    assert "[REDACTED]" in log
