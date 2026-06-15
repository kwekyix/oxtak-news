#!/usr/bin/env python3
"""
Oxtak / Moneypenny Web Mention Scraper
Finds all relevant mentions across blogs, news sites, Reddit, LinkedIn, YouTube, etc.
Outputs structured JSON for use in the oxtak.com/blog page.
"""

import json
import time
import re
import sys
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# --- Configuration ---

SEARCH_TERMS = [
    "Oxtak",
    "Moneypenny",
    "Oxtak Moneypenny",
    "Oxtak AI recorder",
    "oxtak.com",
    "Moneypenny oxtak",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REQUEST_DELAY = 1.5 

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

# --- Helpers ---

def get_page(url: str, timeout: int = 10) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        print(f"  [WARN] Could not fetch {url}: {exc}", file=sys.stderr)
        return None


def search_duckduckgo(query: str, max_results: int = 10) -> list[dict]:
    """
    Scrape DuckDuckGo HTML search results for a query.
    Returns a list of {title, url, snippet} dicts.
    """
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    soup = get_page(url)
    if soup is None:
        return []

    results = []
    for res in soup.select(".result"):
        title_el = res.select_one(".result__title a")
        snippet_el = res.select_one(".result__snippet")
        if not title_el:
            continue
        href = title_el.get("href", "")
        # DuckDuckGo wraps links; extract the real URL
        if "uddg=" in href:
            match = re.search(r"uddg=([^&]+)", href)
            if match:
                from urllib.parse import unquote
                href = unquote(match.group(1))
        results.append({
            "title":   title_el.get_text(strip=True),
            "url":     href,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
        if len(results) >= max_results:
            break

    time.sleep(REQUEST_DELAY)
    return results


def classify_source(url: str) -> str:
    """Classify a URL into a source type."""
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
    """Remove duplicates by URL, keeping first occurrence."""
    seen = set()
    out = []
    for m in mentions:
        key = m["url"].rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def filter_oxtak_relevant(results: list[dict]) -> list[dict]:
    """Keep only results that are truly about Oxtak / Moneypenny (the device)."""
    keywords = ["oxtak", "moneypenny"]
    filtered = []
    for r in results:
        text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
        if any(kw in text for kw in keywords):
            filtered.append(r)
    return filtered


# --- Main scraper ---

def run_scraper(verbose: bool = True) -> list[dict]:
    print("═" * 60)
    print("  Oxtak / Moneypenny Web Mention Scraper")
    print("═" * 60)

    all_mentions: list[dict] = list(KNOWN_MENTIONS)  # seed with curated list

    # Live search across all query terms
    for term in SEARCH_TERMS:
        if verbose:
            print(f"\n Searching: {term!r}")
        results = search_duckduckgo(term, max_results=15)
        filtered = filter_oxtak_relevant(results)
        if verbose:
            print(f"   Found {len(results)} results → {len(filtered)} relevant")

        for r in filtered:
            mention = {
                "url":          r["url"],
                "source":       urlparse(r["url"]).netloc.replace("www.", ""),
                "source_type":  classify_source(r["url"]),
                "title":        r["title"],
                "date":         "",
                "snippet":      r["snippet"],
                "sentiment":    "neutral",
                "language":     "en",
            }
            all_mentions.append(mention)

    # Deduplicate
    all_mentions = deduplicate(all_mentions)
    all_mentions = [m for m in all_mentions if m["url"] not in BLOCKED_URLS]
    all_mentions = [m for m in all_mentions if "oxtak" not in urlparse(m["url"]).netloc.lower()]  # exclude own site

    if verbose:
        print(f"\n  Total unique mentions found: {len(all_mentions)}")
        print()

    return all_mentions


def save_results(mentions: list[dict], path: str = "oxtak_mentions.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scraped_at": datetime.utcnow().isoformat() + "Z",
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
