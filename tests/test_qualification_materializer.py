from __future__ import annotations

import os
from pathlib import Path

import pytest


_TEST_ENV_PATH = Path("/tmp/empire_os_materializer_test.env")
_TEST_ENV_PATH.write_text(
    "SUPABASE_URL=http://127.0.0.1:9\n"
    "SUPABASE_SERVICE_KEY=test-only-key\n",
    encoding="utf-8",
)

_previous_env_path = os.environ.get("EMPIRE_ENV_PATH")
os.environ["EMPIRE_ENV_PATH"] = str(_TEST_ENV_PATH)

from empire_os import autonomous_execution_bus as bus
from empire_os import gtm_engine

if _previous_env_path is None:
    os.environ.pop("EMPIRE_ENV_PATH", None)
else:
    os.environ["EMPIRE_ENV_PATH"] = _previous_env_path


def claimed_job(payload):
    return bus.ClaimedJob(
        id="parent-job",
        opportunity_id="opportunity-1",
        job_type="qualification",
        worker_adapter="omega_qualification_adapter",
        priority=0.9,
        payload=payload,
        lease_token="lease",
        attempts=1,
        max_attempts=5,
    )


def target_payload(batch_size=None):
    payload = {
        "target": {
            "niche_family": "roofing",
            "metro": "Dallas, TX",
        },
    }

    if batch_size is not None:
        payload["qualification_batch_size"] = batch_size

    return payload


def candidate():
    return {
        "id": "prospect-1",
        "business_name": "Example Roofing",
        "niche": "roofing",
        "metro": "Dallas, TX",
        "buy_signal_score": 0.9,
    }


def test_materializer_fails_closed_without_batch_size():
    with pytest.raises(
        bus.BusError,
        match="missing qualification_batch_size",
    ):
        bus._materialize_qualification_jobs(
            claimed_job(target_payload())
        )


def test_materializer_rejects_batch_above_hard_limit():
    with pytest.raises(
        bus.BusError,
        match="must be between 1 and 5",
    ):
        bus._materialize_qualification_jobs(
            claimed_job(target_payload(6))
        )


def test_materializer_checks_real_scoring_engine(
    monkeypatch,
):
    seen = {}

    def fake_rest(method, path, **kwargs):
        params = kwargs.get("params") or {}

        if path == "/rest/v1/prospects":
            return [candidate()]

        if path == "/rest/v1/prospect_qualifications":
            seen["scoring_engine"] = params.get(
                "scoring_engine"
            )
            return [{"prospect_id": "prospect-1"}]

        raise AssertionError(
            f"unexpected request: {method} {path}"
        )

    monkeypatch.setattr(bus, "_rest_json", fake_rest)

    result = bus._materialize_qualification_jobs(
        claimed_job(target_payload(1))
    )

    assert (
        seen["scoring_engine"]
        == "eq.empire_os.lead_scoring"
    )
    assert result["already_qualified"] == 1
    assert result["jobs_created"] == 0


def test_existing_child_job_not_counted_created(
    monkeypatch,
):
    post_calls = []

    def fake_rest(method, path, **kwargs):
        if path == "/rest/v1/prospects":
            return [candidate()]

        if path == "/rest/v1/prospect_qualifications":
            return []

        if (
            path == "/rest/v1/gtm_jobs"
            and method == "GET"
        ):
            return [{"id": "existing-child"}]

        if method == "POST":
            post_calls.append((path, kwargs))
            return [{"id": "unexpected"}]

        raise AssertionError(
            f"unexpected request: {method} {path}"
        )

    monkeypatch.setattr(bus, "_rest_json", fake_rest)

    result = bus._materialize_qualification_jobs(
        claimed_job(target_payload(1))
    )

    assert result["jobs_considered"] == 1
    assert result["jobs_existing"] == 1
    assert result["jobs_created"] == 0
    assert post_calls == []


