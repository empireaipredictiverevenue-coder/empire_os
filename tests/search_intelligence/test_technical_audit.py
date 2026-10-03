from empire_os.search_intelligence.technical_audit import build_technical_audit

def test_unifies_and_prioritizes_observed_findings():
    out=build_technical_audit(crawl_audit={"findings":[
      {"code":"page_title_missing","severity":"high","url":"https://x.test/a","message":"missing"},
      {"code":"structured_data_not_observed","severity":"low","url":"https://x.test","message":"none"}]},
      lighthouse={"opportunities":[{"code":"lighthouse_lcp","severity":"medium","title":"Improve LCP"}]})
    assert out["finding_count"]==3
    assert out["findings"][0]["severity"]=="high"
    assert out["category_counts"]["metadata"]==1
    assert out["category_counts"]["performance"]==1
    assert out["synthetic_metrics"]==0
    assert out["execution_allowed"] is False

def test_deduplicates_same_observed_issue_identity():
    row={"code":"page_title_missing","severity":"high","url":"https://x.test/a","message":"missing"}
    out=build_technical_audit(crawl_audit={"findings":[row,row]})
    assert out["finding_count"]==1

def test_empty_evidence_stays_unavailable():
    out=build_technical_audit()
    assert out["available"] is False
    assert out["finding_count"]==0
    assert out["remediation_queue"]==[]
