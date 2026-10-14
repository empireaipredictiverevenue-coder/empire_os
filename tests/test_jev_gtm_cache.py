"""JEV bounded memory-only caching: no persistence or authority."""
from datetime import datetime, timezone
from math import inf
import pytest

import empire_os.jev_gtm_cache as cache_module
from empire_os.jev_gtm_cache import JevGtmDecisionCache

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)


def case(*, tenant="tenant:1", source_version="v1", body="Hello"):
    entity = "entity:1"
    return {
        "account": {
            "entity_id": entity, "tenant_id": tenant,
            "opportunity_key": "op:1", "entity_verified": True,
            "tenant_binding_verified": True, "description": "roofing hiring",
            "target_buyer_pools": ["local_and_smb_buyers"],
            "target_product_codes": ["managed_service"],
        },
        "signals": [{
            "signal_id": "signal:1", "signal_type": "hiring", "source_id": "jobs:1",
            "truth_class": "OBSERVED", "observed_at": NOW.isoformat(),
            "evidence_refs": ["proof:1"], "entity_id": entity,
            "tenant_id": tenant, "source_revision": source_version,
        }],
        "outreach": {"suppression_checked": False, "suppression_state": "UNKNOWN"},
        "reply": {
            "entity_id": entity, "tenant_id": tenant, "thread_linkage_verified": True,
            "source_ref": "mail:1", "received_at": NOW.isoformat(),
            "body_text": body,
        },
    }


def test_cache_reuses_only_identical_inputs(monkeypatch):
    monkeypatch.setattr(cache_module, "monotonic", lambda: 100.0)
    cache = JevGtmDecisionCache()
    a = cache.evaluate(as_of=NOW, **case())
    b = cache.evaluate(as_of=NOW, **case())
    assert a["cache_hit"] is False and b["cache_hit"] is True
    assert a["decision_fingerprint"] == b["decision_fingerprint"]
    assert cache.status()["hits"] == 1
    assert cache.status()["persistence"] is False


def test_changed_source_or_reply_or_tenant_invalidates(monkeypatch):
    monkeypatch.setattr(cache_module, "monotonic", lambda: 100)
    c = JevGtmDecisionCache()
    c.evaluate(as_of=NOW, **case())
    assert c.evaluate(as_of=NOW, **case(source_version="v2"))["cache_hit"] is False
    assert c.evaluate(as_of=NOW, **case(body="Different reply"))["cache_hit"] is False
    assert c.evaluate(as_of=NOW, **case(tenant="tenant:2"))["cache_hit"] is False


def test_ttl_expiration_requires_recomputation(monkeypatch):
    clock = {"value": 100.0}
    monkeypatch.setattr(cache_module, "monotonic", lambda: clock["value"])
    c = JevGtmDecisionCache(ttl_seconds=5)
    assert c.evaluate(as_of=NOW, **case())["cache_hit"] is False
    clock["value"] += 4
    assert c.evaluate(as_of=NOW, **case())["cache_hit"] is True
    clock["value"] += 2
    assert c.evaluate(as_of=NOW, **case())["cache_hit"] is False


def test_eviction_and_explicit_invalidation(monkeypatch):
    monkeypatch.setattr(cache_module, "monotonic", lambda: 100)
    c = JevGtmDecisionCache(max_entries=1)
    c.evaluate(as_of=NOW, **case())
    c.evaluate(as_of=NOW, **case(source_version="v2"))
    assert c.status()["entries"] == 1
    assert c.evaluate(as_of=NOW, **case())["cache_hit"] is False
    c.invalidate_all()
    assert c.status()["entries"] == 0


def test_cannot_mutate_cached_packet(monkeypatch):
    monkeypatch.setattr(cache_module, "monotonic", lambda: 100)
    c = JevGtmDecisionCache()
    first = c.evaluate(as_of=NOW, **case())
    first["action"] = "SEND"
    second = c.evaluate(as_of=NOW, **case())
    assert second["action"] != "SEND"
    assert second["execution_authority"] == "none"


def test_does_not_retain_raw_reply_text_in_cache(monkeypatch):
    monkeypatch.setattr(cache_module, "monotonic", lambda: 100)
    c = JevGtmDecisionCache()
    c.evaluate(as_of=NOW, **case(body="SECRET UNIQUE MESSAGE NEVER RETAIN"))
    assert "SECRET UNIQUE MESSAGE NEVER RETAIN" not in str(c._values)


def test_bad_bounds_and_non_json_refused():
    with pytest.raises(ValueError):
        JevGtmDecisionCache(max_entries=0)
    with pytest.raises(ValueError):
        JevGtmDecisionCache(ttl_seconds=inf)
    with pytest.raises(ValueError, match="noncanonical"):
        JevGtmDecisionCache().evaluate(as_of=NOW, **{"account": { "foo": object()}})


def test_input_size_bounded():
    with pytest.raises(ValueError, match="too large"):
        JevGtmDecisionCache().evaluate(as_of=NOW, **case(body="x" * 260000))
