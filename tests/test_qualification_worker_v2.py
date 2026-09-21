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

    def fail_request(*args, **kwargs):
        raise AssertionError("no write should occur")

    monkeypatch.setattr(worker, "request_json", fail_request)
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

    def fake_request(method, path, payload=None, prefer=None):
        writes.append((method, path, payload, prefer))
        if "prospect_entity_links" in path and method == "POST":
            links.append(payload)
        return None

    monkeypatch.setattr(worker, "request_json", fake_request)
    resolved = worker.resolve_identity(
        prospect,
        {"source": "overpass_osm"},
        {"fields": {}, "evidence": []},
    )

    assert resolved == entity_id
    assert len(writes) == 2
    assert "business_entities" in writes[0][1]
    assert writes[0][2]["id"] == entity_id
    assert "prospect_entity_links" in writes[1][1]
    assert writes[1][2]["prospect_id"] == prospect["id"]
    assert writes[1][2]["entity_id"] == entity_id


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


def test_payload_binds_entity_when_identity_is_known(monkeypatch):
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


def test_identity_catchup_skips_rows_already_attempted(monkeypatch):
    pending_id = str(uuid4())
    attempted_id = str(uuid4())

    def fake_request(method, path, payload=None, prefer=None):
        if "prospect_qualifications" in path:
            return [
                {
                    "prospect_id": attempted_id,
                    "result_payload": {
                        "identity_resolution": {"attempted": True}
                    },
                },
                {
                    "prospect_id": pending_id,
                    "result_payload": {},
                },
            ]
        if "/rest/v1/prospects?" in path:
            return [
                {
                    **_prospect(),
                    "id": pending_id,
                }
            ]
        raise AssertionError(path)

    monkeypatch.setattr(worker, "request_json", fake_request)
    rows = worker.fetch_unlinked_allocatable_prospects(limit=5)
    assert [row["id"] for row in rows] == [pending_id]


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


def test_promote_verified_website_patches_and_verifies(monkeypatch):
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

    def fake_request(method, path, payload=None, prefer=None):
        calls.append((method, path, payload, prefer))
        if method == "GET":
            return [{"id": prospect["id"], "website": website}]
        return None

    monkeypatch.setattr(worker, "request_json", fake_request)
    result = worker.promote_verified_website(prospect, enrichment)
    assert result == website
    assert calls[0][0] == "PATCH"
    assert calls[0][2] == {"website": website}
    assert calls[0][3] == "return=minimal"
    assert calls[1][0] == "GET"
