#!/usr/bin/env python3
"""
Empire OS — agent-reach Python wrapper
Provides clean API for 13+ platform internet access from any Empire OS agent.
Uses native Python API instead of CLI commands.
"""

import sys
import subprocess
import json
import os
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add agent-reach source to path
AGENT_REACH_SRC = Path("/opt/agent-reach")
if AGENT_REACH_SRC.exists():
    sys.path.insert(0, str(AGENT_REACH_SRC))

try:
    import agent_reach
    from agent_reach.channels import get_channel, get_all_channels
    from agent_reach.config import Config
    from agent_reach import AgentReach
    AGENT_REACH_AVAILABLE = True
except ImportError:
    AGENT_REACH_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────
# Web Search & Read
# ─────────────────────────────────────────────────────────────────

def read_url(url: str, timeout: int = 20) -> Dict[str, Any]:
    """Read any web page. Tries agent-reach, then Wayback, then direct.

    Jina AI blocks VPS IPs (AS20473), so Wayback Machine is primary fallback.
    Returns plain HTML/text.
    """
    # Try agent-reach first (may fail if Jina blocked)
    try:
        web = get_channel('web')
        content = web.read(url)
        if content:
            return {"ok": True, "data": content, "source": "agent-reach"}
    except Exception:
        pass

    # Wayback Machine fallback (always available, no captchas)
    try:
        avail_req = urllib.request.Request(
            f"https://archive.org/wayback/available?url={url}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        avail = json.loads(urllib.request.urlopen(avail_req, timeout=10).read())
        snap = avail.get("archived_snapshots", {}).get("closest", {})
        if snap.get("available"):
            wb_url = snap["url"]
            wb_req = urllib.request.Request(wb_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(wb_req, timeout=timeout) as r:
                return {"ok": True, "data": r.read().decode("utf-8", errors="replace"),
                        "source": "wayback", "snapshot": snap.get("timestamp")}
    except Exception as e:
        pass

    # Direct fetch last
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "data": r.read().decode("utf-8", errors="replace"),
                    "source": "direct"}
    except Exception as e:
        return {"ok": False, "error": f"all sources failed: {e}"}


def wiki_summary(topic: str) -> Dict[str, Any]:
    """Wikipedia REST API summary — free, no key, VPS works."""
    try:
        from urllib.parse import quote
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(topic, safe='_')}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return {"ok": True, "title": d.get("title"),
                "extract": d.get("extract", ""),
                "url": d.get("content_urls", {}).get("desktop", {}).get("page", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ddg_instant(query: str) -> Dict[str, Any]:
    """DuckDuckGo instant answer — JSON API, no captcha, VPS works."""
    try:
        from urllib.parse import quote_plus
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return {"ok": True, "abstract": d.get("AbstractText", ""),
                "abstract_url": d.get("AbstractURL", ""),
                "answer": d.get("Answer", ""),
                "related": [r.get("Text", "") for r in d.get("RelatedTopics", [])[:5] if isinstance(r, dict) and r.get("Text")]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def search_web(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Web search via DuckDuckGo instant answer (fallback).

    For full results, install mcporter + Exa MCP and use agent-reach channels.
    """
    try:
        from urllib.parse import quote_plus
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        results = []
        if d.get("AbstractText"):
            results.append({"title": d.get("Heading", query),
                            "snippet": d["AbstractText"],
                            "url": d.get("AbstractURL", "")})
        for r in d.get("RelatedTopics", [])[:num_results]:
            if isinstance(r, dict) and r.get("Text"):
                results.append({"title": r.get("Text", "")[:80],
                                "snippet": r.get("Text", ""),
                                "url": r.get("FirstURL", "")})
        return {"ok": True, "data": results, "source": "duckduckgo"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
# YouTube
# ─────────────────────────────────────────────────────────────────

def get_youtube_transcript(url: str, langs: str = "en,zh-Hans") -> Dict[str, Any]:
    """Get YouTube video transcript (subtitles). Returns path to .vtt file."""
    try:
        yt = get_channel('youtube')
        # Check if yt-dlp is available
        check_result = yt.check()
        if check_result[0] == 'off':
            return {"ok": False, "error": check_result[1]}
        
        result = yt.transcribe(url)
        return {"ok": True, "transcript": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_youtube_metadata(url: str) -> Dict[str, Any]:
    """Get YouTube video metadata."""
    try:
        yt = get_channel('youtube')
        # Use yt-dlp directly for metadata
        result = subprocess.run(["yt-dlp", "--dump-json", url], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return {"ok": True, "data": json.loads(result.stdout)}
        return {"ok": False, "error": result.stderr}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def search_youtube(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search YouTube."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", f"ytsearch{max_results}:{query}"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return {"ok": True, "data": result.stdout}
        return {"ok": False, "error": result.stderr}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
# Twitter/X
# ─────────────────────────────────────────────────────────────────

def search_x(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search Twitter/X - requires xreach CLI."""
    return {"ok": False, "error": "Twitter search requires xreach CLI. Install: pipx install xreach or see agent-reach install --channels twitter"}


def read_x_tweet(url_or_id: str) -> Dict[str, Any]:
    """Read a single tweet."""
    return {"ok": False, "error": "Requires xreach CLI"}


def get_x_timeline(username: str, limit: int = 20) -> Dict[str, Any]:
    """Get user timeline."""
    return {"ok": False, "error": "Requires xreach CLI"}


def get_x_thread(url_or_id: str) -> Dict[str, Any]:
    """Get full thread."""
    return {"ok": False, "error": "Requires xreach CLI"}


# ─────────────────────────────────────────────────────────────────
# Reddit
# ─────────────────────────────────────────────────────────────────

def search_reddit(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search Reddit via curl (requires login for API)."""
    try:
        reddit = get_channel('reddit')
        check_result = reddit.check()
        if check_result[0] == 'off':
            return {"ok": False, "error": check_result[1]}
        # Reddit channel doesn't have search method, use curl fallback
        return _run_curl([
            "curl", "-s",
            f"https://www.reddit.com/search.json?q={query}&limit={limit}",
            "-H", "User-Agent: agent-reach/1.0"
        ])
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_subreddit_hot(subreddit: str, limit: int = 10) -> Dict[str, Any]:
    """Get hot posts from subreddit."""
    try:
        return _run_curl([
            "curl", "-s",
            f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}",
            "-H", "User-Agent: agent-reach/1.0"
        ])
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
# GitHub (gh CLI)
# ─────────────────────────────────────────────────────────────────

def search_github_repos(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search GitHub repos."""
    return _run_cli(["gh", "search", "repos", query, "--sort", "stars", "--limit", str(limit), "--json", "name,owner,description,stargazerCount,url"])


def get_github_repo(owner: str, repo: str) -> Dict[str, Any]:
    """Get repo details."""
    return _run_cli(["gh", "repo", "view", f"{owner}/{repo}", "--json", "name,description,stargazerCount,url,readme"])


# ─────────────────────────────────────────────────────────────────
# 小红书 / XiaoHongShu
# ─────────────────────────────────────────────────────────────────

def search_xiaohongshu(keyword: str) -> Dict[str, Any]:
    """Search XiaoHongShu."""
    return {"ok": False, "error": "Requires mcporter + xiaohongshu-mcp. Install: agent-reach install --channels xiaohongshu"}


# ─────────────────────────────────────────────────────────────────
# LinkedIn
# ─────────────────────────────────────────────────────────────────

def get_linkedin_profile(url: str) -> Dict[str, Any]:
    """Get LinkedIn profile."""
    return {"ok": False, "error": "Requires linkedin-scraper-mcp + mcporter"}


def search_linkedin(keyword: str, limit: int = 10) -> Dict[str, Any]:
    """Search LinkedIn people."""
    return {"ok": False, "error": "Requires linkedin-scraper-mcp + mcporter"}


# ─────────────────────────────────────────────────────────────────
# Boss直聘 / Boss Zhipin
# ─────────────────────────────────────────────────────────────────

def search_bosszhipin(keyword: str, city: str = "北京") -> Dict[str, Any]:
    """Search Boss直聘 jobs."""
    return {"ok": False, "error": "Requires mcporter + bosszhipin-mcp"}


# ─────────────────────────────────────────────────────────────────
# WeChat Articles (微信公众号)
# ─────────────────────────────────────────────────────────────────

def search_wechat_articles(query: str, limit: int = 5) -> Dict[str, Any]:
    """Search WeChat articles via miku_ai."""
    script = f"""
import asyncio
from miku_ai import get_wexin_article
async def s():
    async for a in get_wexin_article('{query}', {limit}):
        print(f'{a["title"]} | {a["url"]}')
asyncio.run(s())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode == 0:
        return {"ok": True, "data": result.stdout}
    return {"ok": False, "error": result.stderr}


def read_wechat_article(url: str) -> Dict[str, Any]:
    """Read WeChat article via Camoufox."""
    wechat_tool = Path.home() / ".agent-reach" / "tools" / "wechat-article-for-ai"
    if wechat_tool.exists():
        result = subprocess.run(
            ["python3", "main.py", url],
            cwd=str(wechat_tool),
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return {"ok": True, "data": result.stdout}
        return {"ok": False, "error": result.stderr}
    return {"ok": False, "error": "WeChat article tool not installed"}


# ─────────────────────────────────────────────────────────────────
# Bilibili
# ─────────────────────────────────────────────────────────────────

def get_bilibili_video(url: str, langs: str = "zh-Hans,zh,en") -> Dict[str, Any]:
    """Get Bilibili video transcript."""
    try:
        bili = get_channel('bilibili')
        check_result = bili.check()
        if check_result[0] != 'ok':
            return {"ok": False, "error": check_result[1]}
        # Bilibili channel doesn't have direct search method, use yt-dlp
        return get_bilibili_transcript(url, langs)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_bilibili_transcript(url: str, langs: str = "zh-Hans,zh,en") -> Dict[str, Any]:
    """Get Bilibili video transcript via yt-dlp."""
    tmp_dir = "/tmp/agent-reach-bilibili"
    os.makedirs(tmp_dir, exist_ok=True)
    result = subprocess.run([
        "yt-dlp",
        "--write-sub", "--write-auto-sub",
        "--sub-lang", langs,
        "--convert-subs", "vtt",
        "--skip-download",
        "-o", f"{tmp_dir}/%(id)s",
        url
    ], capture_output=True, text=True, timeout=120)
    
    if result.returncode == 0:
        import glob
        vtt_files = glob.glob(f"{tmp_dir}/*.vtt")
        if vtt_files:
            with open(vtt_files[0], "r") as f:
                content = f.read()
            return {"ok": True, "transcript": content, "file": vtt_files[0]}
    return {"ok": False, "error": "Failed to get transcript"}


# ─────────────────────────────────────────────────────────────────
# RSS
# ─────────────────────────────────────────────────────────────────

def read_rss(feed_url: str, limit: int = 5) -> Dict[str, Any]:
    """Read RSS feed via feedparser."""
    try:
        import feedparser
        feed = feedparser.parse(feed_url)
        items = []
        for e in feed.entries[:limit]:
            items.append({"title": e.title, "link": e.link})
        return {"ok": True, "data": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
# Helper: Run CLI command
# ─────────────────────────────────────────────────────────────────

def _run_cli(cmd: List[str], timeout: int = 60) -> Dict[str, Any]:
    """Run CLI command and return parsed JSON."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/opt/agent-reach"
        )
        if result.returncode == 0:
            try:
                return {"ok": True, "data": json.loads(result.stdout)}
            except json.JSONDecodeError:
                return {"ok": True, "data": result.stdout}
        return {"ok": False, "error": result.stderr, "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"Command not found: {e.filename}"}


# ─────────────────────────────────────────────────────────────────
# Doctor / Health Check
# ─────────────────────────────────────────────────────────────────

def doctor() -> Dict[str, Any]:
    """Run agent-reach doctor to check channel status."""
    return _run_cli(["agent-reach", "doctor"])


def health_check() -> Dict[str, Any]:
    """Quick health check of available tools."""
    tools = {
        "mcporter": False,
        "xreach": False,
        "yt-dlp": False,
        "gh": False,
        "curl": False,
    }
    for tool in tools:
        try:
            subprocess.run(["which", tool], capture_output=True, check=True)
            tools[tool] = True
        except subprocess.CalledProcessError:
            tools[tool] = False
    return {"ok": all(tools.values()), "tools": tools}


# ─────────────────────────────────────────────────────────────────
# Main / Test
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== agent-reach wrapper health check ===")
    hc = health_check()
    print(f"Tools: {hc['tools']}")
    print(f"Overall: {'OK' if hc['ok'] else 'ISSUES'}")
    
    print("\n=== Testing web search ===")
    result = read_url("https://empire-ai.co.uk")
    print(f"Web read: {result.get('ok', False)} - {len(result.get('data', ''))} chars")
    
    print("\n=== Testing YouTube metadata ===")
    result = get_youtube_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print(f"YouTube metadata: {result.get('ok', False)}")
    
    print("\n=== Testing YouTube transcript ===")
    result = get_youtube_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print(f"YouTube transcript: {result.get('ok', False)}")
    
    print("\n=== Testing Bilibili transcript ===")
    result = get_bilibili_video("https://www.bilibili.com/video/BV1xx411c7mD")
    print(f"Bilibili transcript: {result.get('ok', False)}")
    
    print("\n=== Testing RSS ===")
    result = read_rss("https://www.reddit.com/r/python/.rss")
    print(f"RSS read: {result.get('ok', False)}")
    
    print("\n=== Done ===")