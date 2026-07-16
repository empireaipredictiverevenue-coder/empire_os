"""
Reddit Sniper — real implementation, salvaged from
predictive-cloud/agents/alpha_scout.py.

Scans 13 high-signal subreddits for high-ticket B2B buying intent.
Scores each post across three vectors:
  1. Reddit engagement  (score + comment velocity)
  2. Keyword intent     (16 buying-signal regex patterns)
  3. Recency boost      (posts < 6h old score 2×)

Output: JSON written to $SCOUT_OUTPUT_PATH (default: .scout_output.json)
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("reddit_sniper")


# ── Config ──────────────────────────────────────────────────────────

CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "EmpireAI-AlphaScout/1.0")
OUTPUT_PATH = os.environ.get("SCOUT_OUTPUT_PATH", ".scout_output.json")
THRESHOLD = int(os.environ.get("LEAD_SCORE_THRESHOLD", "50"))

# 13 subreddits with highest density of decision-makers
TARGETS = [
    "entrepreneur", "startups", "smallbusiness", "business", "sales",
    "marketing", "agency", "consulting", "SaaS", "digitalnomad",
    "ecommerce", "growmybusiness", "b2b",
]

# Buying-intent keyword patterns — each hit adds 10 to lead_score
INTENT_PATTERNS = [
    r"\bneed.{0,25}(developer|agency|consultant|solution|platform|software|tool|engineer)\b",
    r"\blooking for.{0,25}(developer|agency|consultant|automation|integration|freelancer)\b",
    r"\bhiring.{0,25}(freelancer|agency|developer|consultant|contractor)\b",
    r"\brfp\b",
    r"\brequest for proposal\b",
    r"\bquote\b",
    r"\boutsourc\w+\b",
    r"\b(scale|scaling|scaled)\b",
    r"\b(crm|erp|saas|api|integration|automation|pipeline)\b",
    r"\b(arr|mrr|revenue|churn|ltv|cac)\b",
    r"\bpain point\b",
    r"\b(recommend|suggestion|advice).{0,20}(tool|platform|software|service|stack)\b",
    r"\bstruggling with\b",
    r"\b(wasted?|losing?).{0,20}(hours?|time|money|revenue)\b",
    r"\bbudget.{0,20}(for|of|around|under|over)\b",
    r"\bhow do (you|we|i).{0,30}(automate|handle|manage|scale)\b",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in INTENT_PATTERNS]

POSTS_PER_SUB = 75     # hot + new combined
MIN_REDDIT_SCORE = 3   # filter noise
RECENCY_HOURS = 6      # posts younger than this get 2× multiplier


@dataclass
class RedditLead:
    """A scored B2B buying-intent lead from Reddit."""
    id: str = ""
    title: str = ""
    subreddit: str = ""
    url: str = ""
    score: int = 0
    comments: int = 0
    kw_hits: int = 0
    lead_score: int = 0
    author: str = ""
    preview: str = ""
    created_utc: str = ""
    scraped_at: str = ""
    qualified: bool = False


class RedditSniper:
    """Scans subreddits for high-ticket B2B buying intent."""

    def __init__(self):
        self.last_run: Optional[str] = None
        self.leads: list = []

    def is_configured(self) -> bool:
        return bool(CLIENT_ID and CLIENT_SECRET)

    def scrape(self) -> list[dict]:
        """Scrape all target subreddits, return scored leads."""
        try:
            import praw  # type: ignore
        except ImportError:
            logger.error("praw not installed; cannot scrape Reddit")
            return []

        if not self.is_configured():
            logger.warning("Reddit API credentials not set; cannot scrape")
            return []

        reddit = praw.Reddit(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            user_agent=USER_AGENT,
            read_only=True,
        )

        leads = []
        seen_ids = set()
        scraped_at = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"

        for sub_name in TARGETS:
            try:
                sub = reddit.subreddit(sub_name)
                streams = [sub.hot(limit=POSTS_PER_SUB), sub.new(limit=30)]
                for stream in streams:
                    for post in stream:
                        if post.id in seen_ids:
                            continue
                        if post.stickied or post.score < MIN_REDDIT_SCORE:
                            continue

                        body = post.selftext or ""
                        title = post.title or ""
                        hits = self._kw_hits(title + " " + body)
                        if hits == 0:
                            continue

                        seen_ids.add(post.id)
                        ls = self._score_post(post, hits)

                        lead = RedditLead(
                            id=post.id,
                            title=title.strip(),
                            subreddit=sub_name,
                            url=f"https://reddit.com{post.permalink}",
                            score=post.score,
                            comments=post.num_comments,
                            kw_hits=hits,
                            lead_score=ls,
                            author=str(post.author) if post.author else "[deleted]",
                            preview=(body[:400] + "…") if len(body) > 400 else body,
                            created_utc=datetime.datetime.fromtimestamp(
                                post.created_utc, tz=datetime.timezone.utc
                            ).isoformat() + "Z",
                            scraped_at=scraped_at,
                            qualified=ls >= THRESHOLD,
                        )
                        leads.append(asdict(lead))
            except Exception as exc:
                print(f"[RedditSniper] r/{sub_name} error: {exc}", file=sys.stderr)

        leads.sort(key=lambda x: x["lead_score"], reverse=True)
        self.last_run = scraped_at
        self.leads = leads
        qualified = sum(1 for l in leads if l["qualified"])
        logger.info(
            "RedditSniper: %d leads found, %d qualified (threshold=%d)",
            len(leads), qualified, THRESHOLD,
        )
        return leads

    def _kw_hits(self, text: str) -> int:
        return sum(1 for p in COMPILED if p.search(text))

    def _recency_multiplier(self, created_utc: float) -> float:
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        age_h = (now - created_utc) / 3600
        return 2.0 if age_h < RECENCY_HOURS else 1.0

    def _score_post(self, post, hits: int) -> int:
        mult = self._recency_multiplier(post.created_utc)
        return int((post.score + post.num_comments * 2 + hits * 10) * mult)

    def observe(self) -> dict:
        return {
            "agent": "reddit-sniper",
            "leads_total": len(self.leads),
            "qualified": sum(1 for l in self.leads if l.get("qualified")),
            "last_run": self.last_run,
            "configured": self.is_configured(),
        }

    def reason(self, state: dict) -> str:
        return json.dumps({
            "action": "scrape" if state.get("configured") else "skip",
            "reasoning": "scout for new B2B intent" if state.get("configured") else "no Reddit API keys",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        if d.get("action") == "scrape":
            leads = self.scrape()
            return {"action": "scrape", "leads_found": len(leads),
                    "qualified": sum(1 for l in leads if l["qualified"])}
        return {"action": "skip", "summary": "no scrape"}

    def write_output(self, path: Optional[str] = None) -> str:
        """Write leads to JSON file."""
        path = path or OUTPUT_PATH
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.leads, f, ensure_ascii=False, indent=2)
        logger.info("Wrote %d leads to %s", len(self.leads), path)
        return path