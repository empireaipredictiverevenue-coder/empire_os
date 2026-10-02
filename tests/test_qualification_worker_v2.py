import inspect
from uuid import uuid4

import empire_os.qualification_worker_v2 as worker


def _prospect():
    return {
        "id": str(uuid4()),
        "business_name": "Real Roofing Co",
        "niche": "roofing",
        "metro": "Austin",
        "phone": "5125550101",
        "website": None,
        "address": "100 Main St, Austin, TX",
        "buy_signal_score": None,
    }


def test_worker_has_no_direct_vendor_transport():
    source = inspect.getsource(worker)
    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "/rest/v1/" not in source
    assert "urllib." not in source
    assert "request_json" not in source


def test_runtime_env_mapping_is_passed_to_gateway(monkeypatch):
    seen = {}
    fake_gateway = object()
    fake_repository = object()

    monkeypatch.setattr(
        worker,
        "load_runtime_env",
        lambda path: {"EMPIRE_DATA_BACKEND": "supabase_legacy"},
    )

    def gateway_factory(env):
        seen["env"] = env
        return fake_gateway

    def repository_factory(gateway):
        seen["gateway"] = gateway
        return fake_repository

    monkeypatch.setattr(worker, "gateway_from_environment", gateway_factory)
    monkeypatch.setattr(worker, "QualificationDataRepository", repository_factory)

    assert worker._qualification_repository() is fake_repository
    assert seen["env"] == {"EMPIRE_DATA_BACKEND": "supabase_legacy"}
    assert seen["gateway"] is fake_gateway


def test_pending_prospects_delegate_scoring_identity(monkeypatch):
    seen = {}

    class Repo:
        def fetch_pending_prospects(self, **kwargs):
            seen.update(kwargs)
            return [{"id": "p1"}]

    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())

    assert worker.fetch_pending_prospects(7) == [{"id": "p1"}]
    assert seen == {
        "limit": 7,
        "scoring_engine": worker.SCORING_ENGINE,
        "scoring_version": worker.SCORING_VERSION,
    }


def test_evidence_backed_payload_uses_v2_and_preserves_provenance(monkeypatch):
    monkeypatch.setattr(
        worker,
        "enrich_prospect_for_scoring",
        lambda prospect: {
            "fields": {
                "website": "https://realroofing.example",
                "email": "sales@realroofing.example",
            },
            "enrichment_score": 80.0,
            "sources": ["website"],
            "evidence": [
                {"source": "identity_guard", "accepted": True},
                {"source": "website", "accepted": True},
            ],
            "enriched_at": "2026-09-20T11:00:00+00:00",
        },
    )

    payload = worker.build_evidence_backed_payload(_prospect())

    assert payload["scoring_version"] == "v2"
    assert payload["input_snapshot"]["website"] == "https://realroofing.example"
    assert payload["engagement_potential_score"] is None
    assert "engagement_potential" in payload["unknown_dimensions"]
    assert payload["result_payload"]["enrichment"]["sources"] == ["website"]


def test_rejected_site_does_not_become_canonical_evidence(monkeypatch):
    monkeypatch.setattr(
        worker,
        "enrich_prospect_for_scoring",
        lambda prospect: {
            "fields": {},
            "enrichment_score": 0.0,
            "sources": [],
            "evidence": [
                {
                    "source": "identity_guard",
                    "accepted": False,
                    "reasons": ["phone_mismatch"],
                },
                {"source": "website", "accepted": False},
            ],
            "enriched_at": "2026-09-20T11:00:00+00:00",
        },
    )

    prospect = _prospect()
    prospect["phone"] = None
    payload = worker.build_evidence_backed_payload(
        prospect,
        acquisition_website="https://wrong.example",
    )

    assert not payload["input_snapshot"].get("website")
    assert payload["tier"] == "insufficient_evidence"
    assert payload["result_payload"]["enrichment"]["evidence"][0]["accepted"] is False


def test_cycle_continues_after_one_prospect_failure(monkeypatch):
    prospects = [_prospect(), _prospect()]
    monkeypatch.setattr(worker, "fetch_pending_prospects", lambda limit: prospects)

    def fake_qualify(prospect):
        if prospect["id"] == prospects[0]["id"]:
            raise RuntimeError("network down")
        return {"prospect_id": prospect["id"], "tier": "warm"}

    monkeypatch.setattr(worker, "qualify_prospect", fake_qualify)
    result = worker.run_cycle(limit=2)

    assert result["attempted"] == 2
    assert result["qualified"] == 1
    assert result["failed"] == 1
    assert result["real_data_only"] is True
    assert result["outreach_enabled"] is False
    assert result["payment_enabled"] is False


