import html
import json
import os
import random
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

PHT = ZoneInfo("Asia/Manila")

OPENING_MESSAGES = [
    "🚃 Good morning! LRT-1 Vito Cruz is now open. Stay sharp and have a safe commute!",
    "🌅 Rise and ride, commuters! Vito Cruz station is open and trains are running. Have a great one!",
    "🟢 LRT-1 is open! Vito Cruz station is ready for your morning commute. Stay safe out there!",
    "Good morning! 🚃 Vito Cruz is up and running. Another day, another commute. You've got this!",
    "🚃 Trains are rolling! LRT-1 Vito Cruz is now open. Have a safe and smooth commute today!",
    "🚃 Morning, Vito Cruz! LRT-1 is now open and ready to roll. Safe commute today!",
    "🟢 Good morning! Trains are running at Vito Cruz. Let's make it a smooth one today!",
    "🚃 LRT-1 Vito Cruz is open! Wishing everyone a safe and stress-free commute this morning.",
    "☀️ A new day, a new commute. Vito Cruz station is open — ride safe!",
    "🟢 Doors open at Vito Cruz! Start your morning right and have a great commute.",
    "🌅 Early risers, your train awaits! LRT-1 Vito Cruz is now open and running.",
    "🚃 Another morning, another ride. LRT-1 is open at Vito Cruz — make it a good one!",
    "🟢 Vito Cruz is live! Trains are running — stay safe and enjoy the ride.",
    "☀️ Good morning from Vito Cruz! LRT-1 is open. Here's to a smooth commute ahead.",
    "🚃 LRT-1 is running! Whether it's rush hour or a slow start — Vito Cruz is ready for you.",
    "🌄 Morning commuters, Vito Cruz station is open. Safe travels and good vibes today!",
    "🟢 Trains are moving at Vito Cruz. Have a safe commute and a great day ahead!",
]

CLOSING_MESSAGES = [
    "🌙 LRT-1 is closing in 30 minutes. If you're still out, now's the time to head to Vito Cruz!",
    "⏰ Wrapping up soon! LRT-1 closes in 30 minutes. Make your way to the station while you still can.",
    "🌙 Almost done for the night! LRT-1 Vito Cruz will be closing soon. Catch your last train home!",
    "⚠️ 30 minutes left! LRT-1 is winding down for the night. Don't miss your last ride home from Vito Cruz.",
    "🌙 Night owls, heads up! LRT-1 closes in 30 minutes. Get to Vito Cruz before the last train leaves!",
    "🌙 PSA: LRT-1 closes in 30 minutes! Time to wrap up and head to Vito Cruz for your last ride home.",
    "⏰ Last stretch! LRT-1 Vito Cruz is closing soon. Don't get stranded, head to the station now!",
    "🌙 Reminder: LRT-1 wraps up soon. If you're heading home, now's the time to make your move to Vito Cruz.",
    "🏠 Start making your way home! LRT-1 closes in 30 minutes — Vito Cruz station is still open.",
    "⏰ Clock's ticking! About 30 minutes before LRT-1 shuts down for the night. Head to Vito Cruz!",
    "🌙 The last trains are coming. Don't sleep on it — get to Vito Cruz before LRT-1 calls it a night.",
    "🚃 LRT-1 is in its final hour. Make sure you're at Vito Cruz before the last train departs!",
    "⚠️ Friendly reminder: LRT-1 closes in 30 minutes. Wrap up and head to Vito Cruz while you still can.",
    "🌙 It's almost a wrap for LRT-1 tonight. Catch your ride home — head to Vito Cruz now!",
    "🏠 Heading home? LRT-1 closes soon. Better get moving to Vito Cruz before the last train!",
    "⏰ Last trains of the night are near. Don't miss out — Vito Cruz station closes in 30 minutes.",
    "🌙 LRT-1 is winding down. If home is the destination, now's the time to head to Vito Cruz.",
]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@vitocruzdelays")
STATE_FILE = "state.json"

TARGET_STATION = "Vito Cruz"
TARGET_STATION_NORMALIZED = "vito cruz"
REQUEST_TIMEOUT = 20
RSS_FEED_URL = "https://lrmc.ph/feed/"
X_PROFILE_URL = "https://x.com/officialLRT1"
USER_AGENT = "Mozilla/5.0 (compatible; VitoCruzAnnouncementBot/3.0)"
SOURCE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xml,application/xhtml+xml,application/json",
}

