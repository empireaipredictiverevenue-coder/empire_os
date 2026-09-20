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
        "commercial_loop_refresh",
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
        "commercial_loop_refresh",
    ]


def test_complete_loop_dispatches_nothing_when_source_is_healthy():
    assert choose_jobs(
        {"loop_complete": True, "stages": []},
        {"end_to_end_healthy": True},
    ) == []