def test_existing_identity_link_is_reused_without_writes(monkeypatch):
    entity_id = str(uuid4())
    monkeypatch.setattr(
        worker,
        "fetch_active_identity_link",
        lambda prospect_id: {
            "prospect_id": prospect_id,
            "entity_id": entity_id,
            "active": True,
        },
    )
    monkeypatch.setattr(
        worker,
        "_insert_identity_entity",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("no entity write should occur")
        ),
    )
    monkeypatch.setattr(
        worker,
        "_insert_identity_link",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("no link write should occur")
        ),
    )

    resolved = worker.resolve_identity(_prospect(), None, {})
    assert resolved == entity_id


def test_strict_singleton_identity_is_promoted_idempotently(monkeypatch):
    prospect = _prospect()
    entity_id = str(uuid4())
    links = []
    writes = []

    monkeypatch.setattr(
        worker,
        "build_singleton_identity_plan",
        lambda **kwargs: {
            "entity_id_candidate": entity_id,
            "canonical_name_candidate": prospect["business_name"],
            "canonical_niche_candidate": prospect["niche"],
            "canonical_metro_candidate": prospect["metro"],
            "canonical_phone_candidate": prospect["phone"],
            "canonical_website_candidate": "https://realroofing.example",
            "association_confidence": 1.0,
            "resolution_state": "evidence_resolved_candidate",
            "confidence_basis": "strict test evidence",
            "evidence_assertions": ["exact_name", "exact_phone"],
            "source": {"acquisition_source": "overpass_osm"},
        },
    )

    def fake_fetch(prospect_id):
        if links:
            return {
                "prospect_id": prospect_id,
                "entity_id": entity_id,
                "active": True,
            }
        return None

    monkeypatch.setattr(worker, "fetch_active_identity_link", fake_fetch)
    monkeypatch.setattr(
        worker,
        "_insert_identity_entity",
        lambda payload: writes.append(("entity", payload)),
    )

    def insert_link(payload):
        writes.append(("link", payload))
        links.append(payload)

    monkeypatch.setattr(worker, "_insert_identity_link", insert_link)

    resolved = worker.resolve_identity(
        prospect,
        {"source": "overpass_osm"},
        {"fields": {}, "evidence": []},
    )

    assert resolved == entity_id
    assert len(writes) == 2
    assert writes[0][0] == "entity"
    assert writes[0][1]["id"] == entity_id
    assert writes[1][0] == "link"
    assert writes[1][1]["prospect_id"] == prospect["id"]
    assert writes[1][1]["entity_id"] == entity_id


def test_identity_plan_rejection_stays_unresolved(monkeypatch):
    monkeypatch.setattr(
        worker,
        "fetch_active_identity_link",
        lambda prospect_id: None,
    )

    def reject(**kwargs):
        raise worker.SingletonIdentityPlanError("phone mismatch")

    monkeypatch.setattr(worker, "build_singleton_identity_plan", reject)
    resolved = worker.resolve_identity(
        _prospect(),
        {"source": "overpass_osm"},
        {"fields": {}, "evidence": []},
    )
    assert resolved is None


def test_payload_binds_entity_when_identity_is_known():
    entity_id = str(uuid4())
    enrichment = {
        "fields": {},
        "enrichment_score": 0.0,
        "sources": [],
        "evidence": [],
    }
    payload = worker.build_evidence_backed_payload(
        _prospect(),
        enrichment=enrichment,
        entity_id=entity_id,
    )
    assert payload["entity_id"] == entity_id


def test_identity_catchup_delegates_to_repository(monkeypatch):
    pending_id = str(uuid4())
    seen = {}

    class Repo:
        def fetch_unlinked_allocatable_prospects(self, **kwargs):
            seen.update(kwargs)
            return [{**_prospect(), "id": pending_id}]

    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())
    rows = worker.fetch_unlinked_allocatable_prospects(limit=5)

    assert [row["id"] for row in rows] == [pending_id]
    assert seen == {
        "limit": 5,
        "scoring_engine": worker.SCORING_ENGINE,
        "scoring_version": worker.SCORING_VERSION,
    }


def test_verified_enrichment_website_requires_accepted_guard_and_site():
    prospect = _prospect()
    enrichment = {
        "fields": {"website": "https://realroofing.example"},
        "evidence": [
            {"source": "identity_guard", "accepted": True},
            {"source": "website", "accepted": True},
        ],
    }
    assert worker.verified_enrichment_website(
        prospect,
        enrichment,
    ) == "https://realroofing.example"

    rejected = {
        **enrichment,
        "evidence": [
            {"source": "identity_guard", "accepted": False},
            {"source": "website", "accepted": True},
        ],
    }
    assert worker.verified_enrichment_website(prospect, rejected) == ""


