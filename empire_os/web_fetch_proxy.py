"""
Empire OS Web Proxy — completely key-free, self-hosted search + fetch.

Backends (all self-hosted or anonymous):
  - Fetch: direct (curl), with caching, retry, rate limiting
  - Search:
    * github  → gh CLI (works for code/repo queries, 5000 req/hr auth)
    * mojeek  → no-JS, no-captcha search engine
    * bing    → public HTML (rate-limited)
    * brave   → public HTML (sometimes captcha)
    * ddg_lite → lite.duckduckgo.com (less restrictive than /html/)

The proxy does NOT require any API key. We win by owning our own
search/crawl/fetch infrastructure rather than paying Firecrawl/Hunter.
"""
from __future__ import annotations
import os
import re
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import hashlib
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

CACHE_DB = Path("/root/empire_os/feedback/web_fetch_cache.db")
CACHE_TTL_SECONDS = int(os.environ.get("WEB_FETCH_CACHE_TTL", "3600"))
RATE_LIMIT_PER_HOUR = 100  # be a good citizen to anon search engines


def _init_cache():
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(CACHE_DB))
    con.execute(
        "CREATE TABLE IF NOT EXISTS fetch_cache ("
        "  url_hash TEXT PRIMARY KEY, url TEXT, backend TEXT, content TEXT,"
        "  content_type TEXT, fetched_at REAL, expires_at REAL, status INTEGER)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS search_cache ("
        "  query_hash TEXT PRIMARY KEY, query TEXT, backend TEXT, results TEXT,"
        "  fetched_at REAL, expires_at REAL)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_fetched ON fetch_cache(fetched_at)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_search ON search_cache(fetched_at)")
    con.commit()
    return con


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:32]


# ────────────────────────────────────────────────────────────────────
# FETCH (URL → content)
# ────────────────────────────────────────────────────────────────────
def web_fetch(url: str, backend: str = "direct", use_cache: bool = True,
              timeout: int = 30) -> dict[str, Any]:
    """Fetch any URL. Cached 1h. No API key required."""
    con = _init_cache()
    url_h = _h(url)
    now = time.time()

    if use_cache:
        row = con.execute(
            "SELECT content, content_type, fetched_at, expires_at, backend, status "
            "FROM fetch_cache WHERE url_hash=?", (url_h,)
        ).fetchone()
        if row and row[3] > now:
            con.close()
            return {
                "url": url, "status": row[5], "content": row[0],
                "content_type": row[1], "backend": row[4],
                "cached": True, "fetched_at": row[2], "expires_at": row[3],
            }

    if backend == "camoufox":
        status, content, ctype = _fetch_camoufox(url, timeout)
    else:
        status, content, ctype = _fetch_direct(url, timeout)
    expires = now + CACHE_TTL_SECONDS
    if status not in (200, 201):
        expires = now + 60
    con.execute(
        "INSERT OR REPLACE INTO fetch_cache "
        "(url_hash, url, backend, content, content_type, fetched_at, expires_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (url_h, url, backend, content, ctype, now, expires, status),
    )
    con.commit()
    con.close()
    return {
        "url": url, "status": status, "content": content,
        "content_type": ctype, "backend": backend,
        "cached": False, "fetched_at": now, "expires_at": expires,
    }


def _fetch_camoufox(url: str, timeout: int = 45) -> tuple[int, str, str]:
    """Camoufox backend — real headless Firefox, bypasses captchas, renders JS.

    Uses /root/venv/bin/python3 (camoufox in container venv + browser binary).
    Passes -no-remote -P args for LXC sandbox compatibility.
    Returns fully-rendered HTML. Slower than direct, but can handle:
      - Cloudflare challenges
      - JS-rendered SPAs
      - Sites that block curl-based User-Agents
    """
    import subprocess
    try:
        script = (
            "from camoufox.sync_api import Camoufox\n"
            "with Camoufox(headless=True, args=['-no-remote', '-P']) as b:\n"
            "    p = b.new_page()\n"
            f"    p.goto({url!r}, timeout={timeout * 1000}, "
            f"wait_until='domcontentloaded')\n"
            "    print(p.content())\n"
        )
        r = subprocess.run(
            ["/root/venv/bin/python3", "-u", "-c", script],
            capture_output=True, text=True, timeout=timeout + 30,
        )
        if r.returncode != 0:
            return 0, f"camoufox err: {r.stderr[:500]}", "text/plain"
        return 200, r.stdout, "text/html"
    except subprocess.TimeoutExpired:
        return 0, "camoufox timeout", "text/plain"
    except Exception as e:
        return 0, f"camoufox exc: {str(e)[:300]}", "text/plain"


