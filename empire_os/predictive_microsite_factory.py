"""Draft-only Predictive Cloud -> geographically specific microsite proposal.

Builds HTML previews from provided evidence. Never publishes, indexes, sends email,
claims buyer capacity, or assumes local ZIP/postcode membership.
"""
from __future__ import annotations

from datetime import datetime
from base64 import b64encode
from hashlib import sha256
from html import escape
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from empire_os.microsite_cinematic_background import (
    chicago_night_skyline_data_uri, chicago_premium_css,
    chicago_owner_photo_data_uri, CHICAGO_PHOTO_SHA256,
    CHICAGO_PHOTO_CREDIT_URL, CHICAGO_PHOTO_LICENSE_URL,
    chicago_worker_research_photo_data_uri,
    chicago_4k_photo_asset_validated, CHICAGO_4K_PHOTO_SHA256,
    CHICAGO_WORKER_PHOTO_SOURCE, CHICAGO_WORKER_PHOTO_SHA256,
    chicago_4k_visual_refinement_css, chicago_native_4k_layout_css,
    chicago_research_depth_v10_css,
)
from empire_os.geo_registry import acquisition_markets
from empire_os.keyword_universe import review_keyword_record
from empire_os.third_party.slopmonster.deslop import audit, normalise, visible_text


# Original site-owned branding is read without modifying the website's assets.
BRAND_ASSET = Path(__file__).resolve().parent.parent / "apps/empire-public-site/public/brand/empire-logo.svg"


PRIVATE_APPROVED_BRAND_SHA256 = "55e98ad2ae182991d95908738135779102beb81818cd7c3607a3a49e1f2aa596"
CANONICAL_BRAND_CONTRACT_SHA256 = "ead735b5e223a3b179a23965c1ff11dc67efb78b4cd4e71df9b60550872bc518"


def _canonical_brand_contract() -> dict[str, Any] | None:
    """Use the EXISTING founder-approved brand contract, never a new palette.

    A canonical-branded preview fails closed when the brand contract/asset has
    been changed or is unavailable. This grants no public distribution rights.
    """
    value = os.environ.get("EMPIRE_AI_CANONICAL_BRAND_CONTRACT")
    if not value:
        return None
    path = Path(value)
    if path.is_symlink() or not path.is_file():
        raise ValueError("existing canonical brand contract is missing or a symlink")
    raw = path.read_bytes()
    if len(raw) > 10000 or sha256(raw).hexdigest() != CANONICAL_BRAND_CONTRACT_SHA256:
        raise ValueError("existing canonical brand contract digest mismatch")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("canonical brand contract invalid") from exc
    if (data.get("schema") != "empire.ai.brand.canonical_reference.v1"
            or data.get("brand") != "Empire AI"
            or data.get("brand_name") != "EMPIRE AI"
            or data.get("strapline") != "PREDICTIVE REVENUE INFRASTRUCTURE"
            or data.get("colour_tokens") != {
                "deep_navy": "#01091C", "cobalt": "#005AFF",
                "electric_cyan": "#02C7FE", "ice": "#E7F1FD",
                "slate": "#8EA1BF"}):
        raise ValueError("existing canonical brand contract identity mismatch")
    return data


def _original_brand_image() -> tuple[str, str]:
    # Optional PRIVATE staging-only brand approval candidate: use the existing
    # owner-custodied raster by exact hash. Never commit or transfer its bytes.
    # The website/brand owner still has to approve its production distribution.
    contract = _canonical_brand_contract()
    private_path = os.environ.get("EMPIRE_MICROSITE_PRIVATE_APPROVED_LOGO")
    if contract is not None and not private_path:
        raise ValueError("canonical brand requires owner-custodied original raster")
    if private_path:
        image_path = Path(private_path)
        if image_path.is_symlink() or not image_path.is_file():
            raise ValueError("private original logo must be a regular existing file")
        source = image_path.read_bytes()
        if (sha256(source).hexdigest() != PRIVATE_APPROVED_BRAND_SHA256
                or len(source) > 150000
                or source[:8] != b"\x89PNG\r\n\x1a\n"
                or source[12:16] != b"IHDR"
                or int.from_bytes(source[16:20], "big") != 820
                or int.from_bytes(source[20:24], "big") != 160):
            raise ValueError("private original logo fingerprint mismatch")
        return "data:image/png;base64," + b64encode(source).decode("ascii"), PRIVATE_APPROVED_BRAND_SHA256
    source = BRAND_ASSET.read_bytes()
    if (not 100 <= len(source) <= 30000
            or b"<svg " not in source[:200]
            or any(marker in source.lower() for marker in
                   (b"<script", b"<foreignobject", b"onload=", b"<!entity", b"<iframe"))):
        raise ValueError("original Empire AI logo asset unavailable or unsafe")
    return "data:image/svg+xml;base64," + b64encode(source).decode("ascii"), sha256(source).hexdigest()