def test_verified_website_never_overwrites_existing_canonical_site():
    prospect = _prospect()
    prospect["website"] = "https://existing.example"
    enrichment = {
        "fields": {"website": "https://new.example"},
        "evidence": [
            {"source": "identity_guard", "accepted": True},
            {"source": "website", "accepted": True},
        ],
    }
    assert worker.verified_enrichment_website(prospect, enrichment) == ""


def test_promote_verified_website_delegates_and_preserves_verification(monkeypatch):
    prospect = _prospect()
    website = "https://realroofing.example"
    enrichment = {
        "fields": {"website": website},
        "evidence": [
            {"source": "identity_guard", "accepted": True},
            {"source": "website", "accepted": True},
        ],
    }
    calls = []

    class Repo:
        def promote_verified_website(self, prospect_id, value):
            calls.append((prospect_id, value))
            return value

    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())

    result = worker.promote_verified_website(prospect, enrichment)

    assert result == website
    assert calls == [(prospect["id"], website)]


def test_qualification_upsert_delegates(monkeypatch):
    payload = {
        "prospect_id": "p1",
        "scoring_engine": worker.SCORING_ENGINE,
        "scoring_version": worker.SCORING_VERSION,
    }

    class Repo:
        def upsert_qualification(self, value):
            assert value is payload
            return {**value, "id": "q1"}

    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())

    assert worker.upsert_qualification(payload)["id"] == "q1"


def test_emit_event_uses_idempotent_commercial_event_repository(monkeypatch):
    seen = {}

    class Events:
        def append_idempotent(self, event):
            seen.update(event)
            return True

    monkeypatch.setattr(worker, "_commercial_event_repository", lambda: Events())
    monkeypatch.setattr(worker, "_now", lambda: "2026-09-27T12:00:00+00:00")

    worker.emit_event(
        prospect_id="p1",
        qualification_id="q1",
        payload={
            "score": 90,
            "tier": "hot",
            "evidence_confidence": 0.9,
        },
    )

    assert seen["event_type"] == "prospect_qualified_v2"
    assert seen["idempotency_key"] == "prospect:p1:qualified:v2"
    assert seen["payload"]["qualification_id"] == "q1"


def test_recc_missing_stored_website_refreshes_from_member_page(monkeypatch):
    from types import SimpleNamespace
    from empire_os.lead_sources import recc_solar

    monkeypatch.setattr(
        recc_solar,
        "_detail",
        lambda name, url: SimpleNamespace(
            raw={"business_website": "https://real-solar.example"}
        ),
    )

    website = worker.resolve_acquisition_website(
        {
            "business_name": "Real Solar Ltd",
        },
        {
            "source": "recc_solar",
            "source_url": "https://www.recc.org.uk/scheme/members/example",
            "evidence": {"raw": {}},
        },
    )

    assert website == "https://real-solar.example"


def test_stored_acquisition_website_wins_without_live_refresh(monkeypatch):
    from empire_os.lead_sources import recc_solar

    def fail(*args, **kwargs):
        raise AssertionError("live source should not be queried")

    monkeypatch.setattr(recc_solar, "_detail", fail)

    website = worker.resolve_acquisition_website(
        {
            "business_name": "Real Solar Ltd",
        },
        {
            "source": "recc_solar",
            "source_url": "https://www.recc.org.uk/scheme/members/example",
            "evidence": {
                "raw": {
                    "business_website": "https://stored.example"
                }
            },
        },
    )

    assert website == "https://stored.example"


def test_legacy_autonomous_entrypoint_is_vendor_neutral_v2_wrapper(monkeypatch):
    import inspect
    import empire_os.autonomous_qualification_worker as legacy

    source = inspect.getsource(legacy)
    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "/rest/v1/" not in source
    assert "urllib." not in source

    prospect = _prospect()
    monkeypatch.setattr(legacy, "fetch_prospect", lambda prospect_id: prospect)
    monkeypatch.setattr(
        legacy,
        "qualify_prospect",
        lambda row: {
            "prospect_id": row["id"],
            "qualification_id": "q1",
            "tier": "warm",
        },
    )

    result = legacy.qualify(prospect["id"])
    assert result["ok"] is True
    assert result["qualification_id"] == "q1"
    assert result["scoring_version"] == "v2"


def test_low_confidence_recovery_delegates_to_repository(monkeypatch):
    seen = {}
    class Repo:
        def fetch_low_confidence_recovery_candidates(self, **kwargs):
            seen.update(kwargs)
            return [{"id":"q1","prospect_id":"p1","evidence_confidence":0.49}]
    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())
    rows = worker.fetch_low_confidence_recovery_candidates(7)
    assert rows[0]["prospect_id"] == "p1"
    assert seen == {
        "limit":7,
        "scoring_engine":worker.SCORING_ENGINE,
        "scoring_version":worker.SCORING_VERSION,
        "confidence_floor":worker.MIN_DECISION_CONFIDENCE,
    }


