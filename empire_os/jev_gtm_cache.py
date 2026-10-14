"""Bounded, memory-only JEV GTM decision cache.

No new database, socket, timers, or background task. Cache entries contain
non-executable recommendation packets only; never persist raw source inputs.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from time import monotonic
from typing import Any, Mapping

from empire_os.jev_gtm_v2 import build_jev_gtm_decision, POLICY_VERSION, SCHEMA_VERSION


class JevGtmDecisionCache:
    def __init__(self, *, max_entries: int = 128, ttl_seconds: float = 300) -> None:
        if type(max_entries) is not int or not 1 <= max_entries <= 1000:
            raise ValueError("bounded entry count required")
        if not isinstance(ttl_seconds, (float, int)) or not 1 <= ttl_seconds <= 3600:
            raise ValueError("bounded TTL required")
        self.max_entries = max_entries
        self.ttl_seconds = float(ttl_seconds)
        self._values: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def evaluate(self, *, as_of: datetime, **case: Any) -> dict[str, Any]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("timezone-aware as_of required")
        # Only plain JSON-compatible, bounded input envelopes may be cached.
        # This is a fingerprint, not evidence of a canonical source or auth.
        material = {
            "schema": SCHEMA_VERSION, "policy": POLICY_VERSION,
            "as_of": as_of.isoformat(), "case": case,
        }
        try:
            encoded = json.dumps(
                material, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("noncanonical cache input") from exc
        if len(encoded) > 250_000:
            raise ValueError("cache input too large")
        key = sha256(encoded).hexdigest()
        now = monotonic()
        cached = self._values.get(key)
        if cached is not None and cached[0] > now:
            self._values.move_to_end(key)
            self.hits += 1
            return {**deepcopy(cached[1]), "cache_hit": True}
        if cached is not None:
            del self._values[key]
        self.misses += 1
        packet = build_jev_gtm_decision(as_of=as_of, **case)
        if packet["execution_authority"] != "none" or packet["mode"] != "OBSERVE":
            raise ValueError("cache accepts shadow recommendations only")
        # Cache only materialized, read-only output, not raw correspondence.
        self._values[key] = (now + self.ttl_seconds, deepcopy(packet))
        self._values.move_to_end(key)
        while len(self._values) > self.max_entries:
            self._values.popitem(last=False)
        return {**deepcopy(packet), "cache_hit": False}

    def invalidate_all(self) -> None:
        """Explicit invocation by the owning event handler; never scheduled."""
        self._values.clear()

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": "empire.jev.gtm_cache_status.v1",
            "entries": len(self._values),
            "max_entries": self.max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "persistence": False,
            "execution_authority": "none",
            "outbound_sent": False,
        }
