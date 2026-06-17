#!/usr/bin/env python3
"""
Oxtak Web Mention Scraper
Finds relevant mentions across news sites, blogs, and tech media.
Outputs structured JSON for use in the oxtak.com/blog page.

URL resolution for Google News RSS:
  Option A (recommended): Set GOOGLE_API_KEY + GOOGLE_SEARCH_CX env vars.
    → Free 100 queries/day via Google Custom Search API; returns real article URLs.
    Setup:
      1. https://console.cloud.google.com → Enable "Custom Search JSON API"
      2. https://programmablesearchengine.google.com → New search engine → get "cx" ID
      3. https://console.cloud.google.com → APIs & Services → Credentials → Create API Key
      4. Add to .env:  GOOGLE_API_KEY=...   GOOGLE_SEARCH_CX=...

  Option B (no setup): Runs without API keys using Google News RSS.
    → Tries to resolve redirect URLs automatically; skips any that can't be resolved.
"""

import base64
import json
import os
import re
import sys
import time

# Ensure Unicode output works on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

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

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,fr;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
}

REQUEST_DELAY = 1.5
MAX_HTTP_RESOLVES = 8  # Limit slow HTTP-based URL resolution per run

BLOCKED_URLS = {
    "https://techcrunch.com/2026/03/20/ai-notetaker-hardware-devices-pins-pendants-record-transcribe/",
}

