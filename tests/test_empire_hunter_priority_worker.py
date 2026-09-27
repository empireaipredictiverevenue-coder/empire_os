from empire_os.hunter import priority_worker


def test_priority_worker_ranks_unresolved_omega_entities(monkeypatch):
    def fake(method, path, payload=None, prefer=None):
        if "intelligence_scores" in path:
            return [{
                "id":"s1","entity_id":"e1","score":80,"confidence":0.6,
                "features":{"qualification_evidence_confidence":0.7},
                "scored_at":"2026-09-20T12:00:00Z"
            },{
                "id":"s2","entity_id":"e2","score":50,"confidence":0.5,
                "features":{"qualification_evidence_confidence":0.5},
                "scored_at":"2026-09-20T11:00:00Z"
            }]
        if "entity_id=eq.e1" in path:
            return []
        if "entity_id=eq.e2" in path:
            return [{"id":"c2","verification_state":"verified","confidence":0.99}]
        return []
    monkeypatch.setattr(priority_worker,"request_json",fake)
    result=priority_worker.build_priority_queue(10)
    assert result["count"]==2
    assert result["items"][0]["entity_id"]=="e1"
    assert result["items"][0]["contact_ready"] is False
    assert result["outbound_actions"] is False
