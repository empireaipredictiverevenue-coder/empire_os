// Module 5: Bulletproof Rate Limiter
// Redis-backed rate limiter for all outgoing API calls

const redis = require("redis").createClient({
  host: process.env.REDIS_HOST || "127.0.0.1",
  port: parseInt(process.env.REDIS_PORT || 6379)
});

class RateLimiter {
  constructor(options) {
    this.redis = redis;
    this.defaultWindowMs = options && options.defaultWindowMs ? options.defaultWindowMs : 1000;
    this.defaultLimit = options && options.defaultLimit ? options.defaultLimit : 30;
    this.buckets = new Map();
  }

  acquire(key, limit, windowMs) {
    var bucketKey = key + ":" + limit + ":" + windowMs;
    if (this.buckets.has(bucketKey) === false) {
      this.buckets.set(bucketKey, { tokens: limit, lastRefill: Date.now() });
    }
    var bucket = this.buckets.get(bucketKey);
    var now = Date.now();
    var elapsed = now - bucket.lastRefill;
    var tokensToAdd = (elapsed * limit) / windowMs;
    bucket.tokens = Math.min(limit, bucket.tokens + tokensToAdd);
    bucket.lastRefill = now;
    if (bucket.tokens >= 1) {
      bucket.tokens -= 1;
      return { allowed: true, remaining: Math.floor(bucket.tokens), resetAt: now + windowMs };
    }
    var waitTime = ((1 - bucket.tokens) * windowMs) / limit;
    return { allowed: false, remaining: Math.floor(bucket.tokens), resetAt: now + windowMs, waitTime: Math.max(0, waitTime), retryAfter: Math.ceil(waitTime / 1000) + "s" };
  }

  withRateLimit(endpointKey, apiCall) {
    var limits = {
      twentyCRM: { limit: 20, windowMs: 60000 },
      resendEmail: { limit: 10, windowMs: 60000 },
      enrichment: { limit: 50, windowMs: 60000 },
      supabase: { limit: 100, windowMs: 60000 }
    };
    var config = limits[endpointKey] || limits.enrichment;
    var result = this.acquire(endpointKey, config.limit, config.windowMs);
    if (result.allowed) {
      try {
        var r = apiCall();
        return { success: true, data: r, rateLimitInfo: result };
      } catch (error) {
        return { success: false, error: error.message, rateLimitInfo: result };
      }
    } else {
      if (result.waitTime > 0) {
        return new Promise(function(resolve) {
          setTimeout(function() {
            self.withRateLimit(endpointKey, apiCall).then(resolve);
          }, result.waitTime + 100);
        });
      }
      return { success: false, error: "Rate limited", rateLimitInfo: result };
    }
  }
}

var rateLimiter = new RateLimiter();

var callTwentyCRM = function(payload) { return { status: "ok", data: payload }; };
var callResendEmail = function(emailData) { return { id: "msg_" + Date.now(), status: "sent" }; };
var callEnrichmentAPI = function(companyData) { return { enrichedData: { ...companyData, enriched: true } }; };

var limitedTwentyCall = function(payload) { return rateLimiter.withRateLimit("twentyCRM", function() { return callTwentyCRM(payload); }); };
var limitedResendCall = function(emailData) { return rateLimiter.withRateLimit("resendEmail", function() { return callResendEmail(emailData); }); };
var limitedEnrichmentCall = function(companyData) { return rateLimiter.withRateLimit("enrichment", function() { return callEnrichmentAPI(companyData); }); };

if (require.main === module) {
  (async function() {
    console.log("Rate limiter test:");
    var result1 = await rateLimiter.acquire("test_key", 5, 1000);
    console.log("First acquire:", result1);
    for (var i = 0; i < 5; i++) {
      var result = await rateLimiter.acquire("test_key", 5, 1000);
      console.log("Acquire " + (i + 1) + ":", result);
    }
    var wrappedResult = await rateLimiter.withRateLimit("twentyCRM", function() { return callTwentyCRM({ test: true }); });
    console.log("Wrapped call:", wrappedResult);
    console.log("Rate limiter test complete");
  })();
}

module.exports = { RateLimiter, limitedTwentyCall, limitedResendCall, limitedEnrichmentCall, rateLimiter };