KNOWN_MENTIONS = [
    {
        "url": "https://www.notebookcheck.net/Oxtak-unveils-Moneypenny-An-AI-powered-voice-recorder-with-meeting-summaries-and-translation-services.1196189.0.html",
        "source": "NotebookCheck",
        "source_type": "tech_media",
        "title": "Oxtak unveils Moneypenny: An AI-powered voice recorder with meeting summaries and translation services",
        "date": "2026-01-04",
        "snippet": "Oxtak has unveiled the Moneypenny AI voice recorder at CES 2026 with an MSRP of $249, and pre-orders begin in February 2026. The recorder can provide meeting summaries, real-time translations, and answer questions using AI services, including Claude, Deepseek, Gemini, Grok, and OpenAI.",
        "sentiment": "neutral",
        "language": "en",
    },
    {
        "url": "https://www.notebookcheck.com/Moneypenny-Voice-Recorder-kann-Sprachmemos-uebersetzen-zusammenfassen-und-AI-Fragen-beantworten.1196373.0.html",
        "source": "NotebookCheck (DE)",
        "source_type": "tech_media",
        "title": "Moneypenny Voice Recorder kann Sprachmemos übersetzen, zusammenfassen und AI-Fragen beantworten",
        "date": "2026-01-04",
        "snippet": "Mit Moneypenny präsentiert Oxtak ein Hardware-Terminal, das speziell für die AI-Software des Unternehmens entwickelt wurde. Die Hardware fällt relativ simpel aus, denn Oxtak kombiniert einen ARM Cortex-A53 Prozessor mit einem 4 Zoll Touchscreen, einem Lautsprecher und mit zwei Mikrofonen.",
        "sentiment": "neutral",
        "language": "de",
    },
    {
        "url": "https://www.vietnam.vn/en/oxtak-trinh-lang-moneypenny-may-ghi-am-tich-hop-ai-giup-tom-tat-va-dich-thuat-cuoc-hop",
        "source": "Vietnam.vn",
        "source_type": "news",
        "title": "Oxtak unveils Moneypenny: AI-powered recording device that helps summarize and translate meetings",
        "date": "2026-01-04",
        "snippet": "At CES 2026, Oxtak garnered attention by unveiling Moneypenny, a next-generation audio recorder deeply integrated with artificial intelligence. Moneypenny's unique feature lies in its open architecture, allowing users to integrate any third-party large language model (LLM) via proprietary API keys.",
        "sentiment": "positive",
        "language": "en",
    },
    {
        "url": "https://prelaunch.com/projects/moneypenny-by-oxtak-moneypenny-your-idea-s-best-friend",
        "source": "Prelaunch.com",
        "source_type": "crowdfunding",
        "title": "Moneypenny by Oxtak: Next-Gen Retro Futuristic AI Assistant",
        "date": "2026-01",
        "snippet": "Oxtak stands out in the crowded AI transcription and meeting intelligence market through a unique combination of privacy-first architecture, open AI ecosystem, and purpose-built hardware. No data retention: your data is yours. That's why no customer audio or transcripts are stored after processing.",
        "sentiment": "positive",
        "language": "en",
    },
    {
        "url": "https://www.umevo.ai/blogs/ume-all-posts/best-hardware-alternatives-to-fathom-ai-in-2026-physical-recorders-compared",
        "source": "UMEVO.ai",
        "source_type": "blog",
        "title": "Best Hardware Alternatives to Fathom AI in 2026: Physical Recorders Compared",
        "date": "2026-03-13",
        "snippet": "Devices like the Oxtak Moneypenny allow users to plug in their own API keys for Claude or GPT-4o. This charges the user fractions of a cent per transcription directly from the LLM provider, bypassing the manufacturer's markup entirely. If your primary goal is standalone visual translation without a phone, you are better off with the Oxtak Moneypenny.",
        "sentiment": "positive",
        "language": "en",
    },
    {
        "url": "https://x.com/llepen/status/2007853592024133984",
        "source": "X / Twitter (@llepen)",
        "source_type": "social_x",
        "title": "Laurent Le Pen on X: Moneypenny is far more than just a recorder",
        "date": "2026-01-04",
        "snippet": "Moneypenny is far more than just a recorder, it's a new category of standalone Personal AI Assistant. The Oxtak platform is about empowering users with reliable voice interactions and unique AI flexibility through API and data protection.",
        "sentiment": "positive",
        "language": "en",
    },
    {
        "url": "https://www.linkedin.com/posts/laurentlepen_excited-to-unveil-oxtak-at-ces-and-demonstrate-activity-7413603330414923776-3lR4",
        "source": "LinkedIn (Laurent Le Pen)",
        "source_type": "social_linkedin",
        "title": "Excited to unveil Oxtak at CES and demonstrate how Moneypenny is redefining personal AI",
        "date": "2026-01-04",
        "snippet": "Moneypenny is our proprietary and retro futuristic device seamlessly built into Oxtak that automatically syncs every recorded audio. Preorders will kick off in February — head over to oxtak.com and register now to secure one of the limited Founders Edition units!",
        "sentiment": "positive",
        "language": "en",
    },
    {
        "url": "https://www.linkedin.com/in/laurentlepen/",
        "source": "LinkedIn (Laurent Le Pen — BEYOND Expo post)",
        "source_type": "social_linkedin",
        "title": "Oxtak at BEYOND Expo 2026: AI — Digital to Physical",
        "date": "2026-05-27",
        "snippet": "Oxtak now becomes your complete on-demand team, available anytime to support and execute tasks securely out of your smartphone, with zero security risks since it runs independently as a standalone device far from the data leaks. Come say hello at booths S-171 and S-172 at BEYOND Expo 2026.",
        "sentiment": "positive",
        "language": "en",
    },
    {
        "url": "https://www.facebook.com/frandroidcom/posts/oxtak-dévoile-moneypenny-au-ces2026/1340455998118666/",
        "source": "Frandroid (Facebook)",
        "source_type": "social_facebook",
        "title": "Oxtak dévoile Moneypenny au #CES2026 : un dictaphone IA avec écran 4 pouces",
        "date": "2026-01-05",
        "snippet": "Frandroid couvre le lancement de Moneypenny by Oxtak au CES 2026 — un enregistreur IA avec traduction en direct, transcription et résumé automatique.",
        "sentiment": "neutral",
        "language": "fr",
    },
    {
        "url": "https://www.youtube.com/@OxtakGlobal",
        "source": "YouTube (@OxtakGlobal)",
        "source_type": "video_youtube",
        "title": "Oxtak Global — Official YouTube Channel",
        "date": "2026",
        "snippet": "Official Oxtak YouTube channel. Product demos, feature walkthroughs, and team updates for the Oxtak AI audio security platform.",
        "sentiment": "positive",
        "language": "en",
    },
    {
        "url": "https://www.reddit.com/r/oxtak/",
        "source": "Reddit (r/oxtak)",
        "source_type": "social_reddit",
        "title": "r/oxtak — Community subreddit for Oxtak users",
        "date": "2026",
        "snippet": "Community discussions, tips, and user experiences around Oxtak and the Moneypenny device.",
        "sentiment": "community",
        "language": "en",
    },
]

SOURCE_TYPE_LABELS = {
    "tech_media":       "Tech Media",
    "news":             "News",
    "blog":             "Blog",
    "crowdfunding":     "Crowdfunding",
    "social_x":         "X / Twitter",
    "social_linkedin":  "LinkedIn",
    "social_facebook":  "Facebook",
    "social_reddit":    "Reddit",
    "video_youtube":    "YouTube",
}


# --- URL resolution ---

_http_resolve_count = 0


