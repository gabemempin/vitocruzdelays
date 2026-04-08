import unittest
from datetime import date, datetime
from unittest.mock import patch

import monitor


SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <item>
      <title>LRMC announces LRT-1 operating schedule for Holy Week 2026</title>
      <link>https://lrmc.ph/2026/03/17/lrmc-announces-lrt-1-operating-schedule-for-holy-week-2026/</link>
      <guid>https://lrmc.ph/?p=19587</guid>
      <pubDate>Tue, 17 Mar 2026 01:39:36 +0000</pubDate>
      <description><![CDATA[LRT-1 private operator Light Rail Manila Corporation (LRMC) has officially announced the temporary suspension of LRT-1 operations from April 2 (Maundy Thursday) to April 5 (Easter Sunday), 2026.]]></description>
      <content:encoded><![CDATA[
        <p>LRT-1 private operator Light Rail Manila Corporation (LRMC) has officially announced the temporary suspension of LRT-1 operations from April 2 (Maundy Thursday) to April 5 (Easter Sunday), 2026.</p>
        <p>Before the temporary suspension, LRT-1 will implement its normal weekday operating hours from March 30 (Holy Monday) to April 1 (Holy Wednesday). During this period, the first trips will depart simultaneously from Dr. Santos Station and Fernando Poe Jr. Station at 4:30 AM. The last train is scheduled to leave Dr. Santos Station at 10:30 PM, while the last trip from Fernando Poe Jr. Station will depart at 10:45 PM.</p>
        <p>LRT-1 will resume its regular operations on April 6, 2026.</p>
      ]]></content:encoded>
    </item>
    <item>
      <title>LRMC marks decade of service with commitment to continuous improvement and modernization of LRT-1</title>
      <link>https://lrmc.ph/2026/02/24/lrmc-marks-decade-of-service-with-commitment-to-continuous-improvement-and-modernization-of-lrt-1/</link>
      <guid>https://lrmc.ph/?p=19541</guid>
      <pubDate>Tue, 24 Feb 2026 05:32:13 +0000</pubDate>
      <description><![CDATA[LRT-1 private operator Light Rail Manila Corporation (LRMC) is reaffirming its commitment to the continuous development and modernization of the rail system as it marks its 10th year of operations.]]></description>
      <content:encoded><![CDATA[<p>General company news only.</p>]]></content:encoded>
    </item>
  </channel>
