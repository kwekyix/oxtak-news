#!/usr/bin/env python3
"""
Oxtak Web Mention Scraper
Finds relevant mentions across news sites, blogs, and tech media.
Outputs structured JSON for use in the oxtak.com/blog page.

Setup:
  1. Sign up free at serpapi.com (100 searches/month, no credit card)
  2. Copy your API key from the dashboard
  3. Add to .env:  SERPAPI_KEY=your_key_here
  4. Run:  python oxtak_scraper.py
"""

import json
import os
import sys
import time

# Ensure Unicode output works on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

# --- Load .env if present (no python-dotenv dependency needed) ---

def _load_dotenv():
    try:
        with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
    except FileNotFoundError:
        pass

_load_dotenv()

# --- Configuration ---

SEARCH_TERMS = [
    "Oxtak",
    "Moneypenny oxtak",
    "Oxtak AI recorder",
    "Oxtak Moneypenny",
    "Oxtak recorder review",
]

# Japanese-locale searches — run with gl=jp, hl=ja
SEARCH_TERMS_JA = [
    "Oxtak",
    "Oxtak ボイスレコーダー",
    "Oxtak Moneypenny",
    "オクスタック",
]

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

REQUEST_DELAY = 1.5

BLOCKED_URLS = {
    "https://techcrunch.com/2026/03/20/ai-notetaker-hardware-devices-pins-pendants-record-transcribe/",
}

SOURCE_TYPE_LABELS = {
    "tech_media":       "Tech Media",
    "news":             "News",
    "blog":             "Blog",
    "social_x":         "X / Twitter",
    "social_linkedin":  "LinkedIn",
    "social_facebook":  "Facebook",
    "social_reddit":    "Reddit",
    "video_youtube":    "YouTube",
}


# --- Search backend ---

def search_serpapi(query: str, max_results: int = 10, gl: str = "", hl: str = "") -> list[dict]:
    """
    SerpAPI Google News search — requires SERPAPI_KEY in .env.
    Returns real publisher article URLs directly (no redirects).
    Free plan: 100 searches/month at serpapi.com.
    Pass gl='jp' and hl='ja' for Japanese-locale results.
    """
    if not SERPAPI_KEY:
        return []

    params = {
        "engine":  "google_news",
        "q":       query,
        "api_key": SERPAPI_KEY,
    }
    if gl:
        params["gl"] = gl
    if hl:
        params["hl"] = hl

    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"  [WARN] SerpAPI search failed: {exc}", file=sys.stderr)
        return []

    results = []
    for item in data.get("news_results", []):
        # google_news engine nests individual articles inside a "stories" array
        stories = item.get("stories") or [item]
        for story in stories:
            title   = story.get("title", "").strip()
            link    = story.get("link", "").strip()
            snippet = story.get("snippet", "").strip()
            date    = story.get("date", "").strip()
            source  = story.get("source", {})
            source_name = (source.get("name", "") if isinstance(source, dict) else "") or \
                          urlparse(link).netloc.replace("www.", "")

            if title and link:
                results.append({
                    "title":       title,
                    "url":         link,
                    "snippet":     snippet,
                    "date":        date,
                    "source_name": source_name,
                })
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    time.sleep(REQUEST_DELAY)
    return results


# --- Helpers ---

