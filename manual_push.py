#!/usr/bin/env python3
"""
manual_push.py — Manually push a tweet announcement to @vitocruzdelays.

Interactive usage (terminal):
    python manual_push.py

Non-interactive usage (Claude Code slash command):
    python manual_push.py --url URL --text-file FILE [--kind KIND] [--dry-run] [--yes]

Set TELEGRAM_BOT_TOKEN before running. TELEGRAM_CHANNEL defaults to @vitocruzdelays.
"""

import argparse
import re
import sys
from datetime import datetime

from monitor import (
    PHT,
    classify_x_post,
    format_x_message,
    has_posted_item,
    load_state,
    remember_posted_item,
    save_state,
    send_telegram,
)

KINDS = [
    "disruption_start",
    "disruption_update",
    "disruption_clear",
    "flood_alert",
    "flood_clear",
    "crowd_alert_high",
    "crowd_alert_moderate",
]


def extract_tweet_id(url: str) -> str | None:
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None


def run_interactive() -> None:
    url = input("Paste the tweet URL: ").strip()
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        print("Error: Could not extract tweet ID from URL.")
        sys.exit(1)
    url = f"https://x.com/officialLRT1/status/{tweet_id}"

    print("Paste the tweet text below. Press Enter twice when done:")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines:
            break
        lines.append(line)
    tweet_text = "\n".join(lines).strip()
    if not tweet_text:
        print("Error: No tweet text provided.")
        sys.exit(1)

    now = datetime.now(PHT)
    raw_post = {"source": "x", "source_id": f"x_{tweet_id}", "published_at": now, "url": url, "text": tweet_text}
    auto_kind = classify_x_post(raw_post)

    if auto_kind:
        print(f"\nAuto-detected category: {auto_kind}")
    else:
        print("\nCould not auto-detect a category from the tweet text.")

    print("\nAvailable categories:")
    for i, kind in enumerate(KINDS, 1):
        marker = " ← auto-detected" if kind == auto_kind else ""
        print(f"  {i}. {kind}{marker}")
    print("  s. Skip / cancel")

    default = str(KINDS.index(auto_kind) + 1) if auto_kind else ""
    prompt = f"\nChoose category [{default}]: " if default else "\nChoose category: "
    choice = input(prompt).strip().lower()

    if choice == "s":
        print("Cancelled.")
        return
    if choice == "" and auto_kind:
        kind = auto_kind
    elif choice.isdigit() and 1 <= int(choice) <= len(KINDS):
        kind = KINDS[int(choice) - 1]
    else:
        print("Invalid choice.")
        sys.exit(1)

    _send(url, tweet_id, tweet_text, kind, now, dry_run=False, yes=False)


def run_noninteractive(url: str, tweet_text: str, kind_override: str | None, dry_run: bool, yes: bool) -> None:
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        print("Error: Could not extract tweet ID from URL.")
        sys.exit(1)
    url = f"https://x.com/officialLRT1/status/{tweet_id}"

    now = datetime.now(PHT)
    raw_post = {"source": "x", "source_id": f"x_{tweet_id}", "published_at": now, "url": url, "text": tweet_text}
    auto_kind = classify_x_post(raw_post)
    kind = kind_override or auto_kind

    if not kind:
        print("DETECTED_KIND: none")
        print("Could not auto-detect a category. Specify --kind explicitly.")
        sys.exit(1)

    print(f"DETECTED_KIND: {kind}")
    _send(url, tweet_id, tweet_text, kind, now, dry_run=dry_run, yes=yes)


def _send(url: str, tweet_id: str, tweet_text: str, kind: str, now: datetime, dry_run: bool, yes: bool) -> None:
    state = load_state()

    if kind == "disruption_start" and state.get("active_disruption"):
        print("Note: active_disruption is already set — sending as disruption_update.")
        kind = "disruption_update"

    item = {
        "source": "x",
        "source_id": f"x_{tweet_id}",
        "published_at": now,
        "url": url,
        "text": tweet_text,
        "kind": kind,
        "title": None,
        "effective_window": None,
    }

    already_posted = has_posted_item(state, item["source_id"])
    if already_posted:
        print(f"Warning: Tweet {tweet_id} was already posted.")
        if not yes:
            if input("Post again anyway? [y/N]: ").strip().lower() != "y":
                print("Cancelled.")
                return

    message = format_x_message(item)
    print("\n--- Message preview ---")
    print(message)
    print("-----------------------")

    if dry_run:
        print("\n[dry-run] Message not sent. State not updated.")
        return

    if not yes:
        if input("\nSend to Telegram? [y/N]: ").strip().lower() != "y":
            print("Cancelled.")
            return

    remember_posted_item(state, item["source_id"])
    if kind == "disruption_start":
        state["active_disruption"] = item["source_id"]
    elif kind == "disruption_clear":
        state["active_disruption"] = None
    elif kind == "flood_alert":
        state["active_flood"] = item["source_id"]
    elif kind == "flood_clear":
        state["active_flood"] = None

    send_telegram(message)
    save_state(state)
    print("\nDone! Announcement sent and state updated.")


def main() -> None:
    if len(sys.argv) == 1:
        run_interactive()
        return

    parser = argparse.ArgumentParser(description="Manually push an LRT-1 tweet announcement to Telegram.")
    parser.add_argument("--url", required=True, help="Tweet URL")
    parser.add_argument("--text-file", required=True, metavar="FILE", help="Path to file containing tweet text")
    parser.add_argument("--kind", choices=KINDS, help="Override the auto-detected category")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not send")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()

    with open(args.text_file, encoding="utf-8") as f:
        tweet_text = f.read().strip()

    if not tweet_text:
        print("Error: Tweet text file is empty.")
        sys.exit(1)

    run_noninteractive(args.url, tweet_text, args.kind, args.dry_run, args.yes)


if __name__ == "__main__":
    main()
