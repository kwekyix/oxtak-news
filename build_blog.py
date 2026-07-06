#!/usr/bin/env python3
"""
build_blog.py Oxtak Blog Builder
=====================================
HOW IT WORKS
  Reads oxtak_approved.json and writes docs/oxtak_data.js.
  The HTML page (docs/index.html) loads that JS file automatically.
  The HTML is never modified — no placeholder, no template confusion.

FULL WORKFLOW
  Step 1:  python oxtak_scraper.py          scrapes the web, writes oxtak_mentions.json
  Step 2:  python build_blog.py --review    shows new mentions for you to approve/reject
  Step 3:  python build_blog.py             writes docs/oxtak_data.js

  Rejecting a mention during --review permanently blocks it: it's removed
  from oxtak_mentions.json and its URL is added to BLOCKED_URLS in
  oxtak_scraper.py, so it never comes back on a future scrape.

TO REMOVE AN ALREADY-APPROVED POST PERMANENTLY
  1. Delete it from oxtak_approved.json
  2. Add its URL to BLOCKED_URLS in oxtak_scraper.py
  3. Run:  python build_blog.py
"""

import json
import re
import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure Unicode output works on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MENTIONS_FILE = "oxtak_mentions.json"
APPROVED_FILE = "oxtak_approved.json"
SCRAPER_FILE  = "oxtak_scraper.py"
OUTPUT_JS     = os.path.join("docs", "oxtak_data.js")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "mentions" in data:
        return data["mentions"]
    if isinstance(data, list):
        return data
    return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_date(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    if len(raw) >= 7 and raw[4] == "-":
        return raw[:10]
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.match(r"(\d+)\s+(hour|day|week|month)s?\s+ago", raw, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        delta = {"hour": timedelta(hours=n), "day": timedelta(days=n),
                 "week": timedelta(weeks=n), "month": timedelta(days=n * 30)}
        return (datetime.now(timezone.utc) - delta[unit]).strftime("%Y-%m-%d")
    return raw


def approved_urls(approved):
    return {m["url"] for m in approved}


def remove_from_mentions(urls_to_remove):
    """Strip rejected URLs out of oxtak_mentions.json, preserving its
    scraped_at/total wrapper if present, so they don't reappear in review."""
    if not urls_to_remove or not os.path.exists(MENTIONS_FILE):
        return

    with open(MENTIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "mentions" in data:
        data["mentions"] = [m for m in data["mentions"] if m["url"] not in urls_to_remove]
        data["total"] = len(data["mentions"])
    elif isinstance(data, list):
        data = [m for m in data if m["url"] not in urls_to_remove]
    else:
        return

    save_json(MENTIONS_FILE, data)


def block_urls_permanently(urls):
    """Insert rejected URLs into BLOCKED_URLS in oxtak_scraper.py so the
    scraper never surfaces them again."""
    if not urls or not os.path.exists(SCRAPER_FILE):
        return

    with open(SCRAPER_FILE, encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"(BLOCKED_URLS\s*=\s*\{)(.*?)(\n\})", content, re.DOTALL)
    if not match:
        print(f"  [WARN] Could not find BLOCKED_URLS in {SCRAPER_FILE} — URLs not auto-blocked.")
        return

    existing_block = match.group(2)
    new_urls = [u for u in urls if u not in existing_block]
    if not new_urls:
        return

    insertion = "".join(f'\n    "{u}",' for u in new_urls)
    updated = content[:match.end(2)] + insertion + content[match.end(2):]

    with open(SCRAPER_FILE, "w", encoding="utf-8") as f:
        f.write(updated)


# ---------------------------------------------------------------------------
# Review mode  (python build_blog.py --review)
# ---------------------------------------------------------------------------

def review_mode():
    all_mentions  = load_json(MENTIONS_FILE)
    approved      = load_json(APPROVED_FILE)
    known_urls    = approved_urls(approved)
    pending       = [m for m in all_mentions if m["url"] not in known_urls]

    if not pending:
        print("\nNothing new to review. All mentions are already processed.\n")
        return

    print(f"\n{'═' * 60}")
    print(f"REVIEW: {len(pending)} new mention(s) pending")
    print(f"{'═' * 60}")
    print("Y = approve (adds to blog)   N = reject   S = skip for now\n")

    newly_approved = 0
    rejected_urls = []

    for i, m in enumerate(pending, 1):
        url_broken = m.get("url_unresolved", False)

        print(f"\n  [{i}/{len(pending)}] {'─' * 44}")
        print(f"  SOURCE  : {m.get('source', '?')} ({m.get('source_type', '?')})")
        print(f"  TITLE   : {m.get('title', '?')[:80]}")
        print(f"  DATE    : {m.get('date', '?')}")
        if url_broken:
            print(f"  URL     : *** NEEDS FIX — Google News redirect (not a real link) ***")
            print(f"            {m.get('url', '')[:80]}")
        else:
            print(f"  URL     : {m.get('url', '?')[:80]}")
        print(f"  SNIPPET : {m.get('snippet', '?')[:120]}")
        print()

        while True:
            choice = input("  -> [Y / N / S] : ").strip().lower()
            if choice in ("y", "n", "s"):
                break
            print("  Enter Y, N, or S.")

        if choice == "y":
            if url_broken:
                print("  The URL above is a Google News redirect and won't work in the blog.")
                real_url = input("  Paste the real article URL (or press Enter to skip): ").strip()
                if real_url.startswith("http"):
                    m = dict(m)
                    m["url"] = real_url
                    m.pop("url_unresolved", None)
                else:
                    print("  No valid URL — skipping this article.")
                    continue
            m = dict(m)
            m["date"] = normalize_date(m.get("date", ""))
            approved.append(m)
            newly_approved += 1
            print("  Approved.")
        elif choice == "n":
            rejected_urls.append(m["url"])
            print("  Rejected — will be permanently blocked.")
        else:
            print("  Skipped: will appear again next time.")

    save_json(APPROVED_FILE, approved)

    if rejected_urls:
        remove_from_mentions(rejected_urls)
        block_urls_permanently(rejected_urls)

    print(f"\n{'─' * 60}")
    print(f"{newly_approved} approved   |   total approved: {len(approved)}")
    if rejected_urls:
        print(f"{len(rejected_urls)} rejected   |   added to BLOCKED_URLS in {SCRAPER_FILE}")
    print(f"Saved -> {APPROVED_FILE}")
    print(f"\nNow run:  python build_blog.py\n")


# ---------------------------------------------------------------------------
# Build mode  (python build_blog.py)
# ---------------------------------------------------------------------------

def build_mode():
    approved = load_json(APPROVED_FILE)

    if not approved:
        print(f"\n {APPROVED_FILE} is empty.")
        print(f"Run:  python build_blog.py --review   first.\n")
        sys.exit(1)

    os.makedirs("docs", exist_ok=True)

    # Drop any entry that still has an unresolved Google News URL
    broken = [m for m in approved if m.get("url_unresolved")]
    if broken:
        print(f"\n  [WARN] Skipping {len(broken)} entry/entries with unresolved URLs.")
        approved = [m for m in approved if not m.get("url_unresolved")]

    # Serialise each mention as a JS object
    def js_str(s):
        return json.dumps(str(s) if s else "", ensure_ascii=False)

    entries = []
    for m in approved:
        entry = (
            f"  {{\n"
            f"    url:         {js_str(m.get('url'))},\n"
            f"    source:      {js_str(m.get('source'))},\n"
            f"    source_type: {js_str(m.get('source_type'))},\n"
            f"    title:       {js_str(m.get('title'))},\n"
            f"    date:        {js_str(m.get('date'))},\n"
            f"    snippet:     {js_str(m.get('snippet'))},\n"
            f"    language:    {js_str((m.get('language') or 'en').upper())},\n"
            f"  }}"
        )
        entries.append(entry)

    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    js_content = (
        f"// Oxtak approved mentions generated by build_blog.py\n"
        f"// Built: {built_at}  |  Total: {len(approved)}\n"
        f"// Do not edit manually. Run build_blog.py to regenerate.\n\n"
        f"const MENTIONS = [\n"
        + ",\n".join(entries)
        + "\n];\n"
    )

    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"\n{'═' * 60}")
    print(f"  Blog data built successfully")
    print(f"  {'─' * 56}")
    print(f"  Mentions  : {len(approved)}")
    print(f"  Output    : {OUTPUT_JS}")
    print(f"  Built at  : {built_at}")
    print(f"{'═' * 60}")
    print(f"\n  Upload the docs/ folder to oxtak.com/blog\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--review" in sys.argv:
        review_mode()
    else:
        build_mode()
