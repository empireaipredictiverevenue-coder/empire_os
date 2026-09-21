from types import SimpleNamespace

from empire_os.crawler_runner import ingest_candidate, run_source_safe
from empire_os.lead_sources import LeadCandidate


def candidate():
    return LeadCandidate(
        name="Real Roofing LLC",
        phone="512-555-0101",
        niche="roofing",
        metro="Austin",
        state="TX",
        source="overpass_osm",
        lead_score=82,
        url="https://source.example/record/123",
    )


def test_ingest_candidate_new_uses_atomic_writer():
    written = []

    def reader(path, params):
        assert path == "/rest/v1/prospects"
        return []

    def writer(payload):
        written.append(payload)
        return {
            "decision": "created",
            "prospect_id": "prospect-1",
        }

    result = ingest_candidate(candidate(), reader=reader, writer=writer)

    assert result["decision"] == "created"
    assert len(written) == 1
    assert written[0]["prospect"]["business_name"] == "Real Roofing LLC"
    assert written[0]["identity_keys"] == [
        "phone_metro:5125550101|austin",
        "name_metro:real roofing llc|austin",
    ]


def test_ingest_candidate_match_is_read_only():
    writer_calls = []

    def reader(path, params):
        return [{
            "id": "existing-1",
            "business_name": "Real Roofing LLC",
            "phone": "5125550101",
            "metro": "Austin",
            "niche": "roofing",
        }]

    def writer(payload):
        writer_calls.append(payload)
        raise AssertionError("matched prospect must not write")

    result = ingest_candidate(candidate(), reader=reader, writer=writer)

    assert result["decision"] == "matched"
    assert result["prospect"]["id"] == "existing-1"
    assert writer_calls == []


def test_run_source_safe_fails_closed_without_legacy_fallback(monkeypatch):
    candidates = [
        candidate(),
        LeadCandidate(
            name="Second Real Roofing LLC",
            niche="roofing",
            metro="Austin",
            source="overpass_osm",
            url="https://source.example/record/456",
        ),
    ]

    src = SimpleNamespace(
        name="permits",
        tier="real",
        requires=[],
        run_fn=lambda metro=None: iter(candidates),
    )

    calls = []

    def fail_ingest(cand):
        calls.append(cand.name)
        raise RuntimeError("ingest_prospect_atomic unavailable")

    monkeypatch.setattr(
        "empire_os.crawler_runner.ingest_candidate",
        fail_ingest,
    )
    monkeypatch.setattr(
        "empire_os.crawler_runner.log",
        lambda *args, **kwargs: None,
    )

    found, accepted, errors = run_source_safe(src, None, False)

    assert found == 2
    assert accepted == 0
    assert errors == 2
    assert calls == ["Real Roofing LLC", "Second Real Roofing LLC"]


def test_run_source_safe_dry_run_never_ingests(monkeypatch):
    src = SimpleNamespace(
        name="permits",
        tier="real",
        requires=[],
        run_fn=lambda metro=None: iter([candidate()]),
    )

    monkeypatch.setattr(
        "empire_os.crawler_runner.ingest_candidate",
        lambda cand: (_ for _ in ()).throw(
            AssertionError("dry-run must not ingest")
        ),
    )
    monkeypatch.setattr(
        "empire_os.crawler_runner.log",
        lambda *args, **kwargs: None,
    )

    found, accepted, errors = run_source_safe(src, None, True)

    assert (found, accepted, errors) == (1, 0, 0)

def test_ingest_candidate_accepts_direct_endpoint_payload():
    writes = []

    payload = {
        "name": "Observed Plumbing Ltd",
        "phone": "020 7946 0101",
        "niche": "plumbing",
        "metro": "London",
        "source": "aeo_form",
        "lead_score": 71,
        "url": "https://source.example/form/456",
    }

    def reader(path, params):
        return []

    def writer(body):
        writes.append(body)
        return {
            "decision": "created",
            "prospect": {"id": "prospect-real-2"},
        }

    result = ingest_candidate(payload, reader=reader, writer=writer)

    assert result["decision"] == "created"
    assert result["prospect"]["id"] == "prospect-real-2"
    assert writes[0]["prospect"]["business_name"] == "Observed Plumbing Ltd"
    assert writes[0]["prospect"]["contact_source"] == "aeo_form"

