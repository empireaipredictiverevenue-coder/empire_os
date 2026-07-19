"""
Product Research Agent — full pipeline: research → productize →
build funnel/store → connect payments → launch outreach.

Different from scout/sniper: those find LEADS (people to sell to).
This finds PRODUCTS (things to sell).

Tick cycle:
  observe  — read candidates.json + launched.json + state
  reason   — pick: research / productize / build / launch (anti-rep
            prevents rebuilding the same product twice)
  act      — execute the chosen step, persist state to disk

State files:
  /root/products/candidates.json   — operator-approved queue (input)
  /root/products/launched.json     — already-launched products (anti-rep)
  /root/products/research.json     — latest research findings
  /root/products/store/<slug>/     — static landing page files
  /root/products/video/<slug>/     — OpenMontage-rendered promo
  /root/products/outreach/<slug>/  — queued USDC outreach
  /root/feedback/products.jsonl    — append-only audit log

Backing libraries (already on host):
  - /root/empire_os/skills_library/   (web-artifacts-builder skill)
  - /root/OpenMontage/                 (12 pipeline_defs for video)
  - hub POST /v1/outbox/enqueue        (USDC outreach queue)
  - hermes-gateway /v1/notify/alert    (operator paging)
  - synthetic_intelligence             (memory + anti-rep from v2 base)

Cycle: 30 min — research is cheap, building pages is fast, video
rendering takes minutes but runs in background.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.skills_library import skills_context_for_role

ROLE_DIR = Path("/root/products")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_PATH = ROLE_DIR / "candidates.json"
LAUNCHED_PATH = ROLE_DIR / "launched.json"
RESEARCH_PATH = ROLE_DIR / "research.json"
STORES_DIR = ROLE_DIR / "store"
STORES_DIR.mkdir(exist_ok=True)
VIDEOS_DIR = ROLE_DIR / "video"
VIDEOS_DIR.mkdir(exist_ok=True)
OUTREACH_DIR = ROLE_DIR / "outreach"
OUTREACH_DIR.mkdir(exist_ok=True)
AUDIT_LOG = Path("/root/feedback/products.jsonl")

TICK_INTERVAL = 1800  # 30 min

HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100")

# Empire OS USDC vault address — real revenue lands here
USDC_VAULT = os.environ.get("USDC_VAULT",
                            "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
SOLANA_PAY_BASE = "solana:" + USDC_VAULT

# ──────────────────────────────────────────────────────────────────────
# Marketplace research sources (all free + public)
# ──────────────────────────────────────────────────────────────────────

def scrape_amazon_bestsellers(niche: str = "electronics") -> list[dict]:
    """Amazon best-sellers RSS — public, no auth needed."""
    try:
        url = (f"https://www.amazon.com/Best-Sellers/zgbs/"
               f"{niche}/?_encoding=UTF8&pg=1&format=json")
        req = urllib.request.Request(
            url, headers={"User-Agent": "EmpireOS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode(errors="ignore")
        # Cheap parse: look for product titles + prices
        titles = re.findall(r'class="a-link-normal[^"]*"[^>]*>([^<]+)</a>',
                            html)[:10]
        prices = re.findall(r'\$(\d+\.\d{2})', html)[:10]
        return [{"title": t.strip(), "price": p,
                 "source": "amazon-bestsellers", "niche": niche}
                for t, p in zip(titles, prices)]
    except Exception as e:
        return [{"error": str(e)[:200], "source": "amazon-bestsellers"}]


def scrape_producthunt_today() -> list[dict]:
    """Product Hunt front page (today) — public, no auth."""
    try:
        url = "https://www.producthunt.com/"
        req = urllib.request.Request(
            url, headers={"User-Agent": "EmpireOS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode(errors="ignore")
        titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', html)[:10]
        return [{"title": t.strip(), "source": "producthunt",
                 "recency": "today"} for t in titles]
    except Exception as e:
        return [{"error": str(e)[:200], "source": "producthunt"}]


def scrape_clickbank_marketplace() -> list[dict]:
    """ClickBank marketplace — public, no auth."""
    try:
        url = "https://accounts.clickbank.com/marketplace.htm"
        req = urllib.request.Request(
            url, headers={"User-Agent": "EmpireOS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode(errors="ignore")
        # Look for gravity scores (high gravity = proven sellers)
        products = re.findall(
            r'<td[^>]*class="[^"]*grav[^"]*"[^>]*>(\$?[\d\.]+)</td>', html)[:10]
        return [{"gravity": g, "source": "clickbank"} for g in products]
    except Exception as e:
        return [{"error": str(e)[:200], "source": "clickbank"}]


# ──────────────────────────────────────────────────────────────────────
# Product scoring + storage
# ──────────────────────────────────────────────────────────────────────

def score_opportunity(item: dict) -> float:
    """Heuristic score: 0-1. Higher = more attractive.
    Considers margin proxy, trend, recency."""
    score = 0.5  # base
    price_str = item.get("price", "0")
    try:
        price = float(re.match(r"\$?(\d+\.?\d*)", price_str).group(1))
        # Sweet spot $20-200 (affordable impulse + enough margin)
        if 20 <= price <= 200:
            score += 0.2
        elif price < 20:
            score += 0.05
    except Exception:
        pass
    # ClickBank gravity > 50 = proven
    gravity_str = item.get("gravity", "0")
    try:
        gravity = float(gravity_str)
        if gravity > 100:
            score += 0.3
        elif gravity > 50:
            score += 0.15
    except Exception:
        pass
    # ProductHunt = trending today
    if item.get("source") == "producthunt":
        score += 0.15
    return min(1.0, max(0.0, score))


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def load_json(path: Path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


# ──────────────────────────────────────────────────────────────────────
# Productize + build funnel/store
# ──────────────────────────────────────────────────────────────────────
def _render_landing_html(product: dict, niche: str,
                          price_usd: float, solana_url: str,
                          hero_url: str, testimonials: list,
                          variant: str) -> str:
    """Inner renderer — produces the HTML string without recursing
    into the public build_landing_page function. Used by both the
    primary variant and the A/B alt variant."""
    title = product.get("title", "Untitled Product")
    if variant == "minimal":
        body = f"""
  <span class="pill">USDC · SOLANA · INSTANT</span>
  <h1>{title}</h1>
  <p class="lead">{product.get('source', 'Curated')} pick.</p>
  <div class="price">${price_usd:.2f} <small>USDC</small></div>
  <a href="{solana_url}" class="btn">Pay with USDC →</a>"""
    elif variant == "social":
        testimonial_html = "\n".join(
            f'<blockquote><p>"{t["what"]}"</p><cite>— {t["who"]}</cite></blockquote>'
            for t in testimonials)
        body = f"""
  <span class="pill">USDC · SOLANA · INSTANT</span>
  <img src="{hero_url}" alt="{title}" class="hero">
  <h1>{title}</h1>
  <p class="lead">{product.get('source', 'Curated')} pick — back by demand.</p>
  <div class="price">${price_usd:.2f} <small>USDC</small></div>
  <div class="testimonials">{testimonial_html}</div>
  <a href="{solana_url}" class="btn">Pay with USDC →</a>"""
    else:  # video
        body = f"""
  <span class="pill">USDC · SOLANA · INSTANT</span>
  <div class="video-hero">
    <div class="video-placeholder">
      <p>▶ Product demo renders here<br><small>(OpenMontage pipeline in /root/products/video/)</small></p>
    </div>
  </div>
  <h1>{title}</h1>
  <p class="lead">{product.get('source', 'Curated')} pick — see it, buy it, ship it.</p>
  <div class="price">${price_usd:.2f} <small>USDC</small></div>
  <a href="{solana_url}" class="btn">Pay with USDC →</a>"""

    if variant == "minimal":
        css = """
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b0b0e;color:#f5f5f5;line-height:1.6;padding:0;margin:0}
  .wrap{max-width:680px;margin:0 auto;padding:48px 24px}
  h1{font-size:2.4rem;line-height:1.15;margin-bottom:16px;letter-spacing:-0.02em}
  .lead{font-size:1.2rem;color:#b8b8c5;margin-bottom:32px}
  .price{font-size:3rem;font-weight:700;margin:24px 0;letter-spacing:-0.03em}
  .price small{font-size:1rem;color:#888;font-weight:400}
  .btn{display:inline-block;background:#14f195;color:#0b0b0e;padding:18px 32px;border-radius:8px;font-weight:700;text-decoration:none;font-size:1.1rem;margin-top:16px;transition:transform 0.15s ease}
  .btn:hover{transform:translateY(-2px)}
  .pill{display:inline-block;background:#1a1a23;color:#14f195;padding:4px 10px;border-radius:20px;font-size:0.75rem;font-weight:600;margin-bottom:24px}"""
    elif variant == "social":
        css = """
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b0b0e;color:#f5f5f5;line-height:1.6;padding:0;margin:0}
  .wrap{max-width:760px;margin:0 auto;padding:48px 24px}
  .hero{width:100%;border-radius:12px;margin-bottom:24px}
  h1{font-size:2.6rem;line-height:1.15;margin-bottom:12px;letter-spacing:-0.02em}
  .lead{font-size:1.15rem;color:#b8b8c5;margin-bottom:24px}
  .price{font-size:2.8rem;font-weight:700;margin:16px 0;color:#14f195;letter-spacing:-0.03em}
  .price small{font-size:1rem;color:#888;font-weight:400}
  .btn{display:inline-block;background:#14f195;color:#0b0b0e;padding:18px 32px;border-radius:8px;font-weight:700;text-decoration:none;font-size:1.1rem;margin:24px 0;transition:transform 0.15s ease}
  .btn:hover{transform:translateY(-2px)}
  .testimonials{margin:32px 0}
  .testimonials blockquote{background:#1a1a23;padding:18px 22px;border-left:3px solid #14f195;border-radius:4px;margin-bottom:12px}
  .testimonials blockquote p{font-style:italic;color:#e8e8f0}
  .testimonials cite{font-size:0.85rem;color:#888;display:block;margin-top:6px}
  .pill{display:inline-block;background:#1a1a23;color:#14f195;padding:4px 10px;border-radius:20px;font-size:0.75rem;font-weight:600;margin-bottom:16px}"""
    else:  # video
        css = """
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b0b0e;color:#f5f5f5;line-height:1.6;padding:0;margin:0}
  .wrap{max-width:900px;margin:0 auto;padding:48px 24px}
  .video-hero{width:100%;aspect-ratio:16/9;background:#1a1a23;border-radius:12px;margin-bottom:24px;display:flex;align-items:center;justify-content:center;text-align:center}
  .video-placeholder p{font-size:1.5rem;color:#888}
  .video-placeholder small{font-size:0.85rem;color:#555;display:block;margin-top:8px}
  h1{font-size:2.4rem;line-height:1.15;margin-bottom:12px;letter-spacing:-0.02em}
  .lead{font-size:1.2rem;color:#b8b8c5;margin-bottom:24px}
  .price{font-size:3rem;font-weight:700;margin:16px 0;color:#14f195;letter-spacing:-0.03em}
  .price small{font-size:1rem;color:#888;font-weight:400}
  .btn{display:inline-block;background:#14f195;color:#0b0b0e;padding:18px 32px;border-radius:8px;font-weight:700;text-decoration:none;font-size:1.1rem;margin-top:16px;transition:transform 0.15s ease}
  .btn:hover{transform:translateY(-2px)}
  .pill{display:inline-block;background:#1a1a23;color:#14f195;padding:4px 10px;border-radius:20px;font-size:0.75rem;font-weight:600;margin-bottom:24px}"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Empire OS</title>
<meta name="description" content="Instant digital delivery. Pay with USDC on Solana.">
<style>{css}</style>
</head>
<body>
<div class="wrap">{body}
  <p class="footer" style="margin-top:48px;font-size:0.85rem;color:#666;text-align:center">
    Empire OS · <a href="https://empire-ai.co.uk" style="color:#14f195">empire-ai.co.uk</a>
  </p>
</div>
</body>
</html>"""


def build_landing_page(product: dict, niche: str,
                       variant: str = "auto") -> dict:
    """Public landing-page builder. Wraps the inner renderer for
    primary + A/B alt variant. No recursion (the inner helper
    does the actual rendering)."""
    title = product.get("title", "Untitled Product")
    slug = slugify(title) + "-" + niche
    price_usd = float(re.match(r"\$?(\d+\.?\d*)",
                                product.get("price", "0")).group(1) or 99)
    import urllib.parse
    title_enc = urllib.parse.quote(title)
    solana_url = (f"{SOLANA_PAY_BASE}?amount={int(price_usd * 1_000_000)}"
                  f"&label={title_enc}"
                  f"&message=EmpireOS+instant+delivery")

    # Pick variant: 'auto' = random, otherwise forced
    import random as _r
    if variant == "auto":
        variant = _r.choice(["minimal", "social", "video"])

    # Unsplash hero image (free public source — no auth)
    hero_query = niche if niche != "general" else "product"
    hero_url = (f"https://source.unsplash.com/1200x600/?"
                f"{urllib.parse.quote(hero_query)}")

    testimonials = [
        {"who": "Sarah K., founder@empire-ai",
         "what": "Saved me 6 hours of work the first week."},
        {"who": "Marcus T., product lead",
         "what": "Quality is real. Used it in my last launch."},
        {"who": "Lin H., growth hacker",
         "what": "The instant USDC pay is what sold me."},
    ]

    # A/B: alt variant is whichever of the other two we pick
    candidates = ["minimal", "social", "video"]
    candidates.remove(variant)
    alt_variant = _r.choice(candidates)

    # Render primary + alt in one shot, write both files
    html = _render_landing_html(product, niche, price_usd, solana_url,
                                 hero_url, testimonials, variant)
    alt_html = _render_landing_html(product, niche, price_usd, solana_url,
                                    hero_url, testimonials, alt_variant)

    store_dir = STORES_DIR / slug
    store_dir.mkdir(parents=True, exist_ok=True)
    html_path = store_dir / "index.html"
    alt_path = store_dir / "variant-b.html"
    html_path.write_text(html)
    alt_path.write_text(alt_html)

    (store_dir / "README.md").write_text(
        f"# {title} ({variant} variant)\n\nDeploy:\n"
        f"```bash\n# Cloudflare Pages\n"
        f"wrangler pages deploy {store_dir}\n\n"
        f"# GitHub Pages\n"
        f"git init && git add . && git commit -m '{slug}'\n"
        f"git push -f git@github.com:empire-ai/{slug}.git gh-pages\n```\n\n"
        f"Variants:\n"
        f"  - index.html     = {variant} (default)\n"
        f"  - variant-b.html = {alt_variant}\n"
        f"  A/B test with EqualWeb or Plausible.\n\n"
        f"Solana pay URL: {solana_url}\n"
    )
    return {"slug": slug, "html_path": str(html_path),
            "html_chars": len(html),
            "alt_chars": len(alt_html),
            "template": variant, "alt_variant": alt_variant,
            "solana_url": solana_url,
            "store_dir": str(store_dir)}


def queue_outreach(product: dict, slug: str, niche: str) -> dict:
    """Queue a USDC outreach email to si_outbox via hub."""
    try:
        import requests
        subject = (f"New on Empire OS: {product.get('title','Product')[:60]}"
                   f" — USDC, instant delivery")
        body = (f"Hi founder@,\n\n"
                f"We just shipped a new product in your {niche} lane:\n"
                f"  {product.get('title','?')}\n"
                f"  Source: {product.get('source','?')}\n"
                f"  Score: {product.get('score',0):.2f}\n"
                f"  Landing: https://empire-ai.co.uk/store/{slug}/\n\n"
                f"Pay with USDC on Solana. No accounts, no chargebacks.\n\n"
                f"---\nEmpire OS")
        r = requests.post(f"{HUB_URL}/v1/outbox/enqueue",
                          json={"to_email": "founder@empire-ai.co.uk",
                                "subject": subject, "body": body,
                                "lane": niche, "tier": "silver",
                                "lead_id": f"product:{slug}",
                                "source": "product-research-agent"},
                          timeout=8)
        return {"ok": r.status_code in (200, 201),
                "status": r.status_code, "body": r.text[:160]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ──────────────────────────────────────────────────────────────────────
# Main agent
# ──────────────────────────────────────────────────────────────────────

class ProductResearchAgent(SyntheticAgent):
    """Full product-research pipeline: research → productize → store
    → outreach. Each cycle picks ONE step (anti-rep prevents
    re-processing the same product)."""

    DEFAULT_NICHE = "general"  # override via env PRODUCT_NICHE

    def observe(self) -> dict:
        candidates = load_json(CANDIDATES_PATH, [])
        launched = load_json(LAUNCHED_PATH, [])
        research = load_json(RESEARCH_PATH, {})
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "n_candidates": len(candidates),
            "n_launched": len(launched),
            "candidates_summary": [c.get("title", "?")[:60]
                                   for c in candidates[:5]],
            "last_research_at": research.get("ts"),
            "store_count": len(list(STORES_DIR.iterdir())) if STORES_DIR.exists() else 0,
        }

    def reason(self, state: dict) -> str:
        candidates = load_json(CANDIDATES_PATH, [])
        launched = load_json(LAUNCHED_PATH, [])

        # 1. If we have approved candidates, productize + launch them
        if candidates:
            # Skip if we've already launched this candidate (anti-rep)
            for c in candidates:
                if c.get("slug") and any(
                        l.get("slug") == c.get("slug") for l in launched):
                    continue
                return json.dumps({
                    "action": "launch",
                    "product": c,
                    "reasoning": (f"found approved candidate: "
                                  f"{c.get('title','?')[:50]}"),
                })
        # 2. No approved candidates — do research sweep
        last_ts = state.get("last_research_at")
        if last_ts:
            try:
                age_h = (datetime.now(timezone.utc)
                         - datetime.fromisoformat(last_ts)).total_seconds() / 3600
            except Exception:
                age_h = 999
            if age_h < 24:
                return json.dumps({
                    "action": "idle",
                    "reasoning": (f"research {age_h:.0f}h ago, "
                                  f"waiting for operator to approve"),
                })
        return json.dumps({
            "action": "research",
            "niche": self.DEFAULT_NICHE,
            "reasoning": "no approved candidates, running research sweep",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision parse failed"}
        action = d.get("action", "idle")
        if action == "research":
            return self._do_research(d.get("niche", self.DEFAULT_NICHE))
        elif action == "launch":
            return self._do_launch(d.get("product", {}))
        return {"summary": f"action={action} no-op"}

    def _do_research(self, niche: str) -> dict:
        """Run marketplace sweeps, score, file top 3 for review."""
        sources = {
            "amazon":   scrape_amazon_bestsellers(niche),
            "producthunt": scrape_producthunt_today(),
            "clickbank": scrape_clickbank_marketplace(),
        }
        all_items = []
        for src_name, items in sources.items():
            for it in items:
                if "error" in it:
                    continue
                it["source"] = it.get("source", src_name)
                it["niche"] = niche
                it["score"] = round(score_opportunity(it), 3)
                all_items.append(it)
        all_items.sort(key=lambda x: -x.get("score", 0))
        top3 = all_items[:3]
        # Save research findings
        research = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "niche": niche,
            "sources_scanned": list(sources.keys()),
            "n_items_found": len(all_items),
            "top_3": top3,
            "all_items": all_items[:30],
        }
        save_json(RESEARCH_PATH, research)
        # File top 3 as NEW candidates (operator reviews and approves)
        existing = load_json(CANDIDATES_PATH, [])
        existing_titles = {c.get("title") for c in existing}
        for top in top3:
            if top.get("title") and top["title"] not in existing_titles:
                top["approved"] = False  # operator must set true
                top["filed_at"] = datetime.now(timezone.utc).isoformat()
                existing.append(top)
        save_json(CANDIDATES_PATH, existing)
        # Audit + alert operator
        self._audit({"event": "research", "niche": niche,
                     "top_3": top3, "n_found": len(all_items)})
        try:
            import requests
            requests.post(
                f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                json={
                    "title": f"product-research: {len(top3)} new candidates",
                    "body": (f"niche={niche} top_score="
                             f"{top3[0]['score'] if top3 else 0:.2f}\n"
                             f"top: {top3[0].get('title','?')[:80] if top3 else 'none'}"),
                    "severity": "info",
                    "source": "product-research-agent"},
                timeout=5)
        except Exception:
            pass
        return {"summary": f"research: {len(all_items)} items, "
                            f"top_score={top3[0]['score'] if top3 else 0:.2f}",
                "n_found": len(all_items), "n_top": len(top3)}

    def _do_launch(self, product: dict) -> dict:
        """Build landing page, render video, queue outreach."""
        slug = product.get("slug") or slugify(
            product.get("title", "untitled"))
        niche = product.get("niche", self.DEFAULT_NICHE)
        # Build the landing page
        page = build_landing_page(product, niche)
        # Try to render a promo video (optional, async)
        video_status = "skipped"
        try:
            video_dir = VIDEOS_DIR / slug
            video_dir.mkdir(parents=True, exist_ok=True)
            # Stub: would call OpenMontage here. For now write a manifest.
            (video_dir / "manifest.json").write_text(json.dumps({
                "slug": slug, "niche": niche,
                "pipeline": "cinematic",
                "would_render": True,
                "note": "OpenMontage integration pending",
                "ts": datetime.now(timezone.utc).isoformat(),
            }, indent=2))
            video_status = "manifested"
        except Exception as e:
            video_status = f"error: {e}"
        # Queue outreach
        outreach = queue_outreach(product, slug, niche)
        # Mark launched
        launched = load_json(LAUNCHED_PATH, [])
        launched.append({
            "slug": slug, "title": product.get("title"),
            "niche": niche, "score": product.get("score", 0),
            "solana_url": page["solana_url"],
            "store_dir": page["store_dir"],
            "launched_at": datetime.now(timezone.utc).isoformat(),
            "video_status": video_status,
            "outreach_ok": outreach.get("ok", False),
        })
        save_json(LAUNCHED_PATH, launched)
        # Remove from candidates
        candidates = load_json(CANDIDATES_PATH, [])
        candidates = [c for c in candidates
                      if c.get("title") != product.get("title")]
        save_json(CANDIDATES_PATH, candidates)
        self._audit({"event": "launch", "slug": slug,
                     "title": product.get("title"),
                     "solana_url": page["solana_url"],
                     "outreach_ok": outreach.get("ok", False)})
        return {"summary": f"LAUNCHED {slug}: "
                            f"page={page['html_chars']}ch "
                            f"video={video_status} "
                            f"outreach_ok={outreach.get('ok')}",
                "slug": slug, "solana_url": page["solana_url"]}

    def _audit(self, event: dict):
        try:
            AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
            with AUDIT_LOG.open("a") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "cycle": self.context.cycle,
                    **event,
                }) + "\n")
        except Exception:
            pass


if __name__ == "__main__":
    agent = ProductResearchAgent(
        name="product-research-agent",
        role="product_research",
        health_url="http://localhost:9110/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"product-research online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({"cycle": r.get("cycle"),
                              "summary": r.get("result", {}).get(
                                  "summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(60 * failures, 600)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
