from empire_os.revenue_intelligence import analyze, forecast


def test_high_intent_buyer_scores_hot_or_prime():
    r = analyze({"niche":"roofing","email":"owner@example.com","phone":"+441234567890","website":"https://example.com","contact_name":"Owner","email_verified":True,"signals":"urgent RFQ expansion new location","replied":True,"uses_lead_gen":True,"lead_budget_monthly":1500,"expected_monthly_lead_volume":20,"annual_revenue":2500000,"employees":30}, base_lead_value=25)
    assert r.tier in {"hot", "prime"}
    assert r.opportunity_score >= 65
    assert 0 < r.probability_of_purchase <= .95
    assert r.recommended_price >= 1


def test_low_signal_record_is_not_prime():
    r = analyze({"business_name":"Unknown","niche":"unknown"}, base_lead_value=25)
    assert r.tier != "prime"
    assert r.confidence < 80


def test_explicit_scores_are_respected():
    r = analyze({"intent_score":90,"urgency_score":80,"budget_score":70,"conversion_probability":.8,"contactability_score":90,"competitive_pressure":50,"ltv_score":80,"lead_purchase_propensity":.9,"expected_monthly_spend":1000,"expected_months":12,"email":"x@example.com"}, base_lead_value=20)
    assert r.opportunity_score >= 75
    assert r.expected_ltv > r.expected_monthly_value


def test_forecast_aggregates_records():
    rows=[{"niche":"roofing","email":"a@example.com","signals":"urgent buy","replied":True,"expected_monthly_spend":1000},{"niche":"plumbing","email":"b@example.com","expected_monthly_spend":200}]
    f=forecast(rows, base_lead_value=20)
    assert f["records"] == 2
    assert f["forecast_90d"] == round(f["expected_monthly_value"]*3,2)
    assert f["forecast_365d"] == round(f["expected_monthly_value"]*12,2)
