"""Existing Hermes worker's bounded daily SEO intake integration."""
from pathlib import Path

from empire_os import hermes_control, hermes_seo_intake


def test_worker_reads_automated_research_status_without_new_timer(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(
        hermes_control, "fetch_control_refs", lambda *a, **k: None)
    monkeypatch.setattr(
        hermes_control, "list_pending_job_paths", lambda *a, **k: [])
    calls = []
    def preview(repo, *, publish, control_branch):
        calls.append((repo, publish, control_branch))
        return {
            "schema_version": "empire.hermes.seo_research_intake.v1",
            "status": "ALL_FINDINGS_ALREADY_ASSIGNED_OR_UNDER_REVIEW",
            "published_count": 0,
            "execution_authority": "none",
        }
    monkeypatch.setattr(hermes_seo_intake, "reconcile_seo_intake", preview)
    result = hermes_control.run_worker(tmp_path)
    assert calls == [(tmp_path, True, "ops/hermes-control")]
    assert result["processed_count"] == 0
    assert result["seo_intake"]["published_count"] == 0
    assert result["seo_intake"]["status"].startswith("ALL_FINDINGS")
    assert result["production_merge_performed"] is False
    assert result["database_mutation_performed"] is False
    assert result["payment_action_performed"] is False


def test_worker_refreshes_original_control_ref_after_research_job_queued(
    tmp_path, monkeypatch,
):
    fetches = []
    monkeypatch.setattr(
        hermes_control, "fetch_control_refs",
        lambda *a, **k: fetches.append(1))
    monkeypatch.setattr(
        hermes_control, "list_pending_job_paths", lambda *a, **k: [])
    monkeypatch.setattr(
        hermes_seo_intake, "reconcile_seo_intake",
        lambda *a, **k: {
            "status": "RESEARCH_JOB_QUEUED", "published_count": 1,
            "execution_authority": "none",
        })
    result = hermes_control.run_worker(tmp_path)
    assert len(fetches) == 2
    assert result["processed_count"] == 0
    assert result["seo_intake"]["status"] == "RESEARCH_JOB_QUEUED"


def test_intake_exception_does_not_block_original_worker(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(
        hermes_control, "fetch_control_refs", lambda *a, **k: None)
    monkeypatch.setattr(
        hermes_control, "list_pending_job_paths", lambda *a, **k: [])
    def unavailable(*a, **k):
        raise RuntimeError("untrusted upstream detail")
    monkeypatch.setattr(hermes_seo_intake, "reconcile_seo_intake", unavailable)
    result = hermes_control.run_worker(tmp_path)
    assert result["processed_count"] == 0
    assert result["seo_intake"]["status"] == "HELD"
    assert result["seo_intake"]["reason_code"] == "RuntimeError"
    assert "untrusted upstream detail" not in str(result)
    assert result["seo_intake"]["execution_authority"] == "none"
