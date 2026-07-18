#!/usr/bin/env python3
"""
Lead VERIFICATION API — confirm a business is real before any agent buys.

Cheap, stdlib-only (urllib for HTTP, socket for DNS, whois for registration).
Three independent signals:
  1. resolves  — domain has a live A/AAAA/MX record (real on the wire)
  2. has_site  — homepage fetches (HTTP 2xx/3xx) and looks like a real site
  3. intent_score — 0..1 heuristic: TLS, non-parked content, contact/social,
                    copy signals (pricing, "book", "contact", "services"),
                    multiple pages, years in business from WHOIS creation date.

verify(email_or_domain) -> {
    real: bool, domain: str, resolves: bool, has_site: bool,
    intent_score: float, notes: str
}
"""
import re, socket, ssl, urllib.request, urllib.error, json, time

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})$")
DOMAIN_RE = re.compile(r"^(?:https?://)?([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:/|$)")
# free/parked-domain registrars we treat as "domain-for-sale" (not a real business)
PARKED_NS = ("parkingcrew", "sedoparking", "afternic", "hopclick", "domainactive",
             "parklogic", "namecheapparking", "parkingpage", "domainparking")
PARKED_BODY = ("domain is for sale", "buy this domain", "parked", "registrar",
               "godaddy", "sedo", "this domain", "premium domain")
INTENT_WORDS = ("contact", "services", "pricing", "book", "quote", "about",
                "shop", "order", "schedule", "get started", "our team", "request")
TIMEOUT = 6.0


def _extract_domain(email_or_domain):
    s = (email_or_domain or "").strip().lower()
    if not s:
        return None
    m = EMAIL_RE.match(s)
    if m:
        return m.group(1)
    m = DOMAIN_RE.match(s)
    if m:
        return m.group(1)
    if "." in s and re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", s):
        return s
    return None


def _resolves(domain):
    """True if domain resolves to an IP or has MX (live on the wire)."""
    try:
        socket.getaddrinfo(domain, None)
        return True
    except Exception:
        pass
    try:
        socket.getaddrinfo("mail." + domain, None)
        return True
    except Exception:
        return False


def _http_get(domain):
    """Return (ok, body_text, redirected) for the homepage, or (False,'',False)."""
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; EmpireVerify/1.0)"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(200000)
                try:
                    txt = raw.decode("utf-8", "ignore")
                except Exception:
                    txt = raw.decode("latin-1", "ignore")
                return True, txt, r.geturl() != url
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                loc = e.headers.get("Location", "")
                if loc:
                    try:
                        with urllib.request.urlopen(urllib.request.Request(loc, headers={"User-Agent": "Mozilla/5.0"}), timeout=TIMEOUT) as r2:
                            raw = r2.read(200000)
                            return True, raw.decode("utf-8", "ignore"), True
                    except Exception:
                        return True, "", True
            # 4xx/5xx still means a server answered -> site exists
            if e.code and e.code < 500:
                return True, "", False
            return False, "", False
        except Exception:
            continue
    return False, "", False


def _whois_creation_year(domain):
    """Best-effort WHOIS creation date (years in business signal). None on fail."""
    try:
        import whois  # python-whois optional
        w = whois.whois(domain)
        cd = getattr(w, "creation_date", None)
        if isinstance(cd, list):
            cd = cd[0] if cd else None
        if cd:
            return int(cd.year)
    except Exception:
        pass
    return None


def _is_parked(body, domain):
    if not body:
        return False
    low = body.lower()
    if any(p in low for p in PARKED_BODY):
        return True
    # parked pages are usually tiny
    if len(body) < 400 and ("domain" in low or "registrar" in low):
        return True
    return False


def verify(email_or_domain):
    """Verify a business is real. Returns the result dict (see module docstring)."""
    notes = []
    domain = _extract_domain(email_or_domain)
    if not domain:
        return {"real": False, "domain": "", "resolves": False, "has_site": False,
                "intent_score": 0.0,
                "notes": f"could not parse domain from '{email_or_domain}'"}

    resolves = _resolves(domain)
    notes.append("domain resolves" if resolves else "domain does NOT resolve")
    if not resolves:
        return {"real": False, "domain": domain, "resolves": False, "has_site": False,
                "intent_score": 0.0, "notes": "; ".join(notes)}

    ok, body, redirected = _http_get(domain)
    has_site = ok and not _is_parked(body, domain)
    notes.append("homepage live" + (" (redirect)" if redirected else "") if ok else "no homepage")
    if _is_parked(body, domain):
        notes.append("PARKED/for-sale page — not a real business")

    score = 0.0
    # signal: has a real (non-parked) homepage
    if has_site:
        score += 0.4
    # signal: TLS available
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=TIMEOUT):
            with ctx.wrap_socket(socket.socket(), server_hostname=domain):
                pass
        score += 0.2
        notes.append("TLS/HTTPS OK")
    except Exception:
        notes.append("no TLS")
    # signal: content-bearing page (>1KB, multiple intent words)
    if body:
        low = body.lower()
        n_words = sum(1 for w in INTENT_WORDS if w in low)
        if len(body) > 1500:
            score += 0.15
        score += min(0.15, n_words * 0.03)
        if n_words >= 2:
            notes.append(f"{n_words} intent keywords")
    # signal: years in business
    yr = _whois_creation_year(domain)
    if yr:
        age = max(0, 2026 - yr)
        score += min(0.10, age * 0.02)
        notes.append(f"registered {yr} (~{age}y)")
    score = round(min(1.0, score), 2)

    real = resolves and has_site and score >= 0.4
    notes.append(f"intent_score={score}")
    return {"real": real, "domain": domain, "resolves": resolves,
            "has_site": has_site, "intent_score": score,
            "notes": "; ".join(notes)}


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "empire-ai.co.uk"
    print(json.dumps(verify(q), indent=2))
