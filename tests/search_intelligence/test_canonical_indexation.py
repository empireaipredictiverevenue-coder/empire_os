from empire_os.search_intelligence.canonical import evaluate_canonical
from empire_os.search_intelligence.indexation import (
    recommend_indexability,
    recommend_transition,
)
from empire_os.search_intelligence.models import (
    PageLifecycleState,
    QualityResult,
    SearchExecutionMode,
)


def _quality(passes=True):
    return QualityResult(
        overall_score=0.9 if passes else 0.4,
        factor_scores={},
        index_decision="eligible_for_approval" if passes else "noindex,follow",
        eligible_for_approval=passes,
        known_factor_count=10 if passes else 3,
    )


def test_canonical_detects_common_variants():
    result = evaluate_canonical(
        "http://WWW.Empire-AI.co.uk/Guide/?utm_source=test"
    )
    assert result.recommended_url == "https://empire-ai.co.uk/guide"
    assert "http_https_inconsistency" in result.issues
    assert "www_non_www_inconsistency" in result.issues
    assert "route_case_inconsistency" in result.issues
    assert "trailing_slash_inconsistency" in result.issues
    assert "tracking_parameter_variant" in result.issues


def test_indexability_never_executes_in_observe():
    canonical = evaluate_canonical("https://empire-ai.co.uk/guide")
    result = recommend_indexability(
        current_state=PageLifecycleState.QUALITY_REVIEW,
        quality=_quality(True),
        canonical=canonical,
        mode=SearchExecutionMode.OBSERVE,
    )
    assert result.eligible_for_approval is True
    assert result.blocked_by_observe is True
    assert result.recommended_state is PageLifecycleState.APPROVED


def test_transition_is_recommendation_only_in_observe():
    result = recommend_transition(
        PageLifecycleState.DRAFT,
        PageLifecycleState.QUALITY_REVIEW,
        mode=SearchExecutionMode.OBSERVE,
    )
    assert result.transition_valid is True
    assert result.execution_allowed is False
    assert result.blocked_reason == "observe_mode"


def test_future_execute_mode_is_not_enabled_by_foundation():
    result = recommend_transition(
        PageLifecycleState.APPROVED,
        PageLifecycleState.PUBLISHED,
        mode=SearchExecutionMode.APPROVE_AND_EXECUTE,
    )
    assert result.transition_valid is True
    assert result.execution_allowed is False
    assert result.blocked_reason == "execution_mode_not_enabled"
