from empire_os.astra_dispatcher import choose_jobs


def test_choose_jobs_drives_internal_launch_pipeline():
    loop = {
        "loop_complete": False,
        "stages": [
            {"stage": "recognized_revenue", "observed": False},
            {"stage": "buyer_conversation", "observed": False},
            {"stage": "commercial_terms", "observed": False},
        ],
    }
    source = {"end_to_end_healthy": True}
    assert choose_jobs(loop, source) == [
        "buyer_review_materializer",
        "gtm_pipeline",
        "closer_reply_handoff",
        "commercial_product_catalog_refresh",
        "commercial_evidence_auto_verifier",
        "commercial_terms_materializer",
        "conversion_intelligence_refresh",
        "commercial_loop_refresh",
        "revenue_pulse_refresh",
    ]


def test_choose_jobs_adds_source_repair_but_no_duplicate_jobs():
    loop = {
        "loop_complete": False,
        "stages": [
            {"stage": "recognized_revenue", "observed": False},
            {"stage": "buyer_conversation", "observed": True},
            {"stage": "commercial_terms", "observed": False},
        ],
    }
    source = {"end_to_end_healthy": False}
    assert choose_jobs(loop, source) == [
        "source_health_refresh",
        "buyer_review_materializer",
        "closer_reply_handoff",
        "commercial_product_catalog_refresh",
        "commercial_evidence_auto_verifier",
        "commercial_terms_materializer",
        "conversion_intelligence_refresh",
        "commercial_loop_refresh",
        "revenue_pulse_refresh",
    ]


def test_complete_loop_dispatches_nothing_when_source_is_healthy():
    assert choose_jobs(
        {"loop_complete": True, "stages": []},
        {"end_to_end_healthy": True},
    ) == []


def test_deferred_enrichment_is_owned_by_dedicated_timer_not_astra():
    loop = {
        "loop_complete": False,
        "stages": [
            {"stage": "recognized_revenue", "observed": False},
            {"stage": "buyer_conversation", "observed": False},
            {"stage": "commercial_terms", "observed": False},
        ],
    }
    source = {"end_to_end_healthy": True}
    review = {"deferred_enrichment": 4}
    jobs = choose_jobs(loop, source, review)
    assert "buyer_deferred_enrichment" not in jobs
    assert jobs[0] == "buyer_review_materializer"
    assert jobs[-1] == "revenue_pulse_refresh"


def test_dispatch_timeout_does_not_crash_conveyor(monkeypatch, tmp_path):
    import subprocess
    import empire_os.astra_dispatcher as module

    monkeypatch.setattr(module, "LOOP", tmp_path / "loop.json")
    monkeypatch.setattr(module, "SOURCE", tmp_path / "source.json")
    monkeypatch.setattr(module, "BUYER_REVIEW", tmp_path / "review.json")
    monkeypatch.setattr(module, "OUTPUT", tmp_path / "dispatch.json")
    module.LOOP.write_text('{"loop_complete": false, "stages": [{"stage":"recognized_revenue","observed":false},{"stage":"buyer_conversation","observed":true},{"stage":"commercial_terms","observed":true}]}')
    module.SOURCE.write_text('{"end_to_end_healthy": true}')
    module.BUYER_REVIEW.write_text('{"deferred_enrichment": 1}')

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if any(
            str(part).endswith("run_buyer_review_materializer.py")
            for part in command
        ):
            raise subprocess.TimeoutExpired(command, 10)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.dispatch(mode="GUARDED_EXECUTE", timeout_seconds=10)
    assert result["executions"][0]["decision"] == "TIMED_OUT"
    assert any(row["decision"] == "DISPATCHED" for row in result["executions"][1:])


def test_default_dispatch_timeout_is_bounded(monkeypatch, tmp_path):
    import subprocess
    import empire_os.astra_dispatcher as module

    monkeypatch.setattr(module, "LOOP", tmp_path / "loop.json")
    monkeypatch.setattr(module, "SOURCE", tmp_path / "source.json")
    monkeypatch.setattr(module, "BUYER_REVIEW", tmp_path / "review.json")
    monkeypatch.setattr(module, "OUTPUT", tmp_path / "dispatch.json")
    module.LOOP.write_text(
        '{"loop_complete": false, "stages": ['
        '{"stage":"recognized_revenue","observed":true},'
        '{"stage":"buyer_conversation","observed":false},'
        '{"stage":"commercial_terms","observed":true}]}'
    )
    module.SOURCE.write_text('{"end_to_end_healthy": true}')
    module.BUYER_REVIEW.write_text('{"deferred_enrichment": 5}')

    seen = []

    def fake_run(command, **kwargs):
        seen.append(kwargs["timeout"])
        return subprocess.CompletedProcess(
            command, 0, stdout="ok", stderr=""
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.dispatch(mode="GUARDED_EXECUTE")
    assert result["executions"]
    assert all(value == 120 for value in seen)
    assert all(
        row["job"] != "buyer_deferred_enrichment"
        for row in result["executions"]
    )
