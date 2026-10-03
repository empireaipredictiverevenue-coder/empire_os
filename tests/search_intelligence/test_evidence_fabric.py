from empire_os.search_intelligence.evidence_fabric import plan_search_evidence


def _competitor():
    return {"signal_type":"competitor_search_presence","entity_id":"e1","observed_at":"2026-09-29T09:59:16+00:00","confidence":0.9,"payload":{"observations":[{"query":"roofing denver","url":"https://example.com","position":1,"provenance":{"source":"empire_search_fabric","quality_gate":"lexical_v1"}}]}}


def test_competitor_serp_is_preserved_but_not_misclassified():
    p=plan_search_evidence(_competitor())
    assert p.evidence_class == "competitor_serp_presence"
    assert p.destination is None
    assert p.promotion_ready is False
    assert p.provenance == ("empire_search_fabric",)
    assert p.quality_gate == "lexical_v1"
    assert "canonical_competitor_serp_destination_required" in p.blockers


def test_identity_is_deterministic_and_changes_with_evidence():
    a=_competitor(); b=_competitor()
    assert plan_search_evidence(a).evidence_id == plan_search_evidence(b).evidence_id
    b["payload"]["observations"][0]["position"]=2
    assert plan_search_evidence(a).evidence_id != plan_search_evidence(b).evidence_id


def test_ai_citation_routes_only_with_provenance_and_point_in_time():
    raw={"signal_type":"ai_citation_observation","entity_id":"e2","observed_at":"2026-10-02T20:00:00+00:00","confidence":0.95,"provenance":["observed_ai_answer"],"payload":{}}
    p=plan_search_evidence(raw)
    assert p.destination == "seo_ai_visibility_observations"
    assert p.promotion_ready is True
    raw["provenance"]=[]
    assert plan_search_evidence(raw).promotion_ready is False


def test_unknown_and_naive_timestamp_fail_closed():
    p=plan_search_evidence({"signal_type":"mystery","observed_at":"2026-10-02T20:00:00","payload":{}})
    assert p.promotion_ready is False
    assert "unsupported_signal_type" in p.blockers
    assert "valid_point_in_time_required" in p.blockers