STATE_DEFAULTS = {
    "posted_item_ids": [],
    "active_disruption": None,
    "current_schedule_override": None,
    "schedule_overrides": [],
    "last_seen_rss_item_id": None,
    "last_seen_x_post_id": None,
    "last_opening": None,
    "last_closing": None,
    "rss_bootstrapped": False,
    "x_bootstrapped": False,
}

POSTED_ITEM_LIMIT = 250
X_POST_LIMIT = 8

WEEKDAY_SERVICE = {
    "name": "weekday",
    "first_train": time(4, 30),
    "last_train": time(22, 45),
    "closing_announcement": time(22, 0),
}

WEEKEND_OR_HOLIDAY_SERVICE = {
    "name": "weekend_or_holiday",
    "first_train": time(5, 0),
    "last_train": time(21, 45),
    "closing_announcement": time(21, 0),
}

RSS_GATE_KEYWORDS = (
    "operating schedule",
    "operating hours",
    "train schedule",
    "temporary suspension",
    "suspension of lrt-1 operations",
    "extended operating hours",
    "adjusted",
    "maintenance",
    "holy week",
    "holiday schedule",
    "service advisory",
)

X_CLEAR_KEYWORDS = (
    "operations are now back to normal",
    "operations are back to normal",
    "operations normalized",
    "operations have normalized",
    "service has resumed",
    "operations have resumed",
    "normal operations have resumed",
    "train service is now normal",
    "full operations resumed",
)

X_DISRUPTION_KEYWORDS = (
    "service interruption",
    "limited operations",
    "temporary stop",
    "technical issue",
    "technical problem",
    "power issue",
    "unloading passengers",
    "slow moving",
    "delay",
    "single-track",
    "single track",
    "provisional service",
    "train service is temporarily",
    "shortened route",
    "operations are delayed",
)

X_CROWD_KEYWORDS = (
    "high passenger volume",
    "heavy passenger volume",
    "passenger volume",
    "crowding",
    "crowded",
    "long queue",
    "longer queue",
    "queueing",
    "build-up",
    "buildup",
    "heavy foot traffic",
    "station is full",
)

MONTH_PATTERN = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
)
DATE_FRAGMENT_PATTERN = rf"{MONTH_PATTERN}\s+\d{{1,2}}(?:\s*\([^)]+\))?(?:,\s*\d{{4}})?"
DATE_RANGE_RE = re.compile(
    rf"\bfrom\s+({DATE_FRAGMENT_PATTERN})\s+(?:to|-)\s+({DATE_FRAGMENT_PATTERN})",
    re.IGNORECASE,
)
SINGLE_DATE_RE = re.compile(rf"\bon\s+({DATE_FRAGMENT_PATTERN})", re.IGNORECASE)
STARTING_DATE_RE = re.compile(rf"\b(?:starting|effective|beginning)\s+({DATE_FRAGMENT_PATTERN})", re.IGNORECASE)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]M)\b", re.IGNORECASE)
CLOSURE_RANGE_RE = re.compile(
    rf"(?:temporary suspension|suspension of .*? operations|closure|closed)\D{{0,40}}from\s+"
    rf"({DATE_FRAGMENT_PATTERN})\s+(?:to|-)\s+({DATE_FRAGMENT_PATTERN})",
    re.IGNORECASE,
)
CLOSED_ON_RE = re.compile(
    rf"(?:temporary suspension|suspension of .*? operations|closure|closed)\D{{0,40}}on\s+"
    rf"({DATE_FRAGMENT_PATTERN})",
    re.IGNORECASE,
)


def get_daily_message(message_list: list[str]) -> str:
    now = datetime.now(PHT)
    week_number = now.isocalendar()[1]
    day_of_week = now.weekday()
    shuffled = message_list[:]
    random.Random(week_number).shuffle(shuffled)
    return shuffled[day_of_week]


def format_announcement(message: str) -> str:
    match = re.search(r"[!.]\s+", message)
    if match:
        header = message[: match.start() + 1]
        body = message[match.end() :]
        return f"<b>{header}</b>\n\n{body}"
    return message


def log_event(event: str, **payload: Any) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=True, default=str))


def normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def contains_normalized_keyword(text: Any, keywords: tuple[str, ...]) -> bool:
    normalized_text = normalize_name(text)
    return any(normalize_name(keyword) in normalized_text for keyword in keywords)


