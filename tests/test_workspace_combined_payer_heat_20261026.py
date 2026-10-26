"""Owner-preserving three-cohort smoke: six solar + two payers + four heat."""
from copy import deepcopy
import json
import stat

from empire_os.workspace_priority_payer_reply import (
    ANCHORS as PAYER_ANCHORS, newly_observed_priority_candidates,
    review_priority_payer_threads,
)
from tests.test_workspace_heat_pump_reply_tracking_20261026 import (
    FakeService, NOW, MILLIS, INBOUND, SENDER, PARTNER,
    make_threads, msg,
)


def all_threads(*, inbound=False):
    data = make_threads()
    for _, tid, anchor in PAYER_ANCHORS:
        data[tid] = {
            "id": tid, "messages": [
                msg(anchor, tid, SENDER, PARTNER, MILLIS, ["SENT"])
            ],
        }
    if inbound:
        _, tid, anchor = PAYER_ANCHORS[0]
        data[tid]["messages"].append(
            msg("1a88888888888888", tid, PARTNER, SENDER, INBOUND,
                ["INBOX"], reply_to="<" + anchor + "@example.test>")
        )
    return data


class Provider:
    configured = True
    def __init__(self, value): self.service = FakeService(value)
    def _service(self): return self.service


def solar_stub(*args, **kwargs):
    return {"verified_sent_anchors": 6, "monitored_threads": 6,
            "inbound_header_candidate_count": 0}


def test_combined_original_workspace_observer_both_owner_cohorts(monkeypatch):
    import scripts.poll_workspace_solar_outreach_readonly as poll
    monkeypatch.setattr(poll, "collect_workspace_solar_threads", solar_stub)
    provider = Provider(all_threads(inbound=True))
    result = poll.run(provider=provider, write=False, now=NOW)
    assert result["source_scan_complete"] is True
    assert result["verified_sent_anchors_in_live_mailbox"] == 6
    assert result["priority_payer_status"] == "TWO_PRIORITY_PAYER_THREADS_REVIEWED"
    assert result["priority_payer_threads_verified"] == 2
    assert result["heat_pump_verified_sent_anchors"] == 4
    assert result["heat_pump_inbound_header_candidates"] == 0
    assert result["priority_payer_snapshot_written"] is False
    assert result["heat_pump_snapshot_written"] is False
    assert result["outbound_sent"] is False
    assert {x[1] for x in provider.service.accessed} == set(all_threads())


def test_priority_payer_original_reader_keeps_idempotency():
    data = all_threads(inbound=True)
    owner = {tid: data[tid] for _, tid, _ in PAYER_ANCHORS}
    review = review_priority_payer_threads(owner, now=NOW)
    assert review["inbound_header_candidate_count"] == 1
    assert review["contact_or_buyer_authority_verified"] is False
    assert newly_observed_priority_candidates(review, None) == 1
    assert newly_observed_priority_candidates(review, deepcopy(review)) == 0


def test_three_cohort_private_snapshots_are_independent(monkeypatch, tmp_path):
    import scripts.poll_workspace_solar_outreach_readonly as poll
    monkeypatch.setattr(poll, "collect_workspace_solar_threads", solar_stub)
    monkeypatch.setattr(poll, "newly_observed_workspace_replies",
                        lambda *args, **kwargs: 0)
    monkeypatch.setattr(poll, "OUTPUT", tmp_path/"solar.json")
    monkeypatch.setattr(poll, "PRIORITY_OUTPUT", tmp_path/"priority.json")
    monkeypatch.setattr(poll, "HEAT_OUTPUT", tmp_path/"heat.json")
    provider = Provider(all_threads(inbound=True))
    first = poll.run(provider=provider, write=True, now=NOW, output=poll.OUTPUT)
    assert first["snapshot_written"] is True
    assert first["priority_payer_snapshot_written"] is True
    assert first["priority_payer_new_inbound_candidates"] == 1
    assert first["heat_pump_snapshot_written"] is True
    assert first["heat_pump_new_inbound_candidates"] == 0
    second = poll.run(provider=provider, write=True, now=NOW, output=poll.OUTPUT)
    assert second["priority_payer_new_inbound_candidates"] == 0
    for path in (poll.OUTPUT,poll.PRIORITY_OUTPUT,poll.HEAT_OUTPUT):
        assert path.is_file()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        data=json.loads(path.read_text())
        assert "body" not in data and "raw" not in data


def test_absent_priority_does_not_drop_heat_or_solar(monkeypatch):
    import scripts.poll_workspace_solar_outreach_readonly as poll
    monkeypatch.setattr(poll,"collect_workspace_solar_threads",solar_stub)
    result=poll.run(provider=Provider(make_threads()),write=False,now=NOW)
    assert result["source_scan_complete"] is True
    assert result["priority_payer_status"] == "HELD_PRIORITY_PAYER_REVIEW_UNAVAILABLE"
    assert result["heat_pump_verified_sent_anchors"] == 4
