# Changelog

## 2026-04-16

### Added
- **Disruption notice in morning announcements** — when an active disruption carried over from a previous run, the morning opening bundle now includes a `⚠️ Service disruption may still be ongoing` notice with a link to `@officialLRT1`, so subscribers who missed the original alert are still warned.

---

## 2026-04-13

### Changed
- **Term Break suspension of rush hour alerts** — morning and afternoon rush hour alerts are paused for the April 13 – May 3, 2026 term break, when commuter volumes are lower.

---

## 2026-04-10

### Added
- **Weekday rush hour alerts** — two new time-based alerts per weekday:
  - Morning alert fires at 06:30–07:00, heads-up before the 07:00–09:00 AM peak.
  - Afternoon alert fires at 16:30–17:00, heads-up before the 17:00–20:00 PM peak.
- Five rotating messages for each rush window (`MORNING_RUSH_MESSAGES`, `AFTERNOON_RUSH_MESSAGES`), selected daily via the same week/day shuffle used by opening and closing messages.

---

## 2026-04-09

### Changed
- **Weekend closing announcement moved to 21:00** — gives a 35-minute window (21:00–21:35) before the 21:45 last train, replacing the previous 21:30 start that left too little time.
- **Closing window end tightened to `last_train − 10 min`** — prevents the closing message from firing too close to (or after) the last departure regardless of schedule.

---

## 2026-04-08

### Added
- **Evening holiday reminder** (18:00–20:00) — fires the night before a public holiday or RSS-announced override day; includes adjusted or suspended hours. Skipped for regular weekends.
- **Monday weekly outlook** — on Monday mornings, a `📋 This week's LRT-1 schedule` summary is prepended to the opening bundle whenever the week contains a public holiday, adjusted hours, or closure.
- **Tomorrow schedule note in closing message** — when the closing message fires, a `📅 Tomorrow` line is appended if the next day is a weekend, holiday, or has a schedule override.

### Fixed
- Em dashes in closing window comparisons were causing silent comparison bugs; replaced with correct `timedelta` arithmetic.

---

## 2026-04-01

### Changed
- Closing window widened further; added more variety to `OPENING_MESSAGES` and `CLOSING_MESSAGES` pools (17 messages each).

---

## 2026-03-30

### Changed
- **Pivoted data source to official LRMC channels** — the bot now monitors the LRMC RSS feed (`lrmc.ph/feed/`) for planned schedule advisories and `@officialLRT1` on X for real-time disruption posts, replacing the previous approach.
  - RSS items are filtered by service-impacting keywords and parsed for closure/adjusted-hours overrides.
  - X posts are classified as `disruption_start`, `disruption_update`, `disruption_clear`, `crowd_alert_high`, or `crowd_alert_moderate`.
  - Crowd alerts only fire if Vito Cruz is mentioned by name.
  - Schedule overrides from RSS are stored in state and applied to the daily schedule; they expire one day after their end date.
  - Bootstrap mode on first run marks all existing items as seen without posting, preventing backlog floods.
- **GitHub Actions updated to Node 24** runtime.

---

## 2026-03-06

### Fixed
- Opening window now correctly starts at 04:30 on weekdays and 05:00 on weekends/holidays, matching actual first-train times.

---

## 2026-03-05

### Added
- **Daily opening and closing announcements** with 17 rotating messages each, shuffled by `(week_number × 7 + day_of_week) % pool_size` so every message is reachable and rotates daily.
- Opening message includes first/last train times; bold header formatting applied to both opening and closing messages.
- `state.json` persistence via `actions/cache` between GitHub Actions runs.

### Fixed
- Timezone corrected to `Asia/Manila` (PHT, UTC+8).

---

## 2026-03-05 — Initial release

- Telegram bot monitoring LRT-1 Vito Cruz station, posting to `@vitocruzdelays`.
- Runs every 5 minutes as a GitHub Actions workflow; no server required.
- Posts real-time delay and service alerts scraped from official sources.
