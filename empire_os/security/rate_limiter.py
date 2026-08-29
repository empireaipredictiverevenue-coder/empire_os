"""
Audit 3.1 — Rate Limiting (token bucket, in-process)
Standalone rate limiter used by API gateway mock + BSC settlement.
MOCKED external: distributed Redis limiter / Cloudflare edge. Real local bucket.
"""
import time
from dataclasses import dataclass, field


@dataclass
class RateLimitConfig:
    rate_per_min: int = 100       # Audit 3.1 Layer2: 100 req/min per IP
    burst: int = 10
    # BSC settlement limits (Audit 5.4)
    per_wallet_per_hour: int = 100
    per_ip_per_hour: int = 1000


class RateLimiter:
    def __init__(self, cfg: RateLimitConfig = None):
        self.cfg = cfg or RateLimitConfig()
        self._buckets = {}      # key -> (tokens, last_ts)
        self._wallet_hour = {}  # wallet -> [count, window_start]
        self._ip_hour = {}

    def _bucket(self, key, capacity, refill_per_sec):
        now = time.time()
        tokens, last = self._buckets.get(key, (capacity, now))
        tokens = min(capacity, tokens + (now - last) * refill_per_sec)
        if tokens < 1:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1, now)
        return True

    def allow(self, key: str) -> bool:
        refill = self.cfg.rate_per_min / 60.0
        return self._bucket(key, max(self.cfg.burst, self.cfg.rate_per_min), refill)

    def allow_wallet(self, wallet: str) -> bool:
        return self._window(wallet, self._wallet_hour,
                            self.cfg.per_wallet_per_hour, 3600)

    def allow_ip(self, ip: str) -> bool:
        return self._window(ip, self._ip_hour, self.cfg.per_ip_per_hour, 3600)

    def _window(self, key, store, limit, secs):
        now = time.time()
        cnt, start = store.get(key, (0, now))
        if now - start >= secs:
            cnt, start = 0, now
        if cnt >= limit:
            store[key] = (cnt, start)
            return False
        store[key] = (cnt + 1, start)
        return True


if __name__ == "__main__":
    rl = RateLimiter()
    print("allow x5:", [rl.allow("ip:1.2.3.4") for _ in range(5)])
    print("wallet allow:", rl.allow_wallet("0x1339b487046B0ad924a10c20b1791608EA8595a8"))
