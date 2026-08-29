#!/usr/bin/env python3
import json, datetime
from pathlib import Path

s = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "overall": "partial", "recommendation": "run partial intel", "ollama_healthy": True, "services": {"ai_intel": {"healthy": True, "details": "ok"}, "company_intel": {"healthy": False, "details": "timeout"}, "intel_market": {"healthy": False, "details": "timeout"}}}
Path("/root/empire_os/config/intel_status.json").write_text(json.dumps(s, indent=2))
print("written to intel_status.json")