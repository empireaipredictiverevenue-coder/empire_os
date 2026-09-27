from empire_os.search_intelligence.quality import ContentQualityEvaluator


GOOD = {
    "originality": 0.9,
    "useful_content": 0.95,
    "intent_coverage": 0.9,
    "factual_support": 0.9,
    "source_quality": 0.85,
    "topic_completeness": 0.9,
    "page_uniqueness": 0.9,
    "internal_link_support": 0.8,
    "structured_data_validity": 0.9,
    "user_value": 0.95,
    "duplication_risk": 0.1,
    "thin_content_risk": 0.1,
    "unsupported_claims_risk": 0.1,
    "keyword_stuffing_risk": 0.05,
    "template_duplication_risk": 0.1,
    "hallucination_risk": 0.1,
}


def test_quality_pass_is_approval_only():
    result = ContentQualityEvaluator().evaluate(GOOD)
    assert result.eligible_for_approval is True
    assert result.index_decision == "eligible_for_approval"


def test_unknown_or_risky_content_is_noindex():
    result = ContentQualityEvaluator().evaluate({
        "originality": 0.9,
        "useful_content": 0.9,
        "unsupported_claims_risk": 0.9,
    })
    assert result.eligible_for_approval is False
    assert result.index_decision == "noindex,follow"


def test_factor_scores_preserve_raw_risk_values():
    result = ContentQualityEvaluator().evaluate({
        "originality": 0.9,
        "useful_content": 0.9,
        "intent_coverage": 0.9,
        "factual_support": 0.9,
        "source_quality": 0.9,
        "topic_completeness": 0.9,
        "page_uniqueness": 0.9,
        "internal_link_support": 0.9,
        "structured_data_validity": 0.9,
        "user_value": 0.9,
        "duplication_risk": 0.2,
        "thin_content_risk": 0.1,
        "unsupported_claims_risk": 0.1,
        "keyword_stuffing_risk": 0.1,
        "template_duplication_risk": 0.1,
        "hallucination_risk": 0.1,
    })
    assert result.factor_scores["duplication_risk"] == 0.2
