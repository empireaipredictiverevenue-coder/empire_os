from empire_os.commercial_evidence_inventory import fetch_qualification_omega_inventory
from datetime import datetime, timezone


def test_persisted_inventory_survives_zero_activity_cycle():
    calls=[]
    def reader(path, params):
        calls.append((path, params))
        return [{'id':'a','entity_id':'e','scored_at':'2026-10-09T12:00:00Z'}]
    found=fetch_qualification_omega_inventory(reader, now=datetime(2026,10,9,13,tzinfo=timezone.utc))
    assert all(v.observed is True for v in found.values())
    assert len(calls)==2
    assert calls[0][1]['scoring_version']=='eq.v2'
    assert calls[1][1]['model_key']=='eq.omega-2.0-baseline'


def test_empty_inventory_not_invented():
    found=fetch_qualification_omega_inventory(lambda *_: [])
    assert all(v.observed is False for v in found.values())


def test_reader_failure_unknown_not_false():
    def reader(*_):raise RuntimeError('unavailable')
    found=fetch_qualification_omega_inventory(reader)
    assert all(v.observed is None for v in found.values())


def test_malformed_record_not_accepted():
    found=fetch_qualification_omega_inventory(lambda *_:[{'id':'a'}])
    assert all(v.observed is None for v in found.values())


def test_stale_inventory_cannot_claim_current_readiness():
    found = fetch_qualification_omega_inventory(
        lambda *_: [{'id':'a','entity_id':'e','scored_at':'2026-09-01T00:00:00Z'}],
        now=datetime(2026,10,9,13,tzinfo=timezone.utc),
    )
    assert all(v.observed is None for v in found.values())
    assert all('stale' in v.detail for v in found.values())


def test_unconfigured_reader_does_not_mean_empty_inventory():
    found=fetch_qualification_omega_inventory(lambda *_: None)
    assert all(v.observed is None for v in found.values())