</rss>
"""


class MonitorTests(unittest.TestCase):
    def test_parse_rss_feed(self):
        items = monitor.parse_rss_feed(SAMPLE_RSS_XML)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["source_id"], "rss:https://lrmc.ph/?p=19587")
        self.assertEqual(items[0]["published_at"].year, 2026)

    def test_normalize_rss_item_filters_general_news(self):
        raw_items = monitor.parse_rss_feed(SAMPLE_RSS_XML)
        normalized = [monitor.normalize_rss_item(item) for item in raw_items]
        self.assertIsNotNone(normalized[0])
        self.assertIsNone(normalized[1])

    def test_holy_week_article_extracts_schedule_overrides(self):
        raw_item = monitor.parse_rss_feed(SAMPLE_RSS_XML)[0]
        normalized = monitor.normalize_rss_item(raw_item)
        overrides = normalized["schedule_overrides"]
        closed = [override for override in overrides if override["kind"] == "closed"]
        hours = [override for override in overrides if override["kind"] == "hours"]

        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["start_date"], "2026-04-02")
        self.assertEqual(closed[0]["end_date"], "2026-04-05")
        self.assertEqual(hours[0]["start_date"], "2026-03-30")
        self.assertEqual(hours[0]["end_date"], "2026-04-01")
        self.assertEqual(hours[0]["first_train"], "04:30")
        self.assertEqual(hours[0]["last_train"], "22:45")
        self.assertEqual(hours[0]["closing_announcement"], "22:00")

    def test_merge_and_apply_closed_override(self):
        raw_item = monitor.parse_rss_feed(SAMPLE_RSS_XML)[0]
        rss_item = monitor.normalize_rss_item(raw_item)
        state = monitor.STATE_DEFAULTS.copy()
        state["schedule_overrides"] = []
        monitor.merge_schedule_overrides(state, [rss_item], date(2026, 3, 30))

        schedule = monitor.get_service_schedule(datetime(2026, 4, 3, 8, 0, tzinfo=monitor.PHT), state)
        self.assertTrue(schedule["closed"])
        self.assertEqual(schedule["reason"], rss_item["title"])

    def test_schedule_override_expires_after_window(self):
        state = monitor.STATE_DEFAULTS.copy()
        state["schedule_overrides"] = [
            {
                "override_id": "test",
                "source_id": "rss:test",
                "kind": "closed",
                "start_date": "2026-04-02",
                "end_date": "2026-04-05",
                "first_train": None,
                "last_train": None,
                "closing_announcement": None,
                "reason": "Test",
                "url": "https://example.com",
                "published_at": "2026-03-17T09:39:36+08:00",
            }
        ]
        monitor.merge_schedule_overrides(state, [], date(2026, 4, 7))
        self.assertEqual(state["schedule_overrides"], [])

    def test_holiday_base_schedule_uses_weekend_hours(self):
        with patch("monitor.is_public_holiday", return_value=True):
            schedule = monitor.get_base_service_schedule(date(2026, 6, 12))
        self.assertEqual(schedule["first_train"], monitor.WEEKEND_OR_HOLIDAY_SERVICE["first_train"])

    def test_classify_x_vito_cruz_crowd_alert_high(self):
        kind = monitor.classify_x_post({"text": "High passenger volume at Vito Cruz Station. Please expect longer queues."})
        self.assertEqual(kind, "crowd_alert_high")

    def test_classify_x_other_station_crowd_ignored(self):
        kind = monitor.classify_x_post({"text": "High passenger volume at EDSA Station. Please expect longer queues."})
        self.assertIsNone(kind)

    def test_classify_x_disruption_clear(self):
        kind = monitor.classify_x_post({"text": "Operations are now back to normal. Thank you for your patience."})
        self.assertEqual(kind, "disruption_clear")

    def test_classify_x_single_track_hyphenated_keyword(self):
        kind = monitor.classify_x_post({"text": "LRT-1 is under single-track operations due to a technical issue."})
        self.assertEqual(kind, "disruption_start")

    def test_rss_bootstrap_suppresses_backlog(self):
        raw_item = monitor.parse_rss_feed(SAMPLE_RSS_XML)[0]
        rss_item = monitor.normalize_rss_item(raw_item)
        state = monitor.STATE_DEFAULTS.copy()
        messages = monitor.process_rss_items(state, [rss_item], date(2026, 3, 17))
        self.assertEqual(messages, [])
        self.assertTrue(state["rss_bootstrapped"])
        self.assertIn(rss_item["source_id"], state["posted_item_ids"])

    def test_x_processing_clears_active_disruption(self):
        state = monitor.STATE_DEFAULTS.copy()
        state["x_bootstrapped"] = True
        state["active_disruption"] = "x:old"
        x_item = {
            "source": "x",
            "source_id": "x:123",
            "published_at": datetime(2026, 3, 30, 11, 0, tzinfo=monitor.PHT),
            "url": "https://x.com/officialLRT1/status/123",
            "text": "Operations are now back to normal.",
            "kind": "disruption_clear",
            "title": None,
            "effective_window": None,
        }
        messages = monitor.process_x_items(state, [x_item])
        self.assertEqual(len(messages), 1)
        self.assertIsNone(state["active_disruption"])

    def test_closing_message_suppressed_on_closed_day(self):
        state = monitor.STATE_DEFAULTS.copy()
        schedule = {"name": "closed", "closed": True, "reason": "Test", "override": None}
        messages = monitor.check_announcements(state, datetime(2026, 4, 3, 21, 0, tzinfo=monitor.PHT), schedule)
        self.assertEqual(messages, [])

    def test_classify_x_moderate_volume_crowd_alert(self):
        kind = monitor.classify_x_post({"text": "Vito Cruz Station is experiencing moderate volume of passengers."})
        self.assertEqual(kind, "crowd_alert_moderate")

    def test_classify_x_high_volume_of_passengers(self):
        kind = monitor.classify_x_post({"text": "There is a high volume of passengers at Vito Cruz."})
        self.assertEqual(kind, "crowd_alert_high")

    def test_opening_message_includes_train_times(self):
        schedule = {
            "first_train": monitor.WEEKDAY_SERVICE["first_train"],
            "last_train": monitor.WEEKDAY_SERVICE["last_train"],
            "override": None,
        }
        msg = monitor.format_opening_message("🚃 Good morning! LRT-1 is open.", schedule)
        self.assertIn("04:30", msg)
        self.assertIn("22:45", msg)

    def test_closing_announcement_window_ends_before_last_train_weekday(self):
        from datetime import time as time_type
        closing = monitor.WEEKDAY_SERVICE["closing_announcement"]
        last = monitor.WEEKDAY_SERVICE["last_train"]
        window_end = monitor.add_minutes_to_time(closing, 44)
        self.assertLess(window_end, last)

    def test_closing_announcement_window_ends_before_last_train_weekend(self):
        closing = monitor.WEEKEND_OR_HOLIDAY_SERVICE["closing_announcement"]
        last = monitor.WEEKEND_OR_HOLIDAY_SERVICE["last_train"]
        window_end = monitor.add_minutes_to_time(closing, 44)
        self.assertLess(window_end, last)

    def test_future_override_uses_preview_format(self):
        raw_item = monitor.parse_rss_feed(SAMPLE_RSS_XML)[0]
        rss_item = monitor.normalize_rss_item(raw_item)
        state = monitor.STATE_DEFAULTS.copy()
        state["rss_bootstrapped"] = True
        # today is before all overrides in the test fixture (closure Apr 2–5, hours Mar 30–Apr 1)
        messages = monitor.process_rss_items(state, [rss_item], date(2026, 3, 17))
        self.assertTrue(len(messages) > 0)
        self.assertTrue(any("advisory" in m for m in messages))

    def test_disruption_update_while_active(self):
        state = monitor.STATE_DEFAULTS.copy()
        state["x_bootstrapped"] = True
        state["active_disruption"] = "x:111"
        update_item = {
            "source": "x",
            "source_id": "x:222",
            "published_at": datetime(2026, 4, 7, 10, 0, tzinfo=monitor.PHT),
            "url": "https://x.com/officialLRT1/status/222",
            "text": "LRT-1 trains are experiencing delays due to a technical issue.",
            "kind": "disruption_start",
            "title": None,
            "effective_window": None,
        }
        messages = monitor.process_x_items(state, [update_item])
        self.assertEqual(len(messages), 1)
        self.assertIn("update", messages[0])
        self.assertEqual(state["active_disruption"], "x:111")

    def test_resume_message_after_override_day(self):
        state = monitor.STATE_DEFAULTS.copy()
        state["last_override_date"] = "2026-04-06"
        schedule = {
            "name": "weekday",
            "closed": False,
            "override": None,
            "first_train": monitor.WEEKDAY_SERVICE["first_train"],
            "last_train": monitor.WEEKDAY_SERVICE["last_train"],
            "closing_announcement": monitor.WEEKDAY_SERVICE["closing_announcement"],
        }
        now = datetime(2026, 4, 7, 5, 0, tzinfo=monitor.PHT)
        messages = monitor.check_announcements(state, now, schedule)
        self.assertTrue(any("regular hours" in m for m in messages))


    def test_tomorrow_note_on_weekday_to_weekend(self):
        # Friday → Saturday: note should appear
        friday = date(2026, 4, 10)  # a Friday
        saturday = date(2026, 4, 11)
        state = monitor.STATE_DEFAULTS.copy()
        tomorrow_sched = monitor.get_service_schedule(
            datetime.combine(saturday, datetime.min.time()).replace(tzinfo=monitor.PHT), state
        )
        note = monitor.format_tomorrow_schedule_note(saturday, tomorrow_sched)
        self.assertIsNotNone(note)
        self.assertIn("Saturday", note)

    def test_tomorrow_note_absent_on_weekday_to_weekday(self):
        # Monday → Tuesday with no overrides: no note
        tuesday = date(2026, 4, 14)
        state = monitor.STATE_DEFAULTS.copy()
        tomorrow_sched = monitor.get_service_schedule(
            datetime.combine(tuesday, datetime.min.time()).replace(tzinfo=monitor.PHT), state
        )
        with patch("monitor.is_public_holiday", return_value=False):
            note = monitor.format_tomorrow_schedule_note(tuesday, tomorrow_sched)
        self.assertIsNone(note)

    def test_weekly_outlook_skips_on_non_monday(self):
        state = monitor.STATE_DEFAULTS.copy()
        now = datetime(2026, 4, 7, 5, 0, tzinfo=monitor.PHT)  # Tuesday
        result = monitor.format_weekly_outlook(now, state)
        self.assertIsNone(result)

    def test_weekly_outlook_skips_on_regular_week(self):
        state = monitor.STATE_DEFAULTS.copy()
        # A Monday with no holidays and no overrides
        now = datetime(2026, 4, 13, 5, 0, tzinfo=monitor.PHT)  # Monday
        with patch("monitor.is_public_holiday", return_value=False):
            result = monitor.format_weekly_outlook(now, state)
        self.assertIsNone(result)

    def test_weekly_outlook_fires_on_monday_with_holiday(self):
        state = monitor.STATE_DEFAULTS.copy()
        now = datetime(2026, 4, 13, 5, 0, tzinfo=monitor.PHT)  # Monday
        # Make Thursday a public holiday
        def mock_holiday(d):
            return d == date(2026, 4, 16)
        with patch("monitor.is_public_holiday", side_effect=mock_holiday):
            result = monitor.format_weekly_outlook(now, state)
        self.assertIsNotNone(result)
        self.assertIn("Thursday", result)

    def test_holiday_reminder_fires_night_before_holiday(self):
        state = monitor.STATE_DEFAULTS.copy()
        # Sunday night before a Monday public holiday
        now = datetime(2026, 4, 12, 19, 0, tzinfo=monitor.PHT)
        schedule = {
            "name": "weekend_or_holiday",
            "closed": False,
            "override": None,
            "first_train": monitor.WEEKEND_OR_HOLIDAY_SERVICE["first_train"],
            "last_train": monitor.WEEKEND_OR_HOLIDAY_SERVICE["last_train"],
            "closing_announcement": monitor.WEEKEND_OR_HOLIDAY_SERVICE["closing_announcement"],
        }
        def mock_holiday(d):
            return d == date(2026, 4, 13)  # tomorrow is a holiday
        with patch("monitor.is_public_holiday", side_effect=mock_holiday):
            messages = monitor.check_announcements(state, now, schedule)
        self.assertTrue(any("Heads up for tomorrow" in m for m in messages))
        self.assertEqual(state["last_holiday_reminder"], "2026-04-12")

    def test_holiday_reminder_not_fired_for_regular_weekend(self):
        state = monitor.STATE_DEFAULTS.copy()
        # Friday evening — tomorrow is Saturday (regular weekend, not a holiday)
        now = datetime(2026, 4, 10, 19, 0, tzinfo=monitor.PHT)
        schedule = {
            "name": "weekday",
            "closed": False,
            "override": None,
            "first_train": monitor.WEEKDAY_SERVICE["first_train"],
            "last_train": monitor.WEEKDAY_SERVICE["last_train"],
            "closing_announcement": monitor.WEEKDAY_SERVICE["closing_announcement"],
        }
        with patch("monitor.is_public_holiday", return_value=False):
            messages = monitor.check_announcements(state, now, schedule)
        self.assertFalse(any("Heads up for tomorrow" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
