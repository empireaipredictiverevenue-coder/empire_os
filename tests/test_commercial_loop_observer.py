import json

from empire_os.commercial_loop_observer import (
    CommercialLoopObservation,
    assess_commercial_loop,
    observations_from_cycle,
    read_latest_acquisition_accepted,
    write_commercial_loop_snapshot,
)


def test_first_false_stage_is_highest_priority_blocker():
    status = assess_commercial_loop(
        {
            "real_acquisition": CommercialLoopObservation(
                "real_acquisition", True
            ),
            "qualification_v2": CommercialLoopObservation(
                "qualification_v2", True
            ),
            "omega_projection": CommercialLoopObservation(
                "omega_projection", True
            ),
            "verified_buyer_capacity": CommercialLoopObservation(
                "verified_buyer_capacity", False
            ),
        }
    )

    assert status.highest_priority_blocker == "verified_buyer_capacity"
    assert status.blocker_state == "blocked"
    assert status.loop_complete is False
    assert status.outbound_execution is False
    assert status.payment_execution is False
    assert status.revenue_mutation is False


def test_unknown_downstream_stage_stays_unknown():
    status = assess_commercial_loop(
        {
            "real_acquisition": CommercialLoopObservation(
                "real_acquisition", True
            ),
            "qualification_v2": CommercialLoopObservation(
                "qualification_v2", True
            ),
            "omega_projection": CommercialLoopObservation(
                "omega_projection", True
            ),
            "verified_buyer_capacity": CommercialLoopObservation(
                "verified_buyer_capacity", True
            ),
        }
    )

    assert status.highest_priority_blocker == "commercial_terms"
    assert status.blocker_state == "unknown"


def test_cycle_observations_surface_buyer_capacity_blocker():
    observations = observations_from_cycle(
        acquisition_accepted=10,
        qualification={"qualified": 10},
        omega={"scores_written": 2},
        buyer_readiness={"ready_count": 0},
    )
    status = assess_commercial_loop(observations)

    assert status.highest_priority_blocker == "verified_buyer_capacity"
    assert status.stages[0].observed is True
    assert status.stages[1].observed is True
    assert status.stages[2].observed is True
    assert status.stages[3].observed is False


def test_acquisition_parser_reads_real_accepted_count(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps(
            {
                "stdout_tail": (
                    '{"msg":"source_run_done","accepted": 10,"errors": 0}\n'
                    '{"msg":"crawler_run_done","accepted": 10,"errors": 0}'
                )
            }
        )
    )

    assert read_latest_acquisition_accepted(path) == 10


def test_snapshot_is_local_observe_artifact(tmp_path):
    status = assess_commercial_loop(
        {
            "real_acquisition": CommercialLoopObservation(
                "real_acquisition", False
            )
        }
    )
    target = write_commercial_loop_snapshot(
        status,
        tmp_path / "commercial" / "latest.json",
    )

    saved = json.loads(target.read_text())
    assert saved["mode"] == "OBSERVE"
    assert saved["execution_authority"] == "none"
    assert saved["highest_priority_blocker"] == "real_acquisition"
    assert saved["allocation_execution"] is False
