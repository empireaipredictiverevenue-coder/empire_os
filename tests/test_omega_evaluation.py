from empire_os.omega_evaluation import evaluate


def test_evaluation_is_read_only_and_does_not_invent_revenue():
    result = evaluate({"business_name": "Example", "niche": "roofing"})
    assert result["grade"] in {"A", "B", "C", "D"}
    assert result["expected_revenue"] is None
    assert result["expected_gross_profit"] is None
    assert result["billable"] is False
    assert result["execution_authority"] == "none"
    assert result["model_version"]


def test_grade_matches_score():
    result = evaluate({})
    score = result["score"]
    assert result["grade"] == ("A" if score >= 90 else "B" if score >= 70 else "C" if score >= 40 else "D")


def test_eight_domains_are_coverage_not_fabricated_scores():
    result = evaluate({"business_name": "Example", "niche": "roofing"})
    domains = result["legacy_eight_domain_evidence"]
    assert len(domains) == 8
    assert domains["lead_quality"]["status"] == "evidenced"
    assert domains["self_learning"]["status"] == "missing"
    assert result["value_meter"]["verified_realized_revenue"] is None


def test_value_meter_uses_explicit_evidence_only():
    empty = evaluate({"niche": "roofing"})
    evidenced = evaluate({"niche": "roofing", "expected_revenue": 1000, "expected_cost": 400})
    assert empty["value_meter"]["expected_revenue"] is None
    assert evidenced["value_meter"]["revenue_evidence_available"]
    assert evidenced["value_meter"]["gross_profit_evidence_available"]
    assert evidenced["billable"] is False
