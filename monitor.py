import requests
from bs4 import BeautifulSoup
import os
import json
import re
import random
from datetime import datetime
from zoneinfo import ZoneInfo

PHT = ZoneInfo("Asia/Manila")

OPENING_MESSAGES = [
    "🚃 Good morning! LRT-1 Vito Cruz is now open. Stay sharp and have a safe commute!",
    "🌅 Rise and ride, commuters! Vito Cruz station is open and trains are running. Have a great one!",
    "🟢 LRT-1 is open! Vito Cruz station is ready for your morning commute. Stay safe out there!",
    "Good morning! 🚃 Vito Cruz is up and running. Another day, another commute. You've got this!",
    "🚃 Trains are rolling! LRT-1 Vito Cruz is now open. Have a safe and smooth commute today!",
    "🚃 Morning, Vito Cruz! LRT-1 is now open and ready to roll. Safe commute today!",
    "🟢 Good morning! Trains are running at Vito Cruz. Let's make it a smooth one today!",
]

CLOSING_MESSAGES = [
    "🌙 LRT-1 is closing in 30 minutes. If you're still out, now's the time to head to Vito Cruz!",
    "⏰ Wrapping up soon! LRT-1 closes in 30 minutes. Make your way to the station while you still can.",
    "🌙 Almost done for the night! LRT-1 Vito Cruz will be closing soon. Catch your last train home!",
    "⚠️ 30 minutes left! LRT-1 is winding down for the night. Don't miss your last ride home from Vito Cruz.",
    "🌙 Night owls, heads up! LRT-1 closes in 30 minutes. Get to Vito Cruz before the last train leaves!",
    "🌙 PSA: LRT-1 closes in 30 minutes! Time to wrap up and head to Vito Cruz for your last ride home.",
    "⏰ Last stretch! LRT-1 Vito Cruz is closing soon. Don't get stranded, head to the station now!",
]


def get_daily_message(message_list):
    now = datetime.now(PHT)
    week_number = now.isocalendar()[1]
    day_of_week = now.weekday()  # 0 = Monday, 6 = Sunday
    shuffled = message_list[:]
    random.Random(week_number).shuffle(shuffled)
    return shuffled[day_of_week]

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = "@vitocruzdelays"
STATE_FILE = "state.json"
TARGET_STATION = "Vito Cruz"
DELAY_THRESHOLD_MIN = 5
SCRAPE_URL = "https://projectligtas.com/commute"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VitocruzDelayBot/1.0)"}


def fetch_vito_cruz_status():
    resp = requests.get(SCRAPE_URL, timeout=15, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for card in soup.select(".rush-train-card"):
        for station in card.select(".station-item-rush"):
            name_el = station.select_one(".station-name-rush")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if TARGET_STATION.lower() not in name.lower():
                continue

            line_el = card.select_one(".line-title")
            line = line_el.get_text(strip=True) if line_el else "LRT-1"

            directions = {}
            for pill in station.select(".eta-pill"):
                text = pill.get_text(separator=" ", strip=True)
                classes = pill.get("class", [])
                parts = text.split()
                if len(parts) < 2:
                    continue

                direction = parts[0]
                eta_text = " ".join(parts[1:])

                if "eta-now" in classes:
                    status, minutes = "now", 0
                elif "eta-soon" in classes:
                    status, minutes = "soon", 2
                elif "eta-unknown" in classes:
                    status, minutes = "unknown", None
                elif "eta-later" in classes:
                    status = "later"
                    m = re.search(r"(\d+)", eta_text)
                    minutes = int(m.group(1)) if m else None
                else:
                    status, minutes = "unknown", None

                directions[direction] = {
                    "status": status,
                    "minutes": minutes,
                    "text": eta_text,
                }

            return {
                "station": name,
                "line": line,
                "directions": directions,
                "timestamp": datetime.now(PHT).strftime("%I:%M %p"),
            }

    return None


def is_delayed(directions):
    for data in directions.values():
        if data["status"] == "unknown":
            return True
        if data["status"] == "later" and data["minutes"] is not None:
            if data["minutes"] >= DELAY_THRESHOLD_MIN:
                return True
    return False


def format_directions(directions):
    lines = []
    for direction, data in directions.items():
        emoji = "🔴" if data["status"] in ("unknown", "later") and (data["minutes"] is None or (data["minutes"] or 0) >= DELAY_THRESHOLD_MIN) else "🟢"
        lines.append(f"{emoji} {direction}: {data['text']}")
    return "\n".join(lines)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"was_delayed": False}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": CHANNEL, "text": message, "parse_mode": "HTML"}, timeout=10)
    resp.raise_for_status()
    print(f"Telegram sent: {message[:80]}...")


def is_operating_hours():
    now = datetime.now(PHT)
    return 5 <= now.hour < 22  # 5 AM to 10 PM PHT


def check_announcements(state):
    now = datetime.now(PHT)
    hour, minute = now.hour, now.minute
    is_weekday = now.weekday() < 5  # Monday to Friday

    # Opening: 4:30 AM weekdays, 5:00 AM weekends (within a 20-min window)
    opening_hour = 4 if is_weekday else 5
    opening_minute = 30 if is_weekday else 0
    is_opening_window = (hour == opening_hour and opening_minute <= minute < opening_minute + 20)

    # Winding down: 10:00 PM weekdays, 9:00 PM weekends (30 min before last train)
    closing_hour = 22 if is_weekday else 21
    is_closing_window = (hour == closing_hour and 0 <= minute < 20)

    today_str = now.strftime("%Y-%m-%d")

    if is_opening_window and state.get("last_opening") != today_str:
        send_telegram(get_daily_message(OPENING_MESSAGES))
        state["last_opening"] = today_str
        print("Sent opening message.")

    if is_closing_window and state.get("last_closing") != today_str:
        send_telegram(get_daily_message(CLOSING_MESSAGES))
        state["last_closing"] = today_str
        print("Sent closing message.")

    return state


def main():
    print(f"[{datetime.now(PHT).strftime('%Y-%m-%d %H:%M')}] Checking Vito Cruz status...")

    state = load_state()
    state = check_announcements(state)

    if not is_operating_hours():
        print("Outside LRT-1 operating hours (5 AM – 10 PM PHT). Skipping delay check.")
        save_state(state)
        return

    try:
        status = fetch_vito_cruz_status()
    except Exception as e:
        print(f"Fetch error: {e}")
        return

    if not status:
        print("Vito Cruz station not found on page.")
        return

    print(f"Directions: {status['directions']}")

    currently_delayed = is_delayed(status["directions"])
    was_delayed = state.get("was_delayed", False)

    if currently_delayed and not was_delayed:
        eta_text = format_directions(status["directions"])
        msg = (
            f"🚨 <b>Delay at Vito Cruz ({status['line']})</b>\n\n"
            f"{eta_text}\n\n"
            f"⏰ As of {status['timestamp']}"
        )
        send_telegram(msg)
        print("Alert sent: delay started.")

    elif not currently_delayed and was_delayed:
        eta_text = format_directions(status["directions"])
        msg = (
            f"✅ <b>Vito Cruz delay cleared ({status['line']})</b>\n\n"
            f"{eta_text}\n\n"
            f"⏰ As of {status['timestamp']}"
        )
        send_telegram(msg)
        print("Alert sent: delay cleared.")

    else:
        print(f"No change. Currently delayed: {currently_delayed}")

    state["was_delayed"] = currently_delayed
    save_state(state)


if __name__ == "__main__":
    main()
