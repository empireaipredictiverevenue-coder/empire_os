#!/usr/bin/env python3
"""ai_email_infer.py — LLM email-pattern inference via llm_gateway (one brain).

Predicts the most likely valid business email for a domain from business
name + domain. No browser, no proxy, no SMTP. Provider chain (Bai -> Groq)
lives in llm_gateway.py — this module only does prompt + MX filter + DB.
"""
from __future__ import annotations
import sys, re, sqlite3, json, urllib.request, os, time
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
OR_URL = "https://api.b.ai/v1/chat/completions"
MODEL = "deepseek-v4-flash"
BATCH = 400
PROMPT = (
    "You predict B2B contact emails. Given company name + domain, output the SINGLE "
    "most likely valid business email (prefer info@/sales@/admin@, or firstname.lastname@ "
    "for small firms). Reply with ONLY the email, lowercase, no explanation.\n"
    "Company: {name}\nDomain: {domain}\nEmail:"
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
BAD = ("gaf.com", "angieslist", "homeadvisor", "yelp", "thumbtack", "facebook",
       "linkedin", "instagram", "pinterest", "youtube", "wikipedia", "bbb.org",
       "yellowpages", "houzz", "gmail.com", "yahoo.com", "hotmail.com", "outlook.com")
_mx: dict[str, bool] = {}


def log(m): print(f"[ai_email_infer] {m}", flush=True)


def open_db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA busy_timeout=60000")
    return c


def mx_exists(dom: str) -> bool:
    if dom in _mx:
        return _mx[dom]
    try:
        import dns.resolver
        dns.resolver.resolve(dom, "MX")
        _mx[dom] = True
    except Exception:
        _mx[dom] = False
    return _mx[dom]


def _key() -> str:
    for p in ("/root/empire_secrets/bai_api_key", "/root/empire_secrets/groq_api_key", "/root/empire_secrets/openrouter_api_key"):
        try:
            v = open(p).read().strip().replace("BAI_API_KEY=", "").replace("GROQ_API_KEY=", "").replace("OPENROUTER_API_KEY=", "")
            if v:
                return v
        except Exception:
            continue
    return os.environ.get("BAI_API_KEY", "")


def infer(name: str, domain: str) -> str:
    import llm_gateway
    txt = llm_gateway.llm("bulk", PROMPT.format(name=name, domain=domain))
    m = EMAIL_RE.search(txt)
    if m:
        em = m.group(0).lower().strip()
        d = em.split("@")[-1]
        if any(b in d for b in BAD) or not mx_exists(d):
            return ""
        return em
    return ""


def run():
    c = open_db()
    rows = c.execute(
        "SELECT id, business_name, website FROM crm_leads WHERE website IS NOT NULL AND website!='' "
        "AND (email IS NULL OR email='') "
        "AND website NOT LIKE '%gaf.com%' AND website NOT LIKE '%angieslist%' "
        "AND website NOT LIKE '%homeadvisor%' AND website NOT LIKE '%yelp%' "
        "AND website NOT LIKE '%thumbtack%' AND website NOT LIKE '%houzz%' "
        "AND website NOT LIKE '%facebook%' AND website NOT LIKE '%linkedin%' "
        "LIMIT ?", (BATCH,)
    ).fetchall()
    log(f"AI-inferring {len(rows)} domains via OpenRouter...")
    found = 0
    for rid, name, site in rows:
        dom = (site.split("//")[-1].split("/")[0]).replace("www.", "")
        em = infer(name or dom, dom)
        if em:
            c.execute("UPDATE crm_leads SET email=? WHERE id=?", (em, rid))
            found += 1
        time.sleep(0.5)
    c.commit()
    c.close()
    log(f"AI-inferred + MX-verified: {found}")
    import lead_harvest
    lead_harvest.bridge_to_outreach()
    c = open_db()
    valid = c.execute("SELECT COUNT(DISTINCT email) FROM si_buyer_outreach WHERE email_status='valid'").fetchone()[0]
    c.close()
    log(f"valid unique pool now: {valid}")


if __name__ == "__main__":
    run()
