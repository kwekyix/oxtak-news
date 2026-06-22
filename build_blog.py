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
  Step 4:  upload the docs/ folder to oxtak.com/blog

TO REMOVE A POST PERMANENTLY
  1. Delete it from oxtak_approved.json
  2. Add its URL to BLOCKED_URLS in oxtak_scraper.py
  3. Run:  python build_blog.py
"""

import json
import sys
import os
from datetime import datetime, timezone

MENTIONS_FILE = "oxtak_mentions.json"
APPROVED_FILE = "oxtak_approved.json"
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


def approved_urls(approved):
    return {m["url"] for m in approved}


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
            approved.append(m)
            newly_approved += 1
            print("  Approved.")
        elif choice == "n":
            print("  Rejected.")
        else:
            print("  Skipped: will appear again next time.")

    save_json(APPROVED_FILE, approved)

    print(f"\n{'─' * 60}")
    print(f"{newly_approved} approved   |   total approved: {len(approved)}")
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
