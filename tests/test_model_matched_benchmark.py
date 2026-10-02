from empire_os.model_matched_benchmark import score_case, summarize_model


def test_score_case_uses_required_concept_groups_not_subjective_judge():
    score=score_case(
        case_id='x',
        output='Persist a checkpoint, verify with tests, then retire context and keep audit evidence.',
        required_groups=[
            ['persist','checkpoint'],
            ['test','verify'],
            ['retire','clear'],
            ['audit','evidence'],
        ],
    )
    assert score.covered_groups==4
    assert score.coverage==1.0


def test_summarize_model_reports_coverage_latency_and_success_only():
    result=summarize_model([
        {'coverage':1.0,'latency_ms':100.0,'ok':True},
        {'coverage':0.5,'latency_ms':200.0,'ok':False},
    ])
    assert result=={
        'sample_count':2,
        'mean_coverage':0.75,
        'mean_latency_ms':150.0,
        'successful_calls':1,
    }


def test_benchmark_script_checkpoints_partial_progress():
    from pathlib import Path
    text=Path('scripts/benchmark_local_coder_planners.py').read_text()
    assert "completed_observation_count" in text
    assert "expected_observation_count" in text
    assert "complete=False" in text
    assert "results.append(_run_case" in text
