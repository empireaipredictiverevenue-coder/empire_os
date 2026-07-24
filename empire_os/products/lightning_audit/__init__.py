"""Lightning Technical Audit — sellable product."""
from pathlib import Path
import sys, json, subprocess, tempfile, os
from datetime import datetime, timezone

REPO = Path("/root/agent_work/agrici-claude-seo-scan/claude-seo")
SCRIPTS = REPO / "scripts"

def run_script(name: str, *args) -> dict:
    script = SCRIPTS / name
    if not script.exists():
        return {"ok": False, "error": f"missing {name}"}
    cmd = [sys.executable, str(script), *args]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {"ok": out.returncode == 0, "stdout": out.stdout, "stderr": out.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}

def audit(url: str) -> dict:
    results = {}
    results["fetch"] = run_script("fetch_page.py", url)
    results["pagespeed"] = run_script("pagespeed_check.py", url)
    results["parse"] = run_script("parse_html.py", url)
    results["sitemap"] = run_script("sitemap_discovery.py", url)
    # indexnow_submit.py requires API key — skip in demo
    return {"url": url, "ts": datetime.now(timezone.utc).isoformat(), "checks": results}

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default="/tmp/lightning_audit.json")
    a = ap.parse_args()
    res = audit(a.url)
    Path(a.out).write_text(json.dumps(res, indent=2))
    print(f"wrote {a.out}")