def test_run_source_safe_respects_max_candidates(monkeypatch):
    candidates = [
        candidate(),
        LeadCandidate(
            name="Second Real Roofing LLC",
            niche="roofing",
            metro="Austin",
            source="overpass_osm",
        ),
    ]

    src = SimpleNamespace(
        name="permits",
        tier="real",
        requires=[],
        run_fn=lambda metro=None: iter(candidates),
    )

    calls = []

    monkeypatch.setattr(
        "empire_os.crawler_runner.ingest_candidate",
        lambda cand: calls.append(cand.name) or {
            "decision": "created",
            "prospect": {"id": "prospect-1"},
        },
    )
    monkeypatch.setattr(
        "empire_os.crawler_runner.log",
        lambda *args, **kwargs: None,
    )

    found, accepted, errors = run_source_safe(
        src,
        None,
        False,
        max_candidates=1,
    )

    assert (found, accepted, errors) == (1, 1, 0)
    assert calls == ["Real Roofing LLC"]


def test_run_source_safe_rejects_signal_before_ingest(monkeypatch):
    signal_candidate = LeadCandidate(
        name="Example Property Owner LLC (Queens)",
        phone="212-555-0101",
        niche="roofing",
        metro="NYC",
        source="permits_nyc",
        url="https://example.test/permit/123",
        raw={"job__": "123"},
    )

    src = SimpleNamespace(
        name="permits",
        tier="real",
        requires=[],
        run_fn=lambda metro=None: iter([signal_candidate]),
    )

    calls = []

    monkeypatch.setattr(
        "empire_os.crawler_runner.ingest_candidate",
        lambda cand: calls.append(cand.name),
    )
    monkeypatch.setattr(
        "empire_os.crawler_runner.log",
        lambda *args, **kwargs: None,
    )

    found, accepted, errors = run_source_safe(
        src,
        None,
        False,
        max_candidates=1,
    )

    assert (found, accepted, errors) == (1, 0, 0)
    assert calls == []



def test_main_returns_nonzero_when_only_source_errors_and_accepts_nothing(
    monkeypatch,
):
    import sys
    import empire_os.crawler_runner as crawler
    import empire_os.lead_sources as lead_sources

    src = SimpleNamespace(
        name="overpass",
        tier="real",
        requires=[],
        run_fn=lambda metro=None: iter(()),
    )
    monkeypatch.setitem(lead_sources._REGISTRY, "overpass", src)
    monkeypatch.setattr(crawler, "_import_sources", lambda: None)
    monkeypatch.setattr(
        crawler,
        "run_source_safe",
        lambda *args, **kwargs: (0, 0, 1),
    )
    monkeypatch.setattr(crawler, "log", lambda *args, **kwargs: None)
    monkeypatch.setattr(crawler.signal, "signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(crawler.signal, "alarm", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["crawler_runner", "--source", "overpass", "--max-candidates", "1"],
    )

    assert crawler.main() == 1


def test_main_keeps_healthy_zero_result_as_success(monkeypatch):
    import sys
    import empire_os.crawler_runner as crawler
    import empire_os.lead_sources as lead_sources

    src = SimpleNamespace(
        name="overpass",
        tier="real",
        requires=[],
        run_fn=lambda metro=None: iter(()),
    )
    monkeypatch.setitem(lead_sources._REGISTRY, "overpass", src)
    monkeypatch.setattr(crawler, "_import_sources", lambda: None)
    monkeypatch.setattr(
        crawler,
        "run_source_safe",
        lambda *args, **kwargs: (0, 0, 0),
    )
    monkeypatch.setattr(crawler, "log", lambda *args, **kwargs: None)
    monkeypatch.setattr(crawler.signal, "signal", lambda *args, **kwargs: None)
    monkeypatch.setattr(crawler.signal, "alarm", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["crawler_runner", "--source", "overpass", "--max-candidates", "1"],
    )

    assert crawler.main() == 0



def test_run_source_safe_logs_matched_inventory_separately(monkeypatch):
    src = SimpleNamespace(
        name="overpass",
        tier="real",
        requires=[],
        run_fn=lambda metro=None: iter([candidate()]),
    )
    events = []

    monkeypatch.setattr(
        "empire_os.crawler_runner.ingest_candidate",
        lambda cand: {
            "decision": "matched",
            "prospect": {"id": "existing-1"},
        },
    )
    monkeypatch.setattr(
        "empire_os.crawler_runner.log",
        lambda level, msg, **kwargs: events.append((level, msg, kwargs)),
    )

    found, accepted, errors = run_source_safe(src, None, False)

    assert (found, accepted, errors) == (1, 1, 0)
    assert any(msg == "prospect_matched" for _, msg, _ in events)
    assert not any(msg == "prospect_acquired" for _, msg, _ in events)
