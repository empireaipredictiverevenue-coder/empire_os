"""empire_seo.py — Empire SEO: own SEO product, zero third parties.

Runs on host (not container): calls Ollama locally (10.118.155.1:11434 from
container is fine, but CPU inference blocks container hub event loop otherwise).

Stack (all ours, free):
  search  — DDG suggestions API (autocomplete = real search demand signal,
            free, no key) + hub /v1/web/search ddg_lite for SERP checks
  audit   — site_crawler fetches pages; checks mirror OpenSEO/badseo taxonomy
            (title, meta, h1, canonical, viewport, links, noindex, thin content)
  brain   — Ollama llama3.2:3b (local CPU) for keyword intent clustering +
            content briefs
  leads   — cross-links with serp_discovery: audited domains join the
            outbound lead pool

Usage:
  python3 empire_seo.py audit https://example.com
  python3 empire_seo.py keywords "roofing dallas" --expand 25
  python3 empire_seo.py brief roofing "Fort Worth"
  python3 empire_seo.py sweep "roofing dallas" --max 5   # SERP -> audit -> leads
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict

OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
MODEL = "llama3.2:3b"
UA = "Mozilla/5.0 (X11; Linux x86_64) EmpireSEO/1.0"
DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
SUGGEST = "https://duckduckgo.com/ac/?format=json&q={q}"
TIMEOUT = 15


# ── Ollama brain ────────────────────────────────────────────────────────
def ask(prompt: str, timeout: int = 240) -> str:
    req = urllib.request.Request(
        OLLAMA,
        data=json.dumps({"model": MODEL, "prompt": prompt,
                         "stream": False, "options": {"num_ctx": 2048}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("response", "").strip()


def ask_json(prompt: str, timeout: int = 240) -> dict:
    raw = ask(prompt, timeout)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"_raw": raw[:400]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"_raw": raw[:400]}


# ── Free keyword demand: DDG autocomplete ───────────────────────────────
def suggest(keyword: str) -> list[str]:
    url = SUGGEST.format(q=urllib.parse.quote(keyword))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return [x["phrase"] for x in json.loads(r.read())]
    except Exception:
        return []


def expand_keywords(seed: str, rounds: int = 2, fanout: str = "a-z") -> dict:
    """Autocomplete expansion = real typed demand, not a guessed list."""
    seen: dict[str, list[str]] = {}
    queue = [seed.lower()]
    for suf in fanout.split() if fanout != "a-z" else list("abcdefghijklmnopqrstuvwxyz"):
        queue.append(f"{seed.lower()} {suf}")
    for q in queue:
        for ph in suggest(q):
            if ph.lower() != seed.lower():
                seen.setdefault(ph.lower(), []).append(q)
        time.sleep(0.4)  # polite
    return {"seed": seed, "count": len(seen), "keywords": sorted(seen)}


# ── On-page audit (badseo/OpenSEO taxonomy, our own checks) ─────────────
@dataclass
class PageAudit:
    url: str
    status: int
    title: str = ""
    title_len: int = 0
    meta_desc: str = ""
    h1_count: int = 0
    canonical: str = ""
    viewport: bool = False
    noindex: bool = False
    thin_content: bool = False
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    issues: list = field(default_factory=list)
    score: int = 100


def _fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(600_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def audit_page(url: str) -> PageAudit:
    a = PageAudit(url=url, status=0)
    status, html = _fetch(url if url.startswith("http") else f"https://{url}")
    a.status = status
    if not html:
        a.issues.append("unreachable_or_blocked")
        a.score = 0
        return a

    def m1(pat: str) -> str:
        m = re.search(pat, html, re.I | re.S)
        return m.group(1).strip() if m else ""

    a.title = re.sub(r"\s+", " ", m1(r"<title[^>]*>(.*?)</title>"))
    a.title_len = len(a.title)
    a.meta_desc = re.sub(r"\s+", " ", m1(r'<meta\s+name=["\']description["\'][^>]*content=["\'](.*?)["\']'))
    a.h1_count = len(re.findall(r"<h1[\s>]", html, re.I))
    a.canonical = m1(r'<link\s+rel=["\']canonical["\'][^>]*href=["\'](.*?)["\']')
    a.viewport = bool(re.search(r'name=["\']viewport["\']', html, re.I))
    a.noindex = bool(re.search(r'name=["\']robots["\'][^>]*noindex', html, re.I))
    body = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html, flags=re.S | re.I)
    words = body.split()
    a.word_count = len(words)
    a.thin_content = a.word_count < 150
    hrefs = re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.I)
    host = urllib.parse.urlparse(a.url).netloc
    a.internal_links = sum(1 for h in hrefs if host in h)
    a.external_links = len(hrefs) - a.internal_links

    if a.title_len == 0:
        a.issues.append("missing_title")
    elif a.title_len > 60:
        a.issues.append("title_too_long")
    elif a.title_len < 15:
        a.issues.append("title_too_short")
    if not a.meta_desc:
        a.issues.append("missing_meta_description")
    elif len(a.meta_desc) > 160:
        a.issues.append("meta_too_long")
    if a.h1_count == 0:
        a.issues.append("missing_h1")
    elif a.h1_count > 1:
        a.issues.append("multiple_h1")
    if not a.canonical:
        a.issues.append("missing_canonical")
    if not a.viewport:
        a.issues.append("missing_viewport")
    if a.noindex:
        a.issues.append("noindex")
    if a.thin_content:
        a.issues.append("thin_content")
    a.score = max(0, 100 - 12 * len(a.issues))
    return a


def audit_site(url: str, max_pages: int = 8) -> dict:
    """Crawl homepage + internal links, audit each, aggregate."""
    seen = [url if url.startswith("http") else f"https://{url}"]
    audits: list[PageAudit] = []
    base = urllib.parse.urlparse(seen[0]).netloc
    visited = set()
    while seen and len(visited) < max_pages:
        u = seen.pop(0)
        if u in visited:
            continue
        visited.add(u)
        a = audit_page(u)
        audits.append(a)
        if len(audits) == 1:
            # collect internal links from homepage only (cheap single fetch)
            _, html = _fetch(u)
            for h in re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.I)[:40]:
                if base in h and h not in visited and h not in seen:
                    seen.append(h.split("#")[0])
    scores = [a.score for a in audits if a.status]
    agg = {
        "site": base,
        "pages_audited": len(audits),
        "avg_score": round(sum(scores) / len(scores)) if scores else 0,
        "issues": sorted({i for a in audits for i in a.issues}),
        "pages": [asdict(a) for a in audits],
    }
    return agg


# ── Content brief: template-driven (instant) + Ollama polish (batch) ────
def brief(niche: str, metro: str, use_llm: bool = False) -> dict:
    """Deterministic brief from real autocomplete demand. Fast, free, no LLM
    latency. use_llm=True adds Ollama section copy — batch-only (CPU slow)."""
    kws = expand_keywords(f"{niche} {metro}".lower(), fanout="a")
    kws2 = expand_keywords(f"{niche} near {metro}".lower(), fanout="a")
    top = kws["keywords"][:10]
    near = [k for k in kws2["keywords"] if k not in top][:5]
    n = niche.replace("_", " ").title()
    b = {
        "title": f"{n} in {metro} | Verified {n} Pros & Free Quotes"[:60],
        "meta_description":
            f"Compare verified {n.lower()} contractors in {metro}. "
            f"Real reviews, licensed pros, free quotes in minutes."[:155],
        "h1": f"Find Trusted {n} in {metro}",
        "sections": [
            {"h2": f"How much does {n.lower()} cost in {metro}?",
             "points": [f"Typical {n.lower()} pricing in {metro} depends on scope",
                        "Get 3 free quotes from verified local pros"]},
            {"h2": f"What {metro} homeowners should check before hiring",
             "points": ["License + insurance verification", "Written estimate vs verbal",
                        "Local reviews and completed jobs"]},
            {"h2": f"{n} services we match in {metro}",
             "points": [f"All major {n.lower()} categories covered",
                        "Same-week scheduling available"]},
        ],
        "faq": [
            {"q": f"How do I find a good {n.lower()} in {metro}?",
             "a": f"Use our verified {metro} {n.lower()} matching — every pro is license-checked."},
            {"q": f"Is the quote really free?",
             "a": "Yes — compare up to 3 quotes, no obligation."},
        ],
        "cta": f"Get 3 free {n.lower()} quotes in {metro} today",
        "demand_keywords": top + near,
    }
    if use_llm:
        try:
            polish = ask_json(
                f"SEO copy polish for a landing page. Niche: {niche}. Metro: {metro}. "
                f"Real demand keywords: {json.dumps(top[:8])}. Return JSON only "
                '{"intro": "2 sentences using 2-3 keywords naturally"}.',
                timeout=300)
            if "intro" in polish:
                b["intro"] = polish["intro"]
        except Exception:
            pass
    return {"niche": niche, "metro": metro, "brief": b}


# ── SERP -> audit -> lead sweep (the automated loop) ────────────────────
HUB = os.getenv("HUB_URL", "http://127.0.0.1:8081")


def serp_organic(query: str, num: int = 8) -> list[str]:
    """Organic domains via hub /v1/web/search (serper free tier, camoufox).
    Filters aggregators — we want the actual contractor sites."""
    url = f"{HUB}/v1/web/search?q={urllib.parse.quote(query)}&num={num}&backend=serper&use_cache=false"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as r:
            data = json.loads(r.read())
        domains = []
        for res in data.get("results", []):
            if "error" in res:
                continue
            u = res.get("url", "")
            host = urllib.parse.urlparse(u).netloc
            if not host:
                continue
            if any(x in host for x in ("facebook.", "yelp.", "google.", "reddit.",
                                       "indeed.", "ziprecruiter", "bbb.org",
                                       "angi.", "thumbtack", "houzz.", "porch.",
                                       "linkedin.", "instagram.", "youtube.",
                                       "nextdoor.", "birdeye.")):
                continue
            if host not in domains:
                domains.append(host)
        return domains
    except Exception as e:
        return []


def serp_domain_sweep(query: str, max_domains: int = 5) -> dict:
    """SERP -> organic domains -> audit each -> store in site_audits.
    Low-score domains = SEO-weak = hot lead for our services/products."""
    domains = serp_organic(query, num=max_domains + 4)[:max_domains]
    if not domains:
        return {"query": query, "error": "no organic domains from SERP", "audited": []}
    results = []
    for d in domains:
        a = audit_site(d, max_pages=3)
        results.append(a)
        _store_audited_domain(query, d, a)
    return {"query": query, "audited": results}


def _store_audited_domain(query: str, domain: str, audit: dict) -> None:
    """Audited domains -> site_audits table. Score<=70 = SEO-weak -> also
    feed crm_leads (source='seo_audit') for the outbound lead pipeline."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("""CREATE TABLE IF NOT EXISTS site_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, query TEXT, domain TEXT UNIQUE,
        avg_score INTEGER, issues TEXT, pages_audited INTEGER)""")
    con.execute(
        "INSERT INTO site_audits(ts, query, domain, avg_score, issues, pages_audited) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(domain) DO UPDATE SET "
        "ts=excluded.ts, avg_score=excluded.avg_score, issues=excluded.issues",
        (now, query, domain, audit.get("avg_score", 0),
         json.dumps(audit.get("issues", [])), audit.get("pages_audited", 0)))
    con.commit()
    con.close()
    # Lead-gen automation: SEO-weak domains are prospects — push to crm_leads
    if audit.get("avg_score", 0) <= 70 and audit.get("avg_score", 0) > 0:
        _feed_crm(query, domain, audit, now)


def _feed_crm(query: str, domain: str, audit: dict, now: str) -> None:
    """Insert audited SEO-weak site as lead. niche/metro parsed from query."""
    parts = query.lower().split()
    niche = parts[0] if parts else "general"
    stop = {"companies", "company", "services", "service", "near", "me", "in",
            "best", "top", "cheap", "tx", "local"}
    metro = " ".join(p for p in parts[1:] if p not in stop)[:40].title()
    uid = f"seo_{hashlib.md5(domain.encode()).hexdigest()[:12]}"
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("""INSERT INTO crm_leads(lead_uid, source, business_name, website,
        niche, metro, status, notes, created_at)
        VALUES (?,?,?,?,?,?,?,?,datetime('now'))
        ON CONFLICT(lead_uid) DO NOTHING""", (
        uid, "seo_audit", domain.split("www.")[-1].split(".")[0].replace("-", " ").title(),
        f"https://{domain}", niche, metro.title(), "new",
        json.dumps({"seo_score": audit.get("avg_score"),
                    "seo_issues": audit.get("issues", [])[:6],
                    "found_via": query})[:500]))
    con.commit()
    con.close()


def _crm_count() -> int:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    n = con.execute("SELECT count(*) FROM crm_leads WHERE source='seo_audit'").fetchone()[0]
    con.close()
    return n


# ── CLI ─────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "audit":
        print(json.dumps(audit_site(sys.argv[2],
              max_pages=int(sys.argv[3]) if len(sys.argv) > 3 else 8), indent=1)[:3000])
    elif cmd == "keywords":
        seed = sys.argv[2]
        print(json.dumps(expand_keywords(seed), indent=1)[:3000])
    elif cmd == "brief":
        print(json.dumps(brief(sys.argv[2], sys.argv[3]), indent=1)[:3000])
    elif cmd == "sweep":
        r = serp_domain_sweep(sys.argv[2],
                              max_domains=int(sys.argv[3]) if len(sys.argv) > 3 else 5)
        print(json.dumps({
            "query": r.get("query"),
            "error": r.get("error"),
            "audited": [{"site": a.get("site"), "avg_score": a.get("avg_score"),
                         "pages_audited": a.get("pages_audited"),
                         "issues": a.get("issues")}
                        for a in r.get("audited", [])]}, indent=1))
    elif cmd == "matrix":
        """matrix 'roofing|plumbing' 'plano tx|frisco tx' [per_combo] —
        sweep every niche x metro combo. Designed for cron/systemd timer."""
        niches = sys.argv[2].split("|")
        metros = sys.argv[3].split("|")
        per = int(sys.argv[4]) if len(sys.argv) > 4 else 3
        out = []
        for n in niches:
            for m in metros:
                q = f"{n} companies {m}"
                r = serp_domain_sweep(q, max_domains=per)
                got = [{"site": a.get("site"), "score": a.get("avg_score")}
                       for a in r.get("audited", [])]
                out.append({"query": q, "audited": got})
                print(json.dumps(out[-1]), flush=True)
                time.sleep(2)
        fed = _crm_count()
        print(json.dumps({"done": len(out), "seo_audit_leads_total": fed}))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
