import requests
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime

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
                "timestamp": datetime.now().strftime("%I:%M %p"),
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


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Checking Vito Cruz status...")

    try:
        status = fetch_vito_cruz_status()
    except Exception as e:
        print(f"Fetch error: {e}")
        return

    if not status:
        print("Vito Cruz station not found on page.")
        return

    print(f"Directions: {status['directions']}")

    state = load_state()
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

    save_state({"was_delayed": currently_delayed})


if __name__ == "__main__":
    main()
