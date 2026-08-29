import Redis from "ioredis";
import { CONFIG } from "../config/index.js";

const redis = new Redis(CONFIG.REDIS_URL, {
  maxRetriesPerRequest: 3,
  retryStrategy: (times) => Math.min(times * 100, 2000),
});

redis.on("error", (err) => console.error("[Redis]", err.message));
redis.on("connect", () => console.log("[Redis] connected"));

/**
 * Sliding window rate limiter via Redis sorted sets.
 * Returns { allowed, remaining, resetAt } for each service.
 */
export class RateLimiter {
  constructor(service, limitPerMin) {
    this.service = service;
    this.limit = limitPerMin;
    this.windowMs = 60_000;
  }

  async check() {
    const now = Date.now();
    const key = `ratelimit:${this.service}`;
    const clearBefore = now - this.windowMs;

    const multi = redis.multi();
    multi.zremrangebyscore(key, 0, clearBefore);
    multi.zadd(key, now, `${now}:${Math.random().toString(36).slice(2)}`);
    multi.zcard(key);
    multi.pexpire(key, this.windowMs);

    const results = await multi.exec();
    const count = results[2][1];

    const allowed = count <= this.limit;
    const remaining = Math.max(0, this.limit - count);
    const resetAt = new Date(now + this.windowMs);

    if (!allowed) {
      console.warn(
        `[RateLimiter] ${this.service} blocked: ${count}/${this.limit} req/min`
      );
    }

    return { allowed, remaining, resetAt };
  }

  async waitForSlot(maxWaitMs = 30_000) {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      const { allowed } = await this.check();
      if (allowed) return true;
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error(`Rate limit wait timeout for ${this.service} after ${maxWaitMs}ms`);
  }
}

// Pre-configured limiters
export const limiters = {
  resend: new RateLimiter("resend", CONFIG.RATE_LIMITS.resend),
  twenty: new RateLimiter("twenty", CONFIG.RATE_LIMITS.twenty),
  waterfall: new RateLimiter("waterfall", CONFIG.RATE_LIMITS.waterfall),
  glm: new RateLimiter("glm", CONFIG.RATE_LIMITS.glm),
};

export { redis };
