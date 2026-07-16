"""
scout-admin — intel ingest + dispatcher.
  Pulls /root/inbox/phone/* from D: drops
  Parses PDFs (read-only header sniff) + .md/.txt
  Writes summary to /root/feedback/raw_intel/<name>.json
  Cadence: 60s
"""
from __future__ import annotations
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
import subprocess

INBOX = Path("/root/inbox/phone")
RAW   = Path("/root/feedback/raw_intel")
OUT   = Path("/root/feedback/scout_log.jsonl")

INTERVAL = int(os.environ.get("INTERVAL", "60"))

def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "a") as f: f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)

def fingerprint(p: Path) -> dict:
    b = p.read_bytes()
    return {
        "size_bytes": len(b),
        "sha256":     hashlib.sha256(b).hexdigest()[:16],
        "head":       b[:4096].decode("latin-1", errors="replace"),
        "tail":       b[-4096:].decode("latin-1", errors="replace"),
    }

def ingest(path: Path):
    out = RAW / (path.stem + ".json")
    if out.exists(): return  # already seen
    meta = fingerprint(path)
    ext  = path.suffix.lower()
    rec  = {"file": str(path), "seen_at": datetime.now(timezone.utc).isoformat(),
            "ext": ext, **meta}
    out.write_text(json.dumps(rec, indent=2))
    log("INTEL", "ingested", file=path.name, sha=meta["sha256"], size=meta["size_bytes"])

def cycle():
    if not INBOX.exists(): return
    for p in INBOX.iterdir():
        if p.is_file():
            try:
                ingest(p)
            except Exception as e:
                log("ERROR", "ingest_failed", file=p.name, err=str(e)[:200])

if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] scout-admin online — interval {INTERVAL}s",
          flush=True)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        import time; time.sleep(INTERVAL)