MARKETS = {market.market_id: market for market in acquisition_markets()}
KINDS = {"local_utility", "market_report", "commercial_landing"}
US_ZIP = re.compile(r"[0-9]{5}\Z")
UK_POSTCODE = re.compile(r"(?:GIR\s?0AA|(?:[A-Z]{1,2}[0-9][0-9A-Z]?)\s?[0-9][A-Z]{2})\Z", re.I)
SLUG = re.compile(r"[^a-z0-9]+")
STOPWORDS = {"the", "and", "with", "from", "this", "that", "your", "into", "local",
             "for", "you", "are", "our", "about", "research", "review", "area"}


def _string(value: Any, name: str, max_chars: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_chars:
        raise ValueError(f"{name} must be non-empty text up to {max_chars} characters")
    return value.strip()


def _slug(text: str) -> str:
    return SLUG.sub("-", text.casefold()).strip("-")[:85]


def _safe_text(text: str) -> str:
    return escape(text, quote=True)


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.casefold()) if w not in STOPWORDS}


def _fact_rows(spec: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = spec.get("local_facts", [])
    if not isinstance(rows, list):
        raise ValueError("local_facts must be a list")
    result = []
    for n, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"local_facts[{n}] must be an object")
        result.append({
            "statement": _string(row.get("statement"), f"fact {n} statement", 800),
            "source_ref": _string(row.get("source_ref"), f"fact {n} source_ref", 350),
            "checked_at": _string(row.get("checked_at"), f"fact {n} checked_at", 30),
        })
        if row.get("official_url") is not None:
            url = _string(row["official_url"], f"fact {n} official_url", 450)
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.username or parsed.password
                    or parsed.port is not None or parsed.query or parsed.fragment
                    or not parsed.hostname
                    or parsed.hostname not in {
                        "chicago.gov", "www.chicago.gov", "311.chicago.gov",
                        "webapps1.chicago.gov", "idfpr.illinois.gov",
                        "www.census.gov",
                    }):
                raise ValueError(f"fact {n} official_url must link directly to an approved government host")
            result[-1]["official_url"] = url
        try:
            datetime.fromisoformat(result[-1]["checked_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"fact {n} invalid timestamp") from exc
    return result


def review_geography(geo: Mapping[str, Any]) -> dict[str, Any]:
    market_id = _string(geo.get("market_id"), "market_id", 60)
    market = MARKETS.get(market_id)
    if market is None:
        raise ValueError("market_id absent from original EmpireOS geo registry")
    kind = geo.get("kind", "metro")
    if kind not in {"metro", "us_zip", "uk_postcode"}:
        raise ValueError("unsupported territory kind")
    area = _string(geo.get("area", market.metro), "area", 90)
    refs = geo.get("evidence_refs", [])
    if not isinstance(refs, list):
        raise ValueError("geography evidence_refs must be a list")
    valid_refs = [s.strip() for s in refs if isinstance(s, str) and s.strip()]
    if kind == "metro" and area.casefold() != market.metro.casefold():
        raise ValueError("metro name must match canonical geographic registry")
    if kind == "us_zip" and (market.country_code != "US" or not US_ZIP.fullmatch(area)):
        raise ValueError("ZIP must be five digits in a US market")
    if kind == "uk_postcode" and (market.country_code != "GB" or not UK_POSTCODE.fullmatch(area)):
        raise ValueError("postcode must be UK format in a UK market")
    # String shape cannot validate that the postcode/ZIP belongs to this city.
    qualified = kind == "metro" or (geo.get("market_match_verified") is True and bool(valid_refs))
    return {
        "market_id": market_id, "metro": market.metro, "country_code": market.country_code,
        "kind": kind, "area": area, "evidence_refs": valid_refs,
        "region_verified": qualified,
        "review_note": ("market anchor only: ZIP/postcode not independently validated"
                        if kind != "metro" and not qualified else None),
    }


def review_copy(copy: str) -> dict[str, Any]:
    """Use actual pinned SlopMonster code, retaining findings rather than editing."""
    text = normalise(copy)
    findings = audit(text)
    categories = {
        category: [
            {"label": str(x[0]), "detail": str(x[1])} if isinstance(x, tuple)
            else {"label": str(x)}
            for x in matches
        ]
        for category, matches in findings.items()
        if matches
    }
    return {"engine": "SlopMonster", "pinned_commit": "3fc9787d9337b57c599a80afbefbbb3be5a8eb0b",
            "score": 5 - len(categories), "categories": categories,
            "review_required": bool(categories)}


def _template(spec: Mapping[str, Any], geo: dict, facts: list[dict[str, str]],
              title: str, subhead: str, summary: str, keyword: str) -> str:
    kind = spec.get("site_kind")
    canonical = _canonical_brand_contract()
    logo_src, _ = _original_brand_image()
    tokens = canonical["colour_tokens"] if canonical else None
    primary = tokens["electric_cyan"] if tokens else (
        "#65c7ff" if kind != "market_report" else "#e9bb65")
    signal = tokens["electric_cyan"] if tokens else "#e9bb65"
    ink = tokens["ice"] if tokens else "#f1f5fa"
    dim = tokens["slate"] if tokens else "#b9c8df"
    canvas = tokens["deep_navy"] if tokens else "#060d1b"
    cobalt = tokens["cobalt"] if tokens else "#174c7e"
    cyan = tokens["electric_cyan"] if tokens else "#87d7ff"
    evidence_cards = "\n".join(
        f'<article class="fact"><span class="micro">Evidence note {i}</span>'
        f'<p>{_safe_text(f["statement"])}</p>'
        f'<p class="source">Reference: {_safe_text(f["source_ref"])} · Checked: {_safe_text(f["checked_at"])}</p>'
        + (f'<a class="official-link" href="{_safe_text(f["official_url"])}" rel="noopener noreferrer" target="_blank">Read official source</a>'
           if f.get("official_url") else "")
        + '</article>'
        for i, f in enumerate(facts, 1)
    )
    checklist_items = spec.get("research_steps", [])
    if not isinstance(checklist_items, list) or len(checklist_items) > 8:
        raise ValueError("research_steps must be a list with at most eight items")
    if checklist_items and len(checklist_items) < 3:
        raise ValueError("research_steps needs at least three actionable items")
    checklist_items = [
        _string(item, f"research_steps[{n}]", 300)
        for n, item in enumerate(checklist_items)
    ]
    if len(set(item.casefold() for item in checklist_items)) != len(checklist_items):
        raise ValueError("duplicate steps cannot create local page utility")
    checklist = (
        '<section aria-labelledby="utility-title"><p class="tag">Practical planning tool</p>'
        '<h2 id="utility-title">A decision checklist for this project</h2>'
        '<ol class="decision-list">' +
        ''.join(f'<li>{_safe_text(item)}</li>' for item in checklist_items) +
        '</ol></section>'
        if checklist_items else ""
    )
    if not evidence_cards:
        evidence_cards = '<p>No local evidence supplied. This proposal is held for research.</p>'
    title_html = _safe_text(title)
    sub_html = _safe_text(subhead)
    location = _safe_text(geo["area"])
    summary_html = _safe_text(summary)
    kw_html = _safe_text(keyword)
    # The founder's accepted visual direction applies only to the single
    # researched Chicago citywide pilot. Other geographies keep their original
    # preview presentation; never reuse Chicago imagery on arbitrary markets.
    chicago_design = (
        canonical is not None
        and geo.get("market_id") == "US-IL"
        and geo.get("kind") == "metro"
        and kind == "local_utility"
    )
    cinematic_css = (chicago_premium_css()
                     + chicago_4k_visual_refinement_css()
                     + chicago_native_4k_layout_css()
                     + chicago_research_depth_v10_css()
                     if chicago_design else "")
    # Compact Chicago-only CSS to respect the existing strict 400KB QA cap.
    cinematic_css = re.sub(r"\s+", " ", cinematic_css).strip()
    photo_asset = chicago_owner_photo_data_uri() if chicago_design else None
    worker_asset = chicago_worker_research_photo_data_uri() if chicago_design else None
    city_image = photo_asset or (chicago_night_skyline_data_uri() if chicago_design else None)
    # Embed the high-compression offline city image exactly ONCE. Refer to its
    # CSS custom property in both city-photo elements to respect the original
    # site owner's strict 400KB standalone HTML QA size cap.
    city_photo_css_token = (
        ' style="--chicago-city-image:url(' + city_image + ')"'
        if city_image else ""
    )
    cityscape = (
        '<div class="site-art" aria-hidden="true"'
        ' style="background-image:var(--chicago-city-image)"></div>'
        if city_image else ""
    )
    photo_credit = (
        '<span class="photo-attribution">Chicago River skyline photograph: '
        '<a href="' + CHICAGO_PHOTO_CREDIT_URL
        + '" rel="noopener noreferrer" target="_blank">Gael D / Unsplash</a>'
        ' · <a href="' + CHICAGO_PHOTO_LICENSE_URL
        + '" rel="noopener noreferrer" target="_blank">Unsplash License</a>'
        ' · dark overlay and WebP adaptation</span>'
        if photo_asset else ""
    )
    visual_research_heroes = ""
    if chicago_design and worker_asset and city_image:
        # Distinct source-verified scenes, photo-labelled as illustrative.
        # These are visual research navigation cards, not service offers.
        visual_research_heroes = (
            '<div class="research-intro"><div>'
            '<p class="tag">Original source investigation</p>'
            '<h2>Know the rules. Verify the source.</h2></div>'
            '<p>A visual guide to Chicago permit requirements, Illinois roofing licences '
            'and address-based records. No inferred local demand or contractor endorsements.</p></div>'
            '<div class="research-signal-strip" aria-label="Scope of the source review">'
            '<div class="research-signal"><strong class="research-signal-mark">'
            + str(len(facts)).zfill(2) + '</strong>'
            '<span>Original reference notes</span></div>'
            '<div class="research-signal"><strong class="research-signal-mark">02</strong>'
            '<span>Official research pathways</span></div>'
            '<div class="research-signal"><strong class="research-signal-mark">✓</strong>'
            '<span>Research only · no sales claims</span></div>'
            '</div>'
            '<div class="research-visual-grid" aria-label="Two official research pathways">'
            '<article class="research-visual-hero photo-field" style="--feature-image:url('
            + worker_asset + ')">'
            '<span class="visual-caption">Illustrative roofing photo · Houston, TX</span>'
            '<div class="research-visual-content"><span class="tag">01 / PROJECT SCOPE</span>'
            '<h3>Understand the work before the permit</h3>'
            '<p>Roof layers, repairs and structural changes can affect which application applies.</p>'
            '<a href="https://chicago.gov/city/en/sites/guide-to-building-permits/home/help/faq/DOB/EPP-eligible.html" '
            'target="_blank" rel="noopener noreferrer">City of Chicago permit guidance</a>'
            '</div></article>'
            '<article class="research-visual-hero photo-city" style="--feature-image:var(--chicago-city-image)">'
            '<span class="visual-caption">Chicago River · source-backed cityscape</span>'
            '<div class="research-visual-content"><span class="tag">02 / PUBLIC RECORD</span>'
            '<h3>Verify the address and licence</h3>'
            '<p>Check the original permit application status and Illinois contractor licence records.</p>'
            '<a href="https://webapps1.chicago.gov/buildingpermit/help" '
            'target="_blank" rel="noopener noreferrer">Official building permit lookup</a>'
            '</div></article></div>'
            '<div class="evidence-path" aria-label="Research verification sequence">'
            '<div class="evidence-path-item"><span class="evidence-path-num">01</span>'
            '<span class="evidence-path-label">Permit criteria'
            '<span class="evidence-path-detail">City of Chicago guidance</span></span></div>'
            '<div class="evidence-path-item"><span class="evidence-path-num">02</span>'
            '<span class="evidence-path-label">Licence lookup'
            '<span class="evidence-path-detail">Illinois IDFPR original source</span></span></div>'
            '<div class="evidence-path-item"><span class="evidence-path-num">03</span>'
            '<span class="evidence-path-label">Property record'
            '<span class="evidence-path-detail">Actual address, not ZIP inference</span></span></div>'
            '</div>'
        )
    if worker_asset:
        photo_credit += (
            '<span class="photo-attribution">Roof-work image: '
            '<a href="' + CHICAGO_WORKER_PHOTO_SOURCE
            + '" rel="noopener noreferrer" target="_blank">Zohair Mirza / Unsplash</a>'
            ' · illustrative Houston worksite, not a Chicago provider</span>'
        )
    if chicago_design and ":" in title:
        left, right = title.split(":", 1)
        title_html = (
            '<span class="hero-title-base">' + _safe_text(left + ":") + '</span>'
            '<span class="hero-title-accent">' + _safe_text(right.strip()) + '</span>'
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="color-scheme" content="dark">
<title>{title_html} | Empire AI Research Preview</title>
<meta name="description" content="{_safe_text(summary[:155])}">
<style>
:root {{color-scheme:dark; --ink:{ink}; --dim:{dim}; --accent:{primary}; --signal:{signal}; --brand-cobalt:{cobalt}; --brand-cyan:{cyan};}}
* {{box-sizing:border-box}}
html {{scroll-behavior:smooth}}
body {{margin:0; font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif; background:{canvas}; color:var(--ink); line-height:1.6;}}
body::before {{content:"";position:absolute;left:0;top:0;width:100%;height:600px;pointer-events:none;
 background:radial-gradient(ellipse at 75% 15%,var(--brand-cobalt) 0%,transparent 52%),
 radial-gradient(ellipse at 30% 50%,#13243a 0%,transparent 55%);opacity:.8}}
a {{color:inherit}}
.skip {{position:absolute;left:-9999px;top:4px}}
.skip:focus {{left:10px;z-index:10;background:white;color:black;padding:12px}}
header,main,footer {{position:relative}}
.wrap {{max-width:1120px;margin:auto;padding:0 26px}}
nav {{min-height:82px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}
.wordmark {{display:block;max-width:215px;min-width:125px;width:29vw;height:auto}}
.hero-layout {{display:grid;grid-template-columns:minmax(0,1fr) minmax(230px,300px);align-items:center;gap:28px}}
.hero-content {{min-width:0}}
.signal-panel {{border:1px solid #385575;background:linear-gradient(155deg,#142743dd,#0b1529c9);border-radius:20px;padding:25px;box-shadow:0 28px 65px #0005}}
.signal-head {{font-size:.79rem;letter-spacing:.14em;color:var(--signal);text-transform:uppercase;font-weight:800}}
.signal-value {{font-size:1.12rem;font-weight:750;line-height:1.45;margin:7px 0 15px}}
.signal-rule {{border:0;border-top:1px solid #334968;margin:17px 0}}
.tag,.micro {{font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:var(--signal);font-weight:750}}
.preview {{font-size:.78rem; color:var(--dim);border:1px solid #425976;border-radius:100px;padding:6px 14px}}
.hero {{padding:80px 0 66px;max-width:950px}}
h1 {{font-size:clamp(2.5rem,6.2vw,5.4rem);letter-spacing:-.055em;line-height:1.03;margin:18px 0 24px}}
h2 {{font-size:clamp(1.6rem,3.4vw,2.5rem);line-height:1.15;letter-spacing:-.03em}}
.lede {{font-size:clamp(1.1rem,2vw,1.4rem);max-width:760px;color:#dfebfa;line-height:1.55}}
.desc {{max-width:740px;color:var(--dim)}}
.action {{display:inline-flex;min-height:48px;align-items:center;background:var(--accent);
 color:#07101e;text-decoration:none;border-radius:9px;padding:12px 22px;font-weight:800;margin-top:22px}}
.action:focus-visible,a:focus-visible {{outline:3px solid #fff;outline-offset:4px}}
.grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:20px}}
section {{padding:45px 0}}
.fact {{border:1px solid #283d58;background:#111d30c9;padding:26px;border-radius:16px;overflow-wrap:anywhere}}
.fact p {{font-size:1.04rem}}
.source {{color:var(--dim);font-size:.82rem!important}}
.official-link {{display:inline-flex;align-items:center;min-height:44px;color:var(--brand-cyan);font-weight:700;text-underline-offset:3px}}
.decision-list {{max-width:900px;display:grid;gap:14px;padding-left:24px}}
.decision-list li {{padding:13px 18px;border:1px solid #283d58;border-radius:12px;background:#101c2e}}
.decision-list li::marker {{color:var(--signal);font-weight:800}}
.hint {{border-left:3px solid var(--signal);padding:16px 24px;color:var(--dim);background:#182435}}
footer {{padding:32px 0 48px;color:var(--dim);border-top:1px solid #253750}}
@media(max-width:760px) {{.hero-layout{{grid-template-columns:1fr}} .signal-panel{{max-width:560px}}}}
@media(max-width:600px) {{.hero{{padding:44px 0 32px}} .wrap{{padding:0 20px}} nav{{padding:16px 0}} .wordmark{{width:170px}}}}
@media(prefers-reduced-motion:reduce) {{html{{scroll-behavior:auto}}}}
{cinematic_css}
.photo-attribution {{display:block;max-width:850px;font-size:.72rem;color:var(--dim);padding:8px 0}}
.photo-attribution a {{color:var(--brand-cyan);text-underline-offset:3px}}
</style>
</head>
<body{city_photo_css_token}>
{cityscape}
<a class="skip" href="#main">Skip to content</a>
<header class="wrap"><nav aria-label="Main navigation"><img class="wordmark" src="{logo_src}" alt="Empire AI Predictive Revenue" width="215" height="49">
<span class="preview">Internal draft · not published</span></nav></header>
<main id="main">
<div class="wrap"><section class="hero hero-layout"><div class="hero-content">
<p class="tag">{location} / {kw_html}</p>
<h1>{title_html}</h1><p class="lede">{sub_html}</p>
<p class="desc">{summary_html}</p>
<a class="action" href="#research-method">Review the evidence</a></div>
<aside class="signal-panel" aria-label="Evidence summary">
<p class="signal-head">Research status</p><p class="signal-value">Source review in progress</p>
<hr class="signal-rule"><p class="signal-head">Evidence references supplied</p>
<p class="signal-value">{len(facts)} reference notes</p>
<hr class="signal-rule"><p class="signal-head">Commercial verification</p>
<p class="signal-value">Not established by this preview</p></aside>
</section></div>
<div class="wrap"><section id="research-method" aria-labelledby="evidence-title">
<p class="tag">Territory evidence</p><h2 id="evidence-title">What the available research shows</h2>
{visual_research_heroes}
<div class="grid">{evidence_cards}</div></section>
{checklist}
<section aria-labelledby="next-title"><h2 id="next-title">What still needs verifying</h2>
<p class="hint">This is a research preview. Source context, actual demand, local service availability,
buyer acceptance and conversion claims require independent review. No enquiry or payment collection is active.</p>
</section></div></main>
<footer><div class="wrap">Empire AI · Internal preview only · Noindex · No lead collection{photo_credit}</div></footer>
</body></html>"""


def build_candidate(spec: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    """Return proposal and local HTML preview. No database, network, or publishing."""
    if not isinstance(spec, Mapping):
        raise ValueError("input must be an object")
    site_kind = spec.get("site_kind")
    if site_kind not in KINDS:
        raise ValueError("site_kind must be local_utility, market_report or commercial_landing")
    geo = review_geography(spec.get("geography") or {})
    kw = spec.get("keyword_opportunity")
    if not isinstance(kw, Mapping):
        raise ValueError("keyword_opportunity object required")
    keyword_review = review_keyword_record(kw)
    if not keyword_review["review_ready"]:
        raise ValueError(f'invalid keyword opportunity: {keyword_review["blockers"]}')
    record = keyword_review["record"]
    if record["territory_key"] and record["territory_key"] != geo["market_id"]:
        raise ValueError("keyword territory_key must match geographic market_id")
    facts = _fact_rows(spec)
    audience = _string(spec.get("audience"), "audience", 200)
    offer = _string(spec.get("offer"), "offer", 400)
    title = _string(spec.get("headline", f'{record["keyword"].capitalize()}: {geo["area"]}'), "headline", 160)
    subhead = _string(spec.get("subhead", f'A research-led review of {record["keyword"]} in {geo["area"]}.'), "subhead", 300)
    summary = _string(spec.get("summary", offer), "summary", 450)
    # Same text that appears as page copy is checked, rather than only input fields.
    html = _template(spec, geo, facts, title, subhead, summary, record["keyword"])
    copy = visible_text(html)
    slop = review_copy(copy)
    blockers = []
    if not keyword_review["opportunity"]["available"]:
        blockers.append("keyword scoring evidence incomplete")
    if not geo["region_verified"]:
        blockers.append("ZIP/postcode market membership not source-verified")
    if len(facts) < 2:
        blockers.append("at least two independently reviewable local source facts required")
    if len({fact["source_ref"] for fact in facts}) < 2:
        blockers.append("at least two distinct local evidence references required")
    if site_kind == "local_utility" and "research_steps" in spec and len(spec["research_steps"]) < 3:
        blockers.append("at least three distinct actionable utility steps required")
    if slop["review_required"]:
        blockers.append("SlopMonster copy findings require editorial review")
    # Even a candidate with no detected patterns is not automatically publication-ready.
    evidence_notes = ["Sources are provided by the author; content truth and rights not independently verified."]
    identity = sha256(json.dumps(
        {"keyword": record["keyword"], "territory": geo, "site_kind": site_kind,
         "source_refs": [f["source_ref"] for f in facts]}, sort_keys=True
    ).encode()).hexdigest()[:20]
    proposal = {
        "schema_version": "empire.predictive_microsite_candidate.v1",
        "id": f"microsite_{identity}", "status": "HOLD_EVIDENCE" if blockers else "DRAFT_REVIEW",
        "mode": "OBSERVE", "execution_authority": "none",
        "publishing_enabled": False, "indexation_enabled": False,
        "outbound_enabled": False, "payments_enabled": False,
        "candidate_kind": site_kind,
        "brand_profile": ("empire_canonical_reference_v1"
                          if _canonical_brand_contract() else "empire_premium_local"),
        "market": geo, "keyword": keyword_review, "audience": audience, "offer": offer,
        "copy_audit": slop, "content_evidence": facts, "evidence_notes": evidence_notes,
        "html_sha256": sha256(html.encode()).hexdigest(),
        "locally_useful_research_steps": len(spec.get("research_steps", [])),
        "four_k_original_asset_available_for_site_owner": (
            bool(chicago_4k_photo_asset_validated())
            if (_canonical_brand_contract() is not None
                and geo.get("market_id") == "US-IL"
                and geo.get("kind") == "metro"
                and site_kind == "local_utility")
            else False
        ),
        "four_k_background_master_sha256": (
            CHICAGO_4K_PHOTO_SHA256 if (_canonical_brand_contract() is not None
              and geo.get("market_id") == "US-IL"
              and geo.get("kind") == "metro"
              and site_kind == "local_utility"
              and chicago_4k_photo_asset_validated()) else None
        ),
        "illustrative_roofing_photo_used": (
            bool(chicago_worker_research_photo_data_uri()) if
            (_canonical_brand_contract() is not None
             and geo.get("market_id") == "US-IL"
             and geo.get("kind") == "metro" and site_kind == "local_utility")
            else False
        ),
        "illustrative_roofing_photo_sha256": (
            CHICAGO_WORKER_PHOTO_SHA256 if
            (_canonical_brand_contract() is not None
             and geo.get("market_id") == "US-IL" and geo.get("kind") == "metro"
             and site_kind == "local_utility"
             and chicago_worker_research_photo_data_uri()) else None
        ),
        "chicago_photographic_background_used": (
            bool(chicago_owner_photo_data_uri())
            if (_canonical_brand_contract() is not None
                and geo.get("market_id") == "US-IL"
                and geo.get("kind") == "metro"
                and site_kind == "local_utility")
            else False
        ),
        "chicago_photographic_background_sha256": (
            CHICAGO_PHOTO_SHA256
            if (_canonical_brand_contract() is not None
                and geo.get("market_id") == "US-IL"
                and geo.get("kind") == "metro"
                and site_kind == "local_utility"
                and chicago_owner_photo_data_uri())
            else None
        ),
        "cinematic_chicago_art_rendered": (
            _canonical_brand_contract() is not None
            and geo.get("market_id") == "US-IL"
            and geo.get("kind") == "metro"
            and site_kind == "local_utility"
        ),
        "linked_official_source_count": sum(bool(fact.get("official_url")) for fact in facts),
        "source_claims_independently_confirmed_by_site_owner": False,
        "visual_qa": {
            "template_includes": ["responsive_grid", "mobile_viewport", "accessible_skip_link",
                                  "single_h1", "reduced_motion", "focus_visible",
                                  "noindex", "no_live_form", "48px_min_cta"],
            "original_brand_logo_sha256": _original_brand_image()[1],
            "canonical_brand_contract_sha256": (
                CANONICAL_BRAND_CONTRACT_SHA256
                if _canonical_brand_contract() else None
            ),
            "canonical_brand_reference_used": _canonical_brand_contract() is not None,
            "original_brand_logo_source": (
                "existing_empire_ai_canonical_brand_owner_custody"
                if _canonical_brand_contract()
                else "private_original_orbital_a_raster_approval_candidate"
                if os.environ.get("EMPIRE_MICROSITE_PRIVATE_APPROVED_LOGO")
                else "apps/empire-public-site/public/brand/empire-logo.svg"
            ),
            "brand_public_distribution_approved_by_owner": False,
            "browser_visual_review_complete": False,
        },
        "blockers": blockers,
        "required_approvals": ["research_source_owner", "commercial_claim_reviewer",
                               "seo_implementation_owner", "website_release_owner"],
    }
    return proposal, html


def review_portfolio(specs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Detect repeated location-swapped copy before any multi-site release."""
    results = []
    previous: list[tuple[set[str], str]] = []
    for spec in specs:
        proposal, html = build_candidate(spec)
        headline = spec.get("headline", "")
        sub = spec.get("subhead", "")
        summary = spec.get("summary", "")
        # Exclude local geography token strings when comparing core editorial content.
        text = f"{headline} {sub} {summary} " + " ".join(
            row.get("statement", "") for row in spec.get("local_facts", []))
        area = proposal["market"]["area"]
        metro = proposal["market"]["metro"]
        for location in {area, metro}:
            text = re.sub(re.escape(location), "", text, flags=re.I)
        tokens = _tokens(text)
        for old, prior_id in previous:
            similarity = len(tokens & old) / max(1, len(tokens | old))
            if similarity >= .82:
                proposal["blockers"].append(
                    f"near-duplicate location-swapped editorial content versus {prior_id}")
                proposal["status"] = "HOLD_EVIDENCE"
                break
        previous.append((tokens, proposal["id"]))
        results.append(proposal)
    return results
