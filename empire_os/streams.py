"""Redis Streams topology for Empire OS.
Decouples HTTP from async processing: intake -> waterfall -> deliver -> payout.

Requires: pip install redis[hiredis]

Topology:
  lead:intake       — new leads from API/webhook
  waterfall:jobs    — enrichment tasks for waterfall providers
  deliver:queue     — delivery tasks (webhook + email)
  payout:queue      — settlement/payout tasks
  _dlq              — dead-letter queue (all consumers)

Consumer pattern:
  XREADGROUP GROUP <group> <consumer> BLOCK 5000 COUNT 10 STREAMS <stream> >
"""
import os, json, time, logging
from datetime import datetime

logger = logging.getLogger("empire-streams")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
STREAMS = ["lead:intake", "waterfall:jobs", "deliver:queue", "payout:queue", "_dlq"]
GROUPS = {
    "lead:intake": ["intake_worker"],
    "waterfall:jobs": ["waterfall_worker"],
    "deliver:queue": ["deliver_worker"],
    "payout:queue": ["payout_worker"],
}

class StreamClient:
    def __init__(self, url=None):
        self.url = url or REDIS_URL
        self.rc = None

    def connect(self):
        import redis
        self.rc = redis.from_url(self.url, decode_responses=True)
        for stream in STREAMS:
            for group in GROUPS.get(stream, []):
                try:
                    self.rc.xgroup_create(stream, group, id="0", mkstream=True)
                except redis.ResponseError as e:
                    if "BUSYGROUP" not in str(e):
                        raise
        logger.info("streams connected: %s", ", ".join(STREAMS))

    def push(self, stream, data, maxlen=10000):
        data["_ts"] = datetime.utcnow().isoformat()
        return self.rc.xadd(stream, data, maxlen=maxlen)

    def pull(self, stream, group, consumer, count=10, block=5000):
        raw = self.rc.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block)
        if not raw:
            return []
        msgs = []
        for _, entries in raw:
            for mid, data in entries:
                msgs.append((mid, data))
                self.rc.xack(stream, group, mid)
        return msgs

    def dlq(self, original_stream, msg_id, data, reason):
        data["_dlq_from"] = original_stream
        data["_dlq_msg_id"] = msg_id
        data["_dlq_reason"] = reason
        self.push("_dlq", data)

    def stats(self):
        info = {}
        for stream in STREAMS:
            try:
                info[stream] = self.rc.xlen(stream)
            except:
                info[stream] = -1
        return info