def test_new_child_counted_only_after_insert(
    monkeypatch,
):
    inserted = {}

    def fake_rest(method, path, **kwargs):
        if path == "/rest/v1/prospects":
            return [candidate()]

        if path == "/rest/v1/prospect_qualifications":
            return []

        if (
            path == "/rest/v1/gtm_jobs"
            and method == "GET"
        ):
            return []

        if (
            path == "/rest/v1/gtm_jobs"
            and method == "POST"
        ):
            inserted.update(kwargs["payload"])
            return [{"id": "new-child"}]

        raise AssertionError(
            f"unexpected request: {method} {path}"
        )

    monkeypatch.setattr(bus, "_rest_json", fake_rest)

    result = bus._materialize_qualification_jobs(
        claimed_job(target_payload(1))
    )

    assert result["jobs_existing"] == 0
    assert result["jobs_created"] == 1

    assert (
        inserted["idempotency_key"]
        == "qualification:prospect-1:v1"
    )

    assert inserted["status"] == "queued"


def test_gtm_engine_emits_explicit_bounded_batch():
    opportunity = gtm_engine.Opportunity(
        niche="roofing",
        niche_family="roofing",
        metro="Dallas, TX",
        prospect_count=20,
        new_count=10,
        bridged_count=0,
        activated_count=0,
        buyer_count=1,
        buyer_capacity=10,
        high_priority_buyer_count=1,
        observed_buyer_rate=100.0,
        supply_score=0.5,
        buyer_demand_score=0.5,
        economic_score=0.5,
        fulfilment_score=0.5,
        visibility_score=0.5,
        activation_gap_score=0.5,
        market_balance="balanced",
        priority_score=0.9,
        expected_revenue_cents=10000,
        expected_margin_cents=5000,
        rationale=[],
    )

    jobs = gtm_engine.build_gtm_jobs([opportunity])

    qualification_jobs = [
        job
        for job in jobs
        if job.worker_adapter
        == "omega_qualification_adapter"
    ]

    assert len(qualification_jobs) == 1

    assert (
        qualification_jobs[0]
        .payload["qualification_batch_size"]
        == 5
    )

def test_child_insert_race_duplicate_is_idempotent(
    monkeypatch,
):
    post_attempts = 0

    def fake_rest(method, path, **kwargs):
        nonlocal post_attempts

        if path == "/rest/v1/prospects":
            return [candidate()]

        if path == "/rest/v1/prospect_qualifications":
            return []

        if (
            path == "/rest/v1/gtm_jobs"
            and method == "GET"
        ):
            return []

        if (
            path == "/rest/v1/gtm_jobs"
            and method == "POST"
        ):
            post_attempts += 1
            raise bus.BusError(
                'REST POST /rest/v1/gtm_jobs failed HTTP 409: '
                '{"code":"23505","details":'
                '"Key (idempotency_key)=(qualification:'
                'prospect-1:v1) already exists."}'
            )

        raise AssertionError(
            f"unexpected request: {method} {path}"
        )

    monkeypatch.setattr(bus, "_rest_json", fake_rest)

    result = bus._materialize_qualification_jobs(
        claimed_job(target_payload(1))
    )

    assert post_attempts == 1
    assert result["jobs_considered"] == 1
    assert result["jobs_existing"] == 1
    assert result["jobs_created"] == 0


def test_materializer_rejects_non_integer_batch():
    with pytest.raises(
        bus.BusError,
        match="must be an integer",
    ):
        bus._materialize_qualification_jobs(
            claimed_job(target_payload("five"))
        )


def test_atomic_prospect_writer_calls_ingest_rpc(monkeypatch):
    seen = {}

    def fake_rest(method, path, **kwargs):
        seen["method"] = method
        seen["path"] = path
        seen["payload"] = kwargs.get("payload")
        return {
            "decision": "created",
            "prospect": {"id": "prospect-1"},
        }

    monkeypatch.setattr(bus, "_rest_json", fake_rest)

    payload = {
        "prospect": {
            "business_name": "Acme Roofing",
            "niche": "roofing",
            "metro": "austin",
        },
        "evidence": {"source": "permits"},
        "ingest_key": "ingest-1",
        "identity_keys": [
            "phone_metro:5125550101|austin",
            "name_metro:acme roofing|austin",
        ],
    }

    result = bus._write_canonical_prospect(payload)

    assert result["decision"] == "created"
    assert seen["method"] == "POST"
    assert seen["path"] == "/rest/v1/rpc/ingest_prospect_atomic"
    assert seen["payload"] == {
        "p_prospect": payload["prospect"],
        "p_evidence": payload["evidence"],
        "p_ingest_key": payload["ingest_key"],
        "p_identity_keys": payload["identity_keys"],
    }
