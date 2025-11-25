import os
import json
from datetime import date
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
CHANNEL_IDS = os.environ.get("SLACK_CHANNEL_IDS", "")  # e.g. "C0123AAA,C0456BBB"
ANCHOR_DATE = date(2025, 1, 1)  # used for deterministic rotation
def load_topics(path: str | Path = "whs_topics.json") -> dict:
    """Load weekly topics + messages from JSON file in the repo."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Topics file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
def pick_weekly_topic(topics_json: dict, today: date | None = None) -> dict:
    """
    Pick the topic for this week.
    Simple version:
Use ISO week number (1–53)
Rotate through topics by week number
    """
    if today is None:
        today = date.today()
    weekly_topics = topics_json.get("weekly_topics", [])
    if not weekly_topics:
        raise ValueError("No weekly_topics defined in whs_topics.json")
    # ISO week number is stable across years; subtract 1 to make it 0-based
    week_num = today.isocalendar().week  # 1..53
    idx = (week_num - 1) % len(weekly_topics)
    return weekly_topics[idx]
def pick_daily_message(topic: dict, today: date | None = None) -> str:
    """
    Within the chosen topic, pick a different message each day
    using a simple date-based rotation.
    """
    if today is None:
        today = date.today()
    messages = topic.get("messages", [])
    if not messages:
        raise ValueError(f"No messages defined for topic {topic.get('code')}")
    days_since_anchor = (today - ANCHOR_DATE).days
    idx = days_since_anchor % len(messages)
    return messages[idx]["text"]
def pick_message_for_today() -> str:
    """High-level helper: load topics, pick this week's topic, then today's message."""
    topics_json = load_topics()
    today = date.today()
    topic = pick_weekly_topic(topics_json, today)
    text = pick_daily_message(topic, today)
    return text
def post_to_slack(text: str) -> None:
    """Send the message to all configured channels."""
    if not SLACK_BOT_TOKEN:
        raise SystemExit("Missing SLACK_BOT_TOKEN.")
    if not CHANNEL_IDS:
        raise SystemExit("Missing SLACK_CHANNEL_IDS.")
    client = WebClient(token=SLACK_BOT_TOKEN)
    channel_list = [c.strip() for c in CHANNEL_IDS.split(",") if c.strip()]
    for channel_id in channel_list:
        try:
            client.chat_postMessage(channel=channel_id, text=text)
            print(f"Sent message to {channel_id}")
        except SlackApiError as e:
            print(f"Slack error for {channel_id}: {e.response.get('error')}")
def main() -> None:
    text = pick_message_for_today()
    post_to_slack(text)
if __name__ == "__main__":
    main()
