Push a manual LRT-1 announcement to @vitocruzdelays Telegram channel.

Arguments: $ARGUMENTS

## Steps

1. **Get the tweet URL.**
   - If a URL was provided in $ARGUMENTS, use it.
   - Otherwise, ask the user: "What's the tweet URL?"

2. **Get the tweet text.**
   Ask the user: "Paste the full tweet text from @officialLRT1:"
   Wait for their reply.

3. **Write the tweet text to a temp file** at `/tmp/lrt_tweet.txt` using the Write tool.

4. **Run a dry-run** to preview the auto-detected category and formatted message:
   ```
   python manual_push.py --url "<URL>" --text-file /tmp/lrt_tweet.txt --dry-run
   ```

5. **Show the user the message preview** and the detected category (from the `DETECTED_KIND:` line in the output).

6. **Confirm the category.** Ask: "Does this look right? If you want a different category, say so — options are: disruption_start, disruption_update, disruption_clear, flood_alert, flood_clear, crowd_alert_high, crowd_alert_moderate. Otherwise say yes to send."

7. **Send the announcement.**
   - If the user confirmed the auto-detected kind, run:
     ```
     python manual_push.py --url "<URL>" --text-file /tmp/lrt_tweet.txt --yes
     ```
   - If they specified a different kind, run:
     ```
     python manual_push.py --url "<URL>" --text-file /tmp/lrt_tweet.txt --kind <kind> --yes
     ```

8. Confirm to the user that the announcement was sent.

## Notes
- TELEGRAM_BOT_TOKEN must be set in the environment before running.
- If the script exits with an error, show the full output to the user and stop.
- Do not send without explicit user confirmation in step 6.
