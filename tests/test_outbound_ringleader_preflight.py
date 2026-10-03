from pathlib import Path

from empire_os.outbound_ringleader_preflight import evaluate_preflight


def base_env():
    return {
        "EMPIRE_OUTBOUND_RINGLEADER_MODE": "OBSERVE",
        "EMPIRE_OUTBOUND_SCOPE_KEY": "empire",
        "EMPIRE_OUTBOUND_TELEMETRY_SOURCE": "resend",
        "RESEND_API_KEY": "test-key",
        "EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN": "",
        "EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN": "",
        "EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE": "false",
    }


def test_preflight_allows_observe_without_db_when_persistence_not_required(tmp_path):
    context = tmp_path / "context.json"
    context.write_text("{}", encoding="utf-8")
    result = evaluate_preflight(base_env(), context_path=context)
    assert result["status"] == "READY"
    assert result["activation_authorized"] is False
    assert "empiredb_persistence_unconfigured" in result["warnings"]


def test_preflight_blocks_non_observe_mode(tmp_path):
    env = base_env()
    env["EMPIRE_OUTBOUND_RINGLEADER_MODE"] = "EXECUTE"
    result = evaluate_preflight(env, context_path=tmp_path / "missing.json")
    assert result["status"] == "BLOCKED"
    assert "observer_mode_must_be_observe" in result["blockers"]


def test_preflight_blocks_half_configured_db_bindings(tmp_path):
    env = base_env()
    env["EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN"] = "reader"
    result = evaluate_preflight(env, context_path=tmp_path / "missing.json")
    assert result["status"] == "BLOCKED"
    assert "reader_writer_dsn_must_be_paired" in result["blockers"]


def test_preflight_blocks_missing_db_when_persistence_required(tmp_path):
    env = base_env()
    env["EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE"] = "true"
    result = evaluate_preflight(env, context_path=tmp_path / "missing.json")
    assert result["status"] == "BLOCKED"
    assert "persistence_required_but_unconfigured" in result["blockers"]


def test_preflight_blocks_context_that_authorizes_mutation(tmp_path):
    context = tmp_path / "context.json"
    context.write_text('{"mutation_authorized": true}', encoding="utf-8")
    try:
        evaluate_preflight(base_env(), context_path=context)
    except RuntimeError as exc:
        assert "cannot_authorize_mutation" in str(exc)
    else:
        raise AssertionError("expected preflight to reject mutating context")
