# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Telegram bot that monitors LRT-1 Vito Cruz station (Manila) and posts service alerts to `@vitocruzdelays`. It runs every 5 minutes as a GitHub Actions workflow. There is no server — the entire bot is `monitor.py`.

## Commands

```bash
# Run tests
python3 -m unittest discover -s tests -v

# Syntax check
python3 -m py_compile monitor.py tests/test_monitor.py

# Install dependencies
pip install -r requirements.txt
python -m playwright install --with-deps chromium

# Run manually (requires TELEGRAM_BOT_TOKEN env var)
TELEGRAM_BOT_TOKEN=... python monitor.py
```

## Architecture

Everything lives in `monitor.py`. The `main()` function is the entry point and runs the full pipeline each invocation:

1. **Fetch LRMC RSS** (`fetch_lrmc_rss_items`) — pulls from `https://lrmc.ph/feed/`, filters for service-impacting posts using `RSS_GATE_KEYWORDS`, then extracts schedule overrides (closure dates, adjusted hours) via regex parsing of the article body. New items with future overrides get a structured advisory card (`format_override_preview_message`) instead of the raw RSS format.

2. **Fetch X/Twitter posts** (`fetch_x_posts`) — uses Playwright (headless Chromium) to scrape `@officialLRT1`'s public profile. Classifies posts as `disruption_start`, `disruption_update`, `disruption_clear`, `crowd_alert_high`, or `crowd_alert_moderate`. Crowd alerts only fire if Vito Cruz is mentioned by name. If a `disruption_start` arrives while `active_disruption` is already set, it posts as a `disruption_update` without resetting the disruption source.

3. **Resolve service schedule** (`get_service_schedule`) — starts from a weekday or weekend/holiday base schedule, then applies any active `schedule_overrides` stored in state. `closed` overrides take priority over `hours` overrides.

4. **Check announcements** (`check_announcements`) — manages all time-based posts:
   - **Opening window** (`first_train` + 59 min): good morning message with train times; "normal service resumes" prepended if yesterday had an override; Monday weekly outlook if this week has unusual days
   - **Holiday reminder window** (18:00–20:00): standalone heads-up if tomorrow is a public holiday or RSS override day (not regular weekends)
   - **Closing window** (`closing_announcement` to `last_train` − 10 min): good night message with tomorrow's schedule appended if tomorrow is non-standard

5. **Send to Telegram and save state** — messages are sent via Bot API. State is persisted to `state.json` and cached between GitHub Actions runs using `actions/cache`.

## State (`state.json`)

The state file is the bot's memory between runs. Key fields:
- `posted_item_ids` — deduplication list (capped at 250)
- `active_disruption` — source_id of the ongoing disruption, or null
- `schedule_overrides` — parsed closure/hours overrides from RSS, expire 1 day after their `end_date`
- `rss_bootstrapped` / `x_bootstrapped` — on first run, all existing items are marked seen without posting (prevents backlog flood)
- `last_opening` / `last_closing` — date strings to ensure once-per-day announcements
- `last_override_date` — date when an override/closure was last active (triggers "normal service resumes" message)
- `last_holiday_reminder` — date when the evening holiday reminder last fired
- `last_weekly_outlook` — date when the Monday weekly outlook last fired

## Schedule constants

- Weekday: first train 04:30, last train 22:45, closing announcement **21:30**
- Weekend/holiday: first train 05:00, last train 21:45, closing announcement **21:00**
- The closing window runs from `closing_announcement` to `last_train − 10 min`: weekday 21:30–22:35 (65 min), weekend 21:00–21:35 (35 min). This maximizes resilience to GitHub Actions scheduling gaps while never firing after the last train.

## Message rotation

`get_daily_message()` uses `(week_number * 7 + day_of_week) % len(pool)` so all 17 messages in each pool are reachable. The same message plays all day and rotates daily.

## Secrets

- `TELEGRAM_BOT_TOKEN` — GitHub Secret, injected into the workflow. Never in the repo.
- `TELEGRAM_CHANNEL` — defaults to `@vitocruzdelays` if not set.
