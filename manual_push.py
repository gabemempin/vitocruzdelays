#!/usr/bin/env python3
"""
manual_push.py — Manually push a tweet announcement to @vitocruzdelays.

Usage:
    python manual_push.py [tweet_url]
    python manual_push.py --dry-run [tweet_url]

Set TELEGRAM_BOT_TOKEN before running. TELEGRAM_CHANNEL defaults to @vitocruzdelays.
"""

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


def prompt_tweet_text() -> str:
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
    return "\n".join(lines).strip()


def prompt_kind(auto_kind: str | None) -> str | None:
    print("\nAvailable categories:")
    for i, kind in enumerate(KINDS, 1):
        marker = " ← auto-detected" if kind == auto_kind else ""
        print(f"  {i}. {kind}{marker}")
    print("  s. Skip / cancel")

    default = str(KINDS.index(auto_kind) + 1) if auto_kind else ""
    prompt = f"\nChoose category [{default}]: " if default else "\nChoose category: "

    choice = input(prompt).strip().lower()
    if choice == "s":
        return None
    if choice == "" and auto_kind:
        return auto_kind
    if choice.isdigit() and 1 <= int(choice) <= len(KINDS):
        return KINDS[int(choice) - 1]
    print("Invalid choice.")
    sys.exit(1)


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    url = args[0].strip() if args else input("Paste the tweet URL: ").strip()

    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        print("Error: Could not extract tweet ID from URL.")
        sys.exit(1)

    url = f"https://x.com/officialLRT1/status/{tweet_id}"
    tweet_text = prompt_tweet_text()

    if not tweet_text:
        print("Error: No tweet text provided.")
        sys.exit(1)

    now = datetime.now(PHT)
    raw_post = {
        "source": "x",
        "source_id": f"x_{tweet_id}",
        "published_at": now,
        "url": url,
        "text": tweet_text,
    }

    auto_kind = classify_x_post(raw_post)
    if auto_kind:
        print(f"\nAuto-detected category: {auto_kind}")
    else:
        print("\nCould not auto-detect a category from the tweet text.")

    kind = prompt_kind(auto_kind)
    if kind is None:
        print("Cancelled.")
        return

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

    state = load_state()
    if has_posted_item(state, item["source_id"]):
        print(f"\nWarning: Tweet {tweet_id} was already posted.")
        if input("Post again anyway? [y/N]: ").strip().lower() != "y":
            print("Cancelled.")
            return

    if kind == "disruption_start" and state.get("active_disruption"):
        print("\nNote: active_disruption is already set in state.")
        print("The message will be formatted as a disruption_update.")
        if input("Proceed? [y/N]: ").strip().lower() != "y":
            print("Cancelled.")
            return
        item["kind"] = "disruption_update"

    message = format_x_message(item)
    print("\n--- Message preview ---")
    print(message)
    print("-----------------------\n")

    if dry_run:
        print("[dry-run] Message not sent. State not updated.")
        return

    if input("Send to Telegram? [y/N]: ").strip().lower() != "y":
        print("Cancelled.")
        return

    remember_posted_item(state, item["source_id"])
    if kind == "disruption_start":
        state["active_disruption"] = item["source_id"]
    elif kind == "disruption_update":
        pass
    elif kind == "disruption_clear":
        state["active_disruption"] = None
    elif kind == "flood_alert":
        state["active_flood"] = item["source_id"]
    elif kind == "flood_clear":
        state["active_flood"] = None

    send_telegram(message)
    save_state(state)
    print("Done! Announcement sent and state updated.")


if __name__ == "__main__":
    main()