def strip_html(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"<script.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_excerpt(value: str) -> str:
    text = strip_html(value)
    text = re.sub(r"Read More.*$", "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


def truncate_text(text: str, limit: int = 550) -> str:
    if len(text) <= limit:
        return text
    truncated = text[:limit].rsplit(" ", 1)[0].strip()
    return f"{truncated}..."


def parse_rss_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PHT)
    return parsed.astimezone(PHT)


def parse_time_string(value: str | None) -> time | None:
    if not value:
        return None
    cleaned = value.strip().upper()
    return datetime.strptime(cleaned, "%I:%M %p").time()


def time_to_string(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def string_to_time(value: str | None) -> time | None:
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


def date_to_string(value: date | None) -> str | None:
    return value.isoformat() if value else None


def string_to_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def add_minutes_to_time(value: time, minutes: int) -> time:
    shifted = datetime.combine(date.today(), value) + timedelta(minutes=minutes)
    return shifted.time().replace(second=0, microsecond=0)


def format_timestamp(value: datetime | None) -> str:
    if not value:
        return datetime.now(PHT).strftime("%b %d, %I:%M %p")
    return value.astimezone(PHT).strftime("%b %d, %I:%M %p")


def parse_date_fragment(fragment: str, default_year: int) -> date | None:
    cleaned = re.sub(r"\s*\([^)]*\)", "", fragment).replace(",", "").strip()
    parts = cleaned.split()
    if len(parts) == 2:
        cleaned = f"{cleaned} {default_year}"
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def extract_date_ranges(text: str, default_year: int) -> list[tuple[date, date]]:
    ranges = []
    for start_text, end_text in DATE_RANGE_RE.findall(text):
        start_date = parse_date_fragment(start_text, default_year)
        end_date = parse_date_fragment(end_text, default_year)
        if start_date and end_date:
            ranges.append((start_date, end_date))
    return ranges


def extract_single_date(text: str, default_year: int) -> date | None:
    for pattern in (SINGLE_DATE_RE, STARTING_DATE_RE):
        match = pattern.search(text)
        if match:
            return parse_date_fragment(match.group(1), default_year)
    return None


def is_public_holiday(target_date: date) -> bool:
    try:
        import holidays
    except ImportError:
        return False
    return target_date in holidays.country_holidays("PH", years=target_date.year)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(SOURCE_HEADERS)
    return session


def parse_rss_feed(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items = []
    for item_el in root.findall("./channel/item"):
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        guid = (item_el.findtext("guid") or link).strip()
        description_html = item_el.findtext("description") or ""
        body_html = item_el.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or description_html
        published_at = parse_rss_datetime(item_el.findtext("pubDate"))
        items.append(
            {
                "source": "lrmc_rss",
                "source_id": f"rss:{guid}",
                "title": title,
                "url": link,
                "description_html": description_html,
                "body_html": body_html,
                "summary": clean_excerpt(description_html),
                "body": strip_html(body_html),
                "published_at": published_at,
            }
        )
    return items


def fetch_lrmc_rss_items(session: requests.Session) -> list[dict[str, Any]]:
    response = session.get(RSS_FEED_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return parse_rss_feed(response.text)


def rss_item_is_service_impacting(item: dict[str, Any]) -> bool:
    gate_text = f"{item['title']} {item['summary']}"
    return "lrt 1" in normalize_name(gate_text) and contains_normalized_keyword(gate_text, RSS_GATE_KEYWORDS)


def extract_html_paragraphs(body_html: str) -> list[str]:
    paragraphs = [strip_html(match) for match in re.findall(r"<p\b[^>]*>(.*?)</p>", body_html, re.IGNORECASE | re.DOTALL)]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    return paragraphs or [strip_html(body_html)]


def extract_closure_overrides(item: dict[str, Any]) -> list[dict[str, Any]]:
    default_year = item["published_at"].year if item["published_at"] else datetime.now(PHT).year
    body = strip_html(item["body_html"])
    overrides = []

    for start_text, end_text in CLOSURE_RANGE_RE.findall(body):
        start_date = parse_date_fragment(start_text, default_year)
        end_date = parse_date_fragment(end_text, default_year)
        if start_date and end_date:
            overrides.append(
                {
                    "override_id": f"{item['source_id']}:closed:{start_date.isoformat()}:{end_date.isoformat()}",
                    "source_id": item["source_id"],
                    "kind": "closed",
                    "start_date": date_to_string(start_date),
                    "end_date": date_to_string(end_date),
                    "first_train": None,
                    "last_train": None,
                    "closing_announcement": None,
                    "reason": item["title"],
                    "url": item["url"],
                    "published_at": item["published_at"].isoformat() if item["published_at"] else None,
                }
            )

    for date_text in CLOSED_ON_RE.findall(body):
        closed_date = parse_date_fragment(date_text, default_year)
        if closed_date:
            overrides.append(
                {
                    "override_id": f"{item['source_id']}:closed:{closed_date.isoformat()}:{closed_date.isoformat()}",
                    "source_id": item["source_id"],
                    "kind": "closed",
                    "start_date": date_to_string(closed_date),
                    "end_date": date_to_string(closed_date),
                    "first_train": None,
                    "last_train": None,
                    "closing_announcement": None,
                    "reason": item["title"],
                    "url": item["url"],
                    "published_at": item["published_at"].isoformat() if item["published_at"] else None,
                }
            )

    return overrides


def extract_operating_times(paragraph: str) -> dict[str, str] | None:
    if not (re.search(r"\bfirst\b", paragraph, re.IGNORECASE) and re.search(r"\blast\b", paragraph, re.IGNORECASE)):
        return None

    times = [parse_time_string(match.group(1)) for match in TIME_RE.finditer(paragraph)]
    times = [value for value in times if value is not None]
    if len(times) < 2:
        return None

    first_train = min(times)
    last_train = max(times)
    return {
        "first_train": time_to_string(first_train),
        "last_train": time_to_string(last_train),
        # Keep the previous 45-minute lead to better match Vito Cruz’s practical closing window.
        "closing_announcement": time_to_string(add_minutes_to_time(last_train, -45)),
    }


def extract_hours_overrides(item: dict[str, Any]) -> list[dict[str, Any]]:
    default_year = item["published_at"].year if item["published_at"] else datetime.now(PHT).year
    paragraphs = extract_html_paragraphs(item["body_html"])
    overrides = []

    for index, paragraph in enumerate(paragraphs):
        times = extract_operating_times(paragraph)
        if not times:
            continue

        ranges = extract_date_ranges(paragraph, default_year)
        if not ranges:
            context = " ".join(paragraphs[max(0, index - 1) : index + 1])
            ranges = extract_date_ranges(context, default_year)
        if ranges:
            start_date, end_date = ranges[0]
            overrides.append(
                {
                    "override_id": f"{item['source_id']}:hours:{start_date.isoformat()}:{end_date.isoformat()}",
                    "source_id": item["source_id"],
                    "kind": "hours",
                    "start_date": date_to_string(start_date),
                    "end_date": date_to_string(end_date),
                    "first_train": times["first_train"],
                    "last_train": times["last_train"],
                    "closing_announcement": times["closing_announcement"],
                    "reason": item["title"],
                    "url": item["url"],
                    "published_at": item["published_at"].isoformat() if item["published_at"] else None,
                }
            )
            continue

        single_date = extract_single_date(paragraph, default_year)
        if not single_date:
            context = " ".join(paragraphs[max(0, index - 1) : index + 1])
            single_date = extract_single_date(context, default_year)
        if single_date:
            overrides.append(
                {
                    "override_id": f"{item['source_id']}:hours:{single_date.isoformat()}:{single_date.isoformat()}",
                    "source_id": item["source_id"],
                    "kind": "hours",
                    "start_date": date_to_string(single_date),
                    "end_date": date_to_string(single_date),
                    "first_train": times["first_train"],
                    "last_train": times["last_train"],
                    "closing_announcement": times["closing_announcement"],
                    "reason": item["title"],
                    "url": item["url"],
                    "published_at": item["published_at"].isoformat() if item["published_at"] else None,
                }
            )

    return overrides


def normalize_rss_item(raw_item: dict[str, Any]) -> dict[str, Any] | None:
    if not rss_item_is_service_impacting(raw_item):
        return None

    schedule_overrides = extract_closure_overrides(raw_item) + extract_hours_overrides(raw_item)
    kind = "planned_closure" if any(override["kind"] == "closed" for override in schedule_overrides) else "planned_schedule"

    return {
        "source": raw_item["source"],
        "source_id": raw_item["source_id"],
        "published_at": raw_item["published_at"],
        "url": raw_item["url"],
        "title": raw_item["title"],
        "summary": raw_item["summary"] or truncate_text(raw_item["body"], 400),
        "text": raw_item["body"],
        "kind": kind,
        "effective_window": {
            "start_date": min((override["start_date"] for override in schedule_overrides), default=None),
            "end_date": max((override["end_date"] for override in schedule_overrides), default=None),
        }
        if schedule_overrides
        else None,
        "schedule_overrides": schedule_overrides,
    }


def fetch_x_posts() -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed.") from exc

    posts = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 2400},
            locale="en-US",
            timezone_id="Asia/Manila",
        )
        page = context.new_page()
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "media", "font"}
            else route.continue_(),
        )

        try:
            page.goto(X_PROFILE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("article[data-testid='tweet']", timeout=20000)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Timed out waiting for public X posts to render.") from exc

        page.wait_for_timeout(3000)
        tweet_locator = page.locator("article[data-testid='tweet']")
        tweet_count = min(tweet_locator.count(), X_POST_LIMIT)

        for index in range(tweet_count):
            article = tweet_locator.nth(index)
            text_locator = article.locator("[data-testid='tweetText']")
            text_parts = [part.strip() for part in text_locator.all_inner_texts()] if text_locator.count() else []
            text = "\n".join(part for part in text_parts if part)

            permalink = None
            for href in article.locator("a[href*='/status/']").evaluate_all(
                "(anchors) => anchors.map((node) => node.getAttribute('href'))"
            ):
                if href and "/status/" in href:
                    permalink = href if href.startswith("http") else f"https://x.com{href}"
                    break

            if not permalink:
                continue

            tweet_id_match = re.search(r"/status/(\d+)", permalink)
            if not tweet_id_match:
                continue

            datetime_attr = None
            if article.locator("time").count():
                datetime_attr = article.locator("time").first.get_attribute("datetime")

            published_at = None
            if datetime_attr:
                published_at = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00")).astimezone(PHT)

            posts.append(
                {
                    "source": "x",
                    "source_id": f"x:{tweet_id_match.group(1)}",
                    "tweet_id": tweet_id_match.group(1),
                    "published_at": published_at,
                    "url": permalink,
                    "text": text.strip(),
                }
            )

        browser.close()

    return posts


def classify_x_post(raw_post: dict[str, Any]) -> str | None:
    normalized = normalize_name(raw_post.get("text"))
    if not normalized:
        return None

    if TARGET_STATION_NORMALIZED in normalized and contains_normalized_keyword(normalized, X_CROWD_KEYWORDS):
        return "crowd_alert"
    if contains_normalized_keyword(normalized, X_CLEAR_KEYWORDS):
        return "disruption_clear"
    if contains_normalized_keyword(normalized, X_DISRUPTION_KEYWORDS):
        return "disruption_start"
    return None


def normalize_x_post(raw_post: dict[str, Any]) -> dict[str, Any] | None:
    kind = classify_x_post(raw_post)
    if not kind:
        return None
    return {
        "source": raw_post["source"],
        "source_id": raw_post["source_id"],
        "published_at": raw_post["published_at"],
        "url": raw_post["url"],
        "text": raw_post["text"],
        "kind": kind,
        "title": None,
        "effective_window": None,
    }


def load_state() -> dict[str, Any]:
    state = STATE_DEFAULTS.copy()
    if not os.path.exists(STATE_FILE):
        return state

    with open(STATE_FILE, encoding="utf-8") as file:
        saved = json.load(file)

    for key, default_value in STATE_DEFAULTS.items():
        if key in saved:
            state[key] = saved[key]
        else:
            state[key] = default_value

    state["posted_item_ids"] = list(dict.fromkeys(state.get("posted_item_ids") or []))[-POSTED_ITEM_LIMIT:]
    state["schedule_overrides"] = state.get("schedule_overrides") or []
    return state


def save_state(state: dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file)


def send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": CHANNEL, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )
    response.raise_for_status()
    print(f"Telegram sent: {message[:80]}...")


def remember_posted_item(state: dict[str, Any], source_id: str) -> None:
    items = state.setdefault("posted_item_ids", [])
    if source_id not in items:
        items.append(source_id)
    state["posted_item_ids"] = items[-POSTED_ITEM_LIMIT:]


def has_posted_item(state: dict[str, Any], source_id: str) -> bool:
    return source_id in state.get("posted_item_ids", [])


def merge_schedule_overrides(state: dict[str, Any], rss_items: list[dict[str, Any]], today: date) -> None:
    existing_ids = {override["override_id"] for override in state.get("schedule_overrides", [])}
    schedule_overrides = state.setdefault("schedule_overrides", [])

    for item in rss_items:
        for override in item.get("schedule_overrides", []):
            if override["override_id"] not in existing_ids:
                schedule_overrides.append(override)
                existing_ids.add(override["override_id"])

    cutoff = today - timedelta(days=1)
    state["schedule_overrides"] = [
        override
        for override in schedule_overrides
        if string_to_date(override.get("end_date")) is None or string_to_date(override.get("end_date")) >= cutoff
    ]


def applies_on_date(override: dict[str, Any], target_date: date) -> bool:
    start_date = string_to_date(override.get("start_date"))
    end_date = string_to_date(override.get("end_date"))
    if start_date and target_date < start_date:
        return False
    if end_date and target_date > end_date:
        return False
    return True


def get_base_service_schedule(target_date: date) -> dict[str, Any]:
    if target_date.weekday() >= 5 or is_public_holiday(target_date):
        return dict(WEEKEND_OR_HOLIDAY_SERVICE)
    return dict(WEEKDAY_SERVICE)


def get_service_schedule(now: datetime, state: dict[str, Any]) -> dict[str, Any]:
    target_date = now.date()
    schedule = get_base_service_schedule(target_date)
    schedule["closed"] = False
    schedule["reason"] = None
    schedule["override"] = None

    active_overrides = [override for override in state.get("schedule_overrides", []) if applies_on_date(override, target_date)]
    closed_overrides = [override for override in active_overrides if override.get("kind") == "closed"]
    if closed_overrides:
        chosen = sorted(closed_overrides, key=lambda item: item.get("published_at") or "", reverse=True)[0]
        return {
            "name": "closed",
            "closed": True,
            "reason": chosen.get("reason"),
            "override": chosen,
        }

    hour_overrides = [override for override in active_overrides if override.get("kind") == "hours"]
    if hour_overrides:
        chosen = sorted(hour_overrides, key=lambda item: item.get("published_at") or "", reverse=True)[0]
        schedule["first_train"] = string_to_time(chosen.get("first_train")) or schedule["first_train"]
        schedule["last_train"] = string_to_time(chosen.get("last_train")) or schedule["last_train"]
        schedule["closing_announcement"] = (
            string_to_time(chosen.get("closing_announcement")) or schedule["closing_announcement"]
        )
        schedule["override"] = chosen
        schedule["name"] = "override"

    return schedule


def within_window(now: datetime, start_time: time, end_time: time) -> bool:
    current_time = now.time()
    return start_time <= current_time <= end_time


def check_announcements(state: dict[str, Any], now: datetime, schedule: dict[str, Any]) -> list[str]:
    if schedule.get("closed"):
        return []

    messages = []
    today_string = now.strftime("%Y-%m-%d")
    opening_end = add_minutes_to_time(schedule["first_train"], 59)
    closing_end = add_minutes_to_time(schedule["closing_announcement"], 44)

    if within_window(now, schedule["first_train"], opening_end) and state.get("last_opening") != today_string:
        messages.append(format_announcement(get_daily_message(OPENING_MESSAGES)))
        state["last_opening"] = today_string

    if within_window(now, schedule["closing_announcement"], closing_end) and state.get("last_closing") != today_string:
        messages.append(format_announcement(get_daily_message(CLOSING_MESSAGES)))
        state["last_closing"] = today_string

    return messages


def source_link(url: str, label: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'


def format_rss_message(item: dict[str, Any]) -> str:
    title = html.escape(item["title"])
    summary = html.escape(truncate_text(item["summary"]))
    heading = "📣 <b>LRT-1 closure advisory</b>" if item["kind"] == "planned_closure" else "📣 <b>LRT-1 schedule advisory</b>"
    return (
        f"{heading}\n\n"
        f"<b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"🔗 {source_link(item['url'], 'View LRMC post')}\n"
        f"⏰ Posted {format_timestamp(item['published_at'])}"
    )


def format_x_message(item: dict[str, Any]) -> str:
    title = {
        "disruption_start": "🚨 <b>LRT-1 disruption alert</b>",
        "disruption_clear": "✅ <b>LRT-1 operations normalized</b>",
        "crowd_alert": "⚠️ <b>Vito Cruz crowd alert</b>",
    }[item["kind"]]
    text = html.escape(truncate_text(item["text"]))
    return (
        f"{title}\n\n"
        f"{text}\n\n"
        f"🔗 {source_link(item['url'], 'View @officialLRT1 post')}\n"
        f"⏰ Posted {format_timestamp(item['published_at'])}"
    )


def process_rss_items(state: dict[str, Any], rss_items: list[dict[str, Any]]) -> list[str]:
    if rss_items:
        state["last_seen_rss_item_id"] = rss_items[0]["source_id"]

    if not state.get("rss_bootstrapped"):
        for item in rss_items:
            remember_posted_item(state, item["source_id"])
        state["rss_bootstrapped"] = True
        return []

    messages = []
    for item in sorted(rss_items, key=lambda entry: entry["published_at"] or datetime.min.replace(tzinfo=PHT)):
        if has_posted_item(state, item["source_id"]):
            continue
        remember_posted_item(state, item["source_id"])
        messages.append(format_rss_message(item))
    return messages


def process_x_items(state: dict[str, Any], x_items: list[dict[str, Any]]) -> list[str]:
    if x_items:
        state["last_seen_x_post_id"] = x_items[0]["source_id"]

    ordered_items = sorted(x_items, key=lambda entry: entry["published_at"] or datetime.min.replace(tzinfo=PHT))

    if not state.get("x_bootstrapped"):
        for item in ordered_items:
            remember_posted_item(state, item["source_id"])
            if item["kind"] == "disruption_start":
                state["active_disruption"] = item["source_id"]
            elif item["kind"] == "disruption_clear":
                state["active_disruption"] = None
        state["x_bootstrapped"] = True
        return []

    messages = []
    for item in ordered_items:
        if has_posted_item(state, item["source_id"]):
            continue

        remember_posted_item(state, item["source_id"])

        if item["kind"] == "crowd_alert":
            messages.append(format_x_message(item))
            continue

        if item["kind"] == "disruption_start":
            state["active_disruption"] = item["source_id"]
            messages.append(format_x_message(item))
            continue

        if item["kind"] == "disruption_clear":
            if state.get("active_disruption"):
                state["active_disruption"] = None
                messages.append(format_x_message(item))

    return messages


def main() -> None:
    now = datetime.now(PHT)
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Checking official LRT-1 announcements...")

    state = load_state()
    session = build_session()

    raw_rss_items: list[dict[str, Any]] = []
    rss_items: list[dict[str, Any]] = []
    try:
        raw_rss_items = fetch_lrmc_rss_items(session)
        rss_items = [item for item in (normalize_rss_item(raw_item) for raw_item in raw_rss_items) if item]
        merge_schedule_overrides(state, rss_items, now.date())
        log_event(
            "rss_fetch",
            raw_count=len(raw_rss_items),
            relevant_count=len(rss_items),
            latest=raw_rss_items[0]["source_id"] if raw_rss_items else None,
        )
    except Exception as exc:
        log_event("rss_failure", error=str(exc))

    schedule = get_service_schedule(now, state)
    state["current_schedule_override"] = schedule.get("override")

    x_items: list[dict[str, Any]] = []
    try:
        raw_x_posts = fetch_x_posts()
        x_items = [item for item in (normalize_x_post(raw_post) for raw_post in raw_x_posts) if item]
        log_event(
            "x_fetch",
            raw_count=len(raw_x_posts),
            relevant_count=len(x_items),
            latest=raw_x_posts[0]["source_id"] if raw_x_posts else None,
        )
    except Exception as exc:
        log_event("x_failure", error=str(exc))

    messages = []
    messages.extend(process_rss_items(state, rss_items))
    messages.extend(process_x_items(state, x_items))
    messages.extend(check_announcements(state, now, schedule))

    log_event(
        "run_summary",
        message_count=len(messages),
        active_disruption=state.get("active_disruption"),
        current_schedule_override=state.get("current_schedule_override"),
    )

    for message in messages:
        send_telegram(message)

    save_state(state)


if __name__ == "__main__":
    main()