def test_recovery_same_fingerprint_is_skipped_without_network(monkeypatch):
    prospect = _prospect()
    q = {
        "id":"q1",
        "prospect_id":prospect["id"],
        "evidence_confidence":0.30,
        "observed_dimensions":["market_fit"],
        "unknown_dimensions":["business_presence"],
        "entity_id":None,
        "result_payload":{},
    }
    monkeypatch.setattr(worker,"fetch_prospect",lambda pid: prospect)
    monkeypatch.setattr(worker,"fetch_latest_acquisition",lambda pid: None)
    fp = worker._recovery_fingerprint(prospect,None,q)
    q["result_payload"]={"evidence_recovery":{"recovery_attempted":True,"recovery_input_fingerprint":fp}}
    monkeypatch.setattr(worker,"plan_evidence_enrichment",lambda p: (_ for _ in ()).throw(AssertionError("no planner/network work")))
    result=worker.recover_low_confidence_qualification(q)
    assert result["decision"]=="skipped_unchanged_evidence"
    assert result["recovery_attempted"] is False


def test_recovery_deferred_plan_records_attempt_and_does_not_enrich(monkeypatch):
    prospect = _prospect()
    q = {
        "id":"q1","prospect_id":prospect["id"],"evidence_confidence":0.20,
        "observed_dimensions":["market_fit"],"unknown_dimensions":["business_presence"],
        "entity_id":None,"result_payload":{"existing":"keep"},
    }
    monkeypatch.setattr(worker,"fetch_prospect",lambda pid: prospect)
    monkeypatch.setattr(worker,"fetch_latest_acquisition",lambda pid: None)
    monkeypatch.setattr(worker,"plan_evidence_enrichment",lambda p:{"can_reach_target_with_available_actions":False,"selected_actions":[]})
    recorded={}
    monkeypatch.setattr(worker,"record_recovery_metadata",lambda qid,payload: recorded.update({"id":qid,"payload":payload}) or {})
    monkeypatch.setattr(worker,"qualify_prospect",lambda *a,**k: (_ for _ in ()).throw(AssertionError("must not enrich")))
    result=worker.recover_low_confidence_qualification(q)
    assert result["decision"]=="deferred_insufficient_recovery_path"
    assert recorded["payload"]["existing"]=="keep"
    meta=recorded["payload"]["evidence_recovery"]
    assert meta["recovery_changed"] is False
    assert meta["recovery_reason"]=="bounded_plan_cannot_reach_confidence_floor"


def test_recovery_requalifies_when_bounded_plan_can_reach_target(monkeypatch):
    prospect = _prospect()
    q = {
        "id":"q1","prospect_id":prospect["id"],"evidence_confidence":0.30,
        "observed_dimensions":["market_fit"],"unknown_dimensions":["business_presence"],
        "entity_id":None,"result_payload":{},
    }
    monkeypatch.setattr(worker,"fetch_prospect",lambda pid: prospect)
    monkeypatch.setattr(worker,"fetch_latest_acquisition",lambda pid: None)
    monkeypatch.setattr(worker,"plan_evidence_enrichment",lambda p:{"can_reach_target_with_available_actions":True,"selected_actions":[{"key":"first_party_site_probe"}]})
    seen={}
    def fake_qualify(p, *, recovery_context=None):
        seen.update(recovery_context or {})
        return {"prospect_id":p["id"],"qualification_id":"q1","evidence_confidence":0.55,"identity_resolved":True}
    monkeypatch.setattr(worker,"qualify_prospect",fake_qualify)
    result=worker.recover_low_confidence_qualification(q)
    assert result["decision"]=="requalified"
    assert result["previous_confidence"]==0.30
    assert result["new_confidence"]==0.55
    assert seen["previous_confidence"]==0.30
    assert seen["selected_actions"][0]["key"]=="first_party_site_probe"


def test_recovery_cycle_reports_bounded_truth(monkeypatch):
    monkeypatch.setattr(worker,"fetch_low_confidence_recovery_candidates",lambda limit:[{"prospect_id":"p1"},{"prospect_id":"p2"}])
    def recover(row):
        if row["prospect_id"]=="p1":
            return {"decision":"skipped_unchanged_evidence"}
        return {"decision":"deferred_insufficient_recovery_path"}
    monkeypatch.setattr(worker,"recover_low_confidence_qualification",recover)
    result=worker.run_evidence_recovery(2)
    assert result["attempted"]==2
    assert result["requalified"]==0
    assert result["skipped_unchanged"]==1
    assert result["deferred"]==1
    assert result["confidence_floor"]==0.50
    assert result["outreach_enabled"] is False
    assert result["allocation_enabled"] is False
    assert result["payment_enabled"] is False
