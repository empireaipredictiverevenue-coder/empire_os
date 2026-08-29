#!/usr/bin/env python3
"""R&D Agent — Tech Signal Intelligence.

Scans free sources (GitHub, arXiv, HN, Reddit, Product Hunt) for actionable
tech signals. Outputs top 5 opportunities/week with build plans.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("rnd_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

FEEDBACK_DIR = Path("/root/empire_os/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

INTERVAL = 7 * 24 * 3600  # weekly


def fetch_github_trending() -> list:
    """Fetch GitHub trending repos for lead-gen/SEO/AI topics."""
    topics = ["lead-generation", "seo", "ai-agents", "web-scraping", "payments", "b2b-sales"]
    signals = []
    for topic in topics:
        try:
            url = f"https://api.github.com/search/repositories?q=topic:{topic}+stars:>100&sort=stars&order=desc&per_page=5"
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
                for repo in data.get("items", []):
                    signals.append({
                        "source": "github_trending",
                        "topic": topic,
                        "repo": repo["full_name"],
                        "stars": repo["stargazers_count"],
                        "description": repo["description"][:200] if repo["description"] else "",
                        "url": repo["html_url"],
                    })
        except Exception as e:
            logger.warning("GitHub trending %s failed: %s", topic, e)
    return signals


def fetch_hackernews() -> list:
    """Fetch HN stories for relevant keywords."""
    keywords = ["lead generation", "SEO", "local business", "SMB software", "local SEO"]
    signals = []
    try:
        url = "https://hn.algolia.com/api/v1/search?query=lead%20generation%20OR%20SEO%20OR%20local%20business&tags=story&hitsPerPage=20"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
            for hit in data.get("hits", []):
                signals.append({
                    "source": "hackernews",
                    "title": hit.get("title", ""),
                    "points": hit.get("points", 0),
                    "url": hit.get("url", "") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "author": hit.get("author", ""),
                })
    except Exception as e:
        logger.warning("HackerNews fetch failed: %s", e)
    return signals


def fetch_arxiv() -> list:
    """Fetch arXiv papers for relevant categories."""
    # Simplified - in production would use arXiv API
    return []


def score_signal(signal: dict, llm) -> float:
    """Score signal 1-5 on revenue_impact, build_effort, defensibility, urgency, strategic_fit."""
    # Rule-based scoring for now
    score = 3.0
    source = signal.get("source", "")
    if source == "github_trending":
        stars = signal.get("stars", 0)
        if stars > 1000:
            score += 1.0
        elif stars > 500:
            score += 0.5
    elif source == "hackernews":
        points = signal.get("points", 0)
        if points > 100:
            score += 1.0
        elif points > 50:
            score += 0.5
    return min(5.0, max(1.0, score))


def build_opportunity(signal: dict, llm) -> dict:
    """Convert scored signal to opportunity with build plan."""
    score = score_signal(signal, llm)
    
    # Determine revenue path
    revenue_paths = {
        "github_trending": "new_lead_source",
        "hackernews": "aeo_angle",
        "arxiv": "scoring_feature",
    }
    
    return {
        "signal": signal.get("title") or signal.get("repo") or signal.get("description", "")[:100],
        "source": signal.get("source", "unknown"),
        "score": round(score, 1),
        "revenue_path": revenue_paths.get(signal.get("source"), "other"),
        "build_plan": {
            "effort_hours": 20,
            "components": ["research", "prototype", "integration"],
            "dependencies": [],
        },
        "build_vs_buy": "build",
        "rationale": f"Signal from {signal.get('source')} scored {score}/5",
    }


def cycle():
    """Single R&D cycle."""
    logger.info("R&D cycle starting...")
    
    # Initialize LLM
    llm = OllamaClient()
    
    # Fetch signals
    all_signals = []
    all_signals.extend(fetch_github_trending())
    all_signals.extend(fetch_hackernews())
    all_signals.extend(fetch_arxiv())
    
    logger.info("Fetched %d signals", len(all_signals))
    
    # Score and build opportunities
    opportunities = []
    for signal in all_signals:
        try:
            opp = build_opportunity(signal, llm)
            if opp["score"] >= 3.0:  # threshold
                opportunities.append(opp)
        except Exception as e:
            logger.warning("Failed to build opportunity: %s", e)
    
    # Sort by score, take top 5
    opportunities.sort(key=lambda x: x["score"], reverse=True)
    top_opportunities = opportunities[:5]
    
    # Log results
    FEEDBACK_DIR = Path("/root/empire_os/feedback")
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    
    # Raw signals
    with open(FEEDBACK_DIR / "rnd_signals.jsonl", "a") as f:
        for s in all_signals:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **s}) + "\n")
    
    # Opportunities
    with open(FEEDBACK_DIR / "rnd_opportunities.jsonl", "a") as f:
        for o in top_opportunities:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **o}) + "\n")
    
    # Weekly report
    report = {
        "week": datetime.now(timezone.utc).strftime("%Y-W%U"),
        "signals_total": len(all_signals),
        "opportunities": top_opportunities,
    }
    with open(FEEDBACK_DIR / f"rnd_weekly_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json", "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info("R&D cycle complete: %d opportunities", len(top_opportunities))
    
    return {"opportunities": len(top_opportunities)}


def main():
    logger.info("R&D agent starting — weekly cadence")
    consecutive_failures = 0
    while True:
        try:
            result = cycle()
            consecutive_failures = 0
            print(json.dumps(result))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            logger.error("R&D cycle failed: %s (backoff %ds)", e, backoff)
            time.sleep(backoff)
            continue
        time.sleep(INTERVAL)


if __name__ == "__main__":
    import json
    import time
    from datetime import datetime, timezone
    main()