def classify_source(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    if "youtube.com" in domain or "youtu.be" in domain:
        return "video_youtube"
    if "reddit.com" in domain:
        return "social_reddit"
    if "linkedin.com" in domain:
        return "social_linkedin"
    if "twitter.com" in domain or "x.com" in domain:
        return "social_x"
    if "facebook.com" in domain:
        return "social_facebook"
    if "instagram.com" in domain:
        return "social_instagram"
    if "tiktok.com" in domain:
        return "social_tiktok"
    if any(x in domain for x in ["techcrunch", "theverge", "engadget", "wired",
                                   "arstechnica", "notebookcheck", "yankodesign",
                                   "tomsguide", "cnet", "gizmodo", "prelaunch.com",
                                   "kickstarter.com", "indiegogo.com",
                                   "gizmodo.jp", "ascii.jp", "itmedia.co.jp",
                                   "akibapc.com", "4gamer.net", "impress.co.jp",
                                   "watch.impress.co.jp", "pc.watch.impress.co.jp",
                                   "costory.jp", "makuake.com", "campfire.asia",
                                   "greenfunding.jp"]):
        return "tech_media"
    if any(x in domain for x in ["medium.com", "substack.com", "wordpress.com",
                                   "note.com"]):
        return "blog"
    return "news"


def detect_language(url: str, default: str = "en") -> str:
    domain = urlparse(url).netloc.lower()
    if domain.endswith(".jp") or ".co.jp" in domain:
        return "ja"
    if domain.endswith(".de") or domain.endswith(".at") or domain.endswith(".ch"):
        return "de"
    if domain.endswith(".fr"):
        return "fr"
    if domain.endswith(".vn"):
        return "vi"
    return default


def deduplicate(mentions: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for m in mentions:
        key = m["url"].rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def filter_oxtak_relevant(results: list[dict]) -> list[dict]:
    keywords_lower = ["oxtak", "moneypenny"]
    keywords_ja = ["オクスタック", "マネーペニー"]
    return [
        r for r in results
        if any(kw in (r.get("title", "") + " " + r.get("snippet", "")).lower() for kw in keywords_lower)
        or any(kw in (r.get("title", "") + " " + r.get("snippet", "")) for kw in keywords_ja)
    ]


# --- Main scraper ---

def run_scraper(verbose: bool = True) -> list[dict]:
    print("═" * 60)
    print("  Oxtak / Moneypenny Web Mention Scraper")
    print("═" * 60)

    if SERPAPI_KEY:
        print("  Mode: SerpAPI Google News (real article URLs)")
    else:
        print("  [!] No SERPAPI_KEY found in .env — skipping web search.")
        print("      Sign up free at serpapi.com and add SERPAPI_KEY to .env")
    print()

    all_mentions: list[dict] = []

    for term in SEARCH_TERMS:
        if not SERPAPI_KEY:
            break
        if verbose:
            print(f" Searching: {term!r}")

        results  = search_serpapi(term, max_results=10)
        filtered = filter_oxtak_relevant(results)
        if verbose:
            print(f"   Found {len(results)} results → {len(filtered)} relevant")

        for r in filtered:
            all_mentions.append({
                "url":         r["url"],
                "source":      r.get("source_name") or urlparse(r["url"]).netloc.replace("www.", ""),
                "source_type": classify_source(r["url"]),
                "title":       r["title"],
                "date":        r.get("date", ""),
                "snippet":     r["snippet"],
                "language":    detect_language(r["url"]),
            })

    if verbose:
        print()
        print("  [JP] Searching Japanese locale (gl=jp, hl=ja) ...")

    for term in SEARCH_TERMS_JA:
        if not SERPAPI_KEY:
            break
        if verbose:
            print(f" Searching (JP): {term!r}")

        results  = search_serpapi(term, max_results=10, gl="jp", hl="ja")
        filtered = filter_oxtak_relevant(results)
        if verbose:
            print(f"   Found {len(results)} results → {len(filtered)} relevant")

        for r in filtered:
            all_mentions.append({
                "url":         r["url"],
                "source":      r.get("source_name") or urlparse(r["url"]).netloc.replace("www.", ""),
                "source_type": classify_source(r["url"]),
                "title":       r["title"],
                "date":        r.get("date", ""),
                "snippet":     r["snippet"],
                "language":    detect_language(r["url"], default="ja"),
            })

    all_mentions = deduplicate(all_mentions)
    all_mentions = [m for m in all_mentions if m["url"] not in BLOCKED_URLS]
    all_mentions = [m for m in all_mentions if "oxtak" not in urlparse(m["url"]).netloc.lower()]

    # Filter out URLs already in oxtak_approved.json
    approved_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oxtak_approved.json")
    if os.path.exists(approved_path):
        try:
            with open(approved_path, encoding="utf-8") as f:
                adata = json.load(f)
            alist = adata if isinstance(adata, list) else adata.get("mentions", [])
            approved_urls = {m["url"].rstrip("/").lower() for m in alist}
            all_mentions = [m for m in all_mentions if m["url"].rstrip("/").lower() not in approved_urls]
        except Exception:
            pass

    if verbose:
        print(f"\n  New candidates found: {len(all_mentions)}")
        print()

    return all_mentions


def save_results(mentions: list[dict], path: str = "oxtak_mentions.json"):
    # Merge with existing file so manual edits / manually added entries are preserved.
    # Existing entries always win; only truly new URLs are appended.
    # URLs already in oxtak_approved.json are also skipped — approved entries are final.
    existing = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            existing = data.get("mentions", data) if isinstance(data, dict) else data
        except Exception:
            pass

    approved_urls = set()
    approved_path = os.path.join(os.path.dirname(path) or ".", "oxtak_approved.json")
    if os.path.exists(approved_path):
        try:
            with open(approved_path, encoding="utf-8") as f:
                adata = json.load(f)
            alist = adata if isinstance(adata, list) else adata.get("mentions", [])
            approved_urls = {m["url"].rstrip("/").lower() for m in alist}
        except Exception:
            pass

    existing_urls = {m["url"].rstrip("/").lower() for m in existing}
    skip = existing_urls | approved_urls
    new_only = [m for m in mentions if m["url"].rstrip("/").lower() not in skip]
    merged = existing + new_only

    if new_only:
        print(f"  {len(new_only)} new mention(s) added")
    else:
        print(f"  No new mentions found")

    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total":      len(merged),
            "mentions":   merged,
        }, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(merged)} mentions -> {path}")


def print_summary(mentions: list[dict]):
    print("\n" + "─" * 60)
    print("MENTION SUMMARY")
    print("─" * 60)
    by_type: dict[str, int] = {}
    for m in mentions:
        t = m.get("source_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
        label = SOURCE_TYPE_LABELS.get(t, t)
        print(f"  {label:<20} {count}")
    print(f"\n  TOTAL: {len(mentions)}")
    print("─" * 60)

    print("\nTOP MENTIONS:")
    for i, m in enumerate(mentions[:12], 1):
        print(f"\n  {i:2}. [{m.get('source_type','?').upper()}] {m['source']}")
        print(f"      {m['title'][:80]}")
        print(f"      {m['url'][:80]}")
        if m.get("date"):
            print(f"      Date: {m['date']}")


if __name__ == "__main__":
    mentions = run_scraper(verbose=True)
    save_results(mentions)
    print_summary(mentions)