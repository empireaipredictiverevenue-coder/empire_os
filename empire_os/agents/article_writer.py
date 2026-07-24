#!/usr/bin/env python3
"""
article_writer.py — AUTO ARTICLE ENGINE (traffic -> leads moat).

Pulls live market signal from Last30days artifacts, drafts a buyer-intent
SEO article per niche, renders it as an AEO authority page via aeo_surface,
and returns the published URL. The content_engine orchestrator then pushes
the URL into the sitemap + GSC.

One researched brief -> N spun variants (article_spinner) -> N city/niche
landing pages -> SEO moat that feeds the lead funnel.

LLM: OpenRouter (openai/gpt-4o-mini), same creds as Cortex Judge.
"""
import os, sys, json, time, logging
# Put parent dir on path so `from empire_os.X` resolves to top-level modules,
# not the agents/ subdir which would shadow the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(__file__))

from empire_os.aeo_surface import deploy_spec
from empire_os.marketing import AeoSpecDraft
import article_spinner as SP

log = logging.getLogger("article_writer")
FEED = "/root/feedback"
AEO_BASE = os.getenv("AEO_BASE", "https://empire-ai.co.uk/aeo/empire")

NICHES = ["roofing", "hvac", "plumbing", "solar", "landscaping",
          "pest_control", "electrical", "painting", "windows", "fencing"]


def _last30_signal() -> list:
    """Latest Last30days takeaways -> topic seeds."""
    seeds = []
    try:
        import glob
        for f in glob.glob(f"{FEED}/last30days_*.jsonl"):
            if "runs" in f:
                continue
            with open(f) as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                        seeds.append(r.get("takeaway", ""))
                    except Exception:
                        pass
    except Exception:
        pass
    return [s for s in seeds if s][:10]


def draft_spec(niche: str, signal: str = "") -> AeoSpecDraft:
    """LLM-draft an AeoSpecDraft for a niche, seeded by market signal."""
    brief = (
        f"Write an SEO AEO authority-page spec for the local-service niche "
        f"'{niche}'. Buyer intent: a contractor or homeowner looking to buy or "
        f"sell qualified {niche} leads. "
        + (f"Market signal to weave in: {signal[:300]}. " if signal else "")
        + "Return a JSON object with keys: target_audience, pain_points, "
          "key_questions (3 buyer FAQs), content_angle (our unique angle), "
          "body_html (2 short <h3> sections of real advice, HTML), "
          "internal_links (one relative link suggestion), competitors "
          "(2 generic competitor types), call_to_action (a lead-buy CTA with "
          "the phrase 'get verified {niche} leads'). Keep it factual, no fluff."
    )
    c, provider = SP._client()
    r = c.chat.completions.create(
        model=SP._model_name(provider),
        messages=[
            {"role": "system", "content": "You output ONLY valid minified JSON."},
            {"role": "user", "content": brief},
        ],
        temperature=0.6, max_tokens=1200,
    )
    try:
        d = json.loads(r.choices[0].message.content.strip()
                        .strip("`").replace("json", "", 1).strip())
    except Exception:
        d = {}
    niche_d = niche.replace("_", " ")
    return AeoSpecDraft(
        niche=f"empire/{niche}",
        meta_description=d.get("content_angle", f"Verified {niche_d} leads, delivered qualified.")[:160],
        content_angle=d.get("content_angle", f"We deliver verified {niche_d} leads the moment they qualify."),
        target_audience=d.get("target_audience", f"Contractors and businesses buying {niche_d} leads."),
        pain_points=d.get("pain_points", f"Low-quality {niche_d} leads and stale lists."),
        key_questions=d.get("key_questions", f"How do I buy exclusive {niche_d} leads?"),
        body_html=d.get("body_html", f"<h3>Why {niche_d} leads go stale</h3><p>Speed wins.</p>"),
        internal_links=d.get("internal_links", f"/aeo/empire/{niche}/"),
        competitors=d.get("competitors", "generic lead mills"),
        call_to_action=d.get("call_to_action", f"Get verified {niche_d} leads today."),
    )


def publish(niche: str, signal: str = "", spins: int = 2) -> dict:
    """Draft + spin + publish one niche page. Returns result dict."""
    spec = draft_spec(niche, signal)
    path = deploy_spec(spec)
    url = f"{AEO_BASE}/{niche}/"
    # spin variants into side-pages for the moat
    variants = []
    if spins:
        seed = f"{spec.content_angle}\n\n{spec.body_html}"
        for i, v in enumerate(SP.spin(seed, niche, n=spins), 1):
            vspec = AeoSpecDraft(
                niche=f"empire/{niche}_{i}",
                meta_description=spec.meta_description,
                content_angle=spec.content_angle,
                target_audience=spec.target_audience,
                pain_points=spec.pain_points,
                key_questions=spec.key_questions,
                body_html=f"<p>{v[:1500]}</p>",
                internal_links=spec.internal_links,
                competitors=spec.competitors,
                call_to_action=spec.call_to_action,
            )
            deploy_spec(vspec)
            variants.append(f"{AEO_BASE}/{niche}_{i}/")
    return {"niche": niche, "url": url, "path": str(path), "variants": variants}


def run(dry_run: bool = False, limit: int = 3) -> list:
    signals = _last30_signal()
    out = []
    for i, niche in enumerate(NICHES[:limit]):
        sig = signals[i % len(signals)] if signals else ""
        if dry_run:
            out.append({"niche": niche, "url": f"{AEO_BASE}/{niche}/", "dry": True})
            continue
        out.append(publish(niche, sig, spins=2))
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limit", type=int, default=3)
    a = ap.parse_args()
    print(json.dumps(run(dry_run=a.dry, limit=a.limit), indent=2))
