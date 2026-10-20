"""Research-only source history: no duplicated discoveries from repeated files."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest

from empire_os.a2a_evidence_history_v2 import merge_evidence_history
from empire_os.a2a_signal_decision_intelligence_v2 import make_decision_intelligence
from tests.test_a2a_signal_decision_intelligence_v2_20261020 import _inputs, NOW


def _decision():
    signals, release, catalogue = _inputs()
    return make_decision_intelligence(signals, release, catalogue, now=NOW)


def _hashes():
    return dict(community="a"*64, gps="b"*64, catalogue="c"*64,
                nyc="d"*64, provenance="e"*64)


def test_only_records_first_unique_upstream_snapshot():
    decision = _decision()
    first = merge_evidence_history(None, source_hashes=_hashes(), decision=decision)
    assert first["source_snapshots_recorded"] == 1
    assert first["new_source_snapshot_recorded_this_run"]
    repeat = merge_evidence_history(first, source_hashes=_hashes(), decision=decision)
    assert repeat["source_snapshots_recorded"] == 1
    assert repeat["identical_source_snapshot_seen_again"]
    assert repeat["source_families_changed_since_previous_snapshot"] == []
    assert repeat["verified_person_or_buyer_identity_stored"] is False
    assert repeat["trained_on_inferred_conversions"] is False


def test_changed_source_creates_one_new_history_entry():
    d = _decision()
    history = merge_evidence_history(None, source_hashes=_hashes(), decision=d)
    hashes = _hashes()
    hashes["gps"] = "f" * 64
    second = merge_evidence_history(history, source_hashes=hashes, decision=d)
    assert second["source_snapshots_recorded"] == 2
    assert second["source_families_changed_since_previous_snapshot"] == ["gps"]
    assert second["snapshots"][0]["confirmed_new_buyers"] == 0


def test_rejects_bad_digests_corruption_or_fake_buyer():
    d = _decision()
    hashes = _hashes()
    hashes["gps"] = "not-a-sha"
    with pytest.raises(ValueError, match="DIGESTS"):
        merge_evidence_history(None, source_hashes=hashes, decision=d)
    history = merge_evidence_history(None, source_hashes=_hashes(), decision=d)
    corrupted = deepcopy(history)
    corrupted["snapshots"][0]["source_sha256"]["community"] = "tampered"
    with pytest.raises(ValueError, match="CORRUPTED"):
        merge_evidence_history(corrupted, source_hashes=_hashes(), decision=d)
    forged = deepcopy(d)
    forged["verified_new_buyers"] = 8
    with pytest.raises(ValueError, match="DECISION_INTELLIGENCE"):
        merge_evidence_history(None, source_hashes=_hashes(), decision=forged)


def test_history_is_bounded_without_timestamps_as_identity():
    d = _decision()
    h = None
    for i in range(100):
        hashes = _hashes()
        hashes["community"] = f"{i:064x}"
        h = merge_evidence_history(h, source_hashes=hashes, decision=d)
    assert h is not None and h["source_snapshots_recorded"] == 90
    assert h["snapshots"][0]["source_sha256"]["community"] == f"{10:064x}"
    assert h["snapshots"][-1]["source_sha256"]["community"] == f"{99:064x}"
