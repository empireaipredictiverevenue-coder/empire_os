import scripts.run_buyer_deferred_enrichment as worker


class Queue:
    def __init__(self, pending, deferred=0, running=0):
        self.counts = {"pending": pending, "deferred": deferred, "running": running}

    def snapshot(self):
        return {"deferred_by_status": self.counts}


def test_capacity_uses_full_bound_for_large_backlog_on_idle_host(monkeypatch):
    monkeypatch.setattr(worker.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(worker.os, "getloadavg", lambda: (2.0, 2.0, 2.0))
    result = worker.adaptive_capacity(queue=Queue(2000))
    assert result["limit"] == 48
    assert result["workers"] == 8


def test_capacity_backs_off_under_high_host_pressure(monkeypatch):
    monkeypatch.setattr(worker.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(worker.os, "getloadavg", lambda: (12.0, 12.0, 12.0))
    result = worker.adaptive_capacity(queue=Queue(2000))
    assert result["workers"] == 4
    assert result["limit"] == 24


def test_capacity_shrinks_to_small_backlog(monkeypatch):
    monkeypatch.setattr(worker.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(worker.os, "getloadavg", lambda: (1.0, 1.0, 1.0))
    result = worker.adaptive_capacity(queue=Queue(3))
    assert result["workers"] == 3
    assert result["limit"] == 3