def _decode_gnews_base64(google_url: str) -> str | None:
    """
    Try to extract the publisher URL from a Google News CBMi... article ID.
    Works for older Google News URLs where the URL is stored as readable text
    in the base64 payload. Returns None for newer protobuf-encoded IDs.
    """
    try:
        article_id = google_url.split("/articles/")[-1].split("?")[0]
        padding = (4 - len(article_id) % 4) % 4
        decoded = base64.urlsafe_b64decode(article_id + "=" * padding)
        text = decoded.decode("latin-1", errors="replace")
        for prefix in ("https://", "http://"):
            idx = text.find(prefix)
            if idx != -1:
                end = idx
                while end < len(text) and 0x20 <= ord(text[end]) <= 0x7E and text[end] not in ' "\'<>':
                    end += 1
                url = text[idx:end]
                if "google.com" not in url and len(url) > 20:
                    return url
    except Exception:
        pass
    return None


def _resolve_gnews_http(google_url: str) -> str | None:
    """
    Resolve a Google News article URL via HTTP by hitting the /articles/ page.
    Google redirects (HTTP or JS-based) to the real publisher URL.
    Returns None if resolution fails.
    """
    # Strip /rss/ prefix and query params for the article page
    article_url = google_url.replace("/rss/articles/", "/articles/").split("?")[0]
    try:
        resp = requests.get(
            article_url,
            headers=HEADERS,
            timeout=7,
            allow_redirects=True,
        )
        # HTTP redirect took us to the real article
        final = resp.url
        if "news.google.com" not in final and final.startswith("http"):
            return final

        html = resp.text

        # Meta refresh: <meta http-equiv="refresh" content="0;url=https://...">
        meta_match = re.search(
            r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^;]*;\s*url=([^"\'>\s]+)',
            html, re.IGNORECASE,
        )
        if meta_match:
            url = meta_match.group(1).strip()
            if "google.com" not in url and url.startswith("http"):
                return url

        # Canonical link
        canon_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html)
        if canon_match:
            url = canon_match.group(1).strip()
            if "google.com" not in url and url.startswith("http"):
                return url

        # JavaScript redirect: window.location.replace("...") / assign("...") / href = "..."
        js_match = re.search(
            r'window\.location\.(?:replace|assign|href)\s*[=(]\s*["\']([^"\']+)["\']', html
        )
        if js_match:
            url = js_match.group(1).strip()
            if "google.com" not in url and url.startswith("http"):
                return url

    except Exception:
        pass
    return None


def resolve_google_news_url(google_url: str) -> str | None:
    """
    Resolve a Google News RSS article link to the real publisher URL.
    Returns None if the URL cannot be resolved (caller should skip the article).
    """
    global _http_resolve_count

    if "news.google.com" not in google_url:
        return google_url

    # Fast path: try base64 decode (no HTTP request)
    decoded = _decode_gnews_base64(google_url)
    if decoded:
        return decoded

    # Slow path: HTTP request (limited per run to avoid long waits)
    if _http_resolve_count < MAX_HTTP_RESOLVES:
        _http_resolve_count += 1
        resolved = _resolve_gnews_http(google_url)
        if resolved:
            return resolved

    return None  # Unresolvable — caller should skip this article


# --- Search backends ---

