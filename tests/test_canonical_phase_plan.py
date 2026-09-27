from empire_os.canonical_phase_plan import (
    CLOSEOUT_SEQUENCE,
    build_canonical_phase_plan,
)


def test_phase_plan_has_one_current_phase_and_no_skipping():
    result = build_canonical_phase_plan()

    current = [
        row for row in result["phases"]
        if row["status"] == "CURRENT"
    ]
    assert len(current) == 1
    assert current[0]["phase"] == "4"
    assert result["current_phase"] == "4"
    phase_3f = next(row for row in result["phases"] if row["phase"] == "3F")
    assert phase_3f["status"] == "CLOSED_EVIDENCE_GATED"
    assert result["phase_skipping_allowed"] is False
    assert result["new_ideas_interrupt_current_phase"] is False


def test_every_phase_gets_upgrade_and_revenue_closeout():
    result = build_canonical_phase_plan()

    assert tuple(result["closeout_sequence"]) == CLOSEOUT_SEQUENCE
    assert "upgrade_and_enhance" in result["closeout_sequence"]
    assert "revenue_expansion" in result["closeout_sequence"]
    assert result["upgrade_and_enhance_required"] is True
    assert result["revenue_expansion_required"] is True
    assert all(row["revenue_features"] for row in result["phases"])


def test_plan_is_read_only_metadata():
    result = build_canonical_phase_plan()

    assert result["execution_authority"] == "none"