def _fetch_direct(url: str, timeout: int = 30) -> tuple[int, str, str]:
    """Direct fetch — no proxy, no key."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/121.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return r.status, body, r.headers.get("Content-Type", "text/plain")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), "text/plain"
    except Exception as e:
        return 0, str(e)[:500], "text/plain"


# ────────────────────────────────────────────────────────────────────
# SEARCH (query → results)
# ────────────────────────────────────────────────────────────────────
def web_search(query: str, num: int = 5, backend: str = "github",
               use_cache: bool = True) -> dict[str, Any]:
    """Search using a self-hosted backend. No API key needed."""
    con = _init_cache()
    qh = _h(query)
    now = time.time()
    if use_cache:
        row = con.execute(
            "SELECT results, fetched_at, expires_at, backend FROM search_cache "
            "WHERE query_hash=?", (qh,)
        ).fetchone()
        if row and row[2] > now:
            con.close()
            return {
                "backend": row[3], "query": query, "results": json.loads(row[0]),
                "cached": True, "fetched_at": row[1],
            }

    if backend == "github":
        results = _search_github(query, num)
    elif backend == "mojeek":
        results = _search_mojeek(query, num)
    elif backend == "bing":
        results = _search_bing(query, num)
    elif backend == "brave":
        results = _search_brave(query, num)
    elif backend == "ddg_lite":
        results = _search_ddg_lite(query, num)
    elif backend == "serper":
        results = _search_serper(query, num)
    elif backend == "exa":
        results = _search_exa(query, num)
    elif backend == "auto":
        # Priority: serper > exa > github > mojeek > bing > brave > ddg_lite
        if _load_serper_key():
            backend = "serper"
            results = _search_serper(query, num)
        elif exa_key:
            backend = "exa"
            results = _search_exa(query, num)
        else:
            backend = "github"
            results = _search_github(query, num)
    else:
        results = []

    expires = now + CACHE_TTL_SECONDS
    con.execute(
        "INSERT OR REPLACE INTO search_cache "
        "(query_hash, query, backend, results, fetched_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (qh, query, backend, json.dumps(results), now, expires),
    )
    con.commit()
    con.close()
    return {
        "backend": backend, "query": query, "results": results,
        "cached": False, "fetched_at": now,
    }


def _search(query: str, num: int, backend: str) -> list[dict]:
    if backend == "github":
        return _search_github(query, num)
    elif backend == "mojeek":
        return _search_mojeek(query, num)
    elif backend == "bing":
        return _search_bing(query, num)
    elif backend == "brave":
        return _search_brave(query, num)
    elif backend == "ddg_lite":
        return _search_ddg_lite(query, num)
    return []


# ─── Serper.dev backend (Google Search, 2500/mo free) ────────────────
def _load_serper_key() -> str | None:
    """Load SERPER_KEY from env or drop-in file."""
    k = os.environ.get("SERPER_KEY") or os.environ.get("SERPER_API_KEY")
    if k:
        return k
    for path in ["/root/empire_secrets/serper_api_key",
                 "/root/.config/serper/api_key"]:
        try:
            return Path(path).read_text().strip() or None
        except Exception:
            pass
    return None


def _search_serper(query: str, num: int) -> list[dict]:
    """Serper.dev — Google organic results. 2500/mo free, then $5/10k."""
    key = _load_serper_key()
    if not key:
        return [{"error": "SERPER_KEY not configured. "
                           "Drop key at /root/empire_secrets/serper_api_key"}]
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=json.dumps({"q": query, "num": num}).encode(),
            headers={
                "X-API-KEY": key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        results = []
        for item in data.get("organic", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", "")[:300],
            })
            if len(results) >= num:
                break
        return results
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return [{"error": f"serper HTTP {e.code}: {body[:200]}"}]
    except Exception as e:
        return [{"error": str(e)[:200]}]


def _search_github(query: str, num: int) -> list[dict]:
    """GitHub repo search via `gh` CLI. Authed. Free 5000/hr."""
    try:
        out = subprocess.run(
            ["gh", "search", "repos", query, "--limit", str(num)],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return [{"error": out.stderr[:200]}]
        results = []
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            results.append({
                "title": parts[0].strip(),
                "url": f"https://github.com/{parts[0].strip()}",
                "snippet": parts[1].strip()[:300] if len(parts) > 1 else "",
            })
        return results
    except Exception as e:
        return [{"error": str(e)[:200]}]


def _search_mojeek(query: str, num: int) -> list[dict]:
    """Mojeek — UK-based, no captcha, no JS, no key."""
    try:
        url = f"https://www.mojeek.com/search?q={urllib.parse.quote(query)}"
        s, html, _ = _fetch_direct(url, 15)
        if s != 200:
            return [{"error": f"mojeek HTTP {s}"}]
        results = []
        for m in re.finditer(
            r'<a[^>]*class="ob"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html, re.DOTALL,
        ):
            href = m.group(1)
            if href.startswith("//"):
                href = "https:" + href
            if not href.startswith("http"):
                continue
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            results.append({"title": title, "url": href, "snippet": ""})
            if len(results) >= num:
                break
        return results
    except Exception as e:
        return [{"error": str(e)[:200]}]


def _search_bing(query: str, num: int) -> list[dict]:
    """Bing public search."""
    try:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        s, html, _ = _fetch_direct(url, 15)
        if s != 200:
            return [{"error": f"bing HTTP {s}"}]
        results = []
        for m in re.finditer(
            r'<li[^>]*class="b_algo"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<p[^>]*>(.*?)</p>',
            html, re.DOTALL,
        ):
            href = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()[:300]
            results.append({"title": title, "url": href, "snippet": snippet})
            if len(results) >= num:
                break
        return results
    except Exception as e:
        return [{"error": str(e)[:200]}]


def _search_brave(query: str, num: int) -> list[dict]:
    """Brave search public HTML."""
    try:
        url = f"https://search.brave.com/search?q={urllib.parse.quote(query)}"
        s, html, _ = _fetch_direct(url, 15)
        if s != 200:
            return [{"error": f"brave HTTP {s}"}]
        results = []
        # Brave wraps each result in a snippet-data-* div
        for m in re.finditer(
            r'<a[^>]*href="(https?://[^"]+)"[^>]*>.*?'
            r'<div[^>]*class="title"[^>]*>(.*?)</div>',
            html, re.DOTALL,
        ):
            href = m.group(1)
            if "brave.com" in href:
                continue
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            results.append({"title": title, "url": href, "snippet": ""})
            if len(results) >= num:
                break
        return results
    except Exception as e:
        return [{"error": str(e)[:200]}]


def _search_ddg_lite(query: str, num: int) -> list[dict]:
    """DuckDuckGo Lite — minimal HTML, less restrictive."""
    try:
        url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
        s, html, _ = _fetch_direct(url, 15)
        if s != 200:
            return [{"error": f"ddg HTTP {s}"}]
        results = []
        # DDG Lite anchor attrs come in either order AND either quote style:
        #   <a rel="nofollow" href="//duckduckgo.com/l/?uddg=..." class='result-link'>TITLE</a>
        # Filter ad redirects (duckduckgo.com/y.js) — keep organic only.
        for m in re.finditer(
            r"""<a\s[^>]*?href="([^"]+)"[^>]*?class=['"]result-link['"][^>]*>(.*?)</a>""",
            html, re.DOTALL,
        ):
            href = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if "uddg=" in href:
                m2 = re.search(r"uddg=([^&]+)", href)
                if m2:
                    href = urllib.parse.unquote(m2.group(1))
            # skip DDG ad redirects + internal help links
            if "y.js" in href or "duckduckgo-help-pages" in href:
                continue
            if not href.startswith(("http://", "https://")):
                if href.startswith("//"):
                    href = "https:" + href
                else:
                    continue
            if not title:
                continue
            results.append({"title": title, "url": href, "snippet": ""})
            if len(results) >= num:
                break
        if not results:
            return [{"error": "ddg_lite: 0 organic results parsed"}]
        # Also extract snippets
        for i, sm in enumerate(
            re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', html, re.DOTALL)
        ):
            if i < len(results):
                results[i]["snippet"] = re.sub(r"<[^>]+>", "", sm).strip()[:300]
        return results
    except Exception as e:
        return [{"error": str(e)[:200]}]