def search_google_custom_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Google Custom Search JSON API — requires GOOGLE_API_KEY + GOOGLE_SEARCH_CX.
    Returns real publisher article URLs (no Google News redirects).
    Free: 100 queries/day.
    """
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_CX:
        return []
    url = (
        "https://www.googleapis.com/customsearch/v1"
        f"?q={quote_plus(query)}&key={GOOGLE_API_KEY}&cx={GOOGLE_SEARCH_CX}&num={min(max_results, 10)}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"  [WARN] Google Custom Search failed: {exc}", file=sys.stderr)
        return []

    results = []
    for item in data.get("items", []):
        results.append({
            "title":       item.get("title", ""),
            "url":         item.get("link", ""),
            "snippet":     item.get("snippet", ""),
            "date":        "",
            "source_name": item.get("displayLink", ""),
        })

    time.sleep(REQUEST_DELAY)
    return results


def search_bing_news(query: str, max_results: int = 15) -> list[dict]:
    """
    Bing News RSS — no API key required, returns real publisher article URLs directly.
    """
    url = f"https://www.bing.com/news/search?q={quote_plus(query)}&format=rss"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  [WARN] Bing News RSS failed: {exc}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        print(f"  [WARN] Bing RSS parse error: {exc}", file=sys.stderr)
        return []

    results = []
    for item in root.findall(".//item")[:max_results]:
        title    = item.findtext("title", "").strip()
        link     = item.findtext("link", "").strip()
        desc     = item.findtext("description", "")
        pub_date = item.findtext("pubDate", "").strip()

        snippet = BeautifulSoup(desc, "html.parser").get_text(strip=True) if desc else ""

        date_str = ""
        if pub_date:
            try:
                date_str = parsedate_to_datetime(pub_date).strftime("%Y-%m-%d")
            except Exception:
                pass

        source_name = urlparse(link).netloc.replace("www.", "") if link else ""

        if title and link and "bing.com" not in link:
            results.append({
                "title":       title,
                "url":         link,
                "snippet":     snippet,
                "date":        date_str,
                "source_name": source_name,
            })

    time.sleep(REQUEST_DELAY)
    return results


def search_google_news(query: str, max_results: int = 15) -> list[dict]:
    """
    Google News RSS — no API key required.
    Tries to resolve redirect URLs. Articles with unresolvable URLs are included
    with url_unresolved=True so the review step can prompt for a manual URL fix.
    """
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  [WARN] Google News RSS failed: {exc}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        print(f"  [WARN] RSS parse error: {exc}", file=sys.stderr)
        return []

    results = []
    unresolved_count = 0
    for item in root.findall(".//item")[:max_results]:
        title     = item.findtext("title", "").strip()
        link      = item.findtext("link", "").strip()
        desc_html = item.findtext("description", "")
        pub_date  = item.findtext("pubDate", "").strip()
        source_el = item.find("source")
        source_name = source_el.text.strip() if source_el is not None else ""

        snippet = BeautifulSoup(desc_html, "html.parser").get_text(strip=True)

        actual_url = resolve_google_news_url(link)
        unresolved = actual_url is None or "news.google.com" in actual_url
        if unresolved:
            actual_url = link  # Keep Google News URL as placeholder
            unresolved_count += 1

        date_str = ""
        if pub_date:
            try:
                date_str = parsedate_to_datetime(pub_date).strftime("%Y-%m-%d")
            except Exception:
                pass

        if title and actual_url:
            entry = {
                "title":       title,
                "url":         actual_url,
                "snippet":     snippet,
                "date":        date_str,
                "source_name": source_name,
            }
            if unresolved:
                entry["url_unresolved"] = True
            results.append(entry)

    if unresolved_count:
        print(f"   ({unresolved_count} articles need manual URL — will show in review)")

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
                                   "tomsguide", "cnet", "gizmodo"]):
        return "tech_media"
    if any(x in domain for x in ["medium.com", "substack.com", "wordpress.com"]):
        return "blog"
    if any(x in domain for x in ["prelaunch.com", "kickstarter.com", "indiegogo.com"]):
        return "crowdfunding"
    return "news"


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
    keywords = ["oxtak", "moneypenny"]
    return [
        r for r in results
        if any(kw in (r.get("title", "") + " " + r.get("snippet", "")).lower() for kw in keywords)
    ]


# --- Main scraper ---

def run_scraper(verbose: bool = True) -> list[dict]:
    global _http_resolve_count
    _http_resolve_count = 0

    print("═" * 60)
    print("  Oxtak / Moneypenny Web Mention Scraper")
    print("═" * 60)

    using_api = bool(GOOGLE_API_KEY and GOOGLE_SEARCH_CX)
    if using_api:
        print("  Mode: Google Custom Search API (real article URLs)")
    else:
        print("  Mode: Google News RSS (no API key configured)")
        print("  Tip:  Set GOOGLE_API_KEY + GOOGLE_SEARCH_CX in .env for better results")
    print()

    all_mentions: list[dict] = list(KNOWN_MENTIONS)

    for term in SEARCH_TERMS:
        if verbose:
            print(f" Searching: {term!r}")

        if using_api:
            results = search_google_custom_search(term, max_results=10)
        else:
            # Try Bing first (real URLs), fall back to Google News RSS
            results = search_bing_news(term, max_results=15)
            if not results:
                results = search_google_news(term, max_results=15)

        filtered = filter_oxtak_relevant(results)
        if verbose:
            print(f"   Found {len(results)} results → {len(filtered)} relevant")

        for r in filtered:
            mention = {
                "url":         r["url"],
                "source":      r.get("source_name") or urlparse(r["url"]).netloc.replace("www.", ""),
                "source_type": classify_source(r["url"]),
                "title":       r["title"],
                "date":        r.get("date", ""),
                "snippet":     r["snippet"],
                "sentiment":   "neutral",
                "language":    "en",
            }
            all_mentions.append(mention)

    all_mentions = deduplicate(all_mentions)
    all_mentions = [m for m in all_mentions if m["url"] not in BLOCKED_URLS]
    all_mentions = [m for m in all_mentions if "oxtak" not in urlparse(m["url"]).netloc.lower()]

    if verbose:
        print(f"\n  Total unique mentions found: {len(all_mentions)}")
        print()

    return all_mentions


def save_results(mentions: list[dict], path: str = "oxtak_mentions.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total":      len(mentions),
            "mentions":   mentions,
        }, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(mentions)} mentions → {path}")


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