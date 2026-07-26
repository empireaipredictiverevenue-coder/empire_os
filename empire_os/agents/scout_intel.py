"""
scout_intel.py — Empire Scout Intel: file ingestion + health endpoint.
Pulls /root/inbox/phone/* from D: drops, parses PDFs + .md/.txt
Writes summary to /root/feedback/raw_intel/<name>.json
Cadence: 60s (configurable via INTERVAL env)
Health endpoint: http://localhost:9098/health
"""
from __future__ import annotations
import hashlib, json, os, threading, time
from datetime import datetime, timezone
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

INBOX = Path("/root/inbox/phone")
RAW = Path("/root/feedback/raw_intel")
OUT = Path("/root/feedback/scout_log.jsonl")

INTERVAL = int(os.environ.get("INTERVAL", "60"))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "9098"))

# Load .env for secrets
_ENV = "/root/empire_os/.env"
if os.path.exists(_ENV):
    for ln in open(_ENV).read().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "a") as f: f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)

def fingerprint(p: Path) -> dict:
    b = p.read_bytes()
    return {
        "size_bytes": len(b),
        "sha256": hashlib.sha256(b).hexdigest()[:16],
        "head": b[:4096].decode("latin-1", errors="replace"),
        "tail": b[-4096:].decode("latin-1", errors="replace"),
    }

def ingest(path: Path):
    out = RAW / (path.stem + ".json")
    if out.exists(): return  # already seen
    meta = fingerprint(path)
    ext = path.suffix.lower()
    rec = {"file": str(path), "seen_at": datetime.now(timezone.utc).isoformat(),
           "ext": ext, **meta}
    out.write_text(json.dumps(rec, indent=2))
    log("INTEL", "ingested", file=path.name, sha=meta["sha256"], size=meta["size_bytes"])

def cycle():
    if not INBOX.exists(): return
    for p in INBOX.iterdir():
        if p.is_file():
            try: ingest(p)
            except Exception as e: log("ERROR", "ingest_failed", file=p.name, err=str(e)[:200])

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "healthy",
                "service": "scout_intel",
                "inbox": str(INBOX),
                "inbox_exists": INBOX.exists(),
                "raw_intel_count": len(list(RAW.glob("*.json"))) if RAW.exists() else 0,
                "interval_sec": INTERVAL,
                "ts": datetime.now(timezone.utc).isoformat()
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args):
        pass  # suppress default logging

def run_health_server():
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    log("START", "health_server_started", port=HEALTH_PORT)
    server.serve_forever()

if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    
    # Start health server in background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    log("START", "scout_admin_online", interval=INTERVAL, health_port=HEALTH_PORT)